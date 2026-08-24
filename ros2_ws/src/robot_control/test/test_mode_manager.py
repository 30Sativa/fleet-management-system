"""ROS-free safety tests for the velocity mode manager."""

import os
import sys
import types
from types import SimpleNamespace


def _install_ros_stubs():
    def stub(name):
        module = types.ModuleType(name)
        sys.modules[name] = module
        return module

    action_msgs = stub('action_msgs')
    action_msgs_srv = stub('action_msgs.srv')
    action_msgs.srv = action_msgs_srv
    action_msgs_srv.CancelGoal = type('CancelGoal', (), {})

    geometry_msgs = stub('geometry_msgs')
    geometry_msgs_msg = stub('geometry_msgs.msg')
    geometry_msgs.msg = geometry_msgs_msg
    geometry_msgs_msg.Twist = type('Twist', (), {})

    rclpy = stub('rclpy')
    rclpy_node = stub('rclpy.node')
    rclpy.node = rclpy_node
    rclpy_node.Node = type('Node', (), {})
    rclpy_qos = stub('rclpy.qos')
    rclpy.qos = rclpy_qos
    rclpy_qos.DurabilityPolicy = type('DurabilityPolicy', (), {})
    rclpy_qos.QoSProfile = type('QoSProfile', (), {})
    rclpy_qos.ReliabilityPolicy = type('ReliabilityPolicy', (), {})

    std_msgs = stub('std_msgs')
    std_msgs_msg = stub('std_msgs.msg')
    std_msgs.msg = std_msgs_msg
    std_msgs_msg.Bool = type('Bool', (), {})
    std_msgs_msg.String = type('String', (), {})

    std_srvs = stub('std_srvs')
    std_srvs_srv = stub('std_srvs.srv')
    std_srvs.srv = std_srvs_srv
    std_srvs_srv.SetBool = type('SetBool', (), {})


_install_ros_stubs()

_PKG_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PKG_ROOT not in sys.path:
    sys.path.insert(0, _PKG_ROOT)

from robot_control.mode_manager_node import ModeManagerNode  # noqa: E402


def _twist(linear_x=0.0, angular_z=0.0):
    return SimpleNamespace(
        linear=SimpleNamespace(x=linear_x, y=0.0, z=0.0),
        angular=SimpleNamespace(x=0.0, y=0.0, z=angular_z),
    )


def test_command_freshness_rejects_clock_rollback():
    assert ModeManagerNode._is_recent(10.0, 0.5, 10.4)
    assert not ModeManagerNode._is_recent(10.0, 0.5, 10.6)
    assert not ModeManagerNode._is_recent(10.0, 0.5, 9.9)
    assert not ModeManagerNode._is_recent(None, 0.5, 10.0)


def test_non_finite_twist_is_rejected():
    assert ModeManagerNode._is_finite_twist(_twist(0.2, -0.1))
    assert not ModeManagerNode._is_finite_twist(_twist(float('nan'), 0.0))
    assert not ModeManagerNode._is_finite_twist(_twist(0.0, float('-inf')))


def _run_all():
    tests = [value for name, value in sorted(globals().items())
             if name.startswith('test_')]
    failures = 0
    for test in tests:
        try:
            test()
            print(f'PASS  {test.__name__}')
        except AssertionError as exc:
            failures += 1
            print(f'FAIL  {test.__name__}: {exc}')
    print(f'\n{len(tests) - failures}/{len(tests)} passed')
    return failures


if __name__ == '__main__':
    sys.exit(1 if _run_all() else 0)
