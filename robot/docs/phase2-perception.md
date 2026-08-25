# Phase 2 — 3D perception (Astra Pro)

## 0. Đánh giá sơ đồ Phase 2 ban đầu

Sơ đồ gốc:

```
Depth → PointCloud2 → RViz2
```
Kiểm tra: depth đúng không / frame đúng không / cloud lệch không / ground nhiễu không

**Vấn đề lớn nhất: luồng dữ liệu này Phase 1 đã chạy rồi.** Ở Phase 1 bạn đã
thấy point cloud trong RViz2 — nghĩa là `Depth → PointCloud2 → RViz2` đã xong.
Vẽ lại y hệt thì Phase 2 không thêm gì mới.

Cái thật sự làm nên Phase 2 là **4 câu hỏi kiểm tra**, và cả 4 câu đó đều
**không trả lời được bằng mắt**. "Nhìn cloud thấy ổn" không phải là một kết
luận kỹ thuật. Phase 2 = biến 4 câu hỏi đó thành **số đo**.

Bốn điểm sơ đồ gốc còn thiếu:

**1. Thiếu bước hiệu chỉnh mount — đây là cửa ải của cả Phase 2.**
Hiện `x:=0.25 y:=0 z:=0.35` với `roll/pitch/yaw = 0` là **số bịa** từ Phase 1,
chưa ai đo. Mà hai câu hỏi "cloud có lệch không" và "ground có nhiễu không"
**phụ thuộc hoàn toàn** vào mount đúng: nếu pitch sai 3°, sàn sẽ nghiêng lên
trong RViz và bạn sẽ tưởng cloud lệch, trong khi camera hoàn toàn tốt. Không
hiệu chỉnh mount thì 2/4 câu hỏi vô nghĩa.

**2. "depth đúng không" cần mốc so sánh, không phải cảm nhận.**
Phải đặt camera cách tường một khoảng **đo bằng thước**, rồi so với số depth
báo về. Không có mốc thì không có chữ "đúng".

**3. Thiếu giới hạn phần cứng của Astra Pro.**
Tầm đo **0.6–8 m** (khuyến nghị 0.6–5 m). Vật gần hơn 0.6 m → **pixel = 0**,
tức lỗ đen trong cloud. Đây **không phải nhiễu**, mà là sensor báo "tôi không
đo được". Không biết điều này sẽ đi debug nhầm chỗ rất lâu.

**4. Thiếu hình học FOV — lý do "không thấy sàn đâu".**
FOV dọc ~45.5°. Camera lắp ở z=0.35 m và **pitch = 0 (nằm ngang)** thì tia thấp
nhất chỉ chạm sàn ở **~0.83 m** phía trước. Gần hơn thế là vùng mù. Nhiều người
kết luận "ground bị nhiễu / mất sàn" trong khi thực ra sàn chưa vào khung hình.

| pitch (chúc xuống) | sàn bắt đầu thấy từ | còn thấy đường chân trời? |
|---|---|---|
| 0° | 0.83 m | có |
| 5° | 0.67 m | có |
| 10–20° | 0.60 m (chạm giới hạn sensor) | có |
| 25° | 0.60 m | **không** — chỉ thấy sàn, mù vật cản cao |

→ Với robot cao 0.35 m, **pitch 5–15°** là vùng hợp lý: thấy sàn gần mà vẫn
thấy vật cản phía trước.

## 1. Sơ đồ Phase 2 đề xuất

```
Depth (16UC1, mm) + CameraInfo(K)
        ↓ deproject
PointCloud2  (camera_depth_optical_frame)
        ↓ TF: base_link ← camera_link ← ..._optical_frame
Cloud trong base_link
        ↓
   ┌────┴─────────────────────────┐
   ↓                              ↓
RViz2 (nhìn định tính)      depth_check (đo định lượng)
                                  ↓
                    ① sai số depth vs thước đo
                    ② TF giải được + hướng nhìn đúng
                    ③ khớp mặt phẳng sàn → lệch z/pitch/roll
                       + IN RA giá trị mount đã sửa
                    ④ độ lệch chuẩn sàn, theo từng dải khoảng cách
```

Điểm khác cốt lõi so với sơ đồ gốc: **thêm nhánh đo**, và nhánh đó **tự tính ra
giá trị mount cần sửa** thay vì bắt bạn mò.

## 2. Chạy

```bash
cd ~/fleet-management-system/robot/ros2_ws
source install/setup.bash

ros2 launch orbbec_bringup phase2_perception.launch.py \
  x:=0.25 y:=0.0 z:=0.35 pitch:=0.17 \
  expected_center_m:=1.00
```

- `pitch:=0.17` ≈ 10° chúc xuống (radian). Bắt đầu từ đây nếu camera lắp ngang
  thì sàn khó vào khung.
- `expected_center_m:=1.00` — **đo bằng thước** từ mặt trước camera tới tường,
  điền số thật. Để 0 thì bỏ qua kiểm tra sai số tuyệt đối.
- RGB **tắt mặc định**: Phase 2 chỉ cần depth, và tắt màu giải phóng băng thông
  USB — đây chính là lý do Phase 2 chạy được ổn trên VMware dù RGB hay đơ.

Cứ 3 giây node in một báo cáo. Đọc báo cáo, sửa mount, chạy lại.

## 3. Quy trình hiệu chỉnh mount (làm 1–2 vòng là xong)

1. Đặt robot trên **sàn phẳng, trống**, hướng ra khoảng trống ≥ 3 m.
2. Chạy launch ở trên với giá trị mount hiện có.
3. Đọc mục **3** của báo cáo:
   ```
   -> do cao san tai base_link : -47 mm
   -> lech pitch               : +2.85 deg
   Sua mount roi do lai:
     z:=0.3970  pitch:=0.2198  roll:=0.0012
   ```
4. Chạy lại launch với đúng 3 số nó in ra.
5. Lặp cho tới khi cả 3 mục báo PASS (z lệch < 20 mm, pitch/roll < 1°).

Vì xoay quanh gốc camera cũng làm dịch điểm, vòng 1 thường chưa về 0 hẳn —
vòng 2 là hội tụ. Đó là bình thường, không phải lỗi.

## 4. Đọc kết quả — cái nào là lỗi thật

| Báo cáo nói | Có phải lỗi? | Xử lý |
|---|---|---|
| pixel hợp lệ < 40% | Thường KHÔNG | Vật quá gần (<0.6 m), bề mặt đen/bóng, hoặc nắng chiếu trực tiếp |
| "quá ít điểm sàn" | KHÔNG | Sàn chưa vào khung hình — tăng `pitch` (xem bảng FOV mục 0) |
| z lệch, pitch lệch | Lỗi **mount**, không phải camera | Áp số node in ra |
| nhiễu sàn < 15 mm | Tốt | — |
| nhiễu sàn 15–30 mm | Chấp nhận được | Lọc voxel ở Phase 3 là đủ |
| nhiễu sàn > 30 mm | Đáng ngờ | Sàn bóng/nắng, **hoặc** mount sai khiến "sàn" thực ra không phải sàn |
| dải xa nhiễu hơn dải gần | KHÔNG phải lỗi | Structured light: nhiễu tăng theo bình phương khoảng cách |
| "chúc xuống ~-90 deg" | Lỗi **thật** | Cloud đang ở body frame thay vì optical frame |

## 5. Tiêu chí đóng Phase 2

- [ ] Sai số depth ở mốc đo được: trong **±(30 mm + 1%)** khoảng cách
- [ ] TF `base_link ← camera_depth_optical_frame` giải được, hướng nhìn khớp
      với pitch đã khai báo
- [ ] Sàn: |z| < 20 mm, |pitch| < 1°, |roll| < 1° sau khi hiệu chỉnh
- [ ] Nhiễu sàn ≤ 30 mm ở dải 1–3 m
- [ ] Trong RViz: cloud sàn **nằm đúng trên lưới z=0**, nhìn từ ngang không
      thấy nghiêng
- [ ] Ghi lại bộ `x/y/z/roll/pitch/yaw` cuối cùng vào README — đây là output
      quan trọng nhất của Phase 2

## 6. KHÔNG thuộc Phase 2

Lọc voxel, depth→laserscan, costmap/Nav2, ghép màu vào cloud (Astra Pro không
có D2C phần cứng — cần calibrate RGB trước). Tất cả để Phase 3.

Phase 2 chỉ trả lời đúng một câu: **cloud này có đáng tin để đưa vào Nav2 không.**
