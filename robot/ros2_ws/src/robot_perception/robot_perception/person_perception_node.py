"""Phase 4: RGB-D person perception -> Nav2 speed limit.

What this is NOT for
--------------------
It is not what stops the robot hitting people.  Phase 3 already does that: a
person standing in front of the robot is a wall of points in the local costmap
and Nav2 plans around them without knowing what they are.

What Phase 4 adds is the WORD "person".  A costmap obstacle gets swerved around
at full speed; a person should be approached slowly.  That is the entire claim,
and it is worth keeping small.

The awkward part of the Astra Pro
---------------------------------
Its RGB is a SEPARATE UVC webcam, not a stream of the depth sensor.  There is
no hardware depth-to-colour registration, so an RGB pixel (u, v) does NOT index
the depth image.  Drawing "RGB -> detection, Depth -> 3D" as two wires meeting
hides the only hard step in the pipeline.

Instead of registering depth into RGB (a nodelet, a calibration, a whole extra
stage), this node goes the other way once per frame:

    take the depth cloud -> transform into the colour optical frame using the
    extrinsic the driver already publishes in TF -> project with the RGB
    intrinsics -> now every 3D point has an (u, v) in the RGB image.

Then a detection's range is just the depth of the points that land inside its
box.  Same result, ~40 lines, no new package, and the FOV mismatch between the
two sensors is handled for free because points outside the RGB frustum simply
do not land anywhere.

CPU budget
----------
i3-7100T: 2 cores / 4 threads, shared with Nav2.  Detection runs on a timer at
`rate_hz` (5 Hz), on `inference_threads` threads, at `imgsz` 320.  Run
scripts/bench_detector.py on the real machine before trusting any of these
defaults.
"""

import math
import time

import numpy as np
import rclpy
from geometry_msgs.msg import Pose, PoseArray
from nav2_msgs.msg import SpeedLimit
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import CameraInfo, Image, PointCloud2, PointField
from tf2_ros import Buffer, TransformListener
from visualization_msgs.msg import Marker, MarkerArray

PERSON_CLASS_ID = 0  # COCO


# --------------------------------------------------------------------------
# pure helpers (unit-tested in test/test_math.py)
# --------------------------------------------------------------------------

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


def letterbox_params(src_h, src_w, dst):
    """Scale + padding that fits src into a dst x dst square, aspect preserved."""
    r = min(dst / src_h, dst / src_w)
    new_h, new_w = int(round(src_h * r)), int(round(src_w * r))
    return r, (dst - new_w) // 2, (dst - new_h) // 2, new_w, new_h


def unletterbox(boxes, r, pad_x, pad_y, src_w, src_h):
    """xyxy in letterboxed pixels -> xyxy in original image pixels."""
    if boxes.size == 0:
        return boxes
    out = boxes.astype(np.float32).copy()
    out[:, [0, 2]] = (out[:, [0, 2]] - pad_x) / r
    out[:, [1, 3]] = (out[:, [1, 3]] - pad_y) / r
    out[:, [0, 2]] = out[:, [0, 2]].clip(0, src_w - 1)
    out[:, [1, 3]] = out[:, [1, 3]].clip(0, src_h - 1)
    return out


def nms(boxes, scores, iou_thr):
    """Plain numpy NMS. Only needed for models that are not end-to-end."""
    if boxes.shape[0] == 0:
        return np.empty((0,), dtype=np.int64)
    x1, y1, x2, y2 = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
    areas = (x2 - x1).clip(0) * (y2 - y1).clip(0)
    order = scores.argsort()[::-1]
    keep = []
    while order.size:
        i = order[0]
        keep.append(i)
        if order.size == 1:
            break
        rest = order[1:]
        xx1 = np.maximum(x1[i], x1[rest])
        yy1 = np.maximum(y1[i], y1[rest])
        xx2 = np.minimum(x2[i], x2[rest])
        yy2 = np.minimum(y2[i], y2[rest])
        inter = (xx2 - xx1).clip(0) * (yy2 - yy1).clip(0)
        iou = inter / (areas[i] + areas[rest] - inter + 1e-9)
        order = rest[iou < iou_thr]
    return np.asarray(keep, dtype=np.int64)


def parse_detections(raw, conf_thr, iou_thr):
    """Return (xyxy, scores) for the person class, in INPUT pixel coordinates.

    Handles both layouts Ultralytics produces:
      (1, N, 6)  -> end-to-end / NMS-free (YOLO26). x1,y1,x2,y2,score,class.
      (1, 84, N) -> classic head; needs NMS here on the CPU.
    """
    a = np.asarray(raw)
    if a.ndim == 3 and a.shape[0] == 1:
        a = a[0]
    if a.ndim != 2:
        return np.zeros((0, 4), np.float32), np.zeros((0,), np.float32)

    if a.shape[-1] == 6:                       # NMS-free
        m = (a[:, 4] >= conf_thr) & (a[:, 5].astype(int) == PERSON_CLASS_ID)
        return a[m][:, :4].astype(np.float32), a[m][:, 4].astype(np.float32)

    # Classic head is (4 + num_classes, N) and N dwarfs the channel count
    # (8400 anchors at 640, 2100 at 320), so the SHORTER axis is the channel
    # axis. Put it last whichever way the export came out.
    if a.shape[0] < a.shape[1]:
        a = a.T                                # (84, N) -> (N, 84)
    if a.shape[1] < 5 + PERSON_CLASS_ID or a.shape[0] <= a.shape[1]:
        # Not a layout we understand. Say nothing rather than emit garbage
        # boxes - a phantom person makes the robot crawl for no reason.
        return np.zeros((0, 4), np.float32), np.zeros((0,), np.float32)

    scores = a[:, 4 + PERSON_CLASS_ID]
    m = scores >= conf_thr
    if not m.any():
        return np.zeros((0, 4), np.float32), np.zeros((0,), np.float32)
    cx, cy, w, h = a[m, 0], a[m, 1], a[m, 2], a[m, 3]
    boxes = np.stack([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], axis=1)
    s = scores[m]
    keep = nms(boxes, s, iou_thr)
    return boxes[keep].astype(np.float32), s[keep].astype(np.float32)


def cloud_xyz(msg):
    """float32 XYZ from a PointCloud2, or None if the layout is something else."""
    offs, types = {}, {}
    for f in msg.fields:
        offs[f.name], types[f.name] = f.offset, f.datatype
    if any(k not in offs or types[k] != PointField.FLOAT32 for k in ('x', 'y', 'z')):
        return None
    n = msg.width * msg.height
    if n == 0:
        return np.zeros((0, 3), np.float32)
    raw = np.frombuffer(msg.data, dtype=np.uint8)[:n * msg.point_step]
    raw = raw.reshape(n, msg.point_step)
    cols = [raw[:, offs[k]:offs[k] + 4].copy().view(np.float32).reshape(n)
            for k in ('x', 'y', 'z')]
    pts = np.stack(cols, axis=1)
    return pts[np.isfinite(pts).all(axis=1)]


def range_in_box(u, v, z, box, shrink=0.5, band=0.4):
    """Robust distance for one detection.

    A person's bounding box always contains background around the body, so a
    plain median can land on the wall behind them.  Shrink to the middle of the
    box, take a low percentile (biased to the foreground), then average only the
    points within `band` metres of it.
    """
    x1, y1, x2, y2 = box
    cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
    hw, hh = (x2 - x1) * shrink / 2.0, (y2 - y1) * shrink / 2.0
    m = ((u >= cx - hw) & (u <= cx + hw) & (v >= cy - hh) & (v <= cy + hh))
    if m.sum() < 20:
        return None, int(m.sum())
    zz = z[m]
    front = np.percentile(zz, 25)
    core = zz[np.abs(zz - front) < band]
    if core.size < 10:
        return None, int(m.sum())
    return float(np.median(core)), int(m.sum())


# --------------------------------------------------------------------------

class PersonPerceptionNode(Node):

    def __init__(self):
        super().__init__('person_perception')

        p = self.declare_parameter
        p('model_xml', '')
        p('device', 'CPU')
        p('imgsz', 320)
        p('inference_threads', 2)
        p('conf_threshold', 0.45)
        p('iou_threshold', 0.5)
        p('rate_hz', 5.0)
        p('camera_name', 'camera')
        p('base_frame', 'base_link')
        p('stale_after_s', 1.5)
        # Behaviour policy.
        p('publish_speed_limit', True)
        p('slow_zone_m', 3.0)
        p('cone_half_deg', 35.0)
        p('slow_speed_percent', 40.0)
        p('report_period', 5.0)

        self.cam = self.get_parameter('camera_name').value
        self.base_frame = self.get_parameter('base_frame').value
        self.imgsz = int(self.get_parameter('imgsz').value)
        self.conf = float(self.get_parameter('conf_threshold').value)
        self.iou = float(self.get_parameter('iou_threshold').value)
        self.stale = float(self.get_parameter('stale_after_s').value)

        self.rgb = None
        self.info = None
        self.cloud = None
        self.last_limit = None
        self.n_infer = 0
        self.sum_ms = 0.0
        self.n_people = 0
        self.n_no_depth = 0

        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        qos = QoSProfile(depth=1, history=HistoryPolicy.KEEP_LAST,
                         reliability=ReliabilityPolicy.BEST_EFFORT)
        self.create_subscription(Image, f'/{self.cam}/color/image_raw',
                                 lambda m: setattr(self, 'rgb', m), qos)
        self.create_subscription(CameraInfo, f'/{self.cam}/color/camera_info',
                                 lambda m: setattr(self, 'info', m), qos)
        self.create_subscription(PointCloud2, f'/{self.cam}/depth/points',
                                 lambda m: setattr(self, 'cloud', m), qos)

        self.people_pub = self.create_publisher(PoseArray, '/people', 10)
        self.marker_pub = self.create_publisher(MarkerArray, '/people_markers', 10)
        self.limit_pub = self.create_publisher(SpeedLimit, '/speed_limit', 10)

        self.net = self._load_model()
        rate = max(0.5, float(self.get_parameter('rate_hz').value))
        self.create_timer(1.0 / rate, self._tick)
        self.create_timer(float(self.get_parameter('report_period').value), self._report)

    # -- model ------------------------------------------------------------

    def _load_model(self):
        xml = self.get_parameter('model_xml').value
        if not xml:
            self.get_logger().error(
                'model_xml chua duoc dat. Export tren laptop:\n'
                '  yolo export model=yolo26n.pt format=openvino imgsz=320 int8=True\n'
                'roi copy thu muc *_openvino_model sang mini PC.')
            return None
        try:
            import openvino as ov
        except ImportError:
            self.get_logger().error('Chua co openvino: pip3 install "openvino>=2024.0"')
            return None
        device = self.get_parameter('device').value
        cfg = {'PERFORMANCE_HINT': 'LATENCY'}
        threads = int(self.get_parameter('inference_threads').value)
        if device == 'CPU' and threads > 0:
            cfg['INFERENCE_NUM_THREADS'] = threads
        try:
            core = ov.Core()
            compiled = core.compile_model(core.read_model(xml), device, cfg)
        except Exception as exc:  # noqa: BLE001
            self.get_logger().error(f'Khong nap duoc model tren {device}: {exc}')
            if device != 'CPU':
                self.get_logger().error(
                    'HD 630 la Gen9.5 -- OpenVINO GPU plugin hay hong tren doi nay. '
                    'Doi device:=CPU.')
            return None
        self.get_logger().info(
            f'model {xml} tren {device}, {threads} thread, imgsz {self.imgsz}')
        return compiled.create_infer_request()

    # -- image ------------------------------------------------------------

    @staticmethod
    def _rgb_array(msg):
        h, w = msg.height, msg.width
        if msg.encoding in ('rgb8', 'bgr8'):
            a = np.frombuffer(msg.data, np.uint8).reshape(h, msg.step // 3, 3)[:, :w]
            return a[..., ::-1] if msg.encoding == 'bgr8' else a
        if msg.encoding == 'mono8':
            a = np.frombuffer(msg.data, np.uint8).reshape(h, msg.step)[:, :w]
            return np.repeat(a[..., None], 3, axis=2)
        raise ValueError(f'encoding chua ho tro: {msg.encoding}')

    def _age(self, msg):
        t = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
        return self.get_clock().now().nanoseconds * 1e-9 - t

    # -- main loop --------------------------------------------------------

    def _tick(self):
        if self.net is None:
            return
        if self.rgb is None or self.info is None or self.cloud is None:
            return
        if max(self._age(self.rgb), self._age(self.cloud)) > self.stale:
            # A dead camera must not leave the robot crawling for ever. Release
            # the limit; the Phase 3 costmap is still the thing keeping it safe.
            self._publish_limit(100.0)
            return

        try:
            img = self._rgb_array(self.rgb)
        except ValueError as exc:
            self.get_logger().warn(str(exc), throttle_duration_sec=10.0)
            self._publish_limit(100.0)
            return

        import cv2
        src_h, src_w = img.shape[:2]
        r, pad_x, pad_y, nw, nh = letterbox_params(src_h, src_w, self.imgsz)
        canvas = np.full((self.imgsz, self.imgsz, 3), 114, np.uint8)
        canvas[pad_y:pad_y + nh, pad_x:pad_x + nw] = cv2.resize(img, (nw, nh))
        blob = canvas.transpose(2, 0, 1)[None].astype(np.float32) / 255.0

        t0 = time.perf_counter()
        try:
            out = self.net.infer({0: blob})
        except Exception as exc:  # noqa: BLE001
            self.get_logger().error(f'infer loi: {exc}', throttle_duration_sec=10.0)
            self._publish_limit(100.0)
            return
        self.sum_ms += (time.perf_counter() - t0) * 1000.0
        self.n_infer += 1

        raw = list(out.values())[0]
        boxes, scores = parse_detections(raw, self.conf, self.iou)
        boxes = unletterbox(boxes, r, pad_x, pad_y, src_w, src_h)

        people = self._locate(boxes)
        self.n_people += len(people)
        self._publish(people)

    def _locate(self, boxes):
        """boxes (RGB pixels) -> list of (x, y, z) in base_frame."""
        if boxes.shape[0] == 0:
            return []
        pts = cloud_xyz(self.cloud)
        if pts is None or pts.shape[0] == 0:
            return []

        k = self.info.k
        fx, fy, cx, cy = k[0], k[4], k[2], k[5]
        if fx == 0.0 or fy == 0.0:
            self.get_logger().warn('color/camera_info.K rong -- chua calibrate RGB?',
                                   throttle_duration_sec=10.0)
            return []

        colour_frame = self.info.header.frame_id
        try:
            R, T = self._tf(colour_frame, self.cloud.header.frame_id)
            Rb, Tb = self._tf(self.base_frame, colour_frame)
        except Exception as exc:  # noqa: BLE001
            self.get_logger().warn(f'TF: {exc}', throttle_duration_sec=10.0)
            return []

        cam = pts @ R.T + T                     # depth cloud in the colour frame
        front = cam[:, 2] > 0.05
        cam = cam[front]
        if cam.shape[0] == 0:
            return []
        u = fx * cam[:, 0] / cam[:, 2] + cx
        v = fy * cam[:, 1] / cam[:, 2] + cy
        z = cam[:, 2]

        out = []
        for box in boxes:
            rng, _ = range_in_box(u, v, z, box)
            if rng is None:
                self.n_no_depth += 1
                continue
            bu = (box[0] + box[2]) / 2.0
            bv = (box[1] + box[3]) / 2.0
            p_cam = np.array([(bu - cx) * rng / fx, (bv - cy) * rng / fy, rng])
            out.append(Rb @ p_cam + Tb)
        return out

    def _tf(self, target, source):
        tf = self.tf_buffer.lookup_transform(target, source, rclpy.time.Time())
        q, t = tf.transform.rotation, tf.transform.translation
        return quat_to_matrix(q.x, q.y, q.z, q.w), np.array([t.x, t.y, t.z])

    # -- output -----------------------------------------------------------

    def _publish(self, people):
        stamp = self.get_clock().now().to_msg()

        pa = PoseArray()
        pa.header.stamp = stamp
        pa.header.frame_id = self.base_frame
        markers = MarkerArray()
        for i, xyz in enumerate(people):
            pose = Pose()
            pose.position.x, pose.position.y, pose.position.z = map(float, xyz)
            pose.orientation.w = 1.0
            pa.poses.append(pose)

            m = Marker()
            m.header = pa.header
            m.ns = 'people'
            m.id = i
            m.type = Marker.CYLINDER
            m.action = Marker.ADD
            m.pose.position.x = pose.position.x
            m.pose.position.y = pose.position.y
            m.pose.position.z = 0.85
            m.pose.orientation.w = 1.0
            m.scale.x = m.scale.y = 0.5
            m.scale.z = 1.7
            m.color.r, m.color.g, m.color.b, m.color.a = 1.0, 0.6, 0.0, 0.6
            m.lifetime.sec = 1
            markers.markers.append(m)

        # One DELETEALL-style sweep: clear stale ids so old cylinders do not
        # linger when someone walks out of frame.
        clear = Marker()
        clear.header = pa.header
        clear.ns = 'people'
        clear.action = Marker.DELETEALL
        markers.markers.insert(0, clear)

        self.people_pub.publish(pa)
        self.marker_pub.publish(markers)

        self._publish_limit(self._policy(people))

    def _policy(self, people):
        """Nearest person inside the forward cone -> slow down. Nothing else.

        Note there is deliberately no "stop" level. SpeedLimit 0 makes
        controller_server unable to move, SimpleProgressChecker then declares
        the robot stuck, and Nav2 fires a recovery spin -- right next to the
        person. Stopping is the costmap's job, and Phase 3 already does it.
        """
        zone = float(self.get_parameter('slow_zone_m').value)
        cone = math.radians(float(self.get_parameter('cone_half_deg').value))
        for xyz in people:
            d = math.hypot(xyz[0], xyz[1])
            if d <= zone and abs(math.atan2(xyz[1], xyz[0])) <= cone:
                return float(self.get_parameter('slow_speed_percent').value)
        return 100.0

    def _publish_limit(self, percent):
        if not self.get_parameter('publish_speed_limit').value:
            return

        percent = float(percent)
        if not math.isfinite(percent):
            percent = 100.0
        percent = max(1.0, min(100.0, percent))
        changed = self.last_limit is None or abs(percent - self.last_limit) >= 0.5

        # Repeat the current limit so a late/restarted Nav2 subscriber receives it.
        msg = SpeedLimit()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = self.base_frame
        msg.percentage = True
        msg.speed_limit = float(percent)
        self.limit_pub.publish(msg)
        self.last_limit = percent
        if changed:
            self.get_logger().info(f'speed_limit -> {percent:.0f}%')

    def _report(self):
        if self.net is None:
            return
        if self.n_infer == 0:
            missing = [n for n, v in (('color/image_raw', self.rgb),
                                      ('color/camera_info', self.info),
                                      ('depth/points', self.cloud)) if v is None]
            self.get_logger().warn(
                'chua chay suy luan lan nao; thieu: ' + (', '.join(missing) or 'khong ro'))
            return
        self.get_logger().info(
            f'{self.n_infer} khung | {self.sum_ms / self.n_infer:.0f} ms/khung | '
            f'{self.n_people} nguoi | {self.n_no_depth} bbox khong lay duoc do sau')
        self.n_infer = self.n_people = self.n_no_depth = 0
        self.sum_ms = 0.0


def main(args=None):
    rclpy.init(args=args)
    node = PersonPerceptionNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
