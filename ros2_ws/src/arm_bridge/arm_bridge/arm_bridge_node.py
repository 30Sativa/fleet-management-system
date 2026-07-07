"""arm_bridge_node — bridge high-level arm commands to the SCARA controller.

Scope on purpose: this node is the ONLY new runtime piece for the arm. It is
fully independent of the car stack (stm32_bridge, robot_control, ...). It opens
its own device/port, uses its own topics, and never touches the car's code.

Transport is swappable (serial now, can later) via the `transport` parameter.
The node never imports a concrete transport directly beyond selection — all
traffic goes through the ArmTransport interface.

Interface is self-contained: to avoid changing the shared bus_interfaces
package, this node uses only standard messages for now:

  subscribe  /arm/joint_cmd   std_msgs/Float64MultiArray   [j1, j2, z] (deg, deg, mm)
  subscribe  /arm/gripper_cmd std_msgs/Bool                True = close, False = open
  publish    /arm/status      std_msgs/String              last feedback line

If a richer custom action/service is wanted later, it can be added to
bus_interfaces without disturbing this node's structure.

Firmware command vocabulary (text lines, transport-independent):

    ARM,<seq>,<j1_deg>,<j2_deg>,<z_mm>
    GRIP,<seq>,<OPEN|CLOSE>
    HOME,<seq>
    STOP,<seq>

Firmware feedback (echoed onto /arm/status as-is for now):

    AFB,<seq>,<state>            e.g. AFB,7,DONE / AFB,7,BUSY / AFB,7,ERR
"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool, Float64MultiArray, String

from .transport_serial import SerialTransport
from .transport_can import CanTransport


class ArmBridgeNode(Node):
    def __init__(self):
        super().__init__('arm_bridge_node')

        # --- transport selection ---
        self.declare_parameter('transport', 'serial')   # 'serial' | 'can'
        # serial params
        self.declare_parameter('port', '/dev/ttyUSB0')  # arm's OWN port
        self.declare_parameter('baudrate', 115200)
        # can params (used only when transport == 'can')
        self.declare_parameter('can_channel', 'can0')
        self.declare_parameter('can_bitrate', 500000)
        self.declare_parameter('can_arm_tx_id', 0x200)
        self.declare_parameter('can_arm_rx_id', 0x201)
        # loop / safety
        self.declare_parameter('poll_rate_hz', 50.0)
        self.declare_parameter('cmd_timeout', 1.0)

        self._transport_name = str(self.get_parameter('transport').value).lower()
        self._poll_rate = float(self.get_parameter('poll_rate_hz').value)
        self._cmd_timeout = float(self.get_parameter('cmd_timeout').value)

        self._seq = 0
        self._last_cmd_time = self.get_clock().now()

        self._transport = self._make_transport()
        self._open_transport()

        # --- ROS interface (self-contained, standard messages) ---
        self.create_subscription(
            Float64MultiArray, '/arm/joint_cmd', self._on_joint_cmd, 10)
        self.create_subscription(
            Bool, '/arm/gripper_cmd', self._on_gripper_cmd, 10)
        self._status_pub = self.create_publisher(String, '/arm/status', 10)

        self.create_timer(1.0 / max(self._poll_rate, 1.0), self._poll)

        self.get_logger().info(
            f'arm_bridge_node up. transport={self._transport_name}')

    # ------------------------------------------------------------------ setup
    def _make_transport(self):
        if self._transport_name == 'can':
            return CanTransport(
                channel=str(self.get_parameter('can_channel').value),
                bitrate=int(self.get_parameter('can_bitrate').value),
                arm_tx_id=int(self.get_parameter('can_arm_tx_id').value),
                arm_rx_id=int(self.get_parameter('can_arm_rx_id').value),
            )
        # default: serial
        return SerialTransport(
            port=str(self.get_parameter('port').value),
            baudrate=int(self.get_parameter('baudrate').value),
        )

    def _open_transport(self):
        try:
            self._transport.open()
            self.get_logger().info('arm transport opened.')
        except Exception as exc:  # keep node alive; retry in _poll
            self.get_logger().warn(f'arm transport open failed: {exc}')

    # --------------------------------------------------------------- callbacks
    def _next_seq(self) -> int:
        self._seq = (self._seq + 1) % 1000000
        return self._seq

    def _on_joint_cmd(self, msg: Float64MultiArray):
        vals = list(msg.data)
        if len(vals) < 3:
            self.get_logger().warn(
                'joint_cmd needs [j1_deg, j2_deg, z_mm]; ignoring.')
            return
        j1, j2, z = vals[0], vals[1], vals[2]
        self._send(f'ARM,{self._next_seq()},{j1:.3f},{j2:.3f},{z:.3f}')
        self._last_cmd_time = self.get_clock().now()

    def _on_gripper_cmd(self, msg: Bool):
        action = 'CLOSE' if msg.data else 'OPEN'
        self._send(f'GRIP,{self._next_seq()},{action}')
        self._last_cmd_time = self.get_clock().now()

    # -------------------------------------------------------------------- loop
    def _poll(self):
        # reconnect if needed
        if not self._transport.is_open():
            self._open_transport()
            return
        # drain feedback lines
        try:
            while True:
                line = self._transport.read_line()
                if not line:
                    break
                self._status_pub.publish(String(data=line))
        except Exception as exc:
            self.get_logger().warn(f'arm read error: {exc}')

    def _send(self, line: str):
        try:
            if self._transport.is_open():
                self._transport.send_line(line)
            else:
                self.get_logger().warn(f'transport closed, dropped: {line}')
        except Exception as exc:
            self.get_logger().warn(f'arm send error: {exc}')

    def destroy_node(self):
        try:
            if self._transport is not None:
                # best-effort stop before closing
                try:
                    if self._transport.is_open():
                        self._transport.send_line(f'STOP,{self._next_seq()}')
                except Exception:
                    pass
                self._transport.close()
        finally:
            super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = ArmBridgeNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
