import math
import time
from typing import Optional

from geometry_msgs.msg import Twist
import rclpy
from rclpy.node import Node

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


class Stm32BridgeNode(Node):
    """Bridge /cmd_vel Twist commands to the STM32 USB CDC text protocol."""

    def __init__(self):
        super().__init__('stm32_bridge_node')

        self.declare_parameter('port', '/dev/ttyACM0')
        self.declare_parameter('baudrate', 115200)
        self.declare_parameter('wheel_base', 0.60)
        self.declare_parameter('max_wheel_speed_mm_s', 1000.0)
        self.declare_parameter('send_rate_hz', 20.0)
        self.declare_parameter('cmd_timeout', 0.5)
        self.declare_parameter('invert_left', False)
        self.declare_parameter('invert_right', False)
        self.declare_parameter('speed_scale', 1.0)

        self.port = self.get_parameter('port').value
        self.baudrate = int(self.get_parameter('baudrate').value)
        self.wheel_base = float(self.get_parameter('wheel_base').value)
        self.max_wheel_speed_mm_s = float(
            self.get_parameter('max_wheel_speed_mm_s').value)
        self.send_rate_hz = float(self.get_parameter('send_rate_hz').value)
        self.cmd_timeout = float(self.get_parameter('cmd_timeout').value)
        self.invert_left = bool(self.get_parameter('invert_left').value)
        self.invert_right = bool(self.get_parameter('invert_right').value)
        self.speed_scale = float(self.get_parameter('speed_scale').value)

        if self.send_rate_hz <= 0.0:
            self.get_logger().warn(
                'send_rate_hz must be > 0. Falling back to 20 Hz.')
            self.send_rate_hz = 20.0

        if self.cmd_timeout <= 0.0:
            self.get_logger().warn(
                'cmd_timeout must be > 0. Falling back to 0.5 s.')
            self.cmd_timeout = 0.5

        if self.max_wheel_speed_mm_s <= 0.0:
            self.get_logger().warn(
                'max_wheel_speed_mm_s must be > 0. Falling back to 1000 mm/s.')
            self.max_wheel_speed_mm_s = 1000.0

        self._serial = None
        self._next_reconnect_time = 0.0
        self._reconnect_period = 1.0
        self._seq = 0
        self._left_mm_s = 0
        self._right_mm_s = 0
        self._last_cmd_time: Optional[float] = None
        self._timed_out = False
        self._last_tx_log_time = 0.0
        self._last_tx_log_payload = None
        self._rx_buffer = ''

        self.get_logger().info(
            'Starting STM32 bridge: '
            f'port={self.port}, baudrate={self.baudrate}, '
            f'wheel_base={self.wheel_base:.3f} m, '
            f'max_wheel_speed_mm_s={self.max_wheel_speed_mm_s:.1f}, '
            f'speed_scale={self.speed_scale:.3f}, '
            f'invert_left={self.invert_left}, invert_right={self.invert_right}, '
            'number_format=int(round(mm/s)), seq_start=0, seq_wrap=uint32')

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
        self._last_cmd_time = time.monotonic()
        self._timed_out = False

    def _timer_callback(self):
        now = time.monotonic()

        self._ensure_serial(now)

        # Drain incoming feedback first so the firmware's USB CDC buffer never
        # fills up. A full read buffer can stall our write() and trigger a
        # spurious write timeout.
        self._read_feedback()

        if self._last_cmd_time is None:
            # No /cmd_vel received yet. Keep the firmware in STOP state.
            self._send_stop()
        elif (now - self._last_cmd_time) > self.cmd_timeout:
            if not self._timed_out:
                self.get_logger().warn(
                    f'No /cmd_vel for {self.cmd_timeout:.3f} s. Sending stop.')
                self._timed_out = True
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
            line = line.rstrip('\r')
            if line:
                self.get_logger().debug(f'RX: {line}')

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

    def _log_tx(self, command: str, payload: tuple):
        now = time.monotonic()

        if payload != self._last_tx_log_payload or (
            now - self._last_tx_log_time) >= 1.0:
            self.get_logger().info(f'TX: {command}')
            self._last_tx_log_payload = payload
            self._last_tx_log_time = now

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
