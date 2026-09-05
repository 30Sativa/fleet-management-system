# ROS 2 multi-machine: NUC ↔ VM không thấy topic của nhau

Ghi lại lỗi "VM ping được NUC nhưng `ros2 topic list` trên VM chỉ ra
`/parameter_events` + `/rosout`" — đã fix ngày 2026-08-27.

## Triệu chứng

- NUC (robot thật, `<OLD_MINIPC_LAN_IP>`) chạy đầy đủ node: `ros2 topic list` ra
  `/scan`, `/odom`, `/map`, `/ultrasonic/sonar1-4/range`, ...
- VM Ubuntu Humble (VMware, Bridged, `<OLD_VM_LAN_IP>`) chạy `ros2 topic list`
  chỉ ra 2 topic mặc định `/parameter_events` và `/rosout` — như thể
  không có node nào khác đang chạy trong mạng.
- `ping` giữa 2 máy **thông bình thường cả 2 chiều**, 0% loss.
- VMware Network Adapter đã đúng **Bridged (Automatic)**, không phải NAT.
- `ROS_DOMAIN_ID` trống ở cả 2 máy (cùng domain mặc định `0`) → không phải
  nguyên nhân.

## Nguyên nhân gốc

ROS 2 (Fast DDS mặc định) dùng **UDP multicast** để các node tự "khám phá"
nhau (discovery). Unicast (ping, SSH) đi qua bình thường không có nghĩa
multicast cũng đi qua — nhiều router Wi-Fi/switch có **AP/Client
Isolation** hoặc IGMP snooping cấu hình sai, chặn multicast giữa các thiết
bị trong cùng mạng.

Xác nhận bằng test trực tiếp:

```bash
# Trên NUC
ros2 multicast send
# → "Sending one UDP multicast datagram..."

# Trên VM, chạy gần như đồng thời
ros2 multicast receive
# → đứng mãi ở "Waiting for UDP multicast datagram..." — KHÔNG nhận được gì
```

Kết luận: multicast bị chặn giữa NUC và VM dù cùng subnet `<OLD_LAN_SUBNET>`
và ping thông.

## Cách fix: Fast DDS Discovery Server (bypass multicast)

Thay vì multicast, dùng 1 Discovery Server trung tâm mà các máy trỏ về
qua **TCP unicast** — không phụ thuộc router có chặn multicast hay không.

### 1. Trên NUC — chạy Discovery Server như systemd service (tự sống qua reboot)

```bash
sudo tee /etc/systemd/system/fastdds-discovery.service > /dev/null <<'EOF'
[Unit]
Description=Fast DDS Discovery Server for ROS 2
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/bin/fastdds discovery --server-id 0
Restart=on-failure
RestartSec=3
User=sativa

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now fastdds-discovery.service
sudo systemctl status fastdds-discovery.service --no-pager
```

Server lắng nghe cổng mặc định `11811`. Kiểm tra trạng thái bất cứ lúc
nào bằng `systemctl status fastdds-discovery.service`.


### 2. Restart mọi node ROS 2 đang chạy trên NUC

Node nào start **trước** khi biến `ROS_DISCOVERY_SERVER` được set thì vẫn
đang dùng multicast discovery cũ. Dừng (Ctrl+C) và launch lại sau khi biến
đã có hiệu lực.

### 3. Xác nhận

```bash
# Trên VM
ros2 topic list
```

Phải thấy đủ topic của NUC (`/scan`, `/map`, `/ultrasonic/sonar*/range`,
`/tf`, `/slam_toolbox/*`, ...) — không chỉ 2 topic mặc định nữa.

## Introspection với Discovery Server

Khi robot dùng `ROS_DISCOVERY_SERVER=127.0.0.1:11811`, node vẫn có thể chạy và
truyền dữ liệu bình thường dù `ros2 topic list` hoặc `ros2 node info <node>`
đôi khi hiện thiếu endpoint. Ví dụ, `/stm32_bridge_node` vẫn có thể publish
sonar và `ros2 topic echo /ultrasonic/sonar1/range sensor_msgs/msg/Range` vẫn
nhận được dữ liệu trong khi `ros2 node info /stm32_bridge_node` tạm thời hiện
`Publishers:` trống. Đây là giới hạn/độ trễ của graph introspection, không tự
động chứng minh node đã chết.

Khi cần làm mới graph cache để debug, chạy:

```bash
ros2 daemon stop
ROS_SUPER_CLIENT=TRUE ros2 daemon start
ros2 topic list
ros2 node info /stm32_bridge_node
```

Nếu đã biết topic cần kiểm tra, ưu tiên gọi trực tiếp topic đó để xác nhận dữ
liệu trước khi kết luận endpoint bị mất. Giữ nguyên `ROS_DISCOVERY_SERVER`;
không tắt Discovery Server để chữa lỗi introspection và không cần biến tất cả
node thành Super Client. `ROS_SUPER_CLIENT=TRUE` chủ yếu là tuỳ chọn hỗ trợ
debug/introspection cho CLI daemon.

## Lưu ý khi setup máy mới / mạng mới

- Nếu đổi IP LAN của NUC (DHCP cấp lại IP khác), phải sửa lại
  `ROS_DISCOVERY_SERVER` trên VM (và trên mọi máy client khác) cho khớp.
  Cân nhắc đặt IP tĩnh cho NUC để tránh phải sửa lại mỗi lần.
- `ROS_DISCOVERY_SERVER` phải được set **trước khi** node/launch file khởi
  động — set sau khi node đã chạy sẽ không có tác dụng cho tới khi restart
  node đó.
- Cách này không cần Tailscale/VPN gì cả — chỉ cần các máy cùng mạng LAN
  và unicast (ping) thông là đủ. Tailscale chỉ cần thiết nếu sau này giám
  sát/điều khiển từ máy ở **mạng khác hẳn** (không cùng LAN với NUC); khi
  đó vẫn phải dùng chung cơ chế Discovery Server này (không phải multicast)
  vì Tailscale cũng không route multicast.
- Muốn kiểm tra nhanh multicast có bị chặn không ở bất kỳ cặp máy nào:
  dùng lại đúng test `ros2 multicast send` / `ros2 multicast receive` ở
  trên.
</content>
