# Phase 1 — Camera (Orbbec Astra Pro)

> Tài liệu này là bản chạy thực tế cho Phase 1. Chi tiết kỹ thuật của package
> nằm ở `ros2_ws/src/orbbec_bringup/README.md`.

## 0. Đánh giá sơ đồ Phase 1 ban đầu

Sơ đồ gốc:

```
Astra Pro → RGB / Depth / CameraInfo / TF → RViz2
```

Hướng đi đúng, nhưng thiếu 5 điểm khiến Phase 1 dễ "chạy được rồi lại chết":

**1. Astra Pro không phải một camera — nó là hai thiết bị USB.**
Depth/IR đi qua OpenNI2 (`2bc5:0403`), RGB là webcam UVC thường
(`2bc5:0501`, bản FHD là `0502`). Sơ đồ vẽ RGB và Depth song song từ một khối
là sai bản chất: chúng đi hai đường driver khác nhau, hỏng độc lập với nhau,
và RGB thường là cái chết trước.

**2. "CameraInfo" trong sơ đồ đang gộp hai thứ rất khác nhau.**
`depth/camera_info` là intrinsics thật từ firmware. `color/camera_info` chỉ là
giá trị factory mặc định — chưa calibrate thì nó *có* nhưng *sai*. Nếu Phase 1
tick "CameraInfo ✅" mà không phân biệt, Phase 2 (align depth↔color, Nav2) sẽ
lệch và rất khó truy nguyên.

**3. Thiếu điều kiện "không có D2C phần cứng".**
Astra Pro không có hardware depth-to-color registration, vì OpenNI2 không nhìn
thấy sensor màu. `depth_registration:=true` và `enable_colored_point_cloud`
sẽ không hoạt động. Point cloud có màu là việc của Phase 2 (calibrate 2 camera
+ `depth_image_proc::RegisterNode`), không phải Phase 1.

**4. Thiếu tiêu chí nghiệm thu.** "Camera chạy ổn" cần con số, không phải cảm
tính. Lỗi kinh điển của Astra Pro là stream 5 giây rồi treo — nhìn RViz một
lúc sẽ tưởng đã xong.

**5. Thiếu lớp môi trường.** Bạn đang chạy VMware trên Windows: udev, USB
passthrough, và bandwidth USB của VM là 3 nguồn lỗi lớn nhất ở giai đoạn này,
lớn hơn cả bản thân ROS2.

## 1. Sơ đồ Phase 1 đề xuất

```
[VMware USB passthrough]  ← 2 thiết bị: 2bc5:0403 + 2bc5:05xx
        ↓
[udev 56-orbbec-usb.rules + libuvc]        (host layer)
        ↓
astra_camera_node  (ros2_astra_camera, legacy OpenNI)
   ├── OpenNI2 ──→ /camera/depth/image_raw   + depth/camera_info  (intrinsics thật)
   │                /camera/depth/points
   └── libuvc  ──→ /camera/color/image_raw   + color/camera_info  (factory, CHƯA calibrate)
        ↓
TF:  camera_link → camera_depth_frame → camera_depth_optical_frame
                 → camera_color_frame → camera_color_optical_frame
     base_link → camera_link          (đo tay, orbbec_bringup)
        ↓
RViz2 (fixed frame = base_link)
        ↓
verify_astra_pro.sh  → tất cả PASS và giữ ổn định 60 giây
```

Phạm vi Phase 1 dừng ở đây. **Không** đưa vào Phase 1: Docker, depth→laserscan,
Nav2, calibrate RGB, align depth↔color.

## 2. Chuẩn bị VMware (làm trước, đây là chỗ hay tắc nhất)

1. VM tắt hẳn → **Settings → USB Controller → USB compatibility = USB 3.1**.
   Để USB 2.0 thì depth + RGB tranh băng thông và driver treo giữa chừng.
2. Tick **"Show all USB input devices"**.
3. Cắm camera → Windows sẽ hỏi gắn vào máy nào. Astra Pro xuất hiện **hai
   dòng** (một depth, một camera/RGB). **Phải gắn cả hai vào Ubuntu guest.**
   Gắn thiếu dòng RGB là nguyên nhân số 1 của "depth chạy, RGB im".
4. Dùng cáp USB *data*, cắm cổng sau máy (cổng trước / hub thụ động hay thiếu điện).
5. Trong Ubuntu, kiểm tra:

```bash
lsusb -d 2bc5:
# mong đợi 2 dòng: ...2bc5:0403... và ...2bc5:0501 (hoặc 0502)
ls -l /dev/video*
```

Chỉ thấy 1 dòng → quay lại bước 3.

## 3. Cài đặt (chạy 1 lần trong Ubuntu guest)

```bash
cd ~/fleet-management-system
bash ros2_ws/src/orbbec_bringup/scripts/setup_astra_pro.sh
```

Script làm: apt deps → build libuvc từ source → clone
`ros2_astra_camera` vào `ros2_ws/src/third_party/` → cài udev rules → in ra
tình trạng USB hiện tại.

> OpenNI2 redist (x64/arm/arm64) **nằm sẵn trong repo driver**
> (`astra_camera/openni2_redist`). Không cần tải file `openNISDK_ROS2_*.tar.gz`
> nào cả — README cũ của package ghi sai chỗ này, đã sửa.

**Rút và cắm lại camera sau bước này**, udev không áp dụng ngược cho thiết bị
đã enumerate rồi.

Build:

```bash
cd ~/fleet-management-system/ros2_ws
colcon build --symlink-install --cmake-args -DCMAKE_BUILD_TYPE=Release
source install/setup.bash
```

## 4. Chạy

```bash
ros2 launch orbbec_bringup orbbec_with_mount.launch.py \
  x:=0.25 y:=0.0 z:=0.35 \
  rviz:=true
```

`x/y/z` là khoảng cách **đo thật** từ `base_link` tới thân camera (mét, x tới
trước, y sang trái, z lên trên). Đừng để 0 — TF sai thì Phase 2 sai theo.

Bản FHD:

```bash
ros2 launch orbbec_bringup orbbec_with_mount.launch.py uvc_product_id:=0x0502
```

RViz trong VM không có GPU passthrough thì thêm:

```bash
export LIBGL_ALWAYS_SOFTWARE=1
```

## 5. Nghiệm thu Phase 1

Terminal thứ hai, **trong lúc launch đang chạy**:

```bash
cd ~/fleet-management-system/ros2_ws
source install/setup.bash
bash src/orbbec_bringup/scripts/verify_astra_pro.sh
```

Phase 1 chỉ được coi là xong khi:

- [ ] `lsusb -d 2bc5:` ra đủ 2 thiết bị
- [ ] 5 topic có mặt: `color/image_raw`, `color/camera_info`,
      `depth/image_raw`, `depth/camera_info`, `depth/points`
- [ ] `color/image_raw` và `depth/image_raw` ≥ 10 Hz, `depth/points` ≥ 5 Hz
- [ ] `depth/camera_info` có ma trận K khác 0
- [ ] `ros2 run tf2_ros tf2_echo base_link camera_depth_optical_frame` ra kết quả
- [ ] RViz2 (fixed frame `base_link`) hiện point cloud đúng hướng: đưa tay lại
      gần → cloud tiến về phía `base_link`, không phải lộn ngược
- [ ] **Chạy liên tục 60 giây không tụt Hz, không treo** — chạy
      `verify_astra_pro.sh` lần thứ hai sau 1 phút, phải PASS y hệt

Ghi lại giá trị Hz thực đo được vào PR/issue để Phase 2 có mốc so sánh.

## 6. Những thứ đã biết trước, đừng mất thời gian debug

| Hiện tượng | Đây là bình thường vì |
|---|---|
| `color/camera_info` có D/K nhưng ảnh chồng lên depth bị lệch | Chưa calibrate RGB; Astra Pro không có D2C phần cứng. Việc của Phase 2. |
| `camera_color_frame` có 2 parent trong `view_frames` | Quirk của driver vendor. Không chặn Phase 1. |
| `depth_registration:=true` không có tác dụng | Không được hỗ trợ trên model này. |
| Bật `enable_ir:=true` thì depth chết | Depth và IR dùng chung một sensor. Mặc định của package đã để `false`. |

## 7. Sau Phase 1

Theo thứ tự: (1) đóng gói vào Docker + thêm device mapping vào
`docker-compose.yml`, (2) calibrate intrinsics RGB, (3) align depth↔color bằng
`depth_image_proc`, (4) depth→laserscan hoặc voxel layer cho Nav2.
