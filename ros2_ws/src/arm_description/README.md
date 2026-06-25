# arm_description

URDF/xacro mô tả tay robot SCARA, **độc lập với `robot_description` của xe**.

Mục đích: xem cánh tay trong RViz để test riêng, **chưa gắn lên xe**. Không sửa
file URDF nào của xe, nên mô phỏng xe đang chạy không bị ảnh hưởng.

## Files

| File | Vai trò |
|---|---|
| `urdf/arm.xacro` | Macro `scara_arm` — định nghĩa J1/J2/Z/gripper. Tái dùng được. |
| `urdf/arm_standalone.urdf.xacro` | Top-level để xem RIÊNG (gắn tay vào `arm_world`). |
| `launch/display_arm.launch.py` | Mở RViz + joint_state_publisher_gui. |
| `rviz/arm.rviz` | Cấu hình RViz (fixed frame = `arm_world`). |

## Xem tay trong RViz

```bash
cd ~/ros2_ws
colcon build --packages-select arm_description
source install/setup.bash
ros2 launch arm_description display_arm.launch.py
```

Kéo các thanh trượt trong cửa sổ joint_state_publisher_gui để thấy J1 (vai),
J2 (khuỷu), J_z (nâng/hạ), chuyển động.

## Sau này gắn lên xe (KHÔNG viết lại)

Vì tay là 1 macro, khi muốn gắn lên xe chỉ cần — trong
`robot_description/urdf/robot.urdf.xacro` của xe — thêm:

```xml
<xacro:include filename="$(find arm_description)/urdf/arm.xacro"/>
<xacro:scara_arm parent="base_link" xyz="0 0 ${base_height/2}" rpy="0 0 0"/>
```

Là tay gắn vào `base_link` xe. Không phải dựng lại tay.

> Đây là việc của giai đoạn "gắn lên xe", làm sau. Hiện tại để tách riêng cho
> an toàn.

## Lưu ý

Các kích thước trong `arm.xacro` (chiều dài cánh tay, hành trình Z, ...) là
**ước lượng**. Đo lại tay thật rồi sửa các `xacro:property` ở đầu file cho khớp.
Đây chỉ là mô hình hình học để xem/định vị, chưa phải số đo chính xác.

## Gazebo (sim vat ly) — tach biet voi xe

Mo phong tay co trong luc, va cham, kep duoc vat. KHONG dinh gi toi xe.

Files them cho Gazebo (deu trong package nay):

| File | Vai tro |
|---|---|
| `urdf/arm_ros2_control.xacro` | ros2_control + Gazebo plugin cho tay |
| `urdf/arm_sim.urdf.xacro` | top-level cho Gazebo (tay tren `arm_world`) |
| `config/arm_controllers.yaml` | controller 5 khop (JointTrajectoryController) |
| `worlds/arm_demo.world` | the gioi co 1 lon do de tay tap kep |
| `launch/gazebo_arm.launch.py` | spawn tay + nap controller |

Chay:

```bash
cd ~/ros2_ws
colcon build --packages-select arm_description
source install/setup.bash
ros2 launch arm_description gazebo_arm.launch.py
```

Dieu khien tay (dua 5 khop toi 1 tu the: J_z, J1, J2, J_wrist, J_grip):

```bash
ros2 topic pub --once /arm_controller/joint_trajectory trajectory_msgs/msg/JointTrajectory "{
  joint_names: [J_z, J1, J2, J_wrist, J_grip],
  points: [ { positions: [-0.1, 0.5, -0.8, 0.0, 0.05], time_from_start: { sec: 2 } } ]
}"
```

- `J_grip = 0.0` -> khep (kep) ; `J_grip = 0.05` -> mo.
- Doi positions de tay vuon toi lon do va kep thu.

> Luu y: kep vat trong Gazebo Classic hay bi truot (gripper 2 ngam don gian).
> Neu can kep chac de demo, them plugin `gazebo_grasp_fix` hoac tang ma sat
> (da set mu1/mu2 = 1.5 cho ngam). Day la van de chung cua sim, khong phai loi
> cau hinh.

## Demo gap theo kich ban co dinh (pick_demo)

Robot arm KHONG tu nhan dien roi gap. Phai ra lenh cho no. `pick_demo` la
chuoi dong tac DAT SAN (lon o vi tri biet truoc): home -> vuon -> ha Z ->
kep -> nang -> xoay -> tha -> home. Khong can camera/AI.

Chay (sau khi da `ros2 launch arm_description gazebo_arm.launch.py`):

```bash
# terminal khac
source ~/ros2_ws/install/setup.bash
ros2 run arm_description pick_demo
```

Tinh chinh: cac tu the (goc khop) trong `scripts/pick_demo.py` (bien POSES)
la SO UOC LUONG. Xem Gazebo roi sua cho gripper toi dung lon. Moi tu the la
[J_z, J1, J2, J_wrist, J_grip], J_grip=0 khep / 0.05 mo.

> Day la tang 1 (dieu khien khop) + kich ban co dinh. Muon "tu nhan dien va
> gap" can them: dong hoc nghich (MoveIt), camera + nhan dien vat, va pipeline
> pick. Do la cac buoc nang cao lam sau.
