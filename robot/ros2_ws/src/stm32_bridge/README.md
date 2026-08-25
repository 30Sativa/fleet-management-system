# stm32_bridge

ROS2 Humble bridge for the real STM32 motor controller.

Flow:

```text
teleop_twist_keyboard / Nav2
        -> /cmd_vel
        -> stm32_bridge_node
        -> USB CDC Serial
        -> STM32
        -> HBS57H STEP/DIR
        -> motors

STM32
        -> FB feedback
        -> stm32_bridge_node
        -> /odom
        -> TF odom -> base_link
```

The laptop only sends wheel speed commands and computes odometry from STM32
feedback. The STM32 firmware keeps ownership of real-time STEP/DIR generation.

## STM32 Protocol

The current firmware parses these command formats:

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

The bridge sends `CMD,...` for normal non-zero motion and the firmware's
dedicated `STOP,<seq>` for zero Twist commands, watchdog timeout, idle before
the first `/cmd_vel`, feedback timeout safety, and shutdown. Speed units are
`mm/s`, not step/s.

The current firmware sends feedback in this format:

```text
FB,<seq>,<left_count>,<right_count>,<dt_ms>,<status>\r\n
With IMU and the two SR04T sensors enabled, the firmware appends these fields:

```text
FB,<seq>,<left_count>,<right_count>,<dt_ms>,<status>,<yaw_cdeg>,<yaw_valid>,<sonar1_mm>,<sonar1_valid>,<sonar2_mm>,<sonar2_valid>\r\n
```

`sonar*_valid=0` means no valid echo was received; the bridge publishes NaN for
that `sensor_msgs/msg/Range` sample. The schematic mapping is `SONAR1 PB0/PB1`
and `SONAR2 PB11/PB12`, with connector pin 2 as TRIG and pin 3 as ECHO.
```

Example:

```text
FB,42,1200,1195,20,OK
FB,43,1250,1243,20,OK
FB,44,1250,1243,20,STOP
```

Fields:

| Field | Meaning |
|---|---|
| `seq` | Last valid command sequence observed by the STM32 |
| `left_count` | Cumulative signed left step count |
| `right_count` | Cumulative signed right step count |
| `dt_ms` | Firmware feedback period in milliseconds |
| `status` | `OK`, `STOP`, `TIMEOUT`, or `ERR` |

The bridge also accepts the simpler fallback format
`FB,<left_count>,<right_count>,<dt_ms>,<status>` if firmware is changed later.

## Odometry

The node converts count deltas to differential-drive odometry:

```text
wheel_circumference = 2 * pi * wheel_radius
steps_per_meter = steps_per_rev * microstep * gear_ratio / wheel_circumference

left_distance = delta_left_count / steps_per_meter
right_distance = delta_right_count / steps_per_meter

delta_s = (right_distance + left_distance) / 2
delta_theta = (right_distance - left_distance) / wheel_base
```

It publishes:

| Topic | Type |
|---|---|
| `/odom` | `nav_msgs/msg/Odometry` |
| `/ultrasonic/sonar1/range` | `sensor_msgs/msg/Range` |
| `/ultrasonic/sonar2/range` | `sensor_msgs/msg/Range` |

It broadcasts:

```text
odom -> base_link
```

Default drivetrain values match the current firmware notes:

```text
wheel_radius = 0.095 m       # = 190 mm wheel diameter / 2
steps_per_rev = 200          # 57EBP98ALC, 1.8 deg/step
microstep = 8                # 200 * 8 = 1600 = HBS57H driver pulse/rev
gear_ratio = 10              # F57-L1-10-P2 planetary gearbox
steps_per_meter ~= 26805     # 1600 * 10 / (pi * 0.190)
```

These match the physical constants compiled into the firmware
(`firmware/.../motor_driver.h`: `DRIVER_PULSE_PER_REV=1600`, `GEAR_RATIO=10`,
`WHEEL_DIAMETER_MM=190`). If you change a DIP switch or the gearbox, update both
the firmware header and these parameters.

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

## Run Bridge

```bash
ros2 launch stm32_bridge stm32_bridge.launch.py
```

If the STM32 appears on a different port:

```bash
ros2 launch stm32_bridge stm32_bridge.launch.py port:=/dev/ttyACM1
```

Useful tuning examples:

```bash
ros2 launch stm32_bridge stm32_bridge.launch.py speed_scale:=0.2
ros2 launch stm32_bridge stm32_bridge.launch.py max_wheel_speed_mm_s:=150
ros2 launch stm32_bridge stm32_bridge.launch.py invert_left:=true
ros2 launch stm32_bridge stm32_bridge.launch.py publish_odom:=true publish_tf:=true
```

The launch defaults are intentionally bench-safe. `teleop_twist_keyboard`
usually sends `0.5 m/s` when pressing `i`; with `speed_scale=0.3` the bridge
sends about `150 mm/s` to both wheels. The `1600` value in firmware is the HBS57H
driver resolution in pulses per motor revolution, not a wheel speed.

## Run Teleop

In another terminal:

```bash
source ~/ros2_ws/install/setup.bash
ros2 run teleop_twist_keyboard teleop_twist_keyboard
```

## Check Odometry

```bash
ros2 topic echo /odom
```

You should see pose and twist changing while the robot moves and STM32 feedback
arrives.

## Check TF

```bash
ros2 run tf2_ros tf2_echo odom base_link
```

Or generate a frame graph:

```bash
ros2 run tf2_tools view_frames
```

## Parameters

| Parameter | Default | Meaning |
|---|---:|---|
| `port` | `/dev/ttyACM0` | STM32 USB CDC serial port |
| `baudrate` | `115200` | Serial baudrate |
| `wheel_base` | `0.46` | Distance between wheels, meters (center-to-center) |
| `wheel_radius` | `0.095` | Wheel radius, meters |
| `steps_per_rev` | `200.0` | Motor full steps per revolution |
| `microstep` | `8.0` | HBS57H microstep multiplier |
| `gear_ratio` | `10.0` | Motor-to-wheel gear ratio |
| `max_steps_per_sec` | `12000.0` | Expected max step rate for jump warnings |
| `max_wheel_speed_mm_s` | `250.0` | Clamp per-wheel command, mm/s |
| `send_rate_hz` | `20.0` | Periodic serial send/read rate |
| `cmd_timeout` | `0.5` | Send STOP after this many seconds without `/cmd_vel` |
| `invert_left` | `false` | Flip left **command** sign only (does not affect odometry) |
| `invert_right` | `false` | Flip right **command** sign only (does not affect odometry) |
| `odom_invert_left` | `false` | Flip left feedback count sign for **odometry only** |
| `odom_invert_right` | `false` | Flip right feedback count sign for **odometry only** |
| `speed_scale` | `0.3` | Scale wheel commands before invert and clamp |
| `publish_odom` | `true` | Publish `/odom` |
| `publish_tf` | `true` | Broadcast `odom -> base_link` |
| `odom_frame` | `odom` | Odometry parent frame |
| `base_frame` | `base_link` | Robot base child frame |
| `feedback_timeout` | `1.0` | Warn after missing feedback for this many seconds |
| `feedback_counts_are_cumulative` | `true` | Treat feedback counts as cumulative |
| `feedback_rate_warn_hz` | `2.0` | Max warning rate for feedback issues |
| `reset_odom_on_start` | `true` | Use first cumulative sample as zero baseline |
| `odom_covariance_diagonal` | `[0.01, 0.01, 99999.0, 99999.0, 99999.0, 0.1]` | Pose covariance diagonal |
| `twist_covariance_diagonal` | `[0.01, 99999.0, 99999.0, 99999.0, 99999.0, 0.1]` | Twist covariance diagonal |

## If `/odom` Does Not Change

1. Confirm the STM32 is sending lines like `FB,42,1200,1195,20,OK`.
2. Use a serial monitor or `tools/motor_serial_debug.ps1` from this repo to
   inspect raw feedback.
3. Check that `feedback_counts_are_cumulative` matches the firmware.
4. Check drivetrain parameters: `wheel_radius`, `steps_per_rev`, `microstep`,
   and `gear_ratio`.
5. If the pose runs in the wrong direction (e.g. driving forward decreases `x`),
   the **count** sign is reversed. Fix odometry only with
   `odom_invert_left:=true` / `odom_invert_right:=true`. Do **not** use
   `invert_left/right` for this — those flip the motor command, not odometry.

## Test Checklist

- Forward key sends `CMD,<seq>,positive,positive`.
- Backward key sends `CMD,<seq>,negative,negative`.
- Rotate key sends opposite signs on left and right.
- If forward motion moves one wheel only, test each driver path with
  `tools/motor_test_one_wheel.ps1` and compare the left/right counts in `FB`.
- Releasing keys or losing `/cmd_vel` for `cmd_timeout` sends `STOP,<seq>`.
- Incoming `FB,...` lines update `/odom`.
- `tf2_echo odom base_link` shows a live transform.
- Serial disconnect/reconnect does not crash the node.
- If one wheel spins the wrong way, set `invert_left`/`invert_right` (command).
  If the pose integrates the wrong way, set `odom_invert_left`/`odom_invert_right`
  (odometry). These are independent.
- If the robot is too slow after bench testing, increase `speed_scale`, increase
  `max_wheel_speed_mm_s`, or increase the teleop speed.

## Assumptions and Limitations

Read these before trusting `/odom` on the real robot.

- **Open-loop step odometry, not a real encoder.** The firmware count increments
  once per STEP pulse it generates (`count += direction`), not per measured wheel
  rotation. If a wheel slips or the motor stalls, the count still rises and the
  pose drifts. Odometry is only as good as the steps actually translating into
  motion. A real quadrature encoder or IMU fusion is a Stage 4 task.

- **`dt_ms` is "time since last successfully-sent feedback", not a fixed period.**
  In firmware, `dt_ms = now - last_feedback_sent_ms`. If a USB CDC frame is
  dropped, the next delivered frame reports a larger `dt_ms` that still matches
  the true gap the bridge observed, so `velocity = delta_s / dt` stays correct.
  The downside: if the firmware is ever changed to emit a *fixed* period while
  packets are still being dropped, the reported velocity would become wrong. The
  bridge already falls back to ROS-clock dt when `dt_ms <= 0`.

- **Command invert vs. odometry invert are separate.** `invert_left/right` flip
  only the motor command. Because the firmware derives its step direction from the
  (already inverted) command, the feedback count direction already follows the
  physical wheel, so the bridge does **not** reuse the command invert for
  odometry. Use `odom_invert_left/right` only if the count sign is genuinely
  reversed relative to physical forward motion.

- **`reset_odom_on_start` zeroes the count baseline, not the pose.** Pose
  (`x/y/theta`) always starts at 0 on node startup; the first cumulative feedback
  sample is consumed as the baseline so the initial jump is not integrated.
