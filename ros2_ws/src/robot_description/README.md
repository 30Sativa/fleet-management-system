# robot_description

Mô tả URDF/Xacro cho AMR differential-drive: **2 bánh chính có motor + 4 caster bi cầu tự do**.

## Thông số (sửa trong `urdf/common_properties.xacro`)

| Thông số | Giá trị | Ghi chú |
|---|---|---|
| Thân xe (D×R×C) | 0.74 × 0.55 × 0.34 m | `base_length/width/height` |
| Bánh chính | ĐK 0.20 m (R=0.10), rộng 0.05 m | `wheel_radius`, `wheel_width` |
| Khoảng cách 2 bánh | 0.60 m | `wheel_separation` = R thân + rộng bánh |
| Caster | bi cầu R=0.05 m, ở 4 góc | `caster_radius` |
| Khối lượng thân | 40 kg (**ƯỚC LƯỢNG — cân lại**) | `base_mass` |

> Các khối lượng đang là ước lượng. Cân robot thật rồi cập nhật `base_mass`, `wheel_mass`, `caster_mass` để sim sát thực tế.

## Cây frame (chuẩn Nav2)

```
base_footprint
└── base_link
    ├── left_wheel_link / right_wheel_link   (continuous, có motor)
    ├── 4× *_caster_link                     (fixed, bi cầu tự do)
    ├── lidar_link                           (fixed)
    └── imu_link                             (fixed)
```

## File

- `urdf/robot.urdf.xacro` — file chính (top-level).
- `urdf/common_properties.xacro` — **tất cả số đo + macro inertia gom ở đây** (gồm `profile_size` = cỡ thanh nhôm).
- `urdf/chassis_frame.xacro` — macro vẽ **khung nhôm định hình hở** (visual). Đổi `profile_size` để khớp thanh thật (2020=0.02, 4040=0.04).
- `urdf/wheels.xacro` — macro bánh chính + caster.
- `urdf/sensors.xacro` — LiDAR 2D + IMU (vị trí ước lượng, chỉnh theo thực tế).
- `urdf/ros2_control.xacro` — hardware interface (sim ⇄ hardware thật qua `use_sim`).
- `config/diff_drive_controller.yaml` — controller (wheel_separation/radius **phải khớp** URDF).
- `urdf/robot_expanded_sim.urdf` / `robot_expanded_hw.urdf` — URDF đã expand sẵn để tham khảo.

## Build

```bash
cd ~/ros2_ws
colcon build --packages-select robot_description
source install/setup.bash
```

## Xem trong RViz (không cần Gazebo)

```bash
ros2 launch robot_description display.launch.py
```

## Mô phỏng Gazebo + ros2_control

```bash
ros2 launch robot_description gazebo.launch.py
# lái thử:
ros2 run teleop_twist_keyboard teleop_twist_keyboard \
  --ros-args -r /cmd_vel:=/diff_drive_controller/cmd_vel_unstamped
```

## Xuất URDF thủ công

```bash
# bản sim
xacro urdf/robot.urdf.xacro use_sim:=true  > robot.urdf
# bản hardware thật
xacro urdf/robot.urdf.xacro use_sim:=false > robot_hw.urdf
check_urdf robot.urdf
```

## Chuyển sang hardware thật

Trong `urdf/ros2_control.xacro`, nhánh `use_sim=false` đang để mẫu plugin
`diffdrive_arduino`. Đổi `<plugin>` + các `<param>` (cổng serial, baud, số xung
encoder/vòng…) cho đúng driver/board của bạn. Chạy với `use_sim:=false`.

## Đã kiểm tra

- Xacro expand OK cả `use_sim:=true` và `false`.
- Cây TF hợp lệ: 1 root (`base_footprint`), 10 link, 9 joint, không link nào 2 cha.
- Hình học chạm đất: trục bánh chính z=0.10 (=bán kính), tâm caster z=0.05 (=bán kính bi) → cả 6 điểm tiếp đất đồng phẳng tại z=0.
- `wheel_separation` trong YAML (0.60) khớp URDF.
