# robot_description

Mô tả URDF/Xacro cho AMR differential-drive: **2 bánh chính có motor + 4 bánh phụ**, dùng trực tiếp 7 mesh STL từ CAD.

## Thông số (sửa trong `urdf/common_properties.xacro`)

| Thông số | Giá trị | Ghi chú |
|---|---|---|
| Thân xe (D×R×C) | 0.730 × 0.550 × 0.305 m | đo từ `chassis.stl` |
| Bánh chính | ĐK khoảng 0.1945 m, rộng 0.05 m | đo từ `left/right_drive_wheel.stl` |
| Khoảng cách 2 bánh | 0.4325 m | khoảng cách tâm-tâm trong CAD |
| Bánh phụ | khoảng 0.169 × 0.171 m, ở 4 vị trí | 4 mesh caster riêng |
| Khối lượng thân | 40 kg (**ƯỚC LƯỢNG — cân lại**) | `base_mass` |

> Các khối lượng đang là ước lượng. Cân robot thật rồi cập nhật `base_mass`, `wheel_mass`, `caster_mass` để sim sát thực tế.

## Cây frame (chuẩn Nav2)

```
base_footprint
└── base_link
    ├── left_wheel_link / right_wheel_link   (continuous, có motor)
    ├── 4× *_caster_link                     (fixed, bánh phụ)
    ├── lidar_link                           (giữa nóc xe, fixed)
    ├── sonar1_link                          (giữa mặt trước, nhìn +X)
    ├── sonar2_link                          (giữa mặt sau, nhìn -X)
    └── imu_link                             (fixed)
```

## File

- `urdf/robot.urdf.xacro` — file chính (top-level).
- `urdf/common_properties.xacro` — **tất cả số đo + macro inertia gom ở đây**.
- `meshes/*.stl` — 7 mesh đã đổi tên ASCII và đặt trong package.
- `urdf/wheels.xacro` — macro bánh chính + 4 bánh phụ dùng STL cho visual/collision.
- `urdf/sensors.xacro` — LiDAR 2D + IMU + hai SR04T. LiDAR ở giữa nóc xe;
  SONAR1 giữa mặt trước và SONAR2 giữa mặt sau. Đo lại vị trí thật trước
  khi dùng dữ liệu sonar cho tránh vật cản.
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

## Quy ước mesh CAD

STL dùng đơn vị mm và trục CAD `X=trái/phải, Y=cao, Z=trước/sau`. Xacro đổi sang ROS `X=trước, Y=trái, Z=cao` bằng `rpy="1.57079632679 0 1.57079632679"` và `scale="0.001 0.001 0.001"`. Các offset tâm mesh được lưu trong `robot.urdf.xacro` để giữ đúng vị trí từ CAD.

Bánh phụ hiện đang là `fixed` để giữ hình dạng và tiếp xúc trong mô phỏng; cơ cấu swivel/quay tự do chưa có đủ mesh và joint để suy ra chỉ từ 7 STL.

## Đã kiểm tra

- Xacro expand OK cả `use_sim:=true` và `false`; URDF sinh ra có 12 link, 11 joint và 14 mesh references.
- `wheel_separation` trong YAML (0.4325) và `wheel_radius` (0.09725) khớp Xacro.
