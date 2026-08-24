"""Stop navigator: dua xe bus toi cac ben (bus stop) dat ten san tren map.

Nhan action bus_interfaces/GoToStop (goal = stop_id), tra cuu pose trong
bus_stops.yaml, forward sang Nav2 NavigateToPose, bao cao tien do va publish
BusStatus dinh ky cho dispatcher / dashboard.

Test nhanh (sau khi navigation stack da chay):
  ros2 action send_goal /go_to_stop bus_interfaces/action/GoToStop \
      "{stop_id: library}" --feedback
"""
import math
import threading
import time

import yaml

import rclpy
from action_msgs.msg import GoalStatus
from rclpy.action import ActionClient, ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node

from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import NavigateToPose

from bus_interfaces.action import GoToStop
from bus_interfaces.msg import BusStatus

IDLE = 'idle'
NAVIGATING = 'navigating'
ERROR = 'error'


class StopNavigator(Node):
    """Action server go_to_stop -> Nav2 NavigateToPose."""

    def __init__(self):
        super().__init__('stop_navigator')

        self.declare_parameter('bus_id', 'bus1')
        self.declare_parameter('stops_file', '')
        self.declare_parameter('global_frame', 'map')
        self.declare_parameter('nav2_wait_timeout', 10.0)
        self.declare_parameter('status_rate_hz', 1.0)

        self.bus_id = str(self.get_parameter('bus_id').value)
        self.global_frame = str(self.get_parameter('global_frame').value)
        self.nav2_wait_timeout = float(
            self.get_parameter('nav2_wait_timeout').value)

        stops_file = str(self.get_parameter('stops_file').value)
        self._stops = self._load_stops(stops_file)

        # Trang thai (bao ve boi _lock vi action chay o thread khac timer).
        self._lock = threading.Lock()
        self._state = IDLE
        self._current_stop = ''
        self._target_stop = ''
        self._distance_remaining = 0.0
        self._goal_reserved = False

        cb_group = ReentrantCallbackGroup()
        self._nav_client = ActionClient(
            self, NavigateToPose, 'navigate_to_pose',
            callback_group=cb_group)
        self._action_server = ActionServer(
            self, GoToStop, 'go_to_stop',
            execute_callback=self._execute,
            goal_callback=self._on_goal,
            cancel_callback=self._on_cancel,
            callback_group=cb_group)

        self._status_pub = self.create_publisher(BusStatus, 'bus_status', 10)
        rate = max(0.1, float(self.get_parameter('status_rate_hz').value))
        self.create_timer(1.0 / rate, self._publish_status)

        self.get_logger().info(
            f'Stop navigator ready: bus_id={self.bus_id}, '
            f'{len(self._stops)} stops: {sorted(self._stops.keys())}')

    # ------------------------------------------------------------------
    def _load_stops(self, path):
        if not path:
            self.get_logger().error(
                'stops_file parameter is empty; no stops loaded.')
            return {}
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
        except OSError as exc:
            self.get_logger().error(f'Cannot read stops file: {exc}')
            return {}
        stops = {}
        for name, pose in (data.get('stops') or {}).items():
            try:
                stops[str(name)] = {
                    'x': float(pose['x']),
                    'y': float(pose['y']),
                    'yaw': float(pose.get('yaw', 0.0)),
                }
            except (KeyError, TypeError, ValueError):
                self.get_logger().warn(
                    f'Stop "{name}" has invalid pose; skipped.')
        return stops

    def _stop_pose(self, stop_id):
        st = self._stops[stop_id]
        pose = PoseStamped()
        pose.header.frame_id = self.global_frame
        pose.header.stamp = self.get_clock().now().to_msg()
        pose.pose.position.x = st['x']
        pose.pose.position.y = st['y']
        pose.pose.orientation.z = math.sin(st['yaw'] / 2.0)
        pose.pose.orientation.w = math.cos(st['yaw'] / 2.0)
        return pose

    # ------------------------------------------------------------------
    def _on_goal(self, goal_request):
        with self._lock:
            busy = self._goal_reserved
        if busy:
            self.get_logger().warn(
                'Rejecting go_to_stop: already navigating. '
                'Cancel the current goal first.')
            return GoalResponse.REJECT
        if goal_request.stop_id not in self._stops:
            self.get_logger().warn(
                f'Rejecting unknown stop "{goal_request.stop_id}". '
                f'Known: {sorted(self._stops.keys())}')
            return GoalResponse.REJECT
        with self._lock:
            # Reserve before returning ACCEPT. With a reentrant callback group,
            # another goal callback may run before this goal starts executing.
            if self._goal_reserved:
                return GoalResponse.REJECT
            self._goal_reserved = True
        return GoalResponse.ACCEPT

    def _on_cancel(self, goal_handle):
        return CancelResponse.ACCEPT

    # ------------------------------------------------------------------
    def _execute(self, goal_handle):
        stop_id = goal_handle.request.stop_id
        result = GoToStop.Result()
        start = time.monotonic()

        def finish(success, message, terminal):
            with self._lock:
                self._state = IDLE if success or terminal != 'abort' else ERROR
                self._goal_reserved = False
                self._target_stop = ''
                self._distance_remaining = 0.0
                if success:
                    self._current_stop = stop_id
            result.success = success
            result.message = message
            result.nav_duration_s = float(time.monotonic() - start)
            if terminal == 'cancel':
                goal_handle.canceled()
            elif terminal == 'abort':
                goal_handle.abort()
            else:
                goal_handle.succeed()
            return result

        if goal_handle.is_cancel_requested:
            return finish(False, 'canceled', 'cancel')

        if not self._nav_client.wait_for_server(
                timeout_sec=self.nav2_wait_timeout):
            self.get_logger().error('Nav2 navigate_to_pose not available.')
            return finish(False, 'nav2_unavailable', 'abort')

        with self._lock:
            self._state = NAVIGATING
            self._target_stop = stop_id
        self.get_logger().info(f'Driving to stop "{stop_id}".')

        nav_goal = NavigateToPose.Goal()
        nav_goal.pose = self._stop_pose(stop_id)

        def on_nav_feedback(fb):
            with self._lock:
                self._distance_remaining = float(
                    fb.feedback.distance_remaining)

        send_future = self._nav_client.send_goal_async(
            nav_goal, feedback_callback=on_nav_feedback)
        if not self._wait(send_future, self.nav2_wait_timeout):
            return finish(False, 'nav2_send_goal_timeout', 'abort')
        try:
            nav_handle = send_future.result()
        except Exception as exc:  # noqa: BLE001 - action future exceptions vary
            self.get_logger().error(f'Nav2 goal request failed: {exc}')
            return finish(False, 'nav2_send_goal_failed', 'abort')
        if nav_handle is None or not nav_handle.accepted:
            return finish(False, 'nav2_rejected_goal', 'abort')

        result_future = nav_handle.get_result_async()
        feedback = GoToStop.Feedback()
        while not self._wait(result_future, 0.2):
            if goal_handle.is_cancel_requested:
                self.get_logger().info('Cancel requested; canceling Nav2 goal.')
                feedback.nav_state = 'canceling'
                goal_handle.publish_feedback(feedback)
                cancel_future = nav_handle.cancel_goal_async()
                self._wait(cancel_future, 5.0)
                self._wait(result_future, 10.0)
                return finish(False, 'canceled', 'cancel')
            with self._lock:
                feedback.distance_remaining_m = self._distance_remaining
            feedback.nav_state = 'navigating'
            goal_handle.publish_feedback(feedback)

        try:
            nav_result = result_future.result()
        except Exception as exc:  # noqa: BLE001 - action future exceptions vary
            self.get_logger().error(f'Nav2 result failed: {exc}')
            return finish(False, 'nav2_result_failed', 'abort')
        if nav_result is None:
            return finish(False, 'nav2_result_missing', 'abort')
        status = nav_result.status
        if status == GoalStatus.STATUS_SUCCEEDED:
            self.get_logger().info(f'Arrived at stop "{stop_id}".')
            return finish(True, 'arrived', 'succeed')
        self.get_logger().warn(
            f'Nav2 finished with status {status} (not succeeded).')
        return finish(False, f'nav2_status_{status}', 'abort')

    @staticmethod
    def _wait(future, timeout):
        """Block until future done (event-based; needs MultiThreadedExecutor)."""
        event = threading.Event()
        future.add_done_callback(lambda _f: event.set())
        if future.done():
            return True
        return event.wait(timeout=timeout)

    # ------------------------------------------------------------------
    def _publish_status(self):
        msg = BusStatus()
        msg.bus_id = self.bus_id
        with self._lock:
            msg.state = self._state
            msg.current_stop = self._current_stop
            msg.target_stop = self._target_stop
            msg.distance_remaining_m = float(self._distance_remaining)
        self._status_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = StopNavigator()
    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
