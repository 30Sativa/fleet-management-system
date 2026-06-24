"""Unit tests for stm32_bridge odometry math.

These tests do not require a ROS environment. The ROS-specific modules
(``rclpy``, ``geometry_msgs``, ``nav_msgs``, ``tf2_ros``, ``serial``) are stubbed
out before importing the node so the pure-Python helpers can be exercised
directly.

Run with::

    python3 -m pytest ros2_ws/src/stm32_bridge/test/test_odometry.py
    # or simply:
    python3 ros2_ws/src/stm32_bridge/test/test_odometry.py
"""

import math
import os
import sys
import types


# ---------------------------------------------------------------------------
# Stub the ROS / serial modules so the node module imports without a ROS env.
# ---------------------------------------------------------------------------
def _install_ros_stubs():
    def _stub_module(name):
        mod = types.ModuleType(name)
        sys.modules[name] = mod
        return mod

    # geometry_msgs.msg with the message classes the node imports.
    geometry_msgs = _stub_module('geometry_msgs')
    geometry_msgs_msg = _stub_module('geometry_msgs.msg')
    geometry_msgs.msg = geometry_msgs_msg
    geometry_msgs_msg.TransformStamped = type('TransformStamped', (), {})
    geometry_msgs_msg.Twist = type('Twist', (), {})

    nav_msgs = _stub_module('nav_msgs')
    nav_msgs_msg = _stub_module('nav_msgs.msg')
    nav_msgs.msg = nav_msgs_msg
    nav_msgs_msg.Odometry = type('Odometry', (), {})

    rclpy = _stub_module('rclpy')
    rclpy_node = _stub_module('rclpy.node')
    rclpy.node = rclpy_node
    rclpy_node.Node = type('Node', (), {})

    tf2_ros = _stub_module('tf2_ros')
    tf2_ros.TransformBroadcaster = type('TransformBroadcaster', (), {})

    # pyserial: the node tolerates a missing serial module, but provide a stub
    # with the exception types so the import branch is deterministic.
    serial = _stub_module('serial')

    class SerialException(Exception):
        pass

    class SerialTimeoutException(SerialException):
        pass

    serial.SerialException = SerialException
    serial.SerialTimeoutException = SerialTimeoutException
    serial.Serial = type('Serial', (), {})


_install_ros_stubs()

# Make the package importable from this test file location.
_PKG_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PKG_ROOT not in sys.path:
    sys.path.insert(0, _PKG_ROOT)

from stm32_bridge.stm32_bridge_node import Stm32BridgeNode  # noqa: E402


# ---------------------------------------------------------------------------
# Lightweight, ROS-free reimplementation that mirrors the node's odometry math.
# It calls the node's *static* helpers directly so the formulas under test are
# the exact ones used in production, not a copy.
# ---------------------------------------------------------------------------
class OdometryModel:
    def __init__(self, wheel_radius=0.095, wheel_base=0.46,
                 steps_per_rev=200.0, microstep=8.0, gear_ratio=10.0):
        circ = 2.0 * math.pi * wheel_radius
        self.steps_per_meter = steps_per_rev * microstep * gear_ratio / circ
        self.wheel_base = wheel_base
        self.x = 0.0
        self.y = 0.0
        self.theta = 0.0
        self.last_left = None
        self.last_right = None

    def feed(self, left_count, right_count, dt):
        """Integrate one cumulative feedback sample. Returns (lin_v, ang_v)."""
        if self.last_left is None:
            # First sample establishes the baseline (reset_odom_on_start).
            self.last_left = left_count
            self.last_right = right_count
            return 0.0, 0.0

        dl = Stm32BridgeNode._diff_signed_32(left_count, self.last_left)
        dr = Stm32BridgeNode._diff_signed_32(right_count, self.last_right)
        self.last_left = left_count
        self.last_right = right_count

        left_dist = dl / self.steps_per_meter
        right_dist = dr / self.steps_per_meter
        delta_s = (right_dist + left_dist) / 2.0
        delta_theta = (right_dist - left_dist) / self.wheel_base
        heading = self.theta + delta_theta / 2.0

        self.x += delta_s * math.cos(heading)
        self.y += delta_s * math.sin(heading)
        self.theta = Stm32BridgeNode._normalize_angle(self.theta + delta_theta)

        if dt > 0.0:
            return delta_s / dt, delta_theta / dt
        return 0.0, 0.0


# ---------------------------------------------------------------------------
# Tiny assertion helpers (avoid a hard pytest dependency).
# ---------------------------------------------------------------------------
def approx(a, b, tol=1e-6):
    assert math.isclose(a, b, rel_tol=0.0, abs_tol=tol), f'{a} != {b}'


# ---------------------------------------------------------------------------
# Tests.
# ---------------------------------------------------------------------------
def test_steps_per_meter_matches_firmware():
    """1600 driver pulses/rev * 10 gear / (pi * 0.190 m)."""
    m = OdometryModel()
    approx(m.steps_per_meter, 16000.0 / (math.pi * 0.190), tol=1e-3)
    approx(m.steps_per_meter, 26805.0, tol=1.0)


def test_first_sample_is_baseline_no_motion():
    m = OdometryModel()
    lin, ang = m.feed(1000, 1000, 0.02)
    approx(lin, 0.0)
    approx(ang, 0.0)
    approx(m.x, 0.0)
    approx(m.theta, 0.0)


def test_straight_line_forward():
    m = OdometryModel()
    m.feed(0, 0, 0.02)  # baseline
    # Drive forward 1 meter on both wheels.
    steps = int(round(m.steps_per_meter))
    lin, ang = m.feed(steps, steps, 1.0)
    approx(m.x, 1.0, tol=1e-3)
    approx(m.y, 0.0, tol=1e-6)
    approx(m.theta, 0.0, tol=1e-9)
    approx(lin, 1.0, tol=1e-3)
    approx(ang, 0.0, tol=1e-9)


def test_pure_rotation_in_place():
    m = OdometryModel()
    m.feed(0, 0, 0.02)  # baseline
    # Right wheel forward, left wheel backward by equal amounts -> spin in place.
    d = int(round(m.steps_per_meter * 0.1))  # 0.1 m of arc each wheel
    lin, ang = m.feed(-d, d, 1.0)
    approx(m.x, 0.0, tol=1e-3)
    approx(m.y, 0.0, tol=1e-3)
    expected_theta = (2 * (d / m.steps_per_meter)) / m.wheel_base
    approx(m.theta, expected_theta, tol=1e-3)
    approx(lin, 0.0, tol=1e-3)
    approx(ang, expected_theta / 1.0, tol=1e-3)


def test_int32_wrap_is_handled():
    """Cumulative count wraps around INT32_MAX -> delta must stay small."""
    m = OdometryModel()
    near_max = 2 ** 31 - 5
    m.feed(near_max, near_max, 0.02)  # baseline
    # Each wheel advances by 10 counts, wrapping past 2**31 into negatives.
    after = near_max + 10 - 2 ** 32
    lin, ang = m.feed(after, after, 0.02)
    expected_dist = 10 / m.steps_per_meter
    approx(m.x, expected_dist, tol=1e-9)
    approx(ang, 0.0, tol=1e-9)


def test_theta_normalized_to_pi_range():
    m = OdometryModel()
    m.feed(0, 0, 0.02)  # baseline
    # Spin far enough to exceed +pi and confirm wrap to (-pi, pi].
    d = int(round(m.steps_per_meter * 2.0))
    m.feed(-d, d, 1.0)
    assert -math.pi <= m.theta <= math.pi, m.theta


def test_parse_feedback_six_field():
    parsed = Stm32BridgeNode._parse_feedback_line(
        Stm32BridgeNode, 'FB,42,1200,1195,20,OK')
    assert parsed is not None
    seq, left, right, dt_ms, status = parsed
    assert seq == 42
    assert left == 1200
    assert right == 1195
    approx(dt_ms, 20.0)
    assert status == 'OK'


def test_parse_feedback_five_field_fallback():
    parsed = Stm32BridgeNode._parse_feedback_line(
        Stm32BridgeNode, 'FB,1200,1195,50,STOP')
    assert parsed is not None
    seq, left, right, dt_ms, status = parsed
    assert seq is None
    assert left == 1200
    assert right == 1195
    approx(dt_ms, 50.0)
    assert status == 'STOP'


def test_parse_feedback_garbage_returns_none():
    # _parse_feedback_line calls self.get_logger(); give it a no-op logger.
    class _FakeNode:
        @staticmethod
        def get_logger():
            class _L:
                def warn(self, *a, **k):
                    pass
            return _L()

    fake = _FakeNode()
    fake._parse_feedback_line = Stm32BridgeNode._parse_feedback_line
    assert fake._parse_feedback_line(fake, 'FB,not,a,number,OK') is None
    assert fake._parse_feedback_line(fake, 'FB,1,2') is None


def test_yaw_quaternion_roundtrip():
    for yaw in (0.0, 0.5, -1.2, math.pi / 2):
        qx, qy, qz, qw = Stm32BridgeNode._yaw_to_quaternion(yaw)
        recovered = math.atan2(2.0 * qw * qz, 1.0 - 2.0 * qz * qz)
        approx(recovered, yaw, tol=1e-9)


def _run_all():
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    failures = 0
    for fn in tests:
        try:
            fn()
            print(f'PASS  {fn.__name__}')
        except AssertionError as exc:
            failures += 1
            print(f'FAIL  {fn.__name__}: {exc}')
    print(f'\n{len(tests) - failures}/{len(tests)} passed')
    return failures


if __name__ == '__main__':
    sys.exit(1 if _run_all() else 0)
