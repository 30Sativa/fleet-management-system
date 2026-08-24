"""Unit tests for the pure math in person_perception_node.

None of this needs a camera, a model, or a robot -- which is the point. The
functions under test are the ones that fail SILENTLY on hardware: a letterbox
that does not round-trip puts the box on the wrong part of the image, a parser
that misreads the tensor layout invents people, and a range estimator that
grabs the wall behind someone reports 4 m for a person standing at 2 m. All
three look like "the model is bad" when you debug them on the robot.

    colcon test --packages-select robot_perception
    python3 -m pytest test/test_math.py -v      # or standalone
"""

import struct
import sys
import types

import numpy as np


def _stub_ros():
    """Import the node module without a ROS installation present."""
    def stub(name, attrs=()):
        m = types.ModuleType(name)
        for a in attrs:
            setattr(m, a, type(a, (), {}))
        sys.modules[name] = m
        return m

    r = stub('rclpy')
    r.time = types.SimpleNamespace(Time=object)
    stub('rclpy.node', ['Node'])
    q = stub('rclpy.qos')
    for n in ('QoSProfile', 'ReliabilityPolicy', 'HistoryPolicy'):
        setattr(q, n, type(n, (), {'BEST_EFFORT': 0, 'KEEP_LAST': 1}))
    stub('geometry_msgs')
    stub('geometry_msgs.msg', ['Pose', 'PoseArray'])
    stub('nav2_msgs')
    stub('nav2_msgs.msg', ['SpeedLimit'])
    stub('sensor_msgs')
    s = stub('sensor_msgs.msg', ['CameraInfo', 'Image', 'PointCloud2'])
    s.PointField = type('PointField', (), {'FLOAT32': 7})
    stub('tf2_ros', ['Buffer', 'TransformListener'])
    stub('visualization_msgs')
    v = stub('visualization_msgs.msg', ['MarkerArray'])
    v.Marker = type('Marker', (), {'CYLINDER': 3, 'ADD': 0, 'DELETEALL': 3})


_stub_ros()
from robot_perception import person_perception_node as P  # noqa: E402


# -- letterbox --------------------------------------------------------------

def test_letterbox_preserves_aspect_and_fits():
    r, px, py, nw, nh = P.letterbox_params(480, 640, 320)
    assert nw <= 320 and nh <= 320
    assert px >= 0 and py >= 0
    assert abs(nw / nh - 640 / 480) < 0.01


def test_unletterbox_round_trips():
    r, px, py, _, _ = P.letterbox_params(480, 640, 320)
    orig = np.array([[100., 50., 300., 400.]])
    lb = orig.copy()
    lb[:, [0, 2]] = lb[:, [0, 2]] * r + px
    lb[:, [1, 3]] = lb[:, [1, 3]] * r + py
    assert np.allclose(P.unletterbox(lb, r, px, py, 640, 480), orig, atol=0.5)


# -- NMS --------------------------------------------------------------------

def test_nms_merges_overlap_keeps_distinct():
    b = np.array([[0., 0., 10., 10.], [1., 1., 11., 11.], [50., 50., 60., 60.]])
    keep = P.nms(b, np.array([0.9, 0.8, 0.7]), 0.5)
    assert sorted(keep.tolist()) == [0, 2]


def test_nms_empty():
    assert P.nms(np.zeros((0, 4)), np.zeros(0), 0.5).size == 0


# -- output parsing ---------------------------------------------------------

def test_end_to_end_layout():
    raw = np.array([[[10., 10., 50., 90., 0.91, 0.],    # person, keep
                     [10., 10., 50., 90., 0.30, 0.],    # low confidence
                     [60., 10., 90., 90., 0.95, 2.]]])  # car
    boxes, scores = P.parse_detections(raw, 0.45, 0.5)
    assert boxes.shape == (1, 4)
    assert abs(scores[0] - 0.91) < 1e-6


def test_classic_layout_needs_transpose_and_nms():
    a = np.zeros((1, 84, 2100), np.float32)     # what a real 320px export emits
    a[0, 2, :] = 20.
    a[0, 3, :] = 40.
    a[0, 0, :5] = [20, 21, 200, 201, 20]
    a[0, 1, :5] = [30, 31, 210, 211, 30]
    a[0, 4, :5] = [0.90, 0.85, 0.80, 0.10, 0.88]
    a[0, 6, 7] = 0.99                            # a confident CAR
    a[0, 0, 7] = 400.
    a[0, 1, 7] = 400.
    boxes, _ = P.parse_detections(a, 0.45, 0.5)
    assert boxes.shape[0] == 2
    assert not np.any(np.isclose(boxes[:, 0], 390.))   # the car stayed out


def test_malformed_output_invents_nothing():
    boxes, _ = P.parse_detections(np.zeros((1, 3, 9), np.float32), 0.45, 0.5)
    assert boxes.shape[0] == 0


# -- point cloud ------------------------------------------------------------

def test_cloud_xyz_stride_and_nan():
    class F:
        def __init__(self, n, o):
            self.name, self.offset, self.datatype = n, o, 7

    msg = type('M', (), {})()
    msg.fields = [F('x', 0), F('y', 4), F('z', 8)]
    msg.width, msg.height, msg.point_step = 3, 1, 16   # 16, not 12
    msg.data = b''.join(struct.pack('<fff', *p) + b'\x00' * 4
                        for p in [(1., 2., 3.), (float('nan'), 0., 0.), (-1., 0., 2.)])
    out = P.cloud_xyz(msg)
    assert out.shape == (2, 3)
    assert np.allclose(out, [[1, 2, 3], [-1, 0, 2]])


# -- range estimation -------------------------------------------------------

def test_range_in_box_picks_person_not_wall():
    """A bbox always contains background. 4 m of wall must not win over 2 m
    of person."""
    rng = np.random.default_rng(1)
    box = np.array([100., 100., 200., 400.])
    bu = rng.uniform(100, 200, 4000)
    bv = rng.uniform(100, 400, 4000)
    bz = 4.0 + rng.normal(0, 0.02, 4000)
    pu = rng.uniform(130, 170, 1500)
    pv = rng.uniform(180, 320, 1500)
    pz = 2.0 + rng.normal(0, 0.02, 1500)
    got, _ = P.range_in_box(np.concatenate([bu, pu]),
                            np.concatenate([bv, pv]),
                            np.concatenate([bz, pz]), box)
    assert abs(got - 2.0) < 0.1


def test_range_in_box_none_when_starved():
    got, _ = P.range_in_box(np.array([0.]), np.array([0.]), np.array([1.]),
                            np.array([100., 100., 200., 400.]))
    assert got is None


# -- projection -------------------------------------------------------------

def test_deproject_inverts_project():
    fx = fy = 300.0
    cx, cy = 160.0, 120.0
    p = np.array([0.3, 0.1, 2.5])
    u = fx * p[0] / p[2] + cx
    v = fy * p[1] / p[2] + cy
    back = np.array([(u - cx) * p[2] / fx, (v - cy) * p[2] / fy, p[2]])
    assert np.allclose(back, p, atol=1e-5)


def test_people_pose_is_not_modified_by_marker_height():
    class V:
        def __init__(self):
            self.x = self.y = self.z = 0.0

    class Pose:
        def __init__(self):
            self.position = V()
            self.orientation = V()
            self.orientation.w = 0.0

    class PoseArray:
        def __init__(self):
            self.header = types.SimpleNamespace(stamp=None, frame_id='')
            self.poses = []

    class Marker:
        CYLINDER = 3
        ADD = 0
        DELETEALL = 3

        def __init__(self):
            self.header = None
            self.ns = ''
            self.id = 0
            self.type = 0
            self.action = 0
            self.pose = Pose()
            self.scale = V()
            self.color = types.SimpleNamespace(r=0.0, g=0.0, b=0.0, a=0.0)
            self.lifetime = types.SimpleNamespace(sec=0)

    class MarkerArray:
        def __init__(self):
            self.markers = []

    class Publisher:
        def __init__(self):
            self.message = None

        def publish(self, message):
            self.message = message

    old_types = P.Pose, P.PoseArray, P.Marker, P.MarkerArray
    P.Pose, P.PoseArray, P.Marker, P.MarkerArray = (
        Pose, PoseArray, Marker, MarkerArray)
    try:
        node = types.SimpleNamespace(
            base_frame='base_link',
            people_pub=Publisher(),
            marker_pub=Publisher(),
            limit_pub=Publisher(),
            last_limit=None,
            get_clock=lambda: types.SimpleNamespace(
                now=lambda: types.SimpleNamespace(to_msg=lambda: object())),
            get_parameter=lambda _name: types.SimpleNamespace(value=False),
            _policy=lambda _people: 100.0,
            _publish_limit=lambda _percent: None,
        )
        P.PersonPerceptionNode._publish(node, [np.array([1.0, 2.0, 3.0])])
        assert node.people_pub.message.poses[0].position.z == 3.0
        assert node.marker_pub.message.markers[1].pose.position.z == 0.85
    finally:
        P.Pose, P.PoseArray, P.Marker, P.MarkerArray = old_types
