# robot_perception

Phase 4: nhận diện **người** bằng RGB-D (Astra Pro) và cho Nav2 **giảm tốc** khi
có người phía trước. Không thay LiDAR, không tự lái — chỉ thêm một lớp hành vi.

Tài liệu đầy đủ: `docs/phase4-ai.md`.

## Vai trò

Phase 3 đã giữ robot khỏi đâm vào người (người = tường điểm trong costmap).
Phase 4 chỉ thêm **chữ "người"**: vật cản thường thì lách ở tốc độ tối đa, con
người thì tiến lại từ tốn qua `/speed_limit` của Nav2.

## Node

| Node | Việc |
|---|---|
| `person_perception` | RGB → YOLO bbox → chiếu cloud depth vào ảnh RGB → người trong `base_link` → publish `/people`, `/people_markers`, `/speed_limit` |

Script (không phải node): `scripts/bench_detector.py` — **đo model trên mini PC
trước khi build pipeline**. Chạy nó trước tiên.

## Phụ thuộc runtime (trên robot)

Chỉ cần `openvino` + numpy + cv2. **Không** cài torch/ultralytics lên mini PC —
export model làm trên laptop:

```bash
# tren LAPTOP:
pip install ultralytics
yolo export model=yolo26n.pt format=openvino imgsz=320 int8=True
# copy thu muc *_openvino_model sang mini PC

# tren MINI PC:
pip3 install "openvino>=2024.0"
```

## Chạy

```bash
# 0) do truoc (bat buoc), chay 2 lan: may ranh + khi Nav2 dang chay
python3 scripts/bench_detector.py /opt/models/yolo26n_int8_openvino_model/yolo26n.xml

# 1) bat RGB o Phase 3 (mac dinh tat de tiet kiem USB)
ros2 launch robot_navigation navigation.launch.py map:=... camera_enable_color:=true

# 2) chay perception, LAN DAU de che do chi-nhin (khong dung Nav2)
ros2 launch robot_perception person_perception.launch.py \
    model_xml:=/opt/models/yolo26n_int8_openvino_model/yolo26n.xml \
    publish_speed_limit:=false

# 3) on roi thi bo publish_speed_limit:=false de cho anh huong len Nav2
```

## Test

```bash
colcon test --packages-select robot_perception   # 11 unit test toan hoc, khong can camera
```

## Cau hinh

`config/person_perception.yaml`. Mọi số nên là số **đo được**, không phải đoán.
Ràng buộc phần cứng: Dell OptiPlex 3050 Micro (i3-7100T, 2 nhân/4 luồng, không
GPU rời) — xem `docs/phase4-ai.md` mục 1 để hiểu vì sao mặc định là 320/INT8/5Hz/2 luồng/CPU.
