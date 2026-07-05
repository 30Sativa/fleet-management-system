# robot_navigation

Localization (map_server + AMCL) và navigation trên **map đã lưu** cho AMR.
Package này bổ sung phase "chạy production" sau khi đã build map bằng
`robot_control`.

## Workflow tổng thể (3 bước)

```
BƯỚC 1 — BUILD MAP (chọn 1 trong 2 case, đều dùng slam_toolbox):

  Case A: map unknown, tự khám phá (kiểu robot hút bụi)
    ros2 launch robot_control auto_explore.launch.py          # robot thật
    ros2 launch robot_control sim_auto_explore.launch.py      # Gazebo

  Case B: điều khiển tay, quét build map
    ros2 launch robot_control manual_mapping.launch.py        # robot thật
    ros2 launch robot_control sim_manual.launch.py            # Gazebo

BƯỚC 2 — LƯU MAP (khi map trong RViz đã kín):
    ros2 run nav2_map_server map_saver_cli -f \
        ~/fleet-management-system/ros2_ws/src/robot_navigation/maps/my_map
    # tạo my_map.yaml + my_map.pgm, rồi rebuild để copy vào share:
    colcon build --packages-select robot_navigation

BƯỚC 3 — NAVIGATE trên map đã lưu (KHÔNG chạy SLAM nữa):
    ros2 launch robot_navigation navigation.launch.py \
        map:=/path/to/my_map.yaml                             # robot thật
    ros2 launch robot_navigation sim_navigation.launch.py \
        map:=/path/to/my_map.yaml                             # Gazebo
    # Gửi goal: RViz "Nav2 Goal" hoặc fleet_manager.
```

## Launch files

| File | Mục đích |
|---|---|
| `localization.launch.py` | map_server + AMCL + lifecycle manager (standalone hoặc được include) |
| `navigation.launch.py` | Robot thật: bringup + LiDAR + AMCL + Nav2 trên map đã lưu |
| `sim_navigation.launch.py` | Gazebo: mode_manager + relay + AMCL + Nav2 trên map đã lưu |

## Kiến trúc cmd_vel (giống auto_explore)

```
Nav2 -> /cmd_vel_nav -> mode_manager (explore) -> /cmd_vel -> base
teleop -> /cmd_vel_manual (ưu tiên override khi đang explore)
```

## Initial pose (AMCL)

- Mặc định `set_initial_pose: true` tại `(0, 0, 0)` — đúng nếu robot xuất phát
  tại chính chỗ bắt đầu build map (vd: dock sạc).
- Nếu xuất phát chỗ khác: dùng **"2D Pose Estimate"** trong RViz, hoặc publish
  `/initialpose`.
- AMCL publish TF `map -> odom`; nếu localization tốt, đám particle sẽ hội tụ
  quanh robot sau khi chạy vài mét.

## Tuning nhanh

- Odom trượt nhiều → tăng `alpha1..alpha4` trong `config/localization_params.yaml`.
- Bị "lost" giữa chừng → `recovery_alpha_slow: 0.001`, `recovery_alpha_fast: 0.1`
  đã bật recovery re-seeding; có thể tăng `max_particles`.
- LiDAR A3M1: `laser_max_range: 15.0` (spec 25 m trên bề mặt trắng, ~10 m vật
  tối) — khớp với costmap trong `robot_control/config/nav2_params.yaml`
  (raytrace 15 / obstacle 12). Đổi LiDAR thì sửa cả hai chỗ.
