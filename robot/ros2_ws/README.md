# ROS 2 workspace

Đây là workspace ROS 2 của robot xe tự hành. Mã nguồn nằm trong `src/`; mỗi thư mục có `package.xml` là một ROS 2 package độc lập.

## Cấu trúc

```text
ros2_ws/
├── src/
│   ├── bus_interfaces/     # Message/action dùng chung
│   ├── bus_manager/        # Điều hướng tới trạm bus
│   ├── robot_control/      # Mode, mapping và exploration
│   ├── robot_description/  # URDF/Xacro, STL, sensor, ros2_control
│   ├── robot_navigation/   # Localization và Nav2
│   ├── simulation/         # World/model cho Gazebo
│   ├── stm32_bridge/       # Cầu nối /cmd_vel với STM32
│   └── bus_bringup/        # Chỗ dành cho launch tổng hợp; hiện chưa có package
├── build/                  # Sinh bởi colcon
├── install/                # Sinh bởi colcon
└── log/                    # Log của colcon/ROS 2
```

`build/`, `install/` và `log/` chỉ xuất hiện sau khi build/chạy workspace. Không sửa hoặc commit thủ công các thư mục này.

## Chức năng từng package

| Package | Chức năng |
|---|---|
| `bus_interfaces` | Định nghĩa `BusStatus.msg` và action `GoToStop.action`; không chạy node riêng. |
| `bus_manager` | Điều phối xe tới trạm bus, dùng `config/bus_stops.yaml` và action `GoToStop`. |
| `robot_control` | Launch cho robot thật/Gazebo, mode manager, manual mapping và frontier exploration. |
| `robot_description` | Mô tả hình học/frame của xe, 7 STL, LiDAR, IMU và `ros2_control`. |
| `robot_navigation` | Map server, AMCL và Nav2 trên map đã lưu. |
| `simulation` | World Gazebo; hiện có `warehouse_12x12.world`. |
| `stm32_bridge` | Đổi `/cmd_vel` thành lệnh serial gửi STM32, đọc feedback và publish `/odom`. |
| `bus_bringup` | Hiện chỉ có `launch/.gitkeep`; chưa phải package và chưa có chức năng runtime. |

Phần arm trước đây (`arm_bridge`, `arm_description`) đã được bỏ khỏi workspace.

## Các file quan trọng

### `robot_description`

- `urdf/robot.urdf.xacro`: file mô tả robot chính, source of truth.
- `urdf/common_properties.xacro`: kích thước, vị trí và khối lượng.
- `urdf/wheels.xacro`: hai bánh chủ động và bốn bánh phụ.
- `urdf/sensors.xacro`: LiDAR và IMU.
- `urdf/ros2_control.xacro`: interface cho Gazebo hoặc hardware thật.
- `meshes/*.stl`: chassis, hai bánh chính và bốn bánh phụ.
- `launch/display.launch.py`: xem robot trong RViz.
- `launch/gazebo.launch.py`: spawn robot vào Gazebo và nạp controller.

### `robot_control`

- `manual_mode.launch.py`: điều khiển robot thật.
- `manual_mapping.launch.py`: điều khiển tay và chạy SLAM build map.
- `auto_explore.launch.py`: robot thật tự khám phá.
- `sim_manual.launch.py`, `sim_auto_explore.launch.py`: các bản chạy Gazebo.
- `mode_manager_node.py`: điều phối mode và nguồn `/cmd_vel`.

### `robot_navigation`

- `localization.launch.py`: map server + AMCL.
- `navigation.launch.py`: Nav2 cho robot thật.
- `sim_navigation.launch.py`: Nav2 cho Gazebo.
- `config/localization_params.yaml`: tham số AMCL/localization.

### `stm32_bridge`

- `stm32_bridge_node.py`: serial bridge và odometry.
- `launch/stm32_bridge.launch.py`: launch node với cổng serial và thông số bánh.
- `test/test_odometry.py`: test odometry.

### `bus_manager` và `bus_interfaces`

- `bus_manager/stop_navigator_node.py`: điều hướng theo trạm.
- `bus_manager/config/bus_stops.yaml`: danh sách trạm.
- `bus_interfaces/msg/BusStatus.msg`: trạng thái bus.
- `bus_interfaces/action/GoToStop.action`: yêu cầu đi tới trạm.

## Build workspace

```bash
cd ~/fleet-management-system/robot/ros2_ws
source /opt/ros/humble/setup.bash
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install
source install/setup.bash
```

Build riêng một package:

```bash
colcon build --packages-select robot_description
colcon build --packages-select stm32_bridge
```

## Các luồng chạy chính

### Xem model robot

```bash
ros2 launch robot_description display.launch.py
```

Source chính là `robot_description/urdf/robot.urdf.xacro`. Có thể dùng `robot_expanded_sim.urdf` để preview bằng extension VS Code.

### Chạy mô phỏng Gazebo

```bash
ros2 launch robot_description gazebo.launch.py
```

### Build map

Robot thật:

```bash
ros2 launch robot_control manual_mapping.launch.py port:=/dev/ttyACM0 lidar_serial_port:=/dev/ttyUSB0
```

Gazebo:

```bash
ros2 launch robot_control sim_manual.launch.py
```

Lưu map:

```bash
ros2 run nav2_map_server map_saver_cli -f src/robot_navigation/maps/my_map
```

### Navigation trên map đã lưu

```bash
ros2 launch robot_navigation navigation.launch.py map:=/path/to/my_map.yaml
```

Trong Gazebo dùng `ros2 launch robot_navigation sim_navigation.launch.py` với cùng tham số `map`.

### Robot thật qua STM32

```bash
ros2 launch stm32_bridge stm32_bridge.launch.py port:=/dev/ttyACM0 baudrate:=115200
```

Luồng drivetrain:

```text
/cmd_vel -> stm32_bridge -> USB CDC -> STM32 -> motor controller
STM32 feedback -> stm32_bridge -> /odom -> TF odom -> base_link
```

## Thứ tự đọc code cho người mới

1. Đọc README này để nắm package và luồng tổng thể.
2. Đọc `src/robot_description/README.md` để hiểu frame, STL và thông số xe.
3. Đọc `src/robot_control/README.md` để hiểu mapping/exploration.
4. Đọc `src/robot_navigation/README.md` để hiểu localization/Nav2.
5. Đọc `src/stm32_bridge/README.md` trước khi kết nối STM32 thật.

## Quy tắc thay đổi

- Sửa kích thước robot trong `robot_description/urdf/common_properties.xacro`.
- Khi đổi bán kính hoặc khoảng cách bánh, sửa đồng thời `config/diff_drive_controller.yaml`.
- Khi đổi thông số drivetrain thật, kiểm tra cả bridge và firmware STM32.
- Không commit `build/`, `install/`, `log/`, `__pycache__/` hoặc file sinh bởi Gazebo/VS Code extension.
