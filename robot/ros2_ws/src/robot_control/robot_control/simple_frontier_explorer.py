import math
from collections import deque
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Set, Tuple

from action_msgs.msg import GoalStatus
from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import NavigateToPose
from nav_msgs.msg import OccupancyGrid
import rclpy
from rclpy.action import ActionClient
from rclpy.duration import Duration
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from rclpy.time import Time
from std_msgs.msg import Bool, String
from tf2_ros import Buffer, TransformException, TransformListener


@dataclass
class FrontierCluster:
    size: int
    centroid_x: float
    centroid_y: float
    distance: float
    score: float


class SimpleFrontierExplorer(Node):
    """Small frontier explorer for demo mapping with Nav2."""

    def __init__(self):
        super().__init__('simple_frontier_explorer')

        self.declare_parameter('map_topic', '/map')
        self.declare_parameter('mode_state_topic', '/robot_mode_state')
        self.declare_parameter(
            'emergency_stop_state_topic', '/emergency_stop_state')
        self.declare_parameter('navigate_action', 'navigate_to_pose')
        self.declare_parameter('global_frame', 'map')
        self.declare_parameter('robot_base_frame', 'base_footprint')
        self.declare_parameter('explore_period', 2.0)
        self.declare_parameter('goal_timeout', 45.0)
        self.declare_parameter('goal_accept_timeout', 5.0)
        self.declare_parameter('free_threshold', 20)
        self.declare_parameter('occupied_threshold', 65)
        self.declare_parameter('min_frontier_size', 8)
        self.declare_parameter('min_goal_distance', 0.35)
        self.declare_parameter('cluster_size_weight', 0.05)

        self.map_topic = str(self.get_parameter('map_topic').value)
        self.mode_state_topic = str(
            self.get_parameter('mode_state_topic').value)
        self.emergency_stop_state_topic = str(
            self.get_parameter('emergency_stop_state_topic').value)
        self.navigate_action = str(self.get_parameter('navigate_action').value)
        self.global_frame = str(self.get_parameter('global_frame').value)
        self.robot_base_frame = str(
            self.get_parameter('robot_base_frame').value)
        self.explore_period = self._positive_float_parameter(
            'explore_period', 2.0)
        self.goal_timeout = self._positive_float_parameter(
            'goal_timeout', 45.0)
        self.goal_accept_timeout = self._positive_float_parameter(
            'goal_accept_timeout', 5.0)
        self.free_threshold = int(self.get_parameter('free_threshold').value)
        self.occupied_threshold = int(
            self.get_parameter('occupied_threshold').value)
        self.min_frontier_size = int(
            self.get_parameter('min_frontier_size').value)
        self.min_goal_distance = float(
            self.get_parameter('min_goal_distance').value)
        self.cluster_size_weight = float(
            self.get_parameter('cluster_size_weight').value)

        self._map: Optional[OccupancyGrid] = None
        self._goal_active = False
        self._active_goal_handle = None
        self._active_goal_started: Optional[float] = None
        self._mode = 'explore'
        self._emergency_stop = False
        self._last_wait_warn = 0.0
        self._last_no_frontier_warn = 0.0
        self._last_tf_warn = 0.0

        self._tf_buffer = Buffer()
        self._tf_listener = TransformListener(self._tf_buffer, self)
        self._nav_action = ActionClient(
            self, NavigateToPose, self.navigate_action)

        state_qos = QoSProfile(
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )

        self.create_subscription(
            OccupancyGrid, self.map_topic, self._map_callback, 1)
        self.create_subscription(
            String, self.mode_state_topic, self._mode_callback, state_qos)
        self.create_subscription(
            Bool,
            self.emergency_stop_state_topic,
            self._emergency_stop_callback,
            state_qos,
        )
        self._timer = self.create_timer(
            self.explore_period, self._timer_callback)

        self.get_logger().info(
            'Starting simple frontier explorer: '
            f'map_topic={self.map_topic}, action={self.navigate_action}, '
            f'global_frame={self.global_frame}, '
            f'robot_base_frame={self.robot_base_frame}')

    def _map_callback(self, msg: OccupancyGrid):
        self._map = msg

    def _mode_callback(self, msg: String):
        self._mode = msg.data.strip().lower()
        if self._mode != 'explore':
            self._cancel_active_goal('mode_not_explore')

    def _emergency_stop_callback(self, msg: Bool):
        self._emergency_stop = bool(msg.data)
        if self._emergency_stop:
            self._cancel_active_goal('emergency_stop')

    def _timer_callback(self):
        now = self._now()

        if self._mode != 'explore':
            return

        if self._emergency_stop:
            return

        if self._goal_active:
            self._check_goal_timeout(now)
            return

        if self._map is None:
            self._warn_every(
                '_last_wait_warn', 5.0, 'Waiting for occupancy grid /map.')
            return

        robot_pose = self._lookup_robot_pose()
        if robot_pose is None:
            return

        frontier = self._select_frontier(self._map, robot_pose)
        if frontier is None:
            self._warn_every(
                '_last_no_frontier_warn',
                5.0,
                'No reachable frontier found. Exploration is likely complete '
                'or the map/TF is not ready.')
            return

        self._send_goal(frontier, robot_pose)

    def _lookup_robot_pose(self) -> Optional[Tuple[float, float, float]]:
        try:
            transform = self._tf_buffer.lookup_transform(
                self.global_frame,
                self.robot_base_frame,
                Time(),
                timeout=Duration(seconds=0.1),
            )
        except TransformException as exc:
            now = self._now()
            if now - self._last_tf_warn > 5.0:
                self.get_logger().warn(
                    f'Missing TF {self.global_frame} -> '
                    f'{self.robot_base_frame}: {exc}')
                self._last_tf_warn = now
            return None

        translation = transform.transform.translation
        rotation = transform.transform.rotation
        return translation.x, translation.y, self._yaw_from_quaternion(
            rotation.x, rotation.y, rotation.z, rotation.w)

    def _select_frontier(
            self,
            grid: OccupancyGrid,
            robot_pose: Tuple[float, float, float]) -> Optional[FrontierCluster]:
        width = grid.info.width
        height = grid.info.height
        if width == 0 or height == 0:
            return None

        frontier_indices = self._find_frontier_indices(grid)
        if not frontier_indices:
            return None

        clusters = self._cluster_frontiers(grid, frontier_indices, robot_pose)
        if not clusters:
            return None

        clusters.sort(key=lambda cluster: cluster.score)
        best = clusters[0]
        self.get_logger().info(
            'Selected frontier: '
            f'x={best.centroid_x:.2f}, y={best.centroid_y:.2f}, '
            f'size={best.size}, distance={best.distance:.2f}, '
            f'score={best.score:.2f}')
        return best

    def _find_frontier_indices(self, grid: OccupancyGrid) -> Set[int]:
        width = grid.info.width
        height = grid.info.height
        data = grid.data
        frontier_indices: Set[int] = set()

        for y in range(height):
            for x in range(width):
                index = self._index(x, y, width)
                if not self._is_free(data[index]):
                    continue
                if self._has_unknown_neighbor(data, width, height, x, y):
                    frontier_indices.add(index)

        return frontier_indices

    def _cluster_frontiers(
            self,
            grid: OccupancyGrid,
            frontier_indices: Set[int],
            robot_pose: Tuple[float, float, float]) -> List[FrontierCluster]:
        width = grid.info.width
        visited: Set[int] = set()
        clusters: List[FrontierCluster] = []
        robot_x, robot_y, _ = robot_pose

        for start in list(frontier_indices):
            if start in visited:
                continue

            queue = deque([start])
            visited.add(start)
            cells = []

            while queue:
                index = queue.popleft()
                cells.append(index)
                x = index % width
                y = index // width

                for nx, ny in self._neighbors8(x, y, grid.info.width,
                                               grid.info.height):
                    neighbor = self._index(nx, ny, width)
                    if neighbor not in frontier_indices or neighbor in visited:
                        continue
                    visited.add(neighbor)
                    queue.append(neighbor)

            if len(cells) < self.min_frontier_size:
                continue

            points = [
                self._cell_to_world(grid, cell % width, cell // width)
                for cell in cells
            ]
            centroid_x = sum(point[0] for point in points) / len(points)
            centroid_y = sum(point[1] for point in points) / len(points)
            distance = math.hypot(centroid_x - robot_x, centroid_y - robot_y)
            if distance < self.min_goal_distance:
                continue

            size_bonus = self.cluster_size_weight * math.sqrt(len(cells))
            score = distance - size_bonus
            clusters.append(
                FrontierCluster(
                    size=len(cells),
                    centroid_x=centroid_x,
                    centroid_y=centroid_y,
                    distance=distance,
                    score=score,
                ))

        return clusters

    def _send_goal(
            self,
            frontier: FrontierCluster,
            robot_pose: Tuple[float, float, float]):
        if not self._nav_action.wait_for_server(timeout_sec=0.1):
            self._warn_every(
                '_last_wait_warn',
                5.0,
                f'Waiting for Nav2 action server {self.navigate_action}.')
            return

        robot_x, robot_y, _ = robot_pose
        yaw = math.atan2(frontier.centroid_y - robot_y,
                         frontier.centroid_x - robot_x)
        qx, qy, qz, qw = self._yaw_to_quaternion(yaw)

        goal = NavigateToPose.Goal()
        goal.pose = PoseStamped()
        goal.pose.header.frame_id = self.global_frame
        goal.pose.header.stamp = self.get_clock().now().to_msg()
        goal.pose.pose.position.x = frontier.centroid_x
        goal.pose.pose.position.y = frontier.centroid_y
        goal.pose.pose.position.z = 0.0
        goal.pose.pose.orientation.x = qx
        goal.pose.pose.orientation.y = qy
        goal.pose.pose.orientation.z = qz
        goal.pose.pose.orientation.w = qw

        self._goal_active = True
        self._active_goal_started = self._now()
        future = self._nav_action.send_goal_async(goal)
        future.add_done_callback(self._goal_response_callback)
        self.get_logger().info(
            f'Sent frontier goal to Nav2: '
            f'x={frontier.centroid_x:.2f}, y={frontier.centroid_y:.2f}')

    def _goal_response_callback(self, future):
        try:
            goal_handle = future.result()
        except Exception as exc:  # pragma: no cover - depends on ROS graph
            self.get_logger().warn(
                f'Nav2 goal request failed: {exc}. Releasing for retry.')
            self._goal_active = False
            self._active_goal_handle = None
            self._active_goal_started = None
            return

        if not goal_handle.accepted:
            self.get_logger().warn('Frontier goal was rejected by Nav2.')
            self._goal_active = False
            self._active_goal_handle = None
            self._active_goal_started = None
            return

        self._active_goal_handle = goal_handle
        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(self._goal_result_callback)
        self.get_logger().info('Frontier goal accepted by Nav2.')

    def _goal_result_callback(self, future):
        result = future.result()
        status = result.status
        if status == GoalStatus.STATUS_SUCCEEDED:
            self.get_logger().info('Frontier goal reached.')
        elif status == GoalStatus.STATUS_CANCELED:
            self.get_logger().warn('Frontier goal canceled.')
        else:
            self.get_logger().warn(f'Frontier goal ended with status {status}.')

        self._goal_active = False
        self._active_goal_handle = None
        self._active_goal_started = None

    def _check_goal_timeout(self, now: float):
        if self._active_goal_started is None:
            return

        elapsed = now - self._active_goal_started

        # Accept-phase watchdog: we set _goal_active before send_goal_async
        # resolves, but _active_goal_handle is only set once Nav2 accepts the
        # goal. If the action server dies (or never responds) between send and
        # response, we would stay stuck with _goal_active=True forever. Reset
        # so the next timer tick can pick a fresh frontier.
        if self._active_goal_handle is None:
            if elapsed > self.goal_accept_timeout:
                self.get_logger().warn(
                    f'Nav2 did not accept the frontier goal within '
                    f'{self.goal_accept_timeout:.1f}s; releasing and retrying.')
                self._goal_active = False
                self._active_goal_started = None
            return

        if elapsed <= self.goal_timeout:
            return

        self.get_logger().warn(
            f'Frontier goal timed out after {self.goal_timeout:.1f}s; '
            'requesting cancel.')
        cancel_future = self._active_goal_handle.cancel_goal_async()
        cancel_future.add_done_callback(lambda _: None)
        self._active_goal_started = now

    def _cancel_active_goal(self, reason: str):
        if not self._goal_active or self._active_goal_handle is None:
            return
        self.get_logger().warn(f'Canceling frontier goal because of {reason}.')
        cancel_future = self._active_goal_handle.cancel_goal_async()
        cancel_future.add_done_callback(lambda _: None)

    def _has_unknown_neighbor(
            self,
            data: Sequence[int],
            width: int,
            height: int,
            x: int,
            y: int) -> bool:
        for nx, ny in self._neighbors8(x, y, width, height):
            if data[self._index(nx, ny, width)] == -1:
                return True
        return False

    def _is_free(self, value: int) -> bool:
        return 0 <= value <= self.free_threshold

    def _cell_to_world(
            self,
            grid: OccupancyGrid,
            x: int,
            y: int) -> Tuple[float, float]:
        origin = grid.info.origin
        resolution = grid.info.resolution
        local_x = (x + 0.5) * resolution
        local_y = (y + 0.5) * resolution
        yaw = self._yaw_from_quaternion(
            origin.orientation.x,
            origin.orientation.y,
            origin.orientation.z,
            origin.orientation.w,
        )
        cos_yaw = math.cos(yaw)
        sin_yaw = math.sin(yaw)
        world_x = origin.position.x + local_x * cos_yaw - local_y * sin_yaw
        world_y = origin.position.y + local_x * sin_yaw + local_y * cos_yaw
        return world_x, world_y

    @staticmethod
    def _neighbors8(
            x: int,
            y: int,
            width: int,
            height: int) -> Iterable[Tuple[int, int]]:
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nx = x + dx
                ny = y + dy
                if 0 <= nx < width and 0 <= ny < height:
                    yield nx, ny

    @staticmethod
    def _index(x: int, y: int, width: int) -> int:
        return y * width + x

    def _warn_every(self, attr: str, period: float, message: str):
        now = self._now()
        last = getattr(self, attr)
        if now - last < period:
            return
        self.get_logger().warn(message)
        setattr(self, attr, now)

    def _positive_float_parameter(self, name: str, fallback: float) -> float:
        value = float(self.get_parameter(name).value)
        if value <= 0.0:
            self.get_logger().warn(
                f'{name} must be > 0. Falling back to {fallback}.')
            return fallback
        return value

    def _now(self) -> float:
        return self.get_clock().now().nanoseconds / 1e9

    @staticmethod
    def _yaw_to_quaternion(yaw: float) -> Tuple[float, float, float, float]:
        half_yaw = yaw * 0.5
        return 0.0, 0.0, math.sin(half_yaw), math.cos(half_yaw)

    @staticmethod
    def _yaw_from_quaternion(x: float, y: float, z: float, w: float) -> float:
        siny_cosp = 2.0 * (w * z + x * y)
        cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
        return math.atan2(siny_cosp, cosy_cosp)


def main(args=None):
    rclpy.init(args=args)
    node = SimpleFrontierExplorer()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
