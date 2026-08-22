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
    ros2 launch robot_navigation sim_navigation.launch.py    # Gazebo (map co san)
    # Gui goal: RViz "Nav2 Goal", hoac bus_manager (/go_to_stop).
    # RViz KHONG tu mo; them rviz:=true neu muon xem.

LUU Y robot that: KHONG co map mac dinh. Quen map:= se bao loi ro rang roi dung.
       Sim thi da co san maps/warehouse_12x12 (khop world Gazebo), khong can map:=.
```

## Launch files

| File | Mục đích |
|---|---|
| `localization.launch.py` | map_server + AMCL + lifecycle manager (standalone hoặc được include) |
| `navigation.launch.py` | Robot thật: bringup + LiDAR + AMCL + Nav2 trên map đã lưu |
| `sim_navigation.launch.py` | Gazebo: mode_manager + relay + AMCL + Nav2 trên map đã lưu |

Cờ chung: `rviz:=true` mở RViz (mặc định tắt); `camera_enable_color:=true` bật
RGB cho Phase 4 (mặc định tắt để tiết kiệm băng thông USB). `enable_camera` mặc
định true — Astra vào local costmap; `camera_x/y/z/roll/pitch/yaw` **phải** là bộ
số Phase 2 đã hiệu chỉnh.

## Kiến trúc cmd_vel (giống auto_explore)

```
controller_server ─┐
behavior_server   ─┴─► /cmd_vel_ctrl ─► velocity_smoother ─► /cmd_vel_nav
                                                                  │
teleop ─► /cmd_vel_manual (ưu tiên override khi explore) ─────────┤
                                                                  ▼
                                                         mode_manager ─► /cmd_vel ─► base
```

`/cmd_vel_ctrl` là tên nội bộ của Nav2 sau khi remap. **Đừng** remap
`cmd_vel_smoothed` về `/cmd_vel_nav` mà vẫn để `cmd_vel` trỏ vào đó — khi đó
`velocity_smoother` publish đúng lên topic nó đang subscribe (vòng lặp).

## Cảm biến vật cản (Phase 3)

```
RPLiDAR /scan              -> local costmap + global costmap
Astra   /camera/depth/points -> local costmap CHI (obstacle_layer)
```

`navigation.launch.py` bật camera mặc định (`enable_camera:=true`). Bộ số
`camera_x/y/z/roll/pitch/yaw` **phải** là kết quả hiệu chỉnh của Phase 2 —
xem `docs/phase2-perception.md` mục 3. Sai pitch là sàn biến thành tường.

Camera **không** vào global costmap: global không cuộn, mà camera chỉ xoá được
trong nón 58° của nó, nên vết đánh dấu sẽ đóng băng vĩnh viễn vào map.

Kiểm chứng camera có thực sự đóng góp: `ros2 run orbbec_bringup costmap_contrib`.
Chi tiết trong `docs/phase3-nav2.md`.

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
