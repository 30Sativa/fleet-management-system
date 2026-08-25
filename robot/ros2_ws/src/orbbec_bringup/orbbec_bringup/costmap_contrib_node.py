"""Phase 3 diagnostics: does the Astra actually change the costmap?

Phase 3 has exactly one claim to prove -- "Astra thuc su gop phan vao obstacle
avoidance" -- and looking at RViz cannot prove it.  A depth cloud drawn on top
of a costmap looks convincing whether or not a single cell came from it.

So this node measures two numbers instead:

  A = obstacle cells the CAMERA sees that the LIDAR does not, inside the
      camera's own field of view.  A == 0 means the camera is redundant: it
      is running, it is publishing, and it is telling Nav2 nothing new.

  B = how many of those A cells are actually LETHAL on /local_costmap/costmap.
      B == 0 with A > 0 is the real failure mode of Phase 3: the camera sees
      the box, and the wiring drops it (bad TF, height filter, range gate,
      QoS, topic name).

Phase 3 passes when, with a low obstacle in front of the robot, A is clearly
positive and B/A is high.  Everything else in the report exists to tell you
which of the two numbers broke and why.

Run it next to a live navigation stack:

    ros2 run orbbec_bringup costmap_contrib

Defaults mirror the `pointcloud` observation source in
robot_control/config/nav2_params.yaml.  If you retune the costmap, retune the
matching parameter here or the report will disagree with reality for a boring
reason.
"""

import math

import numpy as np
import rclpy
from nav_msgs.msg import OccupancyGrid
from rclpy.node import Node
from rclpy.qos import (DurabilityPolicy, HistoryPolicy, QoSProfile,
                       ReliabilityPolicy)
from sensor_msgs.msg import LaserScan, PointCloud2, PointField
from tf2_ros import Buffer, TransformListener


LETHAL = 253  # nav2: 254 = lethal obstacle, 253 = inscribed. Both mean "do not go".


def quat_to_matrix(x, y, z, w):
    n = math.sqrt(x * x + y * y + z * z + w * w)
    if n == 0.0:
        return np.eye(3)
    x, y, z, w = x / n, y / n, z / n, w / n
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ])


def cloud_xyz(msg):
    """XYZ as an (N, 3) float array. Returns None if the layout is not float32 XYZ."""
    offs, types = {}, {}
    for f in msg.fields:
        offs[f.name] = f.offset
        types[f.name] = f.datatype
    if any(k not in offs or types[k] != PointField.FLOAT32 for k in ('x', 'y', 'z')):
        return None
    n = msg.width * msg.height
    if n == 0:
        return np.zeros((0, 3), dtype=np.float32)
    raw = np.frombuffer(msg.data, dtype=np.uint8)[:n * msg.point_step]
    raw = raw.reshape(n, msg.point_step)
    cols = [raw[:, offs[k]:offs[k] + 4].copy().view(np.float32).reshape(n)
            for k in ('x', 'y', 'z')]
    pts = np.stack(cols, axis=1)
    return pts[np.isfinite(pts).all(axis=1)]


def cells_of(pts_xy, grid_info):
    """World XY -> flat cell ids, dropping anything off the grid."""
    res = grid_info.resolution
    ox = grid_info.origin.position.x
    oy = grid_info.origin.position.y
    ix = np.floor((pts_xy[:, 0] - ox) / res).astype(np.int64)
    iy = np.floor((pts_xy[:, 1] - oy) / res).astype(np.int64)
    ok = (ix >= 0) & (ix < grid_info.width) & (iy >= 0) & (iy < grid_info.height)
    return iy[ok] * grid_info.width + ix[ok], ok


def dilate(cell_ids, width, height):
    """Grow a cell set by one ring, so a half-cell registration error is not
    counted as "the LiDAR missed it"."""
    if cell_ids.size == 0:
        return cell_ids
    iy, ix = np.divmod(cell_ids, width)
    out = []
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            nx, ny = ix + dx, iy + dy
            m = (nx >= 0) & (nx < width) & (ny >= 0) & (ny < height)
            out.append(ny[m] * width + nx[m])
    return np.unique(np.concatenate(out))


class CostmapContribNode(Node):

    def __init__(self):
        super().__init__('costmap_contrib')

        self.declare_parameter('camera_name', 'camera')
        self.declare_parameter('scan_topic', '/scan')
        self.declare_parameter('costmap_topic', '/local_costmap/costmap')
        self.declare_parameter('base_frame', 'base_footprint')
        # Mirror of the `pointcloud` observation source in nav2_params.yaml.
        self.declare_parameter('min_obstacle_height', 0.08)
        self.declare_parameter('max_obstacle_height', 1.20)
        self.declare_parameter('obstacle_min_range', 0.60)
        self.declare_parameter('obstacle_max_range', 3.00)
        self.declare_parameter('report_period', 3.0)
        self.declare_parameter('report_count', 0)

        self.camera_name = self.get_parameter('camera_name').value
        self.base_frame = self.get_parameter('base_frame').value
        self.report_count = int(self.get_parameter('report_count').value)
        self.reports_done = 0

        self.cloud = None
        self.scan = None
        self.grid = None
        self.n_cloud = self.n_scan = self.n_grid = 0

        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        sensor_qos = QoSProfile(depth=1, history=HistoryPolicy.KEEP_LAST,
                                reliability=ReliabilityPolicy.BEST_EFFORT)
        # Nav2 publishes costmaps latched; without TRANSIENT_LOCAL you only see
        # one every full-update cycle, or nothing at all.
        map_qos = QoSProfile(depth=1, history=HistoryPolicy.KEEP_LAST,
                             reliability=ReliabilityPolicy.RELIABLE,
                             durability=DurabilityPolicy.TRANSIENT_LOCAL)

        self.create_subscription(
            PointCloud2, f'/{self.camera_name}/depth/points', self._on_cloud, sensor_qos)
        self.create_subscription(
            LaserScan, self.get_parameter('scan_topic').value, self._on_scan, sensor_qos)
        self.create_subscription(
            OccupancyGrid, self.get_parameter('costmap_topic').value,
            self._on_grid, map_qos)

        self.create_timer(float(self.get_parameter('report_period').value), self._report)
        print('[costmap_contrib] do dong gop cua camera vao local costmap ...', flush=True)

    def _on_cloud(self, msg):
        self.cloud = msg
        self.n_cloud += 1

    def _on_scan(self, msg):
        self.scan = msg
        self.n_scan += 1

    def _on_grid(self, msg):
        self.grid = msg
        self.n_grid += 1

    # -- helpers ------------------------------------------------------------

    def _tf(self, target, source):
        tf = self.tf_buffer.lookup_transform(target, source, rclpy.time.Time())
        q, t = tf.transform.rotation, tf.transform.translation
        return quat_to_matrix(q.x, q.y, q.z, q.w), np.array([t.x, t.y, t.z])

    def _scan_points(self, target):
        """LaserScan endpoints in the costmap frame."""
        m = self.scan
        r = np.asarray(m.ranges, dtype=np.float32)
        a = m.angle_min + np.arange(r.size, dtype=np.float32) * m.angle_increment
        ok = np.isfinite(r) & (r > m.range_min) & (r < m.range_max)
        r, a = r[ok], a[ok]
        pts = np.stack([r * np.cos(a), r * np.sin(a), np.zeros_like(r)], axis=1)
        R, T = self._tf(target, m.header.frame_id)
        return pts @ R.T + T

    # -- report -------------------------------------------------------------

    def _report(self):
        lines = ['', '=' * 68,
                 '  PHASE 3 -- CAMERA CO THUC SU VAO COSTMAP KHONG',
                 '=' * 68, '']

        lines.append('-- 0. Dau vao ---------------------------------------------------')
        for label, msg, count in (
                (f'/{self.camera_name}/depth/points', self.cloud, self.n_cloud),
                (self.get_parameter('scan_topic').value, self.scan, self.n_scan),
                (self.get_parameter('costmap_topic').value, self.grid, self.n_grid)):
            state = f'{count} ban tin' if msg is not None else 'CHUA CO BAN TIN'
            lines.append(f'   {"OK  " if msg is not None else "FAIL"} {label:<34} {state}')
        if self.cloud is None or self.scan is None or self.grid is None:
            lines.append('')
            lines.append('   Thieu dau vao -> chua do duoc. Nav2 va camera da chay chua?')
            return self._flush(lines)

        grid = self.grid
        target = grid.header.frame_id
        info = grid.info
        cost = np.asarray(grid.data, dtype=np.int16).reshape(info.height, info.width)
        # OccupancyGrid carries -1 for unknown; nav2 costmap_raw would keep 255.
        lines.append(f'   costmap: {info.width}x{info.height} @ {info.resolution:.3f} m '
                     f'trong frame "{target}"')

        pts = cloud_xyz(self.cloud)
        if pts is None:
            lines.append('   FAIL  point cloud khong phai float32 XYZ -> khong doc duoc')
            return self._flush(lines)

        try:
            Rc, Tc = self._tf(target, self.cloud.header.frame_id)
            cam_pts = pts @ Rc.T + Tc
            scan_pts = self._scan_points(target)
            Rb, Tb = self._tf(target, self.base_frame)
        except Exception as exc:  # noqa: BLE001 - tf2 raises several types
            lines.append('')
            lines.append(f'   FAIL  TF khong giai duoc: {type(exc).__name__}: {exc}')
            lines.append('         Nav2 cung se im lang y het the. Kiem tra '
                         'camera_mount va robot_state_publisher.')
            return self._flush(lines)

        # --- 1. camera cells ----------------------------------------------
        zmin = float(self.get_parameter('min_obstacle_height').value)
        zmax = float(self.get_parameter('max_obstacle_height').value)
        rmin = float(self.get_parameter('obstacle_min_range').value)
        rmax = float(self.get_parameter('obstacle_max_range').value)

        d = np.linalg.norm(cam_pts[:, :2] - Tc[:2], axis=1)
        in_range = (d >= rmin) & (d <= rmax)
        as_obstacle = in_range & (cam_pts[:, 2] >= zmin) & (cam_pts[:, 2] <= zmax)
        below = in_range & (cam_pts[:, 2] < zmin)

        lines.append('')
        lines.append('-- 1. Camera loc con lai gi --------------------------------------')
        lines.append(f'   diem trong cloud            : {pts.shape[0]}')
        lines.append(f'   trong tam do {rmin:.2f}-{rmax:.2f} m     : {int(in_range.sum())}')
        lines.append(f'   duoi {zmin:.2f} m (san, bi loai)  : {int(below.sum())}')
        lines.append(f'   -> tinh la VAT CAN          : {int(as_obstacle.sum())}')
        if as_obstacle.sum() == 0:
            lines.append('   CHU Y  khong con diem nao. Truoc mat robot trong that, hoac '
                         'mount pitch/z sai khien moi thu nam duoi nguong.')

        cam_cells, _ = cells_of(cam_pts[as_obstacle][:, :2], info)
        cam_cells = np.unique(cam_cells)

        # A floor that leaks through the height gate lands in a thin band just
        # above it, spread over a wide area -- very different from a real box.
        band = as_obstacle & (cam_pts[:, 2] < zmin + 0.07)
        if as_obstacle.sum() > 200 and band.sum() > 0.7 * as_obstacle.sum():
            lines.append(f'   CHU Y  {100.0*band.sum()/as_obstacle.sum():.0f}% vat can nam '
                         f'trong dai {zmin:.2f}-{zmin+0.07:.2f} m ngay tren nguong.')
            lines.append('          Day la dau hieu SAN bi lot qua bo loc: mount chua '
                         'hieu chinh, hoac nhieu san > 30 mm. Xem lai Phase 2 muc 3.')

        # --- 2. lidar cells -------------------------------------------------
        lidar_cells, _ = cells_of(scan_pts[:, :2], info)
        lidar_cells = dilate(np.unique(lidar_cells), info.width, info.height)

        only = np.setdiff1d(cam_cells, lidar_cells, assume_unique=False)
        lines.append('')
        lines.append('-- 2. Camera co thay gi LiDAR khong thay khong -------------------')
        lines.append(f'   o vat can tu camera         : {cam_cells.size}')
        lines.append(f'   o vat can tu LiDAR (+1 o)   : {lidar_cells.size}')
        lines.append(f'   A = o CHI camera thay       : {only.size}')
        if only.size == 0:
            lines.append('   A = 0 -> camera dang khong them thong tin gi. Khong phai loi '
                         'wiring;')
            lines.append('           dat mot thung thap (10-30 cm) truoc robot roi do lai.')

        # --- 3. did those cells reach Nav2 ----------------------------------
        lines.append('')
        lines.append('-- 3. Cac o do co vao Nav2 that khong ---------------------------')
        if only.size == 0:
            lines.append('   (bo qua: A = 0)')
        else:
            iy, ix = np.divmod(only, info.width)
            vals = cost[iy, ix]
            b = int((vals >= LETHAL).sum())
            ratio = 100.0 * b / only.size
            lines.append(f'   B = trong so do da LETHAL   : {b} / {only.size} ({ratio:.0f}%)')
            if b == 0:
                lines.append('   FAIL  camera thay vat can nhung costmap KHONG ghi o nao.')
                lines.append('         Thu tu kiem tra: observation_sources co "pointcloud" '
                             'chua ->')
                lines.append('         topic co dung /%s/depth/points khong -> '
                             'min/max_obstacle_height ->' % self.camera_name)
                lines.append('         obstacle_max_range -> TF base_link->camera_link.')
            elif ratio < 50.0:
                lines.append('   CHU Y  duoi mot nua vao duoc. Thuong la costmap chua kip '
                             'cap nhat (update_frequency 5 Hz) hoac diem nam ngoai ria '
                             'costmap 3x3 m.')
            else:
                lines.append('   PASS  camera dang thuc su bo sung vat can cho Nav2.')

            # How close is the nearest thing only the camera can see?
            cy = (iy[vals >= LETHAL] + 0.5) * info.resolution + info.origin.position.y
            cx = (ix[vals >= LETHAL] + 0.5) * info.resolution + info.origin.position.x
            if cx.size:
                dist = np.hypot(cx - Tb[0], cy - Tb[1])
                lines.append(f'   vat can gan nhat chi camera thay: {dist.min():.2f} m '
                             'tinh tu base')
                if dist.min() < rmin:
                    lines.append(f'   CHU Y  gan hon {rmin:.2f} m -- camera se MAT no khi '
                                 'robot tien them. LiDAR la lop bao ve o cu ly nay.')

        self._flush(lines)

    def _flush(self, lines):
        lines.append('=' * 68)
        print('\n'.join(lines), flush=True)
        self.reports_done += 1
        if self.report_count and self.reports_done >= self.report_count:
            raise SystemExit(0)


def main(args=None):
    rclpy.init(args=args)
    node = CostmapContribNode()
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
