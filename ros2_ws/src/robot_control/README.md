# robot_control

Mode manager, launch files, and a small frontier explorer for the AMR real
robot flow.

## Command Architecture

```text
Manual:
teleop/joystick -> /cmd_vel_manual -> mode_manager -> /cmd_vel -> stm32_bridge

Auto explore:
simple_frontier_explorer -> Nav2 -> /cmd_vel_nav -> mode_manager -> /cmd_vel
  -> stm32_bridge
```

Only `mode_manager_node` should publish the final `/cmd_vel`. The STM32 bridge
subscribes only to `/cmd_vel`.

## Main Topics

| Topic | Type | Role |
|---|---|---|
| `/cmd_vel_manual` | `geometry_msgs/msg/Twist` | Manual keyboard/joystick input |
| `/cmd_vel_nav` | `geometry_msgs/msg/Twist` | Nav2 velocity output |
| `/cmd_vel` | `geometry_msgs/msg/Twist` | Final selected velocity for STM32 |
| `/robot_mode` | `std_msgs/msg/String` | Command mode: `manual` or `explore` |
| `/robot_mode_state` | `std_msgs/msg/String` | Current mode state |
| `/emergency_stop` | `std_srvs/srv/SetBool` | `true` engages, `false` releases |
| `/emergency_stop_state` | `std_msgs/msg/Bool` | Emergency stop state |
| `/scan` | `sensor_msgs/msg/LaserScan` | RPLiDAR scan |
| `/odom` | `nav_msgs/msg/Odometry` | STM32 step-count odometry |
| `/map` | `nav_msgs/msg/OccupancyGrid` | SLAM map |

## TF Frames

Expected real-robot tree:

```text
map -> odom -> base_footprint -> base_link -> lidar_link
```

The launch files run `robot_state_publisher` from `robot_description`. They pass
`base_frame:=base_footprint` into `stm32_bridge` so the bridge publishes
`odom -> base_footprint` and the URDF publishes fixed robot frames below it.

The RPLiDAR launch default uses `frame_id=lidar_link` to match the current URDF.
If your hardware driver is already publishing `laser`, either set
`lidar_frame:=laser` or update the URDF/static transform consistently.

## Build

```bash
cd ~/ros2_ws
rosdep install --from-paths src --ignore-src -r -y
colcon build --packages-select robot_control stm32_bridge robot_description
source install/setup.bash
```

## Manual Mode

```bash
ros2 launch robot_control manual_mode.launch.py \
  port:=/dev/ttyACM0 \
  baudrate:=115200
```

`teleop_twist_keyboard` is remapped to `/cmd_vel_manual`. For joystick control,
launch your joystick stack separately and remap its output to `/cmd_vel_manual`.

## Manual Mapping

Use this first to build a map by driving manually.

```bash
ros2 launch robot_control manual_mapping.launch.py \
  port:=/dev/ttyACM0 \
  lidar_serial_port:=/dev/ttyUSB0
```

This launches:

- `stm32_bridge`
- `mode_manager_node`
- `teleop_twist_keyboard`
- `rplidar_ros`
- `slam_toolbox` online async
- `robot_state_publisher`

Save the map after a good mapping run:

```bash
ros2 run nav2_map_server map_saver_cli -f ~/maps/amr_map
```

## Auto Explore

```bash
ros2 launch robot_control auto_explore.launch.py \
  port:=/dev/ttyACM0 \
  lidar_serial_port:=/dev/ttyUSB0
```

This launches SLAM, Nav2 navigation-while-mapping, and
`simple_frontier_explorer`. Nav2 is remapped so its velocity output goes to
`/cmd_vel_nav`; only `mode_manager_node` publishes final `/cmd_vel`.

Optional manual override inside auto explore:

```bash
ros2 launch robot_control auto_explore.launch.py enable_teleop:=true
```

Manual input has priority over Nav2 while it is fresh. When manual input times
out, explore mode returns control to Nav2.

## Change Mode

Switch to manual:

```bash
ros2 topic pub --once /robot_mode std_msgs/msg/String "{data: manual}"
```

Switch to explore:

```bash
ros2 topic pub --once /robot_mode std_msgs/msg/String "{data: explore}"
```

When switching from explore to manual, `mode_manager_node` publishes zero
velocity and requests cancellation of the active Nav2 `NavigateToPose` goal.

## Emergency Stop

Engage:

```bash
ros2 service call /emergency_stop std_srvs/srv/SetBool "{data: true}"
```

Release:

```bash
ros2 service call /emergency_stop std_srvs/srv/SetBool "{data: false}"
```

While emergency stop is engaged, `mode_manager_node` forces `/cmd_vel` to zero
and blocks manual/Nav2 commands. The STM32 bridge converts zero Twist to the
firmware `STOP,<seq>` command.

## Test Order

1. Manual motor test:
   `ros2 launch robot_control manual_mode.launch.py`
2. Confirm LiDAR:
   `ros2 topic echo /scan --once`
3. Manual mapping:
   `ros2 launch robot_control manual_mapping.launch.py`
4. Nav2 click-goal in RViz:
   run auto launch with `enable_explorer:=false`, then send a Nav2 goal.
5. Auto explore:
   `ros2 launch robot_control auto_explore.launch.py`

## Important Tuning TODOs

- `config/nav2_params.yaml`: `robot_radius=0.47` and `inflation_radius=0.60` are
  set from the real footprint (74x55 cm -> half-diagonal ~0.461 m). `max_vel_x`
  and `max_vel_theta` are still conservative bench defaults; tune on the robot.
- `wheel_base=0.46` m (center-to-center: 55 cm frame width, wheels inset ~2 cm
  with ~5 cm tread => centers 4.5 cm in from each edge => 46 cm). Re-measure if
  the axle spacing changes; it directly affects turn rate and odometry heading.
- `stm32_bridge` real wheel odometry uses `wheel_radius=0.095` from firmware
  notes: 190 mm wheel diameter. The current URDF sim still uses 0.10 m; measure
  the real wheel and align both if needed.
- STM32 feedback counts are generated STEP pulses, not physical encoder ticks.
  Odometry will drift if wheels slip or motors stall.

## Troubleshooting

Robot does not move:

- Check `/emergency_stop_state` is `false`.
- Check exactly one final publisher on `/cmd_vel`: `mode_manager_node`.
- Check `stm32_bridge` opened the serial port and is receiving `/cmd_vel`.
- Check firmware receives `CMD` or `STOP` with `tools/motor_serial_debug.ps1`.

Map is distorted:

- Verify `/odom` changes in the correct direction.
- Tune `wheel_radius`, `wheel_base`, `odom_invert_left`, and
  `odom_invert_right`.
- Confirm `/scan` frame matches a valid TF under `base_footprint`.

Nav2 does not accept goals:

- Confirm TF exists: `map -> odom -> base_footprint -> base_link -> lidar_link`.
- Confirm `/map`, `/odom`, and `/scan` are publishing.
- Run with `enable_explorer:=false` and test an RViz click goal first.

TF missing:

- Check `robot_state_publisher` is running.
- Check `stm32_bridge` was launched with `base_frame:=base_footprint`.
- Check RPLiDAR `frame_id` matches `lidar_link` or your chosen frame.

Multiple `/cmd_vel` publishers:

- Teleop must publish `/cmd_vel_manual`.
- Nav2 must publish `/cmd_vel_nav`.
- Only `mode_manager_node` should publish `/cmd_vel`.

Serial STM32 not connected:

- In Linux/VM: `ls /dev/ttyACM* /dev/ttyUSB*`.
- Pass the actual port with `port:=...`.
- Add the user to `dialout`, log out, and log back in.
