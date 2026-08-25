# System Architecture

How the pieces of CampusTour DT-AMR fit together. This file covers what
crosses a folder boundary. Anything internal to one folder is documented
inside that folder.

- Robot internals: [`robot/README.md`](../robot/README.md)
- Backend internals: `backend/AGENTS.md` <!-- TODO(WP2) -->
- Frontend internals: `web/AGENTS.md` <!-- TODO(WP5) -->

---

## 1. Components

```
   Visitor                     Campus staff
      |                             |
      v                             v
   +-----------------------------------------+
   |  web/     visitor app + ops dashboard    |
   +---------------------+-------------------+
                         | HTTP / realtime
                         v
   +-----------------------------------------+
   |  backend/  booking, scheduling, dispatch |
   +---------------------+-------------------+
                         | ??? (contract not fixed yet)
                         v
   +-----------------------------------------+
   |  robot/   ROS 2 fleet + STM32 firmware   |
   +-----------------------------------------+
```

<!-- TODO(WP1): khi backend và web có hình dạng thật thì vẽ lại sơ đồ này cho đúng. -->

---

## 2. Robot subsystem (settled)

Sensor hierarchy — this is a decision, see
[ADR-0001](decisions/0001-lidar-primary-astra-supplementary.md):

```
RPLiDAR A3M1        -> /scan                 -> local + global costmap, AMCL, SLAM
encoder + IMU       -> /odom                 -> odom -> base_link TF
Astra Pro (depth)   -> /camera/depth/points  -> LOCAL costmap ONLY
Astra Pro (RGB)     -> person detection      -> Nav2 speed limit
```

The STM32G431 owns real-time stepping. ROS 2 sends wheel-speed commands over
USB CDC serial and does not reach below that line.

Named-stop navigation is exposed as a ROS 2 action: `go_to_stop`
(`bus_manager` / `bus_interfaces`). This is the natural seam for the backend
to command a tour.

---

## 3. Robot <-> Backend contract

> **NOT DECIDED YET.** Until this section is filled in, neither side should
> hardcode a field name. Whoever fixes it writes it here first.

<!-- TODO(WP2 + WP3): chốt và điền:

Transport:        rosbridge websocket | MQTT | REST polling | gRPC
Direction:        robot -> backend (telemetry), backend -> robot (commands)
Auth:             robot control channel phải authenticated (yêu cầu NFR bảo mật)

Telemetry robot đẩy lên (tối thiểu):
  robot_id, pose (x, y, theta, frame), battery %, task state,
  current/next stop, fault code, timestamp
  tần suất: ? Hz

Lệnh backend đẩy xuống:
  assign_tour(robot_id, route_id, stops[], start_time)
  cancel_tour(robot_id)
  ...

Đổi bất kỳ field nào ở trên = contract change: sửa file này trong cùng PR.
-->

---

## 4. Digital Twin

<!-- TODO(WP3): twin đồng bộ bằng cách nào (bridge node? bag replay? shared topic namespace?),
     chạy ở đâu (miniPC / máy khác), và đo latency ra sao — vì đây là research question
     của đồ án nên số liệu đo phải lặp lại được. -->

---

## 5. AI tour-guide assistant

<!-- TODO(WP4): STT -> LLM -> TTS chạy ở đâu (miniPC Dell OptiPlex 3050, i3-7100T, 8GB, không GPU rời),
     trigger bằng event nào từ robot, và fallback khi mất mạng. -->

---

## 6. Deployment

| Unit | Built by | Deployed how | Target |
|---|---|---|---|
| `robot/` ROS 2 | GitHub Actions -> DockerHub | `docker compose pull && up -d` | robot miniPC |
| `robot/` firmware | GitHub Actions (compile only) | manual ST-Link flash | STM32G431 |
| `backend/` | <!-- TODO(WP2) --> | <!-- TODO(WP2) --> | <!-- TODO(WP2) --> |
| `web/` | <!-- TODO(WP5) --> | <!-- TODO(WP5) --> | <!-- TODO(WP5) --> |

CI never flashes the STM32 and the miniPC never auto-flashes it — see
[ADR-0002](decisions/0002-manual-stlink-flash-no-can-bootloader.md).
