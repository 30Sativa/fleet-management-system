from typing import Optional

from action_msgs.srv import CancelGoal
from geometry_msgs.msg import Twist
import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import Bool, String
from std_srvs.srv import SetBool


MANUAL_MODE = 'manual'
EXPLORE_MODE = 'explore'
VALID_MODES = {MANUAL_MODE, EXPLORE_MODE}


class ModeManagerNode(Node):
    """Select the safe velocity source and publish the final /cmd_vel."""

    def __init__(self):
        super().__init__('mode_manager_node')

        self.declare_parameter('initial_mode', MANUAL_MODE)
        self.declare_parameter('manual_timeout', 0.5)
        self.declare_parameter('nav_timeout', 0.5)
        self.declare_parameter('output_rate_hz', 20.0)
        self.declare_parameter('manual_priority_in_explore', True)
        self.declare_parameter('cancel_nav2_on_manual', True)
        self.declare_parameter(
            'nav2_cancel_service', '/navigate_to_pose/_action/cancel_goal')

        initial_mode = self._normalize_mode(
            str(self.get_parameter('initial_mode').value))
        if initial_mode is None:
            self.get_logger().warn(
                'initial_mode must be "manual" or "explore". '
                'Falling back to manual.')
            initial_mode = MANUAL_MODE
        self.mode = initial_mode
        self.manual_timeout = self._positive_float_parameter(
            'manual_timeout', 0.5)
        self.nav_timeout = self._positive_float_parameter('nav_timeout', 0.5)
        output_rate_hz = self._positive_float_parameter(
            'output_rate_hz', 20.0)
        self.manual_priority_in_explore = bool(
            self.get_parameter('manual_priority_in_explore').value)
        self.cancel_nav2_on_manual = bool(
            self.get_parameter('cancel_nav2_on_manual').value)
        self.nav2_cancel_service = str(
            self.get_parameter('nav2_cancel_service').value)

        self._manual_cmd: Optional[Twist] = None
        self._nav_cmd: Optional[Twist] = None
        self._last_manual_time: Optional[float] = None
        self._last_nav_time: Optional[float] = None
        self._emergency_stop = False
        self._last_source = ''
        self._last_cancel_warn_time = 0.0

        state_qos = QoSProfile(
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )

        self._cmd_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self._mode_state_pub = self.create_publisher(
            String, '/robot_mode_state', state_qos)
        self._estop_state_pub = self.create_publisher(
            Bool, '/emergency_stop_state', state_qos)

        self.create_subscription(
            Twist, '/cmd_vel_manual', self._manual_callback, 10)
        self.create_subscription(Twist, '/cmd_vel_nav', self._nav_callback, 10)
        self.create_subscription(String, '/robot_mode',
                                 self._mode_topic_callback, 10)
        self.create_service(SetBool, '/emergency_stop',
                            self._emergency_stop_callback)
        self._cancel_client = self.create_client(
            CancelGoal, self.nav2_cancel_service)

        self._timer = self.create_timer(
            1.0 / output_rate_hz, self._timer_callback)

        self.get_logger().info(
            'Starting mode manager: '
            f'mode={self.mode}, manual_timeout={self.manual_timeout:.3f}s, '
            f'nav_timeout={self.nav_timeout:.3f}s, '
            f'output_rate_hz={output_rate_hz:.1f}, '
            f'manual_priority_in_explore={self.manual_priority_in_explore}')
        self._publish_state()
        self._publish_zero('startup')

    def _manual_callback(self, msg: Twist):
        self._manual_cmd = self._copy_twist(msg)
        self._last_manual_time = self._now()

    def _nav_callback(self, msg: Twist):
        self._nav_cmd = self._copy_twist(msg)
        self._last_nav_time = self._now()

    def _mode_topic_callback(self, msg: String):
        requested = self._normalize_mode(msg.data)
        if requested is None:
            self.get_logger().warn(
                f'Ignoring invalid robot mode "{msg.data}". '
                'Use "manual" or "explore".')
            return
        self._set_mode(requested)

    def _emergency_stop_callback(self, request, response):
        requested = bool(request.data)
        if requested == self._emergency_stop:
            state = 'engaged' if self._emergency_stop else 'released'
            response.success = True
            response.message = f'Emergency stop already {state}.'
            return response

        self._emergency_stop = requested
        if self._emergency_stop:
            self._publish_zero('emergency_stop')
            self.get_logger().error(
                'Emergency stop engaged. /cmd_vel forced to zero until reset.')
            response.message = 'Emergency stop engaged.'
        else:
            self._clear_commands()
            self._publish_zero('emergency_stop_reset')
            self.get_logger().warn('Emergency stop released.')
            response.message = 'Emergency stop released.'

        self._publish_state()
        response.success = True
        return response

    def _timer_callback(self):
        now = self._now()

        if self._emergency_stop:
            self._publish_zero('emergency_stop')
            return

        source = ''
        cmd = None

        manual_recent = self._is_recent(self._last_manual_time,
                                        self.manual_timeout, now)
        nav_recent = self._is_recent(self._last_nav_time, self.nav_timeout, now)

        if self.mode == MANUAL_MODE:
            if manual_recent:
                source = 'manual'
                cmd = self._manual_cmd
        elif self.mode == EXPLORE_MODE:
            if self.manual_priority_in_explore and manual_recent:
                source = 'manual_override'
                cmd = self._manual_cmd
            elif nav_recent:
                source = 'nav'
                cmd = self._nav_cmd

        if cmd is None:
            self._publish_zero(f'{self.mode}_timeout')
            return

        self._cmd_pub.publish(cmd)
        self._log_source_change(source)

    def _set_mode(self, new_mode: str):
        if new_mode == self.mode:
            self.get_logger().info(f'Robot mode already {new_mode}.')
            self._publish_state()
            return

        old_mode = self.mode
        self.mode = new_mode

        if old_mode == EXPLORE_MODE and new_mode == MANUAL_MODE:
            self._nav_cmd = None
            self._last_nav_time = None
            self._publish_zero('mode_manual')
            if self.cancel_nav2_on_manual:
                self._request_nav2_cancel()

        if old_mode == MANUAL_MODE and new_mode == EXPLORE_MODE:
            self._manual_cmd = None
            self._last_manual_time = None
            self._publish_zero('mode_explore')

        self.get_logger().warn(f'Robot mode changed: {old_mode} -> {new_mode}')
        self._publish_state()

    def _request_nav2_cancel(self):
        now = self._now()
        if not self._cancel_client.service_is_ready():
            if not self._cancel_client.wait_for_service(timeout_sec=0.05):
                if now - self._last_cancel_warn_time > 2.0:
                    self.get_logger().warn(
                        f'Nav2 cancel service not ready: '
                        f'{self.nav2_cancel_service}')
                    self._last_cancel_warn_time = now
                return

        request = CancelGoal.Request()
        future = self._cancel_client.call_async(request)
        future.add_done_callback(self._cancel_done_callback)
        self.get_logger().info('Requested Nav2 goal cancellation.')

    def _cancel_done_callback(self, future):
        try:
            response = future.result()
        except Exception as exc:  # pragma: no cover - depends on ROS graph
            self.get_logger().warn(f'Nav2 cancel request failed: {exc}')
            return

        self.get_logger().info(
            'Nav2 cancel response: '
            f'return_code={response.return_code}, '
            f'goals_canceling={len(response.goals_canceling)}')

    def _clear_commands(self):
        self._manual_cmd = None
        self._nav_cmd = None
        self._last_manual_time = None
        self._last_nav_time = None

    def _publish_zero(self, reason: str):
        self._cmd_pub.publish(Twist())
        self._log_source_change(f'zero:{reason}')

    def _publish_state(self):
        mode_msg = String()
        mode_msg.data = self.mode
        self._mode_state_pub.publish(mode_msg)

        estop_msg = Bool()
        estop_msg.data = self._emergency_stop
        self._estop_state_pub.publish(estop_msg)

    def _log_source_change(self, source: str):
        if source == self._last_source:
            return
        self._last_source = source
        self.get_logger().info(f'/cmd_vel source: {source}')

    def _positive_float_parameter(self, name: str, fallback: float) -> float:
        value = float(self.get_parameter(name).value)
        if value <= 0.0:
            self.get_logger().warn(
                f'{name} must be > 0. Falling back to {fallback}.')
            return fallback
        return value

    def _normalize_mode(self, value: str) -> Optional[str]:
        normalized = value.strip().lower()
        if normalized in ('auto', 'auto_explore', 'exploration'):
            normalized = EXPLORE_MODE
        if normalized not in VALID_MODES:
            return None
        return normalized

    def _now(self) -> float:
        return self.get_clock().now().nanoseconds / 1e9

    @staticmethod
    def _is_recent(stamp: Optional[float], timeout: float, now: float) -> bool:
        return stamp is not None and (now - stamp) <= timeout

    @staticmethod
    def _copy_twist(msg: Twist) -> Twist:
        copied = Twist()
        copied.linear.x = msg.linear.x
        copied.linear.y = msg.linear.y
        copied.linear.z = msg.linear.z
        copied.angular.x = msg.angular.x
        copied.angular.y = msg.angular.y
        copied.angular.z = msg.angular.z
        return copied


def main(args=None):
    rclpy.init(args=args)
    node = ModeManagerNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node._publish_zero('shutdown')
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
