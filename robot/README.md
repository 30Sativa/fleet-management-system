# fleet-management-system

## Architecture

This repository contains the robot-side software for the **CampusTour DT-AMR**
autonomous mobile robot (ROS 2 Humble + Nav2).

ROS 2 packages under `robot/ros2_ws/src/`:

| Package | Role |
|---|---|
| `stm32_bridge` | `/cmd_vel` -> STM32 motor controller over USB CDC serial; publishes odom + sonar |
| `robot_control` | mode manager (cmd_vel mux), manual / manual-mapping / auto-explore launches, Nav2 + SLAM configs, frontier explorer |
| `robot_description` | URDF/xacro robot model, Gazebo + display launches |
| `robot_navigation` | localization (map_server + AMCL) and navigation on a saved map |
| `orbbec_bringup` | Astra Pro depth camera bringup + mount TF + Phase 2 depth diagnostics |
| `robot_perception` | Phase 4 person perception -> Nav2 speed limit |
| `bus_manager` | `go_to_stop` action: drive to named bus stops via Nav2 |
| `bus_interfaces` | action/msg definitions for the bus system |
| `simulation` | Gazebo worlds/models for testing without hardware |

`robot/firmware/stm32/motor_controller` is the STM32G431 firmware for the HBS57H
STEP/DIR motor controller.

The miniPC runs the ROS 2 side; the STM32 is a separately flashed real-time
motor board. ROS 2 sends wheel-speed commands over USB serial; the STM32 owns
the stepping logic.

## Sensors & architecture

LiDAR + encoder/IMU are the navigation backbone; the Astra Pro is a
supplementary RGB-D perception sensor, **not** the primary localization source.

```
RPLiDAR A3M1 -> /scan               -> local + global costmap, AMCL, SLAM
encoder + IMU (STM32) -> /odom       -> odom -> base_footprint TF
Astra Pro -> /camera/depth/points    -> local costmap ONLY (3D obstacles)
Astra Pro -> RGB                     -> Phase 4 person detection
```

## Build phases

The robot software was brought up in four phases; each has a design doc under
`docs/` with run steps, close-out criteria, and an error table:

1. **Phase 1 — Camera** (`docs/phase1-camera.md`): Astra Pro streaming
   RGB/Depth/CameraInfo/TF reliably into RViz2.
2. **Phase 2 — 3D perception** (`docs/phase2-perception.md`): depth ->
   PointCloud2, with quantitative checks (depth accuracy, TF, ground-plane
   tilt, ground noise) via `orbbec_bringup depth_check`.
3. **Phase 3 — Nav2** (`docs/phase3-nav2.md`): Astra point cloud feeds the
   local costmap for obstacle avoidance; verified with
   `orbbec_bringup costmap_contrib`.
4. **Phase 4 — person perception** (`docs/phase4-ai.md`): RGB person detection
   (YOLO / OpenVINO on the mini PC) -> Nav2 speed limit. This is navigation
   perception, not the WP4 AI tour-guide assistant in `ai-assistant/`.

## Current Deployment Workflow

1. Develop and test on the laptop.
2. Push code to GitHub.
3. GitHub Actions builds the ROS2 Docker image.
4. Pull requests only build/check the image; they do not push to DockerHub.
5. Pushes to `main` or `master` build and push the Docker image to DockerHub.
6. The robot miniPC pulls the image from DockerHub and runs it with Docker
   Compose.
7. STM32 firmware is flashed manually with ST-Link when needed.

This workflow does not implement a CAN bootloader and does not auto-flash the
STM32 from the miniPC or from GitHub Actions.

## Docker Compose Environments

Chỉ còn **một** file: `robot/docker-compose.yml`. Mỗi máy chọn một profile.

| Profile | Máy | Service | Image | USB devices | GUI |
|---|---|---|---|---|---|
| `hardware` | robot miniPC | `robot-ros2` | Prebuilt DockerHub image | STM32, LiDAR, gamepad | không |
| `debug` | Ubuntu guest trong VMware | `ros2-debug` | Build local -> `robot-ros2:dev` | **không có** | X11 tới X server của VM |

Mọi service đều nằm sau profile, nên `docker compose up` trần sẽ không khởi
động gì. Nhờ vậy trên VMware không thể vô tình start service hardware và gặp
lỗi `error gathering device information ... /dev/ttyACM0: no such file or directory`.

`devices:` chỉ tồn tại trong service `robot-ros2`. Anchor `x-ros2-env` dùng
chung chỉ chứa biến môi trường ROS, không chứa devices, nên service debug không
thể kế thừa serial port.

### Networking giữa VMware và miniPC

Cả hai máy phải dùng **cùng `ROS_DOMAIN_ID`** và cùng cấu hình discovery.

- LAN đang dùng **chặn UDP multicast** (đã xác nhận, xem
  `docs/network-ros-discovery.md`), nên Fast DDS Discovery Server là **bắt buộc**,
  không phải tùy chọn. Nếu bỏ trống, VMware chỉ thấy `/rosout` và
  `/parameter_events`.
- Set `ROS_DISCOVERY_SERVER=<MINIPC_IP>:11811` (ví dụ `192.168.1.87:11811`) trong
  `.env` của **cả hai** máy. Không bao giờ dùng `127.0.0.1` trên VMware — địa chỉ
  đó trỏ về chính VM.
- miniPC phải đang chạy `fastdds-discovery.service`:
  `systemctl status fastdds-discovery.service`
- VMware network adapter phải ở chế độ **Bridged** (không phải NAT) để guest nằm
  cùng LAN với miniPC.
- Node nào start **trước** khi biến có hiệu lực thì vẫn dùng discovery cũ — restart
  container sau khi sửa `.env`.

### Chạy trên miniPC

```bash
cd robot
cp .env.example .env      # lần đầu: điền DOCKER_IMAGE, ROS_DOMAIN_ID
docker compose --profile hardware pull
docker compose --profile hardware up -d
docker exec -it robot-ros2 bash
```

Trong container:

```bash
ros2 launch robot_control manual_mapping.launch.py \
  port:=$SERIAL_PORT lidar_serial_port:=$LIDAR_PORT
```

### Chạy trên VMware (debug + RViz2)

```bash
cd robot
cp .env.example .env      # ROS_DOMAIN_ID phải giống miniPC
xhost +local:docker       # cho container nói chuyện với X server của VM
docker compose --profile debug up -d --build
docker exec -it ros2-debug bash
```

Nếu miniPC dùng Discovery Server, truyền IP LAN của nó vào — không hard-code
trong compose:

```bash
ROS_DISCOVERY_SERVER=192.168.1.87:11811 docker compose --profile debug up -d
```

Kiểm tra đã thấy ROS graph của miniPC chưa (chạy trong `ros2-debug`):

```bash
ros2 node list
ros2 topic list
ros2 topic echo /scan
```

Mở RViz2:

```bash
rviz2
```

Source được mount live tại `/ros2_ws/src`, nên có thể sửa code trên VM rồi
build lại trong container:

```bash
colcon build --symlink-install && source /ros2_ws/install/setup.bash
```

Không launch stack điều khiển robot thật từ container debug. VMware chỉ dùng
cho `rviz2`, `ros2 topic`, `ros2 service`, `tf2_echo` và các thao tác chỉ đọc,
trong khi miniPC sở hữu phần cứng.

Khi xong, thu hồi quyền X11:

```bash
xhost -local:docker
```


## How To Build Docker Image Locally

The Dockerfile defaults to ROS2 Humble because the current ROS2 packages and
docs in this repo target Humble.

```bash
docker build -t robot-ros2:local .
```

Run the built image interactively:

```bash
docker run --rm -it --network host robot-ros2:local
```

Run the bridge from inside the container:

```bash
ros2 launch stm32_bridge stm32_bridge.launch.py port:=/dev/ttyACM0 baudrate:=115200
```

Run the real-robot manual stack:

```bash
ros2 launch robot_control manual_mode.launch.py port:=/dev/ttyACM0 baudrate:=115200
```

The manual launch does not start keyboard teleop. In a second terminal, run:

```bash
ros2 run teleop_twist_keyboard teleop_twist_keyboard --ros-args -r cmd_vel:=/cmd_vel_manual
```

Run manual mapping:

```bash
ros2 launch robot_control manual_mapping.launch.py port:=/dev/ttyACM0 lidar_serial_port:=/dev/ttyUSB0
```

Run keyboard teleop separately in another terminal with the same
`/cmd_vel_manual` remap.

Run auto explore:

```bash
ros2 launch robot_control auto_explore.launch.py port:=/dev/ttyACM0 lidar_serial_port:=/dev/ttyUSB0
```

Navigate on a saved map (build a map first — there is no default real-world map):

```bash
ros2 launch robot_navigation navigation.launch.py map:=/path/to/my_map.yaml
```

Run in simulation (Gazebo, uses the bundled `warehouse_12x12` map):

```bash
ros2 launch robot_navigation sim_navigation.launch.py
```

Add `rviz:=true` to any launch above to open RViz with the matching layout
(off by default so a headless robot does not hang).

## How To Push Through GitHub Actions

The workflow lives at `.github/workflows/docker-build-push.yml`.

The workflow has an easy-to-edit `DOCKER_IMAGE` placeholder:

```yaml
env:
  DOCKER_IMAGE: dockerhub-username/robot-ros2
```

Example:

```yaml
env:
  DOCKER_IMAGE: yourname/robot-ros2
```

If you leave the placeholder unchanged, pushes to `main` or `master` resolve it
to `${DOCKERHUB_USERNAME}/robot-ros2` using the GitHub secret username. Edit
`DOCKER_IMAGE` if you want a different DockerHub repository name.

On pull requests, the workflow builds the image only. On pushes to `main` or
`master`, it pushes two tags:

- `latest`
- the short git SHA, for example `a1b2c3d`

## Required GitHub Secrets

Set these secrets in the GitHub repository settings:

- `DOCKERHUB_USERNAME`
- `DOCKERHUB_TOKEN`

Do not commit DockerHub tokens, passwords, ST-Link credentials, or machine
secrets into this repository.

## How miniPC Pulls And Runs The Image

The robot compose file is `docker-compose.yml`. A ready-to-copy template is
at `robot/.env.example` — `.env` itself is git-ignored, never commit it:

```bash
cp .env.example .env
nano .env   # fill in your real DOCKER_IMAGE
```

Example `.env` on the miniPC:

```bash
DOCKER_IMAGE=307sativa/robot-ros2:0f26981
SERIAL_PORT=/dev/ttyACM0
BAUDRATE=115200
ROS_DOMAIN_ID=0
```

Start or update the robot runtime:

```bash
docker compose pull
docker compose up -d
```

When GitHub Actions publishes a new image, update `.env` to the new commit SHA
on both the miniPC and VMware before comparing results. Use `git pull` only when
the compose file or other runtime configuration changed; pulling a new image
does not require a repository update.

If the STM32 appears as `/dev/ttyUSB0` instead of `/dev/ttyACM0`, change:

```bash
SERIAL_PORT=/dev/ttyUSB0
```

The compose file uses `network_mode: host` so ROS2 discovery and local robot
communication work more naturally on the real miniPC.

## STM32 Firmware Build Check

The STM32 workflow lives at `.github/workflows/stm32-build.yml`.

It only compiles the firmware and uploads artifacts. It does not flash the
board.

The current firmware project has a generated STM32CubeIDE makefile under:

```text
robot/firmware/stm32/motor_controller/Debug/makefile
```

The generated makefile contains a Windows absolute linker-script path, so the
CI job patches that path inside the GitHub Actions runner before running
`make`. This patch is only for CI portability and does not change the checked-in
firmware source code.

The workflow uploads these artifacts when build succeeds:

- `MotorController_G431.elf`
- `MotorController_G431.bin`
- `MotorController_G431.hex`
- `MotorController_G431.map`
- `MotorController_G431.list`

## STM32 Flashing Policy

- STM32 flashing is manual through ST-Link.
- GitHub Actions must never flash the STM32.
- The miniPC must not auto-flash the STM32.
- This workflow does not include a CAN bootloader.
- Do not change the STM32 serial protocol or motor-control logic unless a
  separate task explicitly asks for it.

Current ROS2 serial defaults:

- `SERIAL_PORT=/dev/ttyACM0`
- `BAUDRATE=115200`
