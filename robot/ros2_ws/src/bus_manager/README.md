# bus_manager — Smart Campus Bus

Tầng "bus" của hệ thống Smart Campus Bus: điều xe tới các **bến (bus stop)**
đặt tên sẵn trên map campus, phía trên Nav2.

## Milestone hiện tại: stop navigator (1 xe)

```
client (CLI / app gọi xe / dispatcher sau này)
   │  action: /go_to_stop (bus_interfaces/GoToStop)
   ▼
stop_navigator ── tra bus_stops.yaml ──► NavigateToPose ──► Nav2
   │
   └── publish /bus_status (bus_interfaces/BusStatus, 1 Hz)
```

## Chạy thử (sau khi navigation stack đã lên)

```bash
# 1. Navigation stack (sim hoặc thật) — xem robot_navigation/README.md
ros2 launch robot_navigation sim_navigation.launch.py map:=...

# 2. Stop navigator
ros2 launch bus_manager stop_navigator.launch.py use_sim_time:=true

# 3. Gọi bus tới bến
ros2 action send_goal /go_to_stop bus_interfaces/action/GoToStop \
    "{stop_id: library}" --feedback

# 4. Theo dõi trạng thái xe
ros2 topic echo /bus_status
```

## bus_stops.yaml

Tọa độ bến phải lấy từ **map đã lưu** (RViz "Publish Point" → `/clicked_point`).
Giá trị trong `config/bus_stops.yaml` là placeholder (depot, main_gate,
library, dorm_a) — chỉnh sau khi quét map.

## Hành vi

- Goal tới bến không tồn tại → **reject** ngay (log kèm danh sách bến).
- Đang chạy mà nhận goal mới → reject (cancel goal cũ trước). Xếp hàng
  đón/trả sẽ do route scheduler xử lý ở milestone sau.
- Cancel goal → cancel luôn goal Nav2 bên dưới, xe dừng.
- `/bus_status`: `state` (idle/navigating/error), bến hiện tại/đích, quãng
  đường còn lại — nền cho dispatcher nhiều xe.

## Tiếp theo (roadmap Smart Campus Bus)

1. Route scheduler: `Route.msg` (chuỗi bến), chạy tuyến vòng lặp, dừng đón
   trả tại mỗi bến.
2. 2-3 xe: namespace per-bus (`/bus1/...`), dispatcher phân xe theo yêu cầu
   gọi (điểm đón gần nhất, xe rảnh).
3. Digital twin campus (Isaac Sim / Gazebo world campus) để test toàn hệ thống.
