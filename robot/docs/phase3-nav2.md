# Phase 3 — Astra vào Nav2 (obstacle avoidance)

## 0. Đánh giá sơ đồ Phase 3 ban đầu

Sơ đồ gốc:

```
LiDAR ───────► local costmap
                  ▲
                  │
Astra ─► PointCloud2
                  │
                  ▼
                 Nav2
```

Sơ đồ này đúng về ý, nhưng có một chỗ sai và bốn chỗ thiếu.

**Sai: "PointCloud2 → Nav2" không phải một đường dây.** Nav2 không nhận point
cloud. Chỗ duy nhất nhận là `observation_sources` của **obstacle_layer** trong
costmap. Vẽ mũi tên thẳng vào Nav2 làm mất chính cái nút mà 90% lỗi Phase 3 nằm
ở đó.

**Thiếu 1 — Chỉ local costmap, KHÔNG global.** Sơ đồ không nói rõ và đây là
quyết định quan trọng nhất. Local costmap **cuộn** theo robot: ô cũ rơi ra khỏi
cửa sổ 3×3 m là biến mất. Global costmap thì không cuộn — vết đánh dấu nằm đó
tới khi có tia raytrace xoá đi, mà camera chỉ xoá được **trong nón 58°** của
chính nó. Robot quay một vòng là mọi vết camera phía sau **đóng băng vĩnh viễn**
vào global map, và planner sẽ đi vòng tránh những vật cản đã biến mất từ lâu.

**Thiếu 2 — Sàn.** Camera nhìn thấy sàn; LiDAR thì không. Đưa cloud thô vào
costmap thì **sàn trở thành tường** và robot đứng im ngay tại chỗ. Thứ chặn nó
lại là `min_obstacle_height`. Mà ngưỡng đó chỉ đặt được nếu **biết mặt phẳng sàn
nằm ở đâu so với z=0** — tức là chính output của Phase 2. Đây là mắt xích giữa
hai phase, sơ đồ gốc không có.

**Thiếu 3 — Camera không thể là cảm biến an toàn.** Astra Pro: FOV ngang 58.4°,
mù dưới 0.6 m. Vật cản áp sát mũi robot **biến mất** khỏi cloud, và vì
`clearing: true` nên nó còn bị **xoá** khỏi costmap. Nghĩa là camera là lớp **bổ
sung**, LiDAR vẫn là lớp bảo vệ. Sơ đồ vẽ hai mũi tên ngang hàng dễ khiến hiểu
nhầm là hai cái thay thế được nhau.

**Thiếu 4 — Không có cách chứng minh.** Mục tiêu ghi "Astra thực sự góp phần vào
obstacle avoidance". Nhìn RViz **không chứng minh được**: cloud vẽ đè lên costmap
trông y hệt nhau dù có ô nào sinh ra từ camera hay không. Phase 3 cần đúng hai
con số:

- **A** = số ô vật cản **chỉ camera** thấy, LiDAR không thấy → camera có thêm
  thông tin gì không.
- **B** = trong A, bao nhiêu ô **thực sự LETHAL** trên `/local_costmap/costmap`
  → thông tin đó có vào được Nav2 không.

`A = 0` và `B = 0` là hai lỗi **khác hẳn nhau** và cần sửa ở hai chỗ khác hẳn
nhau. Một con số duy nhất không phân biệt được.

## 1. Sơ đồ Phase 3 đề xuất

```
RPLiDAR A3M1 ─► /scan ──────────┬────────► global costmap (obstacle_layer)
   360°, 15 m, MỘT mặt phẳng    │              + static_layer (map đã lưu)
                                │
                                ▼
Astra Pro ─► /camera/depth/points ─► local costmap · obstacle_layer
   58° ngang, 0.6–3 m               observation_sources: scan pointcloud
   thấy VẬT THẤP / NHÔ RA               ├─ min_obstacle_height: 0.08  ← loại sàn
                                        │     (số này đến từ Phase 2)
                                        ├─ max_obstacle_height: 1.20
                                        └─ obstacle_max_range: 3.00
                                              │
                                              ▼
                                        inflation_layer
                                              │
                                              ▼
                                   controller_server (DWB)
                                              │
                                    /cmd_vel_ctrl → velocity_smoother
                                              │
                                    /cmd_vel_nav → mode_manager → /cmd_vel → base

                    kiểm chứng: ros2 run orbbec_bringup costmap_contrib
                                → A = ô chỉ camera thấy
                                → B = trong đó bao nhiêu ô đã vào costmap
```

Khác biệt cốt lõi: **camera chỉ vào local costmap**, có **bộ lọc chiều cao lấy
từ Phase 2**, và có **nhánh đo** để trả lời "góp phần" bằng số chứ không bằng
mắt.

## 2. Những gì đã thay đổi trong repo

| File | Thay đổi |
|---|---|
| `robot_control/config/nav2_params.yaml` | `local_costmap.obstacle_layer`: thêm source `pointcloud`. `global_costmap`: ghi rõ lý do **không** thêm |
| `robot_navigation/launch/navigation.launch.py` | Thêm `enable_camera` (mặc định true) + `camera_x/y/z/roll/pitch/yaw`, include `orbbec_with_mount.launch.py` |
| `orbbec_bringup/costmap_contrib_node.py` | Node mới đo A và B |
| `orbbec_bringup/depth_check_node.py` | Phase 2: thêm mục 5 kiểm tra `depth/points` — đúng topic mà Phase 3 dùng |

Độ phân giải depth cho nav hạ xuống **320×240 @ 10 Hz** (~77k điểm/khung).
640×480 @ 30 Hz là gấp **9 lần** lưu lượng đó; costmap `update_frequency: 5.0`
sẽ trễ nhịp trên mini PC. Nếu driver không nhận 320×240, chạy
`camera_depth_width:=640 camera_depth_height:=480 camera_depth_fps:=10`.

## 3. Chạy

```bash
cd ~/fleet-management-system/robot/ros2_ws
colcon build --packages-select orbbec_bringup robot_control robot_navigation
source install/setup.bash

ros2 launch robot_navigation navigation.launch.py \
  map:=$HOME/fleet-management-system/robot/ros2_ws/src/robot_navigation/maps/my_map.yaml \
  camera_x:=0.25 camera_y:=0.0 camera_z:=0.3996 \
  camera_roll:=0.0297 camera_pitch:=0.2498
```

> `camera_*` phải là **bộ số Phase 2 đã hội tụ**, không phải số mặc định trong
> launch. Mặc định chỉ là điểm khởi động. Sai pitch 3° là sàn thành tường.

Cửa sổ thứ hai:

```bash
ros2 run orbbec_bringup costmap_contrib
```

Chạy LiDAR-only để so sánh: `enable_camera:=false`.

## 4. Bài test quyết định

Sơ đồ nào cũng "chạy được" trong hành lang trống. Vật cản để thử phải là thứ
**LiDAR không thể thấy**:

1. LiDAR nằm ở `lidar_z ≈ base_height/2 + 0.025`. Đo chiều cao thật của mặt
   phẳng quét.
2. Đặt một **thùng carton cao 15–30 cm** — thấp hơn mặt phẳng LiDAR — cách robot
   khoảng **1.2 m**, ngay giữa đường.
3. `ros2 topic echo /scan --once` → thùng **không** xuất hiện. Đúng như mong đợi.
4. Đọc `costmap_contrib`. Mong đợi: **A vài chục ô, B/A ≥ 50%**.
5. Gửi Nav2 Goal ở phía sau thùng. Robot phải **đi vòng**. Chạy lại với
   `enable_camera:=false` — nó sẽ **đâm thẳng vào**.

Bước 5 là bằng chứng cuối. Bốn bước trên chỉ để biết vì sao nếu nó hỏng.

## 5. Đọc kết quả — cái nào là lỗi thật

| Báo cáo nói | Nghĩa là | Xử lý |
|---|---|---|
| `depth/points` CHƯA CÓ BẢN TIN | Driver không publish cloud | `enable_point_cloud:=true`; xem `docs/phase1-camera.md` |
| `costmap` CHƯA CÓ BẢN TIN | Nav2 chưa lên, hoặc sai tên topic | `ros2 topic list \| grep costmap` |
| TF không giải được | `camera_mount` chưa chạy | Nav2 cũng im lặng y hệt — đây là lỗi im lặng nguy hiểm nhất |
| **A = 0**, B bỏ qua | Camera **không thêm gì**. Không phải lỗi wiring | Trước mặt trống thật, hoặc vật cản LiDAR cũng thấy. Làm bài test mục 4 |
| **A > 0 nhưng B = 0** | Camera thấy, **costmap không ghi**. Đây là lỗi Phase 3 điển hình | Theo thứ tự: `observation_sources` có `pointcloud` chưa → đúng topic chưa → `min/max_obstacle_height` → `obstacle_max_range` → TF |
| B/A trong 1–50% | Costmap chưa kịp cập nhật, hoặc điểm rơi ra ngoài rìa 3×3 m | Bình thường khi robot đang chạy. Đứng yên rồi đo lại |
| ">70% vật cản nằm sát ngưỡng" | **Sàn đang lọt qua bộ lọc** | Quay lại Phase 2 mục 3. Đừng nâng `min_obstacle_height` để giấu — sẽ mất luôn thùng thấp |
| "điểm trong cloud" ~0 | Vật quá gần (<0.6 m) hoặc nắng chiếu | Giới hạn phần cứng, không phải lỗi |
| Vật cản gần nhất < 0.60 m | Camera sắp **mất** nó khi robot tiến thêm | Đúng thiết kế. LiDAR + `robot_radius: 0.47` là lớp bảo vệ ở cự ly này |
| Robot dừng ngay khi khởi động | Sàn thành tường | Gần như luôn là mount pitch/z sai. Kiểm tra bằng `depth_check` trước |

## 6. Quyết định thiết kế và cái giá của nó

**`expected_update_rate: 0.0` cho source camera.** Camera chết → costmap **không**
bị đánh dấu stale → Nav2 vẫn chạy bằng LiDAR. Đó là chủ ý: camera là lớp bổ
sung. Cái giá: camera chết âm thầm mà không ai biết. Nếu muốn Nav2 **từ chối
chạy** khi mất camera, đặt `expected_update_rate: 5.0` — an toàn hơn nhưng
robot sẽ đứng im mỗi lần USB chập.

**`clearing: true` cho camera.** Cho phép camera xoá vật cản đã đi khỏi. Cái giá:
vật cản lọt vào vùng mù < 0.6 m sẽ bị **xoá**. Đây là lý do camera không bao giờ
được là cảm biến an toàn duy nhất.

**ObstacleLayer chứ không VoxelLayer.** VoxelLayer là công cụ "đúng sách" cho
dữ liệu 3D — nó raytrace xuyên một lưới voxel thay vì trên mặt phẳng 2D. Nhưng
nó **không** giải được vấn đề sàn: cả hai layer dùng chung `ObservationBuffer`,
và bộ lọc `min/max_obstacle_height` cắt điểm **ngay lúc nạp vào buffer**, trước
khi raytrace. Đổi sang VoxelLayer vẫn phải đặt đúng ngưỡng sàn, vẫn cần Phase 2.

Cái nó thật sự đổi là chất lượng **xoá** vết cũ — và ở cấu hình LiDAR + camera
này, LiDAR đã làm việc đó rồi. `ObstacleLayer::updateBounds` chạy **toàn bộ
raytrace xoá trước, rồi mới đánh dấu**:

```
for (clearing_observations) raytraceFreespace(...);   // LiDAR xoá ô
for (observations)          mark(...);                // camera đánh dấu lại
```

Nên trong cùng một chu kỳ: tia LiDAR quét qua ô có thùng thấp → xoá; camera vẫn
thấy thùng → đánh dấu lại. **Đánh dấu thắng.** Khi thùng được dọn đi, camera
thôi đánh dấu và LiDAR xoá hẳn. Hai cảm biến tự bù cho nhau, đúng cái mà
VoxelLayer sinh ra để làm — với chi phí CPU của ObstacleLayer.

Trên i3-7100T 2 nhân đã cõng Nav2 và sắp cõng thêm YOLO, đó là đánh đổi đáng.
Đổi sang VoxelLayer khi nào? Khi mục 3 của `costmap_contrib` báo B/A cao nhưng
costmap đầy **vết ma ở nơi LiDAR không quét tới** (dưới gầm bàn, hốc tường). Lúc
đó thêm `z_voxels: 16, z_resolution: 0.05, origin_z: 0.0, mark_threshold: 0,
unknown_threshold: 15` và đổi tên plugin — phần còn lại của config giữ nguyên.

**Mount vẫn là static_transform_publisher, chưa vào URDF.** Đúng khi số còn đang
tinh chỉnh — mỗi vòng Phase 2 chỉ cần sửa launch arg. Khi bộ số đã đóng băng, đưa
`camera_link` vào `robot_description/urdf/sensors.xacro` để có **một** nguồn sự
thật, rồi bỏ `camera_mount.launch.py` khỏi đường nav.

## 7. Lỗ hổng đã biết: vật THẤP ở cự ly GẦN

Đây là chỗ hai cảm biến **cùng mù**, và nó không hiện ra trên bất kỳ sơ đồ kiến
trúc nào — phải lần theo cơ chế mới thấy.

```
   khoảng cách tính từ base_link
   0.47 m        0.85 m                     3.0 m
   ├──footprint──┼──────────────────────────┤
                 │
   LiDAR  ███████████████████████████████████   thấy — nhưng chỉ ở độ cao của nó
   Astra  ░░░░░░░│███████████████████████████   mù trước 0.85 m (0.6 m tính từ
                 │                              camera đặt ở x=0.25)
   THÙNG THẤP    │
   ở đây  ──────►│◄── không cảm biến nào thấy
```

Kịch bản: robot tiến tới một thùng cao 20 cm. Ở 2 m, camera thấy → costmap đánh
dấu → tốt. Robot tiến tiếp. Khi còn **dưới 0.85 m**, thùng lọt vào vùng mù 0.6 m
của Astra, camera **thôi đánh dấu**. Cùng lúc đó tia LiDAR vẫn quét qua ô đó ở
độ cao 30 cm, không thấy gì, nên **xoá**. Vết biến mất khỏi costmap **đúng lúc
nó quan trọng nhất**.

Đây là hệ quả trực tiếp của `clearing: true` ở mục 6 — không phải bug, mà là cái
giá đã biết. Ba cách xử lý:

**a) Dùng 2 con sonar bạn đã có.** `stm32_bridge` đang publish
`/ultrasonic/sonar1/range` và `sonar2` dạng `sensor_msgs/Range`, và **hiện không
node nào subscribe**. Nav2 có sẵn `RangeSensorLayer` ăn đúng kiểu message đó, và
sonar nhìn thấy vật thấp ở đúng dải 0.2–0.85 m mà cả hai cảm biến kia mù:

```yaml
      plugins: ["obstacle_layer", "sonar_layer", "inflation_layer"]
      sonar_layer:
        plugin: "nav2_costmap_2d::RangeSensorLayer"
        enabled: true
        topics: ["/ultrasonic/sonar1/range", "/ultrasonic/sonar2/range"]
        input_sensor_type: "ALL"
        clear_on_max_reading: true   # het tam = trong, neu khong vet se dinh mai
        no_readings_timeout: 2.0
        mark_threshold: 0.9          # cao hon mac dinh 0.8: sonar rat nhieu
        clear_threshold: 0.2
        phi: 1.2
```

> Trước khi bật: `sonar_max_range` trong `stm32_bringup` đang để **6.0 m**. SR04T
> thực tế ~4.5 m, và với chùm ~30° thì ở 3 m vết loang rộng gần 1.6 m — đủ để
> dựng tường ma giữa hành lang. **Hạ xuống 1.5–2.0 m.** Sonar ở đây chỉ có một
> việc: canh vùng mù sát robot. Đừng để nó tham gia điều hướng tầm xa.

**b) Chấp nhận, và để Phase 4 lo.** `/speed_limit` khi có người khiến robot tới
gần chậm hơn, nên quãng đường mù trôi qua chậm hơn. Không giải quyết được vật
không phải người.

**c) Không làm gì.** `robot_radius: 0.47` + `inflation_radius: 0.35` nghĩa là
vùng mù chỉ rộng ~0.38 m và robot đã gần dừng ở đó. Với hành lang campus thoáng,
đây là lựa chọn hợp lý — miễn là **biết** mình đang chọn nó.

Khuyến nghị: đóng Phase 3 bằng (c), thử (a) khi đã có bản đồ thật và thấy robot
húc vào vật thấp trong thử nghiệm.

## 8. Tiêu chí đóng Phase 3

- [ ] `costmap_contrib` mục 0: cả 3 đầu vào OK, TF giải được
- [ ] Không có cảnh báo "sàn lọt qua bộ lọc"
- [ ] Với thùng cao 15–30 cm ở 1.2 m: **A > 0** và **B/A ≥ 50%**
- [ ] `ros2 topic echo /scan` xác nhận LiDAR **không** thấy thùng đó
- [ ] Nav2 Goal phía sau thùng: robot đi vòng khi `enable_camera:=true`,
      đâm vào khi `false` — **đây là bằng chứng, phần còn lại là chẩn đoán**
- [ ] Hành lang trống: không có ô lethal ma; robot không tự dừng
- [ ] `top` khi đang chạy: `nav2_controller` không nghẽn ở 100% một core

## 9. KHÔNG thuộc Phase 3

Ghép màu vào cloud, nhận dạng vật thể, voxel layer 3D, camera vào global
costmap, đưa `camera_link` vào URDF, đóng Docker. Phase 3 chỉ trả lời một câu:
**camera có thực sự làm costmap khác đi không, và khác đi đúng chỗ không.**
