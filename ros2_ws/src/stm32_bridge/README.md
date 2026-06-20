# stm32_bridge

ROS2 Humble bridge for the real STM32 motor controller.

Flow:

```text
teleop_twist_keyboard -> /cmd_vel -> stm32_bridge_node -> USB CDC Serial -> STM32
```

The laptop only sends wheel speed commands. The STM32 firmware keeps ownership
of the real-time STEP/DIR generation for the HBS57H drivers.

## STM32 Protocol

The current firmware parses two command formats:

```text
CMD,<seq>,<left_mm_s>,<right_mm_s>\r\n
STOP,<seq>\r\n
```

Examples:

```text
CMD,0,300,300
CMD,1,-300,-300
CMD,2,-300,300
STOP,3
```

The bridge sends `CMD,...` for normal motion and the firmware's dedicated
`STOP,<seq>` for the watchdog timeout, for the idle state before the first
`/cmd_vel`, and on shutdown. `STOP` puts the firmware into its STOP state,
which is cleaner than sending `CMD,<seq>,0,0`.

Speed units are `mm/s`, not step/s. The bridge rounds wheel commands to integer
mm/s before sending. Firmware currently parses speed values with `strtof`, so
integer text values are accepted. `seq` starts at 0 and wraps at uint32; the
firmware stores the last `seq` but does not require it to increase.

## Environment

When running inside Ubuntu 22.04 on VMware:

```bash
ls /dev/ttyACM*
dmesg | grep tty
```

If `/dev/ttyACM0` does not appear, connect the STM32 USB device to the VM from
VMware Removable Devices first.

Give your user serial permission:

```bash
sudo usermod -aG dialout $USER
```

Then log out and log back in.

## Build

```bash
cd ~/ros2_ws
rosdep install --from-paths src --ignore-src -r -y
colcon build --packages-select stm32_bridge
source install/setup.bash
```

## Run

```bash
ros2 launch stm32_bridge stm32_bridge.launch.py
```

In another terminal:

```bash
source ~/ros2_ws/install/setup.bash
ros2 run teleop_twist_keyboard teleop_twist_keyboard
```

If the STM32 appears on a different port:

```bash
ros2 launch stm32_bridge stm32_bridge.launch.py port:=/dev/ttyACM1
```

Useful tuning examples:

```bash
ros2 launch stm32_bridge stm32_bridge.launch.py speed_scale:=0.5
ros2 launch stm32_bridge stm32_bridge.launch.py max_wheel_speed_mm_s:=600
ros2 launch stm32_bridge stm32_bridge.launch.py invert_left:=true
```

## Parameters

| Parameter | Default | Meaning |
|---|---:|---|
| `port` | `/dev/ttyACM0` | STM32 USB CDC serial port |
| `baudrate` | `115200` | Serial baudrate |
| `wheel_base` | `0.60` | Distance between wheels, meters |
| `max_wheel_speed_mm_s` | `1000.0` | Clamp per-wheel speed, mm/s |
| `send_rate_hz` | `20.0` | Periodic serial send rate |
| `cmd_timeout` | `0.5` | Send stop after this many seconds without `/cmd_vel` |
| `invert_left` | `false` | Flip left wheel sign |
| `invert_right` | `false` | Flip right wheel sign |
| `speed_scale` | `1.0` | Scale wheel speeds before invert and clamp |

## Test Checklist

- Forward key sends `CMD,<seq>,positive,positive`.
- Backward key sends `CMD,<seq>,negative,negative`.
- Rotate key sends opposite signs on left and right.
- Releasing keys or losing `/cmd_vel` for `cmd_timeout` sends `STOP,<seq>`.
- If one wheel direction is wrong, set `invert_left` or `invert_right`.
- If the robot is too slow, increase `speed_scale`, increase
  `max_wheel_speed_mm_s`, or increase the teleop speed.
- If the robot is roughly 2x too fast, the current firmware value
  `WHEEL_DIAMETER_MM = 100` may not match the real 190-200 mm wheel. For this
  phase, compensate with `speed_scale:=0.5`; do not change firmware here.
