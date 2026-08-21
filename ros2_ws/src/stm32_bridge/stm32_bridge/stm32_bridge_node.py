import math
import time
from typing import Optional, Sequence, Tuple

from geometry_msgs.msg import TransformStamped, Twist
from nav_msgs.msg import Odometry
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Range
from tf2_ros import TransformBroadcaster

try:
    import serial
    from serial import SerialException, SerialTimeoutException
except ImportError:  # pragma: no cover - depends on host ROS environment
    serial = None

    class SerialException(Exception):
        pass

    class SerialTimeoutException(SerialException):
        pass


UINT32_MODULO = 2 ** 32
INT32_MODULO = 2 ** 32
INT32_HALF_RANGE = 2 ** 31
DEFAULT_ODOM_COVARIANCE_DIAGONAL = [
    0.01,
    0.01,
    99999.0,
    99999.0,
    99999.0,
    0.1,
]
DEFAULT_TWIST_COVARIANCE_DIAGONAL = [
    0.01,
    99999.0,
    99999.0,
    99999.0,
    99999.0,
    0.1,
]


class Stm32BridgeNode(Node):
    """Bridge /cmd_vel commands and STM32 feedback for wheel odometry."""

    def __init__(self):
        super().__init__('stm32_bridge_node')

        self.declare_parameter('port', '/dev/ttyACM0')
        self.declare_parameter('baudrate', 115200)
        self.declare_parameter('wheel_base', 0.46)
        self.declare_parameter('wheel_radius', 0.095)
        self.declare_parameter('steps_per_rev', 200.0)
        self.declare_parameter('microstep', 8.0)
        self.declare_parameter('gear_ratio', 10.0)
        self.declare_parameter('max_steps_per_sec', 12000.0)
        self.declare_parameter('max_wheel_speed_mm_s', 250.0)
        self.declare_parameter('send_rate_hz', 20.0)
        self.declare_parameter('cmd_timeout', 0.5)
        self.declare_parameter('invert_left', False)
        self.declare_parameter('invert_right', False)
        self.declare_parameter('odom_invert_left', False)
        self.declare_parameter('odom_invert_right', False)
        self.declare_parameter('speed_scale', 0.3)
        self.declare_parameter('publish_odom', True)
        self.declare_parameter('publish_tf', True)
        self.declare_parameter('odom_frame', 'odom')
        self.declare_parameter('base_frame', 'base_link')
        self.declare_parameter('publish_sonar', True)
        self.declare_parameter('sonar1_topic', '/ultrasonic/sonar1/range')
        self.declare_parameter('sonar2_topic', '/ultrasonic/sonar2/range')
        self.declare_parameter('sonar1_frame', 'sonar1_link')
        self.declare_parameter('sonar2_frame', 'sonar2_link')
        self.declare_parameter('sonar_min_range', 0.20)
        self.declare_parameter('sonar_max_range', 6.0)
        self.declare_parameter('sonar_field_of_view', 0.52)
        self.declare_parameter('feedback_timeout', 1.0)
        self.declare_parameter('feedback_counts_are_cumulative', True)
        self.declare_parameter('feedback_rate_warn_hz', 2.0)
        self.declare_parameter('reset_odom_on_start', True)
        # = True: dung yaw tu IMU (BNO08x) lam heading odometry (chinh xac hon
        # encoder vi khong troi do banh truot). Tu dong fallback ve encoder
        # neu firmware khong gui yaw.
        self.declare_parameter('use_imu_heading', True)
        self.declare_parameter(
            'odom_covariance_diagonal',
            DEFAULT_ODOM_COVARIANCE_DIAGONAL,
        )
        self.declare_parameter(
            'twist_covariance_diagonal',
            DEFAULT_TWIST_COVARIANCE_DIAGONAL,
        )

        self.port = self.get_parameter('port').value
        self.baudrate = int(self.get_parameter('baudrate').value)
        self.wheel_base = float(self.get_parameter('wheel_base').value)
        self.wheel_radius = float(self.get_parameter('wheel_radius').value)
        self.steps_per_rev = float(self.get_parameter('steps_per_rev').value)
        self.microstep = float(self.get_parameter('microstep').value)
        self.gear_ratio = float(self.get_parameter('gear_ratio').value)
        self.max_steps_per_sec = float(
            self.get_parameter('max_steps_per_sec').value)
        self.max_wheel_speed_mm_s = float(
            self.get_parameter('max_wheel_speed_mm_s').value)
        self.send_rate_hz = float(self.get_parameter('send_rate_hz').value)
        self.cmd_timeout = float(self.get_parameter('cmd_timeout').value)
        self.invert_left = bool(self.get_parameter('invert_left').value)
        self.invert_right = bool(self.get_parameter('invert_right').value)
        self.odom_invert_left = bool(
            self.get_parameter('odom_invert_left').value)
        self.odom_invert_right = bool(
            self.get_parameter('odom_invert_right').value)
        self.speed_scale = float(self.get_parameter('speed_scale').value)
        self.publish_odom = bool(self.get_parameter('publish_odom').value)
        self.publish_tf = bool(self.get_parameter('publish_tf').value)
        self.odom_frame = str(self.get_parameter('odom_frame').value)
        self.base_frame = str(self.get_parameter('base_frame').value)
        self.publish_sonar = bool(self.get_parameter('publish_sonar').value)
        self.sonar1_topic = str(self.get_parameter('sonar1_topic').value)
        self.sonar2_topic = str(self.get_parameter('sonar2_topic').value)
        self.sonar1_frame = str(self.get_parameter('sonar1_frame').value)
        self.sonar2_frame = str(self.get_parameter('sonar2_frame').value)
        self.sonar_min_range = float(
            self.get_parameter('sonar_min_range').value)
        self.sonar_max_range = float(
            self.get_parameter('sonar_max_range').value)
        self.sonar_field_of_view = float(
            self.get_parameter('sonar_field_of_view').value)
        self.feedback_timeout = float(
            self.get_parameter('feedback_timeout').value)
        self.feedback_counts_are_cumulative = bool(
            self.get_parameter('feedback_counts_are_cumulative').value)
        self.feedback_rate_warn_hz = float(
            self.get_parameter('feedback_rate_warn_hz').value)
        self.use_imu_heading = bool(
            self.get_parameter('use_imu_heading').value)
        self.reset_odom_on_start = bool(
            self.get_parameter('reset_odom_on_start').value)
        self.odom_covariance_diagonal = self._read_diagonal_parameter(
            'odom_covariance_diagonal',
            DEFAULT_ODOM_COVARIANCE_DIAGONAL,
        )
        self.twist_covariance_diagonal = self._read_diagonal_parameter(
            'twist_covariance_diagonal',
            DEFAULT_TWIST_COVARIANCE_DIAGONAL,
        )

        if self.send_rate_hz <= 0.0:
            self.get_logger().warn(
                'send_rate_hz must be > 0. Falling back to 20 Hz.')
            self.send_rate_hz = 20.0

        if self.cmd_timeout <= 0.0:
            self.get_logger().warn(
                'cmd_timeout must be > 0. Falling back to 0.5 s.')
            self.cmd_timeout = 0.5

        if self.feedback_timeout <= 0.0:
            self.get_logger().warn(
                'feedback_timeout must be > 0. Falling back to 1.0 s.')
            self.feedback_timeout = 1.0

        if self.feedback_rate_warn_hz <= 0.0:
            self.get_logger().warn(
                'feedback_rate_warn_hz must be > 0. Falling back to 2 Hz.')
            self.feedback_rate_warn_hz = 2.0

        if self.max_wheel_speed_mm_s <= 0.0:
            self.get_logger().warn(
                'max_wheel_speed_mm_s must be > 0. Falling back to 250 mm/s.')
            self.max_wheel_speed_mm_s = 250.0

        if self.max_steps_per_sec <= 0.0:
            self.get_logger().warn(
                'max_steps_per_sec must be > 0. Falling back to 12000.')
            self.max_steps_per_sec = 12000.0

        self.steps_per_meter = self._compute_steps_per_meter()
        self._feedback_warn_period = 1.0 / self.feedback_rate_warn_hz

        self._serial = None
        self._next_reconnect_time = 0.0
        self._reconnect_period = 1.0
        self._seq = 0
        self._left_mm_s = 0
        self._right_mm_s = 0
        self._command_is_stop = True
        self._last_cmd_time: Optional[float] = None
        self._timed_out = False
        self._last_tx_log_time = 0.0
        self._last_tx_log_payload = None
        self._rx_buffer = ''

        self._x = 0.0
        self._y = 0.0
        self._theta = 0.0
        # IMU yaw (radian) tu STM32 feedback (truong yaw_cdeg/yaw_valid).
        self._imu_yaw: Optional[float] = None
        self._imu_yaw_offset: Optional[float] = None  # de zero hoa luc bat dau
        self._last_left_count: Optional[int] = None
        self._last_right_count: Optional[int] = None
        self._last_feedback_mono: Optional[float] = None
        self._last_feedback_ros_sec: Optional[float] = None
        self._last_feedback_seq: Optional[int] = None
        self._last_feedback_status = ''
        self._node_start_mono = time.monotonic()
        self._last_feedback_timeout_warn_time = 0.0
        self._last_invalid_dt_warn_time = 0.0
        self._last_count_jump_warn_time = 0.0

        self._odom_pub = None
        self._tf_broadcaster = None
        self._sonar1_pub = None
        self._sonar2_pub = None
        if self.publish_odom:
            self._odom_pub = self.create_publisher(Odometry, '/odom', 10)
        if self.publish_tf:
            self._tf_broadcaster = TransformBroadcaster(self)
        if self.publish_sonar:
            self._sonar1_pub = self.create_publisher(Range, self.sonar1_topic, 10)
            self._sonar2_pub = self.create_publisher(Range, self.sonar2_topic, 10)

        self.get_logger().info(
            'Starting STM32 bridge: '
            f'port={self.port}, baudrate={self.baudrate}, '
            f'wheel_base={self.wheel_base:.3f} m, '
            f'wheel_radius={self.wheel_radius:.3f} m, '
            f'steps_per_rev={self.steps_per_rev:.1f}, '
            f'microstep={self.microstep:.1f}, '
            f'gear_ratio={self.gear_ratio:.3f}, '
            f'steps_per_meter={self.steps_per_meter:.3f}, '
            f'max_wheel_speed_mm_s={self.max_wheel_speed_mm_s:.1f}, '
            f'speed_scale={self.speed_scale:.3f}, '
            f'invert_left={self.invert_left}, invert_right={self.invert_right}, '
            f'odom_invert_left={self.odom_invert_left}, '
            f'odom_invert_right={self.odom_invert_right}, '
            f'publish_odom={self.publish_odom}, publish_tf={self.publish_tf}, '
            f'odom_frame={self.odom_frame}, base_frame={self.base_frame}, '
            f'publish_sonar={self.publish_sonar}, '
            f'sonar_topics=({self.sonar1_topic},{self.sonar2_topic}), '
            'command_format=CMD/STOP mm/s, feedback_format=FB seq/count/dt/status')

        self._open_serial()

        self.create_subscription(Twist, '/cmd_vel', self._cmd_vel_callback, 10)
        self._timer = self.create_timer(
            1.0 / self.send_rate_hz, self._timer_callback)

    def _cmd_vel_callback(self, msg: Twist):
        left_mm_s = (
            msg.linear.x - msg.angular.z * self.wheel_base / 2.0) * 1000.0
        right_mm_s = (
            msg.linear.x + msg.angular.z * self.wheel_base / 2.0) * 1000.0

        left_mm_s *= self.speed_scale
        right_mm_s *= self.speed_scale

        if self.invert_left:
            left_mm_s = -left_mm_s

        if self.invert_right:
            right_mm_s = -right_mm_s

        left_mm_s = self._clamp_wheel_speed(left_mm_s, 'left')
        right_mm_s = self._clamp_wheel_speed(right_mm_s, 'right')

        self._left_mm_s = int(round(left_mm_s))
        self._right_mm_s = int(round(right_mm_s))
        self._command_is_stop = (
            self._is_zero_twist(msg) or
            (self._left_mm_s == 0 and self._right_mm_s == 0)
        )
        self._last_cmd_time = time.monotonic()
        self._timed_out = False

    def _timer_callback(self):
        now = time.monotonic()

        self._ensure_serial(now)

        # Drain incoming feedback first so the firmware's USB CDC buffer never
        # fills up. A full read buffer can stall write() and trigger a spurious
        # write timeout.
        self._read_feedback()
        self._check_feedback_timeout(now)

        if self._last_cmd_time is None:
            # No /cmd_vel received yet. Keep the firmware in STOP state.
            self._send_stop()
        elif (now - self._last_cmd_time) > self.cmd_timeout:
            if not self._timed_out:
                self.get_logger().warn(
                    f'No /cmd_vel for {self.cmd_timeout:.3f} s. Sending stop.')
                self._timed_out = True
            self._send_stop()
        elif self._command_is_stop:
            self._send_stop()
        else:
            self._send_command(self._left_mm_s, self._right_mm_s)

    def _clamp_wheel_speed(self, value: float, wheel_name: str) -> float:
        clamped = max(
            -self.max_wheel_speed_mm_s,
            min(self.max_wheel_speed_mm_s, value),
        )

        if not math.isclose(value, clamped, rel_tol=0.0, abs_tol=1e-9):
            self.get_logger().warn(
                f'{wheel_name} wheel command clamped: '
                f'{value:.1f} -> {clamped:.1f} mm/s')

        return clamped

    def _send_command(self, left_mm_s: int, right_mm_s: int):
        seq = self._seq
        command = f'CMD,{seq},{left_mm_s},{right_mm_s}\r\n'

        if self._write_serial(command):
            self._seq = (self._seq + 1) % UINT32_MODULO
            self._log_tx(f'CMD,{seq},{left_mm_s},{right_mm_s}',
                         ('CMD', left_mm_s, right_mm_s))

    def _send_stop(self):
        # Use the firmware's dedicated STOP command so the controller enters its
        # STOP state instead of "running at zero speed".
        seq = self._seq
        command = f'STOP,{seq}\r\n'

        if self._write_serial(command):
            self._seq = (self._seq + 1) % UINT32_MODULO
            self._log_tx(f'STOP,{seq}', ('STOP', 0, 0))

    def _open_serial(self):
        if serial is None:
            self.get_logger().error(
                'pyserial is not installed. Install python3-serial before '
                'running stm32_bridge_node.')
            return

        try:
            self._serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=0.0,
                write_timeout=None,
            )
            self._rx_buffer = ''
            self.get_logger().info(
                f'Opened serial port {self.port} at {self.baudrate} baud.')
        except (OSError, SerialException) as exc:
            self._serial = None
            self._next_reconnect_time = time.monotonic() + self._reconnect_period
            self.get_logger().error(
                f'Failed to open serial port {self.port}: {exc}. '
                f'Retrying every {self._reconnect_period:.1f} s.')

    def _ensure_serial(self, now: float):
        if self._serial is not None and self._serial.is_open:
            return

        if now < self._next_reconnect_time:
            return

        self._next_reconnect_time = now + self._reconnect_period
        self.get_logger().info(
            f'Trying to reconnect serial port {self.port}...')
        self._open_serial()

    def _write_serial(self, command: str) -> bool:
        if self._serial is None or not self._serial.is_open:
            return False

        try:
            self._serial.write(command.encode('ascii'))
            return True
        except SerialTimeoutException:
            # The USB CDC pipe is momentarily congested, not disconnected.
            # Drop this frame instead of tearing down the port; the next timer
            # tick will send a fresh command.
            self.get_logger().warn(
                f'Serial write timed out on {self.port}; dropping one frame.')
            try:
                self._serial.reset_output_buffer()
            except (OSError, SerialException):
                pass
            return False
        except (OSError, SerialException) as exc:
            self.get_logger().error(
                f'Serial write failed on {self.port}: {exc}. '
                'Closing port and waiting for reconnect.')
            self._enter_safe_stop_state('serial_write_failed')
            self._close_serial()
            return False

    def _read_feedback(self):
        if self._serial is None or not self._serial.is_open:
            return

        try:
            waiting = self._serial.in_waiting
            if waiting <= 0:
                return

            chunk = self._serial.read(waiting).decode(
                'ascii', errors='replace')
        except (OSError, SerialException) as exc:
            self.get_logger().error(
                f'Serial read failed on {self.port}: {exc}. '
                'Closing port and waiting for reconnect.')
            self._close_serial()
            return

        self._rx_buffer += chunk
        while '\n' in self._rx_buffer:
            line, self._rx_buffer = self._rx_buffer.split('\n', 1)
            line = line.rstrip('\r').strip()
            if line:
                self.get_logger().debug(f'RX: {line}')
                self._process_rx_line(line)

    def _process_rx_line(self, line: str):
        if line.startswith('FB,'):
            self._handle_feedback_line(line)
            return

        if line.startswith('ERR,'):
            self.get_logger().warn(f'STM32 protocol error: {line}')
            return

        self.get_logger().debug(f'Ignoring non-feedback serial line: {line}')

    def _handle_feedback_line(self, line: str):
        parsed = self._parse_feedback_line(line, include_sonar=True)
        if parsed is None:
            return

        (seq, left_count, right_count, dt_ms, status, yaw_rad,
         sonar1, sonar2) = parsed

        # Cap nhat yaw IMU (zero-hoa lan dau de heading bat dau tu 0).
        if yaw_rad is not None:
            if self._imu_yaw_offset is None:
                self._imu_yaw_offset = yaw_rad
            self._imu_yaw = self._normalize_angle(yaw_rad - self._imu_yaw_offset)
        now_mono = time.monotonic()
        now_ros = self.get_clock().now()
        now_ros_sec = now_ros.nanoseconds / 1e9

        if sonar1 is not None:
            self._publish_sonar_range(
                self._sonar1_pub, self.sonar1_frame, sonar1, now_ros)
        if sonar2 is not None:
            self._publish_sonar_range(
                self._sonar2_pub, self.sonar2_frame, sonar2, now_ros)

        self._last_feedback_mono = now_mono
        self._last_feedback_seq = seq
        self._last_feedback_status = status
        self.get_logger().debug(
            'Parsed feedback: '
            f'seq={seq}, left_count={left_count}, right_count={right_count}, '
            f'dt_ms={dt_ms:.3f}, status={status}')

        delta_left_count, delta_right_count = self._compute_count_delta(
            left_count,
            right_count,
        )
        dt = self._resolve_feedback_dt(dt_ms, now_ros_sec, now_mono)

        self._last_left_count = left_count
        self._last_right_count = right_count
        self._last_feedback_ros_sec = now_ros_sec

        if delta_left_count is None or delta_right_count is None:
            self._publish_odometry(now_ros, 0.0, 0.0)
            return

        # NOTE: do NOT reuse invert_left/invert_right here. The firmware counts
        # steps as `count += direction`, where direction already follows the
        # sign of the (already-inverted) wheel command. So the feedback count
        # direction tracks the *physical* wheel motion. Re-applying the command
        # invert would cancel out and make the pose run backwards. Use the
        # dedicated odom_invert_* parameters only when the firmware's count sign
        # is genuinely reversed relative to physical forward motion.
        if self.odom_invert_left:
            delta_left_count = -delta_left_count
        if self.odom_invert_right:
            delta_right_count = -delta_right_count

        self._warn_if_count_jump(delta_left_count, delta_right_count, dt,
                                 now_mono)
        linear_velocity, angular_velocity = self._update_odometry(
            delta_left_count,
            delta_right_count,
            dt,
        )
        self._publish_odometry(now_ros, linear_velocity, angular_velocity)

    def _parse_feedback_line(
            self,
            line: str,
            include_sonar: bool = False
    ) -> Optional[Tuple]:
        parts = [part.strip() for part in line.split(',')]
        yaw_rad: Optional[float] = None
        sonar1 = None
        sonar2 = None
        try:
            # New format appends mm/valid pairs for SONAR1 and SONAR2.
            if len(parts) == 12:
                seq = int(parts[1])
                left_count = int(parts[2])
                right_count = int(parts[3])
                dt_ms = float(parts[4])
                status = parts[5].upper()
                yaw_cdeg = int(parts[6])
                yaw_valid = int(parts[7])
                if yaw_valid != 0:
                    yaw_rad = math.radians(yaw_cdeg / 100.0)
                sonar1 = (int(parts[8]), int(parts[9]) != 0)
                sonar2 = (int(parts[10]), int(parts[11]) != 0)
            # Format with IMU only: FB,seq,left,right,dt,status,yaw_cdeg,yaw_valid
            elif len(parts) == 8:
                seq = int(parts[1])
                left_count = int(parts[2])
                right_count = int(parts[3])
                dt_ms = float(parts[4])
                status = parts[5].upper()
                yaw_cdeg = int(parts[6])
                yaw_valid = int(parts[7])
                if yaw_valid != 0:
                    yaw_rad = math.radians(yaw_cdeg / 100.0)
            elif len(parts) == 6:
                seq = int(parts[1])
                left_count = int(parts[2])
                right_count = int(parts[3])
                dt_ms = float(parts[4])
                status = parts[5].upper()
            elif len(parts) == 5:
                seq = None
                left_count = int(parts[1])
                right_count = int(parts[2])
                dt_ms = float(parts[3])
                status = parts[4].upper()
            else:
                raise ValueError(
                    f'expected 5, 6, 8 or 12 CSV fields, got {len(parts)}')
        except ValueError as exc:
            self.get_logger().warn(
                f'Failed to parse STM32 feedback "{line}": {exc}')
            return None

        parsed = seq, left_count, right_count, dt_ms, status, yaw_rad
        if include_sonar:
            return parsed + (sonar1, sonar2)
        return parsed

    def _compute_count_delta(
            self,
            left_count: int,
            right_count: int) -> Tuple[Optional[int], Optional[int]]:
        if not self.feedback_counts_are_cumulative:
            return left_count, right_count

        if self._last_left_count is None or self._last_right_count is None:
            if self.reset_odom_on_start:
                return None, None
            return left_count, right_count

        return (
            self._diff_signed_32(left_count, self._last_left_count),
            self._diff_signed_32(right_count, self._last_right_count),
        )

    def _resolve_feedback_dt(
            self,
            dt_ms: float,
            now_ros_sec: float,
            now_mono: float) -> float:
        if math.isfinite(dt_ms) and dt_ms > 0.0:
            return dt_ms / 1000.0

        if self._last_feedback_ros_sec is not None:
            dt = now_ros_sec - self._last_feedback_ros_sec
            if dt > 0.0:
                return dt

        if now_mono - self._last_invalid_dt_warn_time >= self._feedback_warn_period:
            self.get_logger().warn(
                'Invalid feedback dt_ms and no valid ROS fallback dt yet; '
                'publishing zero velocity for this sample.')
            self._last_invalid_dt_warn_time = now_mono
        return 0.0

    def _update_odometry(
            self,
            delta_left_count: int,
            delta_right_count: int,
            dt: float) -> Tuple[float, float]:
        left_distance = delta_left_count / self.steps_per_meter
        right_distance = delta_right_count / self.steps_per_meter

        delta_s = (right_distance + left_distance) / 2.0
        # delta_theta tu encoder (du phong khi khong co IMU).
        delta_theta_enc = (right_distance - left_distance) / self.wheel_base

        use_imu = self.use_imu_heading and (self._imu_yaw is not None)
        if use_imu:
            # Heading lay TRUC TIEP tu IMU (chinh xac hon, khong troi do encoder
            # truot). delta_theta = chenh lech yaw IMU so voi buoc truoc.
            prev_theta = self._theta
            new_theta = self._imu_yaw
            delta_theta = self._normalize_angle(new_theta - prev_theta)
            heading = prev_theta + delta_theta / 2.0
            self._x += delta_s * math.cos(heading)
            self._y += delta_s * math.sin(heading)
            self._theta = self._normalize_angle(new_theta)
        else:
            delta_theta = delta_theta_enc
            heading = self._theta + delta_theta / 2.0
            self._x += delta_s * math.cos(heading)
            self._y += delta_s * math.sin(heading)
            self._theta = self._normalize_angle(self._theta + delta_theta)

        if dt > 0.0:
            linear_velocity = delta_s / dt
            angular_velocity = delta_theta / dt
        else:
            linear_velocity = 0.0
            angular_velocity = 0.0

        self.get_logger().debug(
            'Odom: '
            f'x={self._x:.4f}, y={self._y:.4f}, theta={self._theta:.4f}, '
            f'linear={linear_velocity:.4f}, angular={angular_velocity:.4f}')
        return linear_velocity, angular_velocity

    def _publish_odometry(
            self,
            stamp,
            linear_velocity: float,
            angular_velocity: float):
        qx, qy, qz, qw = self._yaw_to_quaternion(self._theta)

        if self.publish_odom and self._odom_pub is not None:
            odom = Odometry()
            odom.header.stamp = stamp.to_msg()
            odom.header.frame_id = self.odom_frame
            odom.child_frame_id = self.base_frame
            odom.pose.pose.position.x = self._x
            odom.pose.pose.position.y = self._y
            odom.pose.pose.position.z = 0.0
            odom.pose.pose.orientation.x = qx
            odom.pose.pose.orientation.y = qy
            odom.pose.pose.orientation.z = qz
            odom.pose.pose.orientation.w = qw
            odom.pose.covariance = self._diagonal_to_covariance(
                self.odom_covariance_diagonal)
            odom.twist.twist.linear.x = linear_velocity
            odom.twist.twist.angular.z = angular_velocity
            odom.twist.covariance = self._diagonal_to_covariance(
                self.twist_covariance_diagonal)
            self._odom_pub.publish(odom)

        if self.publish_tf and self._tf_broadcaster is not None:
            transform = TransformStamped()
            transform.header.stamp = stamp.to_msg()
            transform.header.frame_id = self.odom_frame
            transform.child_frame_id = self.base_frame
            transform.transform.translation.x = self._x
            transform.transform.translation.y = self._y
            transform.transform.translation.z = 0.0
            transform.transform.rotation.x = qx
            transform.transform.rotation.y = qy
            transform.transform.rotation.z = qz
            transform.transform.rotation.w = qw
            self._tf_broadcaster.sendTransform(transform)

    def _publish_sonar_range(
            self,
            publisher,
            frame_id: str,
            reading: Tuple[int, bool],
            stamp):
        if not self.publish_sonar or publisher is None:
            return

        distance_mm, valid = reading
        range_msg = Range()
        range_msg.header.stamp = stamp.to_msg()
        range_msg.header.frame_id = frame_id
        range_msg.radiation_type = Range.ULTRASOUND
        range_msg.field_of_view = self.sonar_field_of_view
        range_msg.min_range = self.sonar_min_range
        range_msg.max_range = self.sonar_max_range

        distance_m = distance_mm / 1000.0
        if valid and self.sonar_min_range <= distance_m <= self.sonar_max_range:
            range_msg.range = distance_m
        else:
            # sensor_msgs/Range uses NaN for an invalid or missing echo.
            range_msg.range = float('nan')

        publisher.publish(range_msg)

    def _check_feedback_timeout(self, now: float):
        if not self.publish_odom and not self.publish_tf:
            return

        last_feedback = self._last_feedback_mono
        if last_feedback is None:
            elapsed = now - self._node_start_mono
            if elapsed <= self.feedback_timeout:
                return
        else:
            elapsed = now - last_feedback
            if elapsed <= self.feedback_timeout:
                return

        if now - self._last_feedback_timeout_warn_time < self._feedback_warn_period:
            return

        if last_feedback is None:
            self.get_logger().warn(
                f'No STM32 feedback received after {elapsed:.3f} s. '
                'Expected FB,<seq>,<left_count>,<right_count>,<dt_ms>,<status>.')
        else:
            self.get_logger().warn(
                f'No STM32 feedback for {elapsed:.3f} s. '
                f'Last status={self._last_feedback_status}, '
                f'last_seq={self._last_feedback_seq}.')
        self._last_feedback_timeout_warn_time = now
        self._enter_safe_stop_state('feedback_timeout')
        self._send_stop()

    def _warn_if_count_jump(
            self,
            delta_left_count: int,
            delta_right_count: int,
            dt: float,
            now: float):
        effective_dt = dt if dt > 0.0 else (1.0 / self.send_rate_hz)
        max_expected_delta = self.max_steps_per_sec * effective_dt * 4.0
        max_delta = max(abs(delta_left_count), abs(delta_right_count))

        if max_delta <= max_expected_delta:
            return

        if now - self._last_count_jump_warn_time < self._feedback_warn_period:
            return

        self.get_logger().warn(
            'Suspicious feedback count jump: '
            f'delta_left={delta_left_count}, delta_right={delta_right_count}, '
            f'dt={dt:.4f}s, threshold={max_expected_delta:.1f} steps.')
        self._last_count_jump_warn_time = now

    def _close_serial(self):
        if self._serial is None:
            return

        try:
            if self._serial.is_open:
                self._serial.close()
        except (OSError, SerialException) as exc:
            self.get_logger().warn(f'Error while closing serial port: {exc}')
        finally:
            self._serial = None

    def _enter_safe_stop_state(self, reason: str):
        was_active = (
            self._last_cmd_time is not None or
            self._left_mm_s != 0 or
            self._right_mm_s != 0
        )
        self._left_mm_s = 0
        self._right_mm_s = 0
        self._command_is_stop = True
        self._last_cmd_time = None
        self._timed_out = True

        if was_active:
            self.get_logger().warn(
                f'Entering safe stop state because of {reason}.')

    def _log_tx(self, command: str, payload: tuple):
        now = time.monotonic()

        if payload != self._last_tx_log_payload or (
            now - self._last_tx_log_time) >= 1.0:
            self.get_logger().info(f'TX: {command}')
            self._last_tx_log_payload = payload
            self._last_tx_log_time = now

    def _compute_steps_per_meter(self) -> float:
        wheel_circumference = 2.0 * math.pi * self.wheel_radius
        if wheel_circumference <= 0.0:
            self.get_logger().warn(
                'wheel_radius must be > 0. Falling back to 0.095 m.')
            self.wheel_radius = 0.095
            wheel_circumference = 2.0 * math.pi * self.wheel_radius

        if self.steps_per_rev <= 0.0:
            self.get_logger().warn(
                'steps_per_rev must be > 0. Falling back to 200.')
            self.steps_per_rev = 200.0

        if self.microstep <= 0.0:
            self.get_logger().warn(
                'microstep must be > 0. Falling back to 8.')
            self.microstep = 8.0

        if self.gear_ratio <= 0.0:
            self.get_logger().warn(
                'gear_ratio must be > 0. Falling back to 10.')
            self.gear_ratio = 10.0

        return (
            self.steps_per_rev *
            self.microstep *
            self.gear_ratio /
            wheel_circumference
        )

    def _read_diagonal_parameter(
            self,
            name: str,
            default: Sequence[float]) -> Sequence[float]:
        value = self.get_parameter(name).value
        raw_values = value

        if isinstance(value, str):
            stripped = value.strip()
            if stripped.startswith('[') and stripped.endswith(']'):
                stripped = stripped[1:-1]
            raw_values = [
                item.strip()
                for item in stripped.split(',')
                if item.strip()
            ]

        try:
            diagonal = [float(item) for item in raw_values]
        except (TypeError, ValueError):
            self.get_logger().warn(
                f'{name} must be a 6-value numeric list. Using defaults.')
            return list(default)

        if len(diagonal) != 6:
            self.get_logger().warn(
                f'{name} must contain exactly 6 values. Using defaults.')
            return list(default)

        return diagonal

    @staticmethod
    def _diagonal_to_covariance(diagonal: Sequence[float]) -> list:
        covariance = [0.0] * 36
        for index, value in zip((0, 7, 14, 21, 28, 35), diagonal):
            covariance[index] = float(value)
        return covariance

    @staticmethod
    def _diff_signed_32(current: int, previous: int) -> int:
        delta = current - previous
        if delta > INT32_HALF_RANGE:
            delta -= INT32_MODULO
        elif delta < -INT32_HALF_RANGE:
            delta += INT32_MODULO
        return delta

    @staticmethod
    def _normalize_angle(angle: float) -> float:
        return math.atan2(math.sin(angle), math.cos(angle))

    @staticmethod
    def _yaw_to_quaternion(yaw: float) -> Tuple[float, float, float, float]:
        half_yaw = yaw * 0.5
        return 0.0, 0.0, math.sin(half_yaw), math.cos(half_yaw)

    @staticmethod
    def _is_zero_twist(msg: Twist) -> bool:
        values = (
            msg.linear.x,
            msg.linear.y,
            msg.linear.z,
            msg.angular.x,
            msg.angular.y,
            msg.angular.z,
        )
        return all(math.isclose(value, 0.0, abs_tol=1e-9) for value in values)

    def destroy_node(self):
        try:
            self.get_logger().info('Sending stop command before shutdown.')
            self._send_stop()
        finally:
            self._close_serial()
            super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = Stm32BridgeNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
