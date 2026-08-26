# robot_description

Mô tả URDF/Xacro cho AMR differential-drive: **2 bánh chính có motor + 4 bánh phụ**, dùng trực tiếp 35 mesh STL từ CAD.

## Thông số (sửa trong `urdf/common_properties.xacro`)

| Thông số | Giá trị | Ghi chú |
|---|---|---|
| Thân xe (D×R×C) | 0.8054 × 0.5662 × 0.4160 m | bao ngoài 28 body mesh, không tính LiDAR |
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
    ├── sonar1_link                          (góc trước-trái, nhìn chéo +45°)
    ├── sonar2_link                          (góc trước-phải, nhìn chéo -45°)
    ├── sonar3_link                          (góc sau-trái, nhìn chéo 135°)
    ├── sonar4_link                          (góc sau-phải, nhìn chéo -135°)
    └── imu_link                             (fixed)
```

## File

- `urdf/robot.urdf.xacro` — file chính (top-level).
- `urdf/common_properties.xacro` — **tất cả số đo + macro inertia gom ở đây**.
- `meshes/*.stl` — 35 mesh đã đổi tên ASCII và đặt trong package; 28 body mesh
  giữ nguyên tọa độ assembly, LiDAR, 2 bánh chính và 4 caster có link riêng.
- `urdf/wheels.xacro` — macro bánh chính + 4 bánh phụ dùng STL cho visual và
  primitive đơn giản cho collision.
- `urdf/sensors.xacro` — LiDAR 2D + IMU + bốn SR04T. LiDAR ở giữa nóc xe;
  4 sonar đặt ở 4 góc vuông của khung xe (SONAR1 trước-trái, SONAR2
  trước-phải, SONAR3 sau-trái, SONAR4 sau-phải), mỗi con nhìn chéo ra góc.
  Đo lại vị trí thật trước khi dùng dữ liệu sonar cho tránh vật cản.
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

STL dùng đơn vị mm và trục CAD `X=trái/phải, Y=cao, Z=trước/sau`. Xacro đổi sang ROS `X=trước, Y=trái, Z=cao` bằng `rpy="1.57079632679 0 1.57079632679"` và `scale="0.001 0.001 0.001"`. Các body mesh giữ chung tọa độ assembly và dùng `body_mesh_origin`; offset tâm của từng bánh được lưu trong `robot.urdf.xacro`.

Bánh phụ hiện đang là `fixed` để giữ hình dạng và tiếp xúc trong mô phỏng; bộ CAD chưa mô tả các trục swivel/quay tự do để tách thành joint chính xác.

## Đã kiểm tra

- Xacro expand OK cả `use_sim:=true` và `false`; URDF sinh ra có 12 link, 11 joint và 35 mesh references.
- `wheel_separation` trong YAML (0.4325) và `wheel_radius` (0.09725) khớp Xacro.
