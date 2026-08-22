"""Phase 2 diagnostics: turn "does the cloud look right?" into numbers.

One node answers all four Phase 2 questions:

  1. depth dung khong   -> metric error at a known target distance
  2. frame dung khong   -> TF chain resolves, optical axis points where expected
  3. cloud lech khong   -> ground-plane fit gives the mount z/pitch/roll error,
                           and prints the corrected launch arguments
  4. ground nhieu khong -> residual spread of the ground plane, per distance band

It reads the depth image + CameraInfo directly (no cv_bridge, no PCL) and
deprojects with numpy, so the only extra dependency is numpy.

Astra Pro publishes 16UC1 in millimetres (PIXEL_FORMAT_DEPTH_1_MM); 32FC1 in
metres is also accepted in case the driver is reconfigured later.
"""

import math

import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from sensor_msgs.msg import CameraInfo, Image, PointCloud2
from tf2_ros import Buffer, TransformListener


# Astra Pro hardware limits.  Points outside this band are not "noise", they
# are the sensor telling you it has nothing to report.
ASTRA_MIN_RANGE_M = 0.6
ASTRA_MAX_RANGE_M = 8.0


def quat_to_matrix(x, y, z, w):
    """Rotation matrix from a quaternion, without pulling in transforms3d."""
    n = math.sqrt(x * x + y * y + z * z + w * w)
    if n == 0.0:
        return np.eye(3)
    x, y, z, w = x / n, y / n, z / n, w / n
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ])


def fit_plane(x, y, z, iterations=2, sigma=2.5):
    """Least-squares z = a*x + b*y + c, re-fitted after rejecting outliers.

    Returns (a, b, c, residual_std, n_used) or None when there is not enough
    data to say anything honest.
    """
    mask = np.ones_like(z, dtype=bool)
    coef = None
    for _ in range(iterations):
        if mask.sum() < 50:
            return None
        A = np.stack([x[mask], y[mask], np.ones(mask.sum())], axis=1)
        coef, *_ = np.linalg.lstsq(A, z[mask], rcond=None)
        resid = z - (coef[0] * x + coef[1] * y + coef[2])
        std = resid[mask].std()
        # A near-zero spread means the fit is already exact; rejecting at
        # 2.5 sigma there would cut on floating-point noise and throw away
        # almost every point.
        if std < 1e-5:
            break
        mask = np.abs(resid) < sigma * std
    if coef is None or mask.sum() < 50:
        return None
    resid = z[mask] - (coef[0] * x[mask] + coef[1] * y[mask] + coef[2])
    return float(coef[0]), float(coef[1]), float(coef[2]), float(resid.std()), int(mask.sum())


class DepthCheckNode(Node):

    def __init__(self):
        super().__init__('depth_check')

        self.declare_parameter('camera_name', 'camera')
        self.declare_parameter('base_frame', 'base_link')
        # Distance to a flat target filling the centre of the view.  Put the
        # camera a measured distance from a wall and set this; 0 disables the check.
        self.declare_parameter('expected_center_m', 0.0)
        self.declare_parameter('center_tolerance_m', 0.03)
        # Where to look for the floor, in base_link metres.
        self.declare_parameter('ground_x_min', 0.6)
        self.declare_parameter('ground_x_max', 2.5)
        self.declare_parameter('ground_y_half', 0.8)
        self.declare_parameter('ground_z_min', -0.30)
        self.declare_parameter('ground_z_max', 0.15)
        # Current mount values, so the report can print corrected absolutes.
        self.declare_parameter('mount_z', 0.0)
        self.declare_parameter('mount_pitch', 0.0)
        self.declare_parameter('mount_roll', 0.0)
        self.declare_parameter('stride', 4)
        self.declare_parameter('report_period', 3.0)
        self.declare_parameter('report_count', 0)

        self.camera_name = self.get_parameter('camera_name').value
        self.base_frame = self.get_parameter('base_frame').value
        self.stride = max(1, int(self.get_parameter('stride').value))
        self.report_count = int(self.get_parameter('report_count').value)
        self.reports_done = 0

        self.info = None
        self.depth = None
        # Phase 3 hand-off: the costmap consumes /<camera>/depth/points, not the
        # depth image this node deprojects itself.  Watch that topic too, or
        # Phase 2 can pass while the topic Nav2 will actually read is dead.
        self.cloud = None
        self.cloud_count = 0
        self.cloud_t0 = None

        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        # BEST_EFFORT on the subscriber side is compatible with a RELIABLE
        # publisher as well as a SENSOR_DATA one.  RELIABLE here would go
        # permanently silent the day anyone launches with depth_qos:=sensor_data,
        # and a silent diagnostic is worse than no diagnostic.
        qos = QoSProfile(depth=1, history=HistoryPolicy.KEEP_LAST,
                         reliability=ReliabilityPolicy.BEST_EFFORT)
        self.create_subscription(
            CameraInfo, f'/{self.camera_name}/depth/camera_info', self._on_info, qos)
        self.create_subscription(
            Image, f'/{self.camera_name}/depth/image_raw', self._on_depth, qos)
        self.create_subscription(
            PointCloud2, f'/{self.camera_name}/depth/points', self._on_cloud, qos)

        self.create_timer(float(self.get_parameter('report_period').value), self._report)
        print(f'[depth_check] watching /{self.camera_name}/depth/* '
              f'against frame "{self.base_frame}"', flush=True)

    def _on_info(self, msg):
        self.info = msg

    def _on_depth(self, msg):
        self.depth = msg

    def _on_cloud(self, msg):
        self.cloud = msg
        self.cloud_count += 1
        if self.cloud_t0 is None:
            self.cloud_t0 = self.get_clock().now()

    # -- decoding -----------------------------------------------------------

    def _depth_metres(self, msg):
        """Depth image as a float array in metres, invalid pixels as NaN."""
        h, w = msg.height, msg.width
        if msg.encoding == '16UC1':
            arr = np.frombuffer(msg.data, dtype=np.uint16)
            arr = arr.reshape(h, msg.step // 2)[:, :w].astype(np.float32) / 1000.0
        elif msg.encoding == '32FC1':
            arr = np.frombuffer(msg.data, dtype=np.float32)
            arr = arr.reshape(h, msg.step // 4)[:, :w].astype(np.float32)
        else:
            raise ValueError(f'unsupported depth encoding: {msg.encoding}')
        out = arr.copy()
        out[out <= 0.0] = np.nan
        return out

    # -- reporting ----------------------------------------------------------

    def _report(self):
        if self.depth is None or self.info is None:
            print('[depth_check] waiting for depth image + camera_info ...', flush=True)
            return
        msg, info = self.depth, self.info

        # The Astra Pro is known to start, stream a few frames, then stall on a
        # VM.  Without this the report keeps re-analysing one frozen frame and
        # looks perfectly healthy.
        stamp = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
        now = self.get_clock().now().nanoseconds * 1e-9
        age = now - stamp
        if age > 2.0:
            print(f'[depth_check] CHU Y  khung depth cu {age:.1f} s -- driver da '
                  f'treo? (thu depth_fps:=15, enable_ir:=false, cong USB 3.x)',
                  flush=True)

        try:
            depth_m = self._depth_metres(msg)
        except ValueError as exc:
            print(f'[depth_check] FAIL {exc}', flush=True)
            return

        h, w = depth_m.shape
        total = depth_m.size
        valid_mask = ~np.isnan(depth_m)
        n_valid = int(valid_mask.sum())

        lines = []
        lines.append('')
        lines.append('=' * 68)
        lines.append(f'  PHASE 2 DEPTH / POINTCLOUD CHECK   ({w}x{h})')
        lines.append('=' * 68)

        # --- 1. depth dung khong ------------------------------------------
        lines.append('')
        lines.append('-- 1. Depth co dung khong --------------------------------------')
        cw = max(4, w // 20)
        ch = max(4, h // 20)
        centre = depth_m[h // 2 - ch:h // 2 + ch, w // 2 - cw:w // 2 + cw]
        centre_valid = centre[~np.isnan(centre)]
        if centre_valid.size == 0:
            lines.append('   FAIL  vung trung tam khong co diem hop le nao')
            centre_med = float('nan')
        else:
            centre_med = float(np.median(centre_valid))
            spread = float(centre_valid.std())
            lines.append(f'   trung tam ({2*cw}x{2*ch} px): {centre_med:.3f} m '
                         f'(std {spread*1000:.0f} mm, {centre_valid.size} diem)')
            expected = float(self.get_parameter('expected_center_m').value)
            if expected > 0.0:
                tol = float(self.get_parameter('center_tolerance_m').value) + 0.01 * expected
                err = centre_med - expected
                verdict = 'PASS' if abs(err) <= tol else 'FAIL'
                lines.append(f'   {verdict}  do thuc te {expected:.3f} m -> '
                             f'sai so {err*1000:+.0f} mm (nguong +/-{tol*1000:.0f} mm)')
            else:
                lines.append('   (dat expected_center_m:=<met> de cham diem sai so tuyet doi)')

        pct_valid = 100.0 * n_valid / total
        if n_valid:
            d = depth_m[valid_mask]
            near = 100.0 * float((d < ASTRA_MIN_RANGE_M).sum()) / total
            far = 100.0 * float((d > ASTRA_MAX_RANGE_M).sum()) / total
            lines.append(f'   pixel hop le: {pct_valid:.1f}%   '
                         f'(<{ASTRA_MIN_RANGE_M} m: {near:.1f}%, >{ASTRA_MAX_RANGE_M} m: {far:.1f}%)')
            lines.append(f'   tam do: {float(np.nanmin(d)):.2f} .. {float(np.nanmax(d)):.2f} m')
        if pct_valid < 40.0:
            lines.append('   CHU Y  duoi 40% pixel hop le -- thuong la canh qua gan '
                         f'(<{ASTRA_MIN_RANGE_M} m), be mat den/bong, hoac nang chieu truc tiep')

        # --- 2. frame dung khong ------------------------------------------
        lines.append('')
        lines.append('-- 2. Frame co dung khong --------------------------------------')
        src_frame = msg.header.frame_id
        lines.append(f'   depth image frame_id : {src_frame}')
        try:
            tf = self.tf_buffer.lookup_transform(
                self.base_frame, src_frame, rclpy.time.Time())
        except Exception as exc:  # noqa: BLE001 - tf2 raises several types
            lines.append(f'   FAIL  khong tra duoc TF {self.base_frame} <- {src_frame}')
            lines.append(f'         {type(exc).__name__}: {exc}')
            self._flush(lines)
            return
        t = tf.transform.translation
        q = tf.transform.rotation
        R = quat_to_matrix(q.x, q.y, q.z, q.w)
        T = np.array([t.x, t.y, t.z])
        lines.append(f'   PASS  TF {self.base_frame} <- {src_frame} giai duoc')
        lines.append(f'   camera dat tai       : x={t.x:+.3f} y={t.y:+.3f} z={t.z:+.3f} m')

        # The optical frame looks down its own +z.  Where does that point in base_link?
        look = R @ np.array([0.0, 0.0, 1.0])
        pitch_deg = math.degrees(math.asin(max(-1.0, min(1.0, -look[2]))))
        yaw_deg = math.degrees(math.atan2(look[1], look[0]))
        lines.append(f'   huong nhin cua camera : chuc xuong {pitch_deg:+.1f} deg, '
                     f'lech trai/phai {yaw_deg:+.1f} deg')
        if abs(pitch_deg) > 60.0 or abs(yaw_deg) > 60.0:
            lines.append('   CHU Y  huong nhin lech qua lon so voi truc x cua base_link.')
            lines.append('          Neu bao chuc xuong ~-90 deg: cloud dang o BODY frame chu '
                         'khong phai optical frame.')
            lines.append('          Neu lech ngang ~90 deg: sai yaw cua mount hoac lap camera '
                         'quay ngang.')

        # --- deproject ------------------------------------------------------
        fx, fy = info.k[0], info.k[4]
        cx, cy = info.k[2], info.k[5]
        if fx == 0.0 or fy == 0.0:
            lines.append('')
            lines.append('   FAIL  camera_info.K rong -> khong deproject duoc')
            self._flush(lines)
            return

        s = self.stride
        zz = depth_m[::s, ::s]
        vs, us = np.mgrid[0:h:s, 0:w:s]
        good = ~np.isnan(zz)
        zc = zz[good]
        xc = (us[good] - cx) * zc / fx
        yc = (vs[good] - cy) * zc / fy
        pts_cam = np.stack([xc, yc, zc], axis=1)
        pts = pts_cam @ R.T + T

        # --- 3. cloud co lech khong ---------------------------------------
        lines.append('')
        lines.append('-- 3. Point cloud co bi lech khong -----------------------------')
        if pts.shape[0] < 100:
            lines.append('   khong du diem de danh gia')
            self._flush(lines)
            return
        cen = pts.mean(axis=0)
        lines.append(f'   trong tam cloud (base_link): x={cen[0]:+.2f} y={cen[1]:+.2f} '
                     f'z={cen[2]:+.2f} m   [{pts.shape[0]} diem, stride {s}]')
        if cen[0] <= 0.0:
            lines.append('   CHU Y  trong tam nam PHIA SAU base_link -- kiem tra lai yaw '
                         'cua mount hoac chieu lap camera')

        gx0 = float(self.get_parameter('ground_x_min').value)
        gx1 = float(self.get_parameter('ground_x_max').value)
        gyh = float(self.get_parameter('ground_y_half').value)
        gz0 = float(self.get_parameter('ground_z_min').value)
        gz1 = float(self.get_parameter('ground_z_max').value)
        gm = ((pts[:, 0] > gx0) & (pts[:, 0] < gx1) &
              (np.abs(pts[:, 1]) < gyh) &
              (pts[:, 2] > gz0) & (pts[:, 2] < gz1))
        gp = pts[gm]
        lines.append(f'   vung tim san: x {gx0}..{gx1} m, |y|<{gyh} m, z {gz0}..{gz1} m '
                     f'-> {gp.shape[0]} diem')

        fit = fit_plane(gp[:, 0], gp[:, 1], gp[:, 2]) if gp.shape[0] >= 50 else None
        if fit is None:
            lines.append('   KHONG DANH GIA DUOC  qua it diem san trong vung tren.')
            lines.append('   Nguyen nhan hay gap: camera lap ngang (pitch=0) nen san '
                         'chua vao khung hinh,')
            lines.append('   hoac gia tri mount z/pitch dang sai nhieu. Xem muc 4 cua docs.')
            self._flush(lines)
            return

        a, b, c, resid_std, n_used = fit
        pitch_err = math.degrees(math.atan(a))
        roll_err = math.degrees(math.atan(b))
        lines.append(f'   mat phang san khop: z = {a:+.4f}*x {b:+.4f}*y {c:+.4f}  '
                     f'({n_used} diem)')
        lines.append(f'   -> do cao san tai base_link : {c*1000:+.0f} mm  (mong doi ~0)')
        lines.append(f'   -> lech pitch               : {pitch_err:+.2f} deg')
        lines.append(f'   -> lech roll                : {roll_err:+.2f} deg')

        ok_z = abs(c) <= 0.02
        ok_p = abs(pitch_err) <= 1.0
        ok_r = abs(roll_err) <= 1.0
        lines.append(f'   {"PASS" if ok_z else "FAIL"}  do cao san lech {abs(c)*1000:.0f} mm '
                     '(nguong 20 mm)')
        lines.append(f'   {"PASS" if ok_p else "FAIL"}  pitch lech {abs(pitch_err):.2f} deg '
                     '(nguong 1.0 deg)')
        lines.append(f'   {"PASS" if ok_r else "FAIL"}  roll lech {abs(roll_err):.2f} deg '
                     '(nguong 1.0 deg)')

        if not (ok_z and ok_p and ok_r):
            mz = float(self.get_parameter('mount_z').value)
            mp = float(self.get_parameter('mount_pitch').value)
            mr = float(self.get_parameter('mount_roll').value)
            new_z = mz - c
            new_pitch = mp + math.atan(a)
            new_roll = mr - math.atan(b)
            lines.append('')
            lines.append('   Sua mount roi do lai (lam 1-2 vong la hoi tu):')
            lines.append(f'     z:={new_z:.4f}  pitch:={new_pitch:.4f}  roll:={new_roll:.4f}')
            if mz == 0.0 and mp == 0.0 and mr == 0.0:
                lines.append('     (dang tinh tu mount_z/mount_pitch/mount_roll = 0; '
                             'truyen gia tri that vao node de ra so tuyet doi dung)')

        # --- 4. ground co nhieu khong -------------------------------------
        lines.append('')
        lines.append('-- 4. Ground co bi nhieu khong ---------------------------------')
        lines.append(f'   do lech chuan so voi mat phang khop: {resid_std*1000:.1f} mm')
        if resid_std <= 0.015:
            lines.append('   PASS  san phang, nhieu thap (<15 mm)')
        elif resid_std <= 0.030:
            lines.append('   OK    nhieu vua phai (15-30 mm) -- dung duoc cho Nav2 '
                         'neu loc voxel')
        else:
            lines.append('   FAIL  nhieu cao (>30 mm) -- san bong/nang chieu, hoac mount '
                         'sai khien "san" thuc ra khong phai san')
        lines.append('')
        lines.append('   Nhieu theo tam xa (residual std moi dai):')
        lines.append('     tam (m)      so diem    std (mm)')
        for lo, hi in ((0.6, 1.0), (1.0, 2.0), (2.0, 3.0), (3.0, 4.0), (4.0, 5.0)):
            band = gp[(gp[:, 0] >= lo) & (gp[:, 0] < hi)]
            if band.shape[0] < 20:
                lines.append(f'     {lo:.1f} - {hi:.1f}     {band.shape[0]:>6}    (qua it diem)')
                continue
            r = band[:, 2] - (a * band[:, 0] + b * band[:, 1] + c)
            lines.append(f'     {lo:.1f} - {hi:.1f}     {band.shape[0]:>6}    {r.std()*1000:>6.1f}')
        lines.append('   (nhieu cua structured light tang theo binh phuong khoang cach -- '
                     'dai xa xau hon la binh thuong)')

        # --- 5. topic ma Phase 3 se dung ----------------------------------
        lines.append('')
        lines.append('-- 5. San sang cho Phase 3 (Nav2) ------------------------------')
        topic = f'/{self.camera_name}/depth/points'
        if self.cloud is None:
            lines.append(f'   FAIL  {topic} chua co ban tin nao.')
            lines.append('         Nav2 doc topic NAY, khong doc depth/image_raw.')
            lines.append('         Chay lai voi enable_point_cloud:=true.')
        else:
            hz = 0.0
            if self.cloud_t0 is not None:
                dt = (self.get_clock().now() - self.cloud_t0).nanoseconds * 1e-9
                if dt > 0.5:
                    hz = self.cloud_count / dt
            n_pts = self.cloud.width * self.cloud.height
            lines.append(f'   PASS  {topic}: ~{hz:.1f} Hz, {n_pts} diem/ban tin, '
                         f'frame "{self.cloud.header.frame_id}"')
            if n_pts > 120000:
                lines.append('   CHU Y  cloud rat nang cho costmap. Phase 3 nen ha '
                             'depth_width:=320 depth_height:=240 depth_fps:=10.')
            if hz and hz < 3.0:
                lines.append('   CHU Y  duoi 3 Hz -- costmap se cap nhat vat can qua cham.')

        self._flush(lines)

    def _flush(self, lines):
        lines.append('=' * 68)
        print('\n'.join(lines), flush=True)
        self.reports_done += 1
        if self.report_count and self.reports_done >= self.report_count:
            raise SystemExit(0)


def main(args=None):
    rclpy.init(args=args)
    node = DepthCheckNode()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
