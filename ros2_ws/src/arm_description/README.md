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
