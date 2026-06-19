# Chạy thử mô phỏng & lái xe

Mục tiêu: spawn AMR vào Gazebo, lái bằng bàn phím, và **kiểm tra odometry đúng**
trước khi làm SLAM/Nav2. Giả định ROS 2 **Humble** + **Gazebo Classic**.

---

## 0. Cài dependency (1 lần)

```bash
sudo apt update
sudo apt install -y \
  ros-humble-gazebo-ros-pkgs \
  ros-humble-gazebo-ros2-control \
  ros-humble-ros2-control \
  ros-humble-ros2-controllers \
  ros-humble-diff-drive-controller \
  ros-humble-joint-state-broadcaster \
  ros-humble-xacro \
  ros-humble-teleop-twist-keyboard \
  ros-humble-robot-state-publisher \
  ros-humble-joint-state-publisher-gui \
  ros-humble-rviz2
```

## 1. Build package

```bash
cd ~/ros2_ws          # đổi cho đúng đường dẫn workspace của bạn
colcon build --packages-select robot_description
source install/setup.bash
```

> Mỗi lần mở terminal mới phải `source install/setup.bash` lại.

## 2. Xem hình trong RViz trước (nhanh, không cần Gazebo)

```bash
ros2 launch robot_description display.launch.py
```

Kéo thanh trượt trong cửa sổ joint_state_publisher_gui → 2 bánh chính phải quay.
Nếu hình đúng (khung + 2 bánh + 4 caster) thì sang bước 3.

## 3. Spawn vào Gazebo

```bash
ros2 launch robot_description gazebo.launch.py
```

Chờ Gazebo mở, robot rơi xuống và đứng yên trên 6 điểm (2 bánh + 4 caster).
Nếu robot lật/nảy/chìm sàn → xem mục Sự cố bên dưới.

## 4. Lái bằng bàn phím

Mở **terminal mới** (nhớ source lại):

```bash
source ~/ros2_ws/install/setup.bash
ros2 run teleop_twist_keyboard teleop_twist_keyboard \
  --ros-args -r /cmd_vel:=/diff_drive_controller/cmd_vel_unstamped
```

Dùng phím `i` (tiến), `,` (lùi), `j`/`l` (quay trái/phải). Robot trong Gazebo phải di chuyển theo.

---

## 5. CHECKLIST kiểm tra odometry (quan trọng nhất)

Chạy song song trong terminal khác (đã source):

```bash
# (a) Controller đã chạy chưa? Phải thấy 'active'
ros2 control list_controllers
#  -> diff_drive_controller   active
#  -> joint_state_broadcaster active

# (b) Có topic odom + cmd_vel không?
ros2 topic list | grep -E "odom|cmd_vel|scan|imu"

# (c) Xem odometry khi đang lái
ros2 topic echo /diff_drive_controller/odom --once

# (d) TF có đủ chuỗi odom -> base_footprint -> base_link không?
ros2 run tf2_tools view_frames
#  -> tạo file frames.pdf, mở xem cây TF
```

**Bài test odometry "đi thẳng 1 mét":**

1. Trong Gazebo, nhớ vị trí robot.
2. Lái tiến một đoạn rồi dừng.
3. So sánh: `ros2 topic echo /diff_drive_controller/odom --once` xem `pose.position.x`
   với khoảng cách robot thực sự đi trong Gazebo. Lệch nhiều (>10%) nghĩa là
   `wheel_radius` hoặc `wheel_separation` trong YAML chưa khớp thực tế.

**Bài test "quay tại chỗ 360°":**

1. Lái quay (phím `j` hoặc `l`) cho robot xoay đúng 1 vòng theo mắt.
2. Xem `orientation` trong odom có khớp ~360° không.
3. Lệch → chỉnh `wheel_separation` (0.60) trong `config/diff_drive_controller.yaml`.

---

## Sự cố thường gặp

| Triệu chứng | Nguyên nhân & cách xử lý |
|---|---|
| `controller_manager` không thấy / spawner lỗi | Thiếu `gazebo_ros2_control`. Cài lại apt ở bước 0. |
| Robot chìm xuống sàn / nảy tung | Inertia/khối lượng chưa hợp lý. Cân lại, sửa `*_mass` trong `common_properties.xacro`. |
| Robot không chạy khi lái | Sai remap topic. Kiểm tra `ros2 topic list`, lái đúng topic `/diff_drive_controller/cmd_vel_unstamped`. |
| Quay/đi sai khoảng cách | `wheel_separation` / `wheel_radius` trong YAML lệch URDF. Phải khớp: 0.60 và 0.10. |
| Xe trượt khi quay | Caster `mu` chưa = 0, hoặc bánh chính `mu` thấp. Xem `wheels.xacro`. |
| RViz báo `$(find robot_description)` not found | Chưa build/source, hoặc extension chưa reload. `colcon build` rồi mở lại. |

---

## Sau khi sim chạy ngon

Tiếp theo có thể làm: **SLAM** (slam_toolbox dựng bản đồ) → **Nav2** (điều hướng tự động).
Cả hai dùng lại đúng URDF + TF + odom này.
