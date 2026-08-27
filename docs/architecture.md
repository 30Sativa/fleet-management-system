# System Architecture

How the pieces of CampusTour DT-AMR fit together. This file covers what
crosses a folder boundary. Anything internal to one folder is documented
inside that folder.

- Robot internals: [`robot/README.md`](../robot/README.md)
- Digital Twin internals: [`digital-twin/README.md`](../digital-twin/README.md)
- Backend internals: `backend/AGENTS.md` <!-- TODO(WP2) -->
- AI tour-guide internals: [`ai-assistant/README.md`](../ai-assistant/README.md)
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
   +-----------------------------------------+       +------------------------+
   |  robot/   ROS 2 fleet + STM32 firmware   |  ???  |  ai-assistant/         |
   |  person perception + thin audio adapter  |<----->|  STT + dialogue + TTS |
   +-----------------------------------------+       +------------------------+
                         |
                         | ??? twin synchronization
                         v
   +-----------------------------------------+
   |  digital-twin/ scenarios + measurements  |
   +-----------------------------------------+
```

`???` marks cross-deploy-unit contracts that are not fixed yet. The assistant
box is deliberately outside `robot/`; Section 5 defines the ownership boundary.

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
                       (`robot_perception`, not the AI tour guide)
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

`robot/ros2_ws/src/simulation/` and `digital-twin/` have different purposes:

| Concern | Location | Responsibility |
|---|---|---|
| Robot simulation | `robot/ros2_ws/src/simulation/` | Minimal Gazebo worlds and launches for developing/testing the robot stack without hardware |
| Digital Twin | `digital-twin/` | Live state synchronization, scenario orchestration, replay and repeatable latency/accuracy experiments |

The Digital Twin runs on a simulation workstation/server, never on the robot
miniPC. It must not duplicate the authoritative robot model, navigation logic
or ROS interfaces from `robot/`, and a scenario result must not directly
command a physical robot. Applying a validated route or schedule goes through
the authenticated backend/operator workflow.

> **INTERFACE NOT DECIDED YET.** WP2 and WP3 must define the synchronization
> transport, telemetry schema, timestamp/clock policy, update rate and replay
> format here before implementing the bridge. The experiment runner must record
> enough configuration and timing data for latency/accuracy results to be
> reproduced.

---

## 5. AI tour-guide assistant

`robot_perception` and the AI tour-guide assistant are separate systems with
different owners and safety boundaries:

| Concern | Owner | Runs on | Responsibility |
|---|---|---|---|
| Person perception | WP3, `robot/ros2_ws/src/robot_perception/` | robot miniPC | RGB-D person detection and Nav2 speed limiting |
| AI tour guide | WP4, `ai-assistant/` | server/cloud | multilingual STT, campus knowledge/dialogue and TTS |

`robot_perception` does not answer visitor questions, generate narration or
own campus content. The AI tour guide does not publish `/cmd_vel`, set Nav2
goals, alter `/speed_limit`, or make any movement/safety decision.

A future thin robot-side adapter may listen for stop/task events, capture or
forward visitor audio, play returned speech and use cached narration when the
assistant is unavailable. That adapter belongs in `robot/`; STT, retrieval,
LLM/dialogue and TTS orchestration belong in `ai-assistant/`.

> **INTERFACE NOT DECIDED YET.** Before either side implements the integration,
> WP3 and WP4 must define the event/audio transport, schemas, authentication,
> timeouts and offline fallback here. Until then, neither side should hardcode
> cross-boundary field names.

---

## 6. Deployment

| Unit | Built by | Deployed how | Target |
|---|---|---|---|
| `robot/` ROS 2 | GitHub Actions -> DockerHub | `docker compose pull && up -d` | robot miniPC |
| `robot/` firmware | GitHub Actions (compile only) | manual ST-Link flash | STM32G431 |
| `digital-twin/` | <!-- TODO(WP3) --> | service/container | simulation workstation/server |
| `backend/` | <!-- TODO(WP2) --> | <!-- TODO(WP2) --> | <!-- TODO(WP2) --> |
| `ai-assistant/` | <!-- TODO(WP4) --> | service/container | server/cloud, not robot miniPC |
| `web/` | <!-- TODO(WP5) --> | <!-- TODO(WP5) --> | <!-- TODO(WP5) --> |

CI never flashes the STM32 and the miniPC never auto-flashes it — see
[ADR-0002](decisions/0002-manual-stlink-flash-no-can-bootloader.md).
