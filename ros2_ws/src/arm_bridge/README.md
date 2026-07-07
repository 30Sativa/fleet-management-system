# arm_bridge

ROS2 bridge for the SCARA arm mounted on the AMR. It is **independent of the
car stack** (`stm32_bridge`, `robot_control`, ...): it opens its own port, uses
its own topics, and does not modify any existing car code.

```text
ROS2 (miniPC)
    -> /arm/joint_cmd, /arm/gripper_cmd
    -> arm_bridge_node
    -> ArmTransport  (serial NOW / CAN LATER)
    -> Arduino Uno + CNC Shield  (or STM32 later)
    -> A4988 x3 (J1/J2/Z) + servo gripper
    -> arm

arm controller
    -> AFB feedback line
    -> arm_bridge_node
    -> /arm/status
```

## Why a transport layer

The arm runs on **USB CDC serial now** (fast to bench-test, same proven path the
car uses) and will move to **CAN later**. To make that switch painless,
"what we say to the arm" is separated from "how we send it":

- `transport_base.py` — the `ArmTransport` interface the node talks to.
- `transport_serial.py` — Serial (USB CDC). **Used now.**
- `transport_can.py` — CAN. **Stub**, implement when migrating.

Switching is one launch arg — no node changes:

```bash
ros2 launch arm_bridge arm_bridge.launch.py transport:=serial   # now
ros2 launch arm_bridge arm_bridge.launch.py transport:=can      # later
```

## Independence from the car (important)

- The car STM32 is usually `/dev/ttyACM0`. The arm uses its **own** port,
  default `/dev/ttyUSB0` (Arduino Uno CH340). Keep them different so the two
  bridges never fight over a device.
- This package does **not** touch `bus_interfaces`. It uses standard messages
  so existing builds are unaffected.

## ROS interface (self-contained)

| Direction | Topic | Type | Meaning |
|---|---|---|---|
| sub | `/arm/joint_cmd` | `std_msgs/Float64MultiArray` | `[j1_deg, j2_deg, z_mm]` |
| sub | `/arm/gripper_cmd` | `std_msgs/Bool` | `true` = close, `false` = open |
| pub | `/arm/status` | `std_msgs/String` | last feedback line from the controller |

## Command vocabulary (transport-independent)

These text lines are what the firmware parses. On CAN they get encoded into
frames and decoded back into the same lines, so the format never changes.

```text
ARM,<seq>,<j1_deg>,<j2_deg>,<z_mm>
GRIP,<seq>,<OPEN|CLOSE>
HOME,<seq>
STOP,<seq>
```

Feedback:

```text
AFB,<seq>,<DONE|BUSY|ERR>
```

## Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `transport` | `serial` | `serial` (now) or `can` (later) |
| `port` | `/dev/ttyUSB0` | arm's own serial port |
| `baudrate` | `115200` | serial baudrate |
| `can_channel` | `can0` | SocketCAN channel (CAN only) |
| `can_bitrate` | `500000` | CAN bitrate (CAN only) |
| `poll_rate_hz` | `50.0` | feedback poll / reconnect rate |
| `cmd_timeout` | `1.0` | reserved for future watchdog |

## Build

```bash
cd ~/ros2_ws
colcon build --packages-select arm_bridge
source install/setup.bash
```

## Run

```bash
ros2 launch arm_bridge arm_bridge.launch.py port:=/dev/ttyUSB0
```

Quick manual test:

```bash
# move joints (j1=90 deg, j2=45 deg, z=120 mm)
ros2 topic pub --once /arm/joint_cmd std_msgs/Float64MultiArray "{data: [90.0, 45.0, 120.0]}"
# close gripper
ros2 topic pub --once /arm/gripper_cmd std_msgs/Bool "{data: true}"
# watch feedback
ros2 topic echo /arm/status
```

## Status

This is a working **skeleton**. The serial transport and node loop are real;
the firmware (`firmware/arduino/arm_controller`) and the actual motion logic
are filled in once the hardware arrives. Do not wire it to the car's port.
