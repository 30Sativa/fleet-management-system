# Phase 1 → miniPC deploy checklist

Camera đã chứng minh chạy đúng trên VMware (RGB+Depth+PointCloud+TF vào RViz2).
Việc còn lại là chạy trên miniPC — nơi RGB sẽ đạt tốc độ thật và ổn định.
Tài liệu này ghi lại chính xác những gì đã học được để miniPC không vấp lại.

## Trạng thái Phase 1 (đã đạt trên VM)

| Mục | VM (VMware) | miniPC (dự kiến) |
|---|---|---|
| USB 2 thiết bị (0403 + 0501) | PASS | PASS |
| 5 topic RGB/Depth/CameraInfo/points | PASS | PASS |
| Depth ~10-15 Hz | PASS | ~30 Hz |
| RGB | ~5 Hz, hay đơ (USB ảo) | ~30 Hz ổn định |
| RViz: RGB+Depth+cloud+TF | Hiện đủ | Hiện đủ |
| TF base_link → camera_*_optical_frame | PASS | PASS |

Kết luận: driver + workspace + launch ĐÚNG. Giới hạn RGB chỉ là do USB ảo
của VMware, sẽ tự hết trên phần cứng thật.

## Bài học đã gặp — đừng lặp lại trên miniPC

1. **KHÔNG build trên folder OneDrive / thư mục chia sẻ Windows.**
   Lỗi `failed to create symbolic link ... Is a directory` là do đó.
   → Trên miniPC clone repo vào ổ Linux thật: `~/fleet-management-system`, không phải folder mount.

2. **Driver cần `nlohmann-json3-dev`** (README gốc của vendor quên).
   → Đã bổ sung vào `setup_astra_pro.sh`, miniPC chạy script là có sẵn.

3. **OpenNI2 redist nằm sẵn trong repo driver** (`astra_camera/openni2_redist/x64`).
   Không cần tải `openNISDK_ROS2_*.tar.gz` riêng.

4. **VMware cần connect tay dòng RGB** mỗi lần cắm lại. miniPC cắm thẳng, không có bước này.

## Các bước trên miniPC

Giả định miniPC đã cài Ubuntu 22.04 + ROS 2 Humble.

```bash
# 1. Clone vào ổ Linux thật (KHÔNG dùng folder chia sẻ)
cd ~
git clone https://github.com/30Sativa/fleet-management-system.git
cd fleet-management-system

# 2. Cài đặt host (apt deps, libuvc, driver, udev, nlohmann-json)
bash ros2_ws/src/orbbec_bringup/scripts/setup_astra_pro.sh

# 3. Cắm camera, xác nhận đủ 2 thiết bị
lsusb -d 2bc5:
#   mong đợi: 2bc5:0403 (depth) + 2bc5:0501 (RGB)

# 4. Build
cd ros2_ws
colcon build --cmake-args -DCMAKE_BUILD_TYPE=Release
source install/setup.bash

# 5. Chạy (miniPC có GPU/desktop thì bỏ LIBGL_ALWAYS_SOFTWARE)
ros2 launch orbbec_bringup orbbec_with_mount.launch.py \
  x:=0.25 y:=0.0 z:=0.35 rviz:=true

# 6. Nghiệm thu — miniPC dùng ngưỡng gốc (RGB >= 10 Hz), KHÔNG cần MIN_COLOR_HZ
cd ~/fleet-management-system/ros2_ws
source install/setup.bash
bash src/orbbec_bringup/scripts/verify_astra_pro.sh
```

## Đo lại giá trị x/y/z thật của miniPC

`x:=0.25 y:=0.0 z:=0.35` chỉ là số tạm trên VM. Trên robot thật, đo khoảng cách
thật từ `base_link` (tâm robot) tới thân camera, đơn vị mét, ROS convention
(x tới trước, y sang trái, z lên trên), rồi truyền vào launch. TF sai → Nav2 sai.

## Tiêu chí đóng Phase 1 chính thức (trên miniPC)

- [ ] `verify_astra_pro.sh` ALL PASS với ngưỡng gốc (RGB ≥ 10 Hz)
- [ ] RGB KHÔNG đơ sau khi chạy liên tục 60 giây (chạy verify lần 2 sau 1 phút)
- [ ] RViz: point cloud đúng hướng, không lộn ngược
- [ ] Ghi lại Hz thực đo được (RGB / Depth / points) làm mốc cho Phase 2

## Phase 2 (không thuộc Phase 1)

Đóng gói Docker + device mapping trong docker-compose.yml → calibrate RGB
intrinsics → align depth↔color (`depth_image_proc`) → depth→laserscan cho Nav2.
