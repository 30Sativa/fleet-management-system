# Phase 4 — AI perception (person → Nav2)

## 0. Đánh giá sơ đồ Phase 4 ban đầu

Sơ đồ gốc:

```
RGB ─► object detection
          │
Depth ────┘
          ↓
      3D object
          ↓
    AMR behavior
```

Sơ đồ này đúng về khái niệm nhưng bỏ qua đúng những chỗ sẽ làm bạn mất một tuần.

**1. `Depth ────┘` không phải một sợi dây. Đó là toàn bộ phần khó.**
Astra Pro có RGB là **một webcam UVC riêng biệt**, không phải một stream của cảm
biến depth, và **không có D2C phần cứng**. Chính `docs/phase1-camera.md` của bạn
đã ghi điều này. Hệ quả: pixel RGB `(u,v)` **không** index được ảnh depth. Vẽ hai
mũi tên gặp nhau làm biến mất bước duy nhất thực sự khó trong pipeline.

**2. Không có ngân sách CPU.** i3-7100T là **2 nhân / 4 luồng**, và Nav2 đã ngồi
sẵn trên đó từ Phase 3. Sơ đồ ngầm giả định detection là miễn phí. Nó không. Nếu
detector ăn hết luồng, `controller_server` trượt nhịp 10 Hz và robot đi loạng
choạng — triệu chứng trông giống lỗi Nav2, thực ra là lỗi lập lịch.

**3. `AMR behavior` là hộp đen.** Phải gọi tên một interface thật, nếu không
bạn sẽ viết một node điều khiển song song với Nav2 rồi hai thằng đánh nhau. Câu
trả lời có sẵn trong Nav2 Humble: `controller_server` **đã subscribe
`/speed_limit`** (`nav2_msgs/SpeedLimit`) và `DWBLocalPlanner::setSpeedLimit`
được cài đặt thật. Không cần viết một dòng code điều khiển nào.

**4. Băng thông USB.** Phase 3 **cố ý tắt RGB** để depth ổn định trên một bus
USB. Phase 4 bật lại chính là mở lại đúng vấn đề Phase 1 đã gặp (RGB ~5 Hz, hay
đơ). Đây là đánh đổi, không phải chuyện miễn phí.

**5. Phạm vi quá rộng.** Danh sách "pallet detection, human/object detection,
docking, task-specific perception" là danh sách cho một robot kho hàng.
CampusTour DT-AMR không có pallet. Và **docking bằng YOLO là sai lựa chọn** —
một marker ArUco cho ra pose 6-DOF chính xác milimet với vài trăm micro-giây
CPU, không cần train, không cần dataset, không hỏng khi đổi ánh sáng. Phase 4
chỉ nên có **một** việc: **phát hiện người**.

**6. Và điều quan trọng nhất, dễ over-claim nhất:**
Phase 4 **không phải** thứ giữ robot khỏi đâm vào người. **Phase 3 đã làm việc
đó rồi** — một người đứng trước robot là một bức tường điểm trong local costmap,
Nav2 tránh mà không cần biết đó là cái gì.

Thứ Phase 4 thêm vào là **chữ "người"**. Vật cản costmap thì lách qua ở tốc độ
tối đa; con người thì phải tiến lại từ tốn. Đó là toàn bộ giá trị của Phase 4,
và giữ đúng phạm vi đó là cách duy nhất để nó không phình ra.

## 1. Ngân sách CPU — con số quyết định thiết kế

Dell OptiPlex 3050 Micro · **i3-7100T, 2 nhân / 4 luồng @ 3.4 GHz, 35 W** ·
HD Graphics 630 (Gen9.5) · 8 GB RAM · không GPU rời.

| Đang chạy | Ước lượng |
|---|---|
| Nav2 (DWB 16×40 mẫu @10 Hz + 2 costmap + AMCL 2000 hạt) | ~1.5–2 luồng |
| Astra driver + point cloud 320×240 @10 Hz | ~0.3–0.5 luồng |
| **Còn lại cho detection** | **~1.5–2 luồng** |

Từ đó suy ra toàn bộ cấu hình: **2 luồng, 320×320, INT8, 5 Hz, chỉ class
person**. Không phải vì đó là con số đẹp, mà vì đó là chỗ trống còn lại.

**Runtime trên robot chỉ cần `openvino` + numpy + cv2.** Không cài
torch/ultralytics lên mini PC — 8 GB RAM và bạn không train gì trên đó. Export
model làm trên laptop.

## 2. Chọn model

| Model | mAP<sup>val</sup> | CPU ONNX (tham chiếu) | Ghi chú |
|---|---|---|---|
| **YOLO26n** | **40.9** | **38.9 ms** | NMS-free, ~31% nhanh hơn YOLO11n trên CPU |
| YOLO11n | 39.5 | 56.1 ms | Chín, tài liệu nhiều |
| YOLOv8n | 37.3 | ~80 ms | Cũ hơn cả hai ở mọi mặt |

> Cột "CPU ONNX" là số của Ultralytics đo ở **640 px trên một Intel Xeon
> @ 2.00 GHz**, **không phải** máy bạn. Ở 320 px sẽ nhanh hơn ~2.5–3 lần, nhưng
> trên 2 nhân sẽ chậm hơn đáng kể. **Đừng dùng con số này để lập kế hoạch — tự
> đo.** Đó là lý do bước 0 ở mục 4 là chạy benchmark.

**Chọn: YOLO26n, OpenVINO INT8, 320×320, lọc class person, 5 Hz, 2 luồng, CPU.**

Lý do NMS-free đáng giá **đúng trên phần cứng này**: NMS phải duyệt 2100 (ở 320
px) tới 8400 hộp ứng viên trong numpy, tốn vài ms thật trên một CPU yếu — và nó
là một núm tinh chỉnh nữa mà bạn không cần.

Thang dự phòng, theo thứ tự:

1. YOLO26n không export/chạy được → **YOLO11n**, y hệt cấu hình. Node đọc được
   cả hai layout output, không phải sửa code.
2. Vẫn quá nặng → **`person-detection-0202`** (Intel Open Model Zoo,
   MobileNetV2-SSD, một class duy nhất, nhẹ hơn nhiều, INT8 sẵn cho OpenVINO).
   Đổi lại: mất khả năng nhận class khác nếu sau này WP tour-guide cần.
3. Vẫn quá nặng → hạ `imgsz` xuống 256, `rate_hz` xuống 2–3.

**Đừng đặt cược vào iGPU.** HD 630 là Gen9.5 — có báo cáo GPU inference hỏng
trên UHD 630 với OpenVINO 2025.x. Script benchmark thử cả hai trong một phút:
chạy được thì đó là headroom miễn phí và CPU để nguyên cho Nav2; không chạy
được thì dùng CPU. Biết trong một phút, không phải sau một tuần tích hợp.

## 3. Sơ đồ Phase 4 đề xuất

```
RGB 640×480 @5 Hz ──► YOLO26n INT8 (OpenVINO, 320, chỉ person)
  (bật lại ở Phase 4)          │ bbox 2D
                               │
Depth cloud @10 Hz ────────────┤
  (đã có sẵn từ Phase 3)       │
                               ▼
        chiếu cloud VÀO mặt phẳng ảnh RGB
        (TF depth_optical→color_optical + K_rgb)
                               │
        median z trong lõi bbox (loại nền phía sau)
                               ▼
                    người, toạ độ base_link
                               │
              ┌────────────────┴────────────────┐
              ▼                                 ▼
   /people (PoseArray)               /speed_limit (nav2_msgs/SpeedLimit)
   /people_markers (RViz)                       │
   → cho Digital Twin / WP khác                 ▼
                                     controller_server → DWB
```

**Điểm mấu chốt: đi ngược chiều.** Thay vì register depth vào RGB (cần một
nodelet, một phiên calibrate, cả một stage nữa), node lấy cloud depth → đổi sang
frame màu → chiếu bằng `K_rgb`. Giờ mỗi điểm 3D có sẵn `(u,v)` trên ảnh RGB, và
khoảng cách của một detection chỉ là độ sâu của các điểm rơi vào trong hộp.

Cùng kết quả, ~40 dòng numpy, không package mới, và chênh lệch FOV giữa hai cảm
biến tự xử lý — điểm nào nằm ngoài khung RGB thì đơn giản là không rơi vào đâu cả.

## 4. Chạy

### Bước 0 — Đo trước, xây sau (bắt buộc)

Trên **laptop**:

```bash
pip install ultralytics
yolo export model=yolo26n.pt format=openvino imgsz=320 int8=True
# -> yolo26n_int8_openvino_model/{yolo26n.xml, yolo26n.bin}
```

Copy thư mục đó sang mini PC, rồi trên **mini PC**:

```bash
pip3 install "openvino>=2024.0"
python3 ros2_ws/src/robot_perception/scripts/bench_detector.py \
    /opt/models/yolo26n_int8_openvino_model/yolo26n.xml
```

Chạy **hai lần**: một lần máy rảnh, một lần trong khi `navigation.launch.py`
đang chạy. **Lần thứ hai mới là con số thật.** Nếu nó báo "QUÁ NẶNG", quay lại
mục 2 và tụt xuống một bậc trong thang dự phòng — trước khi viết thêm bất cứ gì.

### Bước 1 — Calibrate intrinsics RGB

`color/camera_info` hiện là **số phỏng đoán từ nhà máy**, không phải calibrate
của chiếc camera này — Phase 1 đã cắm sẵn đường dây cho việc này nhưng chưa dùng.

```bash
ros2 run camera_calibration cameracalibrator \
    --size 8x6 --square 0.025 \
    image:=/camera/color/image_raw camera:=/camera/color
# rồi trỏ vào file kết quả:
#   ros2 launch ... camera_color_info_url:=file:///home/.../color.yaml
```

Sai `K_rgb` → sai hướng và sai khoảng cách của mọi detection. 30 phút, công cụ
tiêu chuẩn, làm một lần.

### Bước 2 — Chạy, nhưng chưa cho đụng Nav2

```bash
ros2 launch robot_navigation navigation.launch.py \
    map:=... camera_enable_color:=true

ros2 launch robot_perception person_perception.launch.py \
    model_xml:=/opt/models/yolo26n_int8_openvino_model/yolo26n.xml \
    publish_speed_limit:=false
```

`publish_speed_limit:=false` là chế độ **chỉ nhìn**: node publish `/people` và
`/people_markers` nhưng không chạm vào Nav2. Xem trụ màu cam trong RViz trước
khi cho nó quyền thay đổi tốc độ robot.

Đồng thời kiểm tra depth **không bị tụt** khi RGB bật lên:
`ros2 topic hz /camera/depth/points`.

### Bước 3 — Kiểm chứng khoảng cách (bài test quyết định)

Extrinsic giữa RGB và depth **đã có sẵn trong TF** do driver publish từ thông số
nhà máy. Node dùng luôn. Bài test này là để biết nó có đủ tốt không:

1. Nhờ một người đứng đúng **2.00 m** trước robot, đo bằng thước.
2. `ros2 topic echo /people --once`
3. `sqrt(x² + y²)` phải nằm trong **±10 cm**.

Đạt → xong, không cần calibrate thêm gì. Không đạt (lệch > 15 cm) → stereo
calibrate RGB + IR. **Lưu ý:** bật IR phải tắt depth — driver Astra Pro không
chạy được cả hai cùng lúc (đã ghi trong `orbbec_bringup/README.md`).

### Bước 4 — Bật ảnh hưởng lên Nav2

Bỏ `publish_speed_limit:=false`. Gửi một goal, để một người bước vào hành lang
phía trước. Robot phải **chậm lại rõ rệt** trước khi tới gần, thay vì lách qua ở
tốc độ tối đa.

## 5. Đọc lỗi

| Triệu chứng | Nghĩa là | Xử lý |
|---|---|---|
| `chua chay suy luan lan nao; thieu: color/image_raw` | RGB chưa bật | `camera_enable_color:=true` |
| `model_xml chua duoc dat` | Chưa trỏ model | Xem bước 0 |
| Nạp model hỏng trên GPU | HD 630 Gen9.5 | `device:=CPU`. Bình thường |
| `color/camera_info.K rong` | Chưa calibrate RGB | Bước 1 |
| Nhiều `bbox khong lay duoc do sau` | Người ngoài tầm 0.6–8 m, hoặc TF màu↔depth sai | Bước 3 |
| Khoảng cách luôn xa hơn thực tế | Đang bắt vào **tường phía sau** người | Bbox quá rộng; tăng `conf_threshold` |
| Có người mà `/people` rỗng | conf thấp, ánh sáng kém, hoặc RGB đơ | `ros2 topic hz /camera/color/image_raw` |
| Robot bò chậm cả khi không có ai | `/speed_limit` kẹt ở mức thấp | `ros2 topic echo /speed_limit` — camera chết thì node tự nhả về 100% |
| Nav2 trượt nhịp, robot loạng choạng | Detector ăn hết CPU | Hạ `inference_threads`, `rate_hz`, hoặc `imgsz` |
| Depth tụt Hz khi bật RGB | Băng thông USB — đúng vấn đề Phase 1 | Hạ `color_fps`, hoặc chấp nhận và giảm `rate_hz` |

## 6. Quyết định thiết kế và cái giá của nó

**Không có mức "dừng hẳn" trong speed limit.** `SpeedLimit` = 0 làm
`controller_server` không thể di chuyển, `SimpleProgressChecker` kết luận robot
bị kẹt (`required_movement_radius: 0.20` trong 12 s), và Nav2 kích hoạt recovery
— **quay tại chỗ ngay cạnh người**. Việc dừng là việc của costmap, và Phase 3 đã
làm rồi. Mức thấp nhất ở đây là 40%.

**Chiếu depth vào RGB, không register RGB vào depth.** Rẻ hơn, ít stage hơn, tự
xử lý chênh FOV. Cái giá: không có ảnh RGB-D căn khớp để làm việc khác sau này.
Khi nào cần (ví dụ đo kích thước vật thể) thì mới làm registration thật.

**Một process, không tách detector và policy.** Trên 2 nhân, mỗi process là một
khoản chi. Cái giá: muốn thay policy phải sửa node. Chấp nhận được vì policy chỉ
có một ngưỡng.

**Extrinsic lấy từ TF nhà máy, không stereo calibrate.** Ở 2 m, sai số vài mm
baseline là không đáng kể cho quyết định "chậm lại". Bước 3 là bài kiểm tra để
biết giả định đó đúng hay sai — nếu sai thì mới bỏ tiền ra calibrate.

## 7. Tiêu chí đóng Phase 4

- [ ] `bench_detector.py` **khi Nav2 đang chạy**: ≤ 75% ngân sách một chu kỳ
- [ ] `K_rgb` là calibrate thật, không phải số nhà máy
- [ ] Depth vẫn ≥ 8 Hz sau khi bật RGB
- [ ] Người ở 2.00 m đo bằng thước → `/people` báo trong **±10 cm**
- [ ] Hành lang trống 60 s: `/people` rỗng, `/speed_limit` giữ 100%
      (không có người ma làm robot bò)
- [ ] Người bước vào nón trước mặt → `/speed_limit` xuống 40% trong ≤ 1 s
- [ ] `top` khi chạy đủ: `nav2_controller` không nghẽn 100% một core
- [ ] `colcon test --packages-select robot_perception` xanh (11 test)

## 8. KHÔNG thuộc Phase 4

**Docking** — dùng marker ArUco, không dùng YOLO, và để Phase 5.
**Tracking/ID người** (ai là ai, đi hướng nào), **multi-class semantics cho
tour assistant**, **đồng bộ Digital Twin**, **registration RGB-D đầy đủ**,
**đóng Docker**.

Phase 4 chỉ trả lời một câu: **robot có biết cái vật cản đó là một con người
không, và có cư xử khác đi không.**
