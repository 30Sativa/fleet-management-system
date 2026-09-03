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

Use the compose file that matches the machine. The product compose is for the
robot miniPC; the dev compose is for the Ubuntu guest inside VMware on the
Windows development machine.

| Environment | Compose file | Image/source | USB devices | RViz | Intended use |
|---|---|---|---|---|---|
| Product / robot miniPC | `docker-compose.yml` | Prebuilt DockerHub image | STM32, LiDAR, gamepad | Off by default | Deployed runtime |
| Dev / Ubuntu VMware | `docker-compose.dev.yml` | Built locally, source mounted | None by default; `hardware` profile adds STM32 + LiDAR | X11 to Ubuntu VM | Build, Gazebo, RViz, hardware mapping |

### Dev on Ubuntu VMware

Run these commands inside the Ubuntu VM, from the `robot/` directory. The
Windows host path is not used by Docker directly; clone or mount the repository
inside the Ubuntu guest and run Docker there.

Allow local containers to connect to the VM X server before opening RViz:

```bash
xhost +local:docker
docker compose -f docker-compose.dev.yml up -d --build robot-ros2-dev
docker exec -it robot-ros2-dev bash
```

Inside the container, source is mounted at `/ros2_ws/src`. Rebuild after source
changes, then launch simulation or display with `rviz:=true`:

```bash
colcon build --symlink-install
source /ros2_ws/install/setup.bash
ros2 launch robot_description display.launch.py
# or:
ros2 launch robot_control sim_manual.launch.py rviz:=true
```

For real-robot mapping, first connect the STM32 and RPLiDAR to the Ubuntu VM
through VMware USB passthrough, then verify their names:

```bash
ls -l /dev/ttyACM* /dev/ttyUSB*
```

Start the hardware profile and run the mapping launch inside its container:

```bash
docker compose -f docker-compose.dev.yml --profile hardware up -d --build robot-ros2-dev-hardware
docker exec -it robot-ros2-dev-hardware bash

ros2 launch robot_control manual_mapping.launch.py \
  port:=/dev/ttyACM0 \
  lidar_serial_port:=/dev/ttyUSB0 \
  rviz:=true
```

If the device names differ, set them on the compose command:

```bash
SERIAL_PORT_DEV=/dev/ttyACM1 LIDAR_PORT_DEV=/dev/ttyUSB1 \
docker compose -f docker-compose.dev.yml --profile hardware up -d robot-ros2-dev-hardware
```

The Astra Pro remains a native Ubuntu-VM device as documented in the camera
bring-up notes; its ROS topics can be consumed by the container through
`network_mode: host` and the same `ROS_DOMAIN_ID`. Do not start the product and
dev containers for the same robot at the same time, because both could publish
commands and odometry.

When finished with the dev VM X11 permission:

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

Run manual mapping:

```bash
ros2 launch robot_control manual_mapping.launch.py port:=/dev/ttyACM0 lidar_serial_port:=/dev/ttyUSB0
```

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
DOCKER_IMAGE=yourname/robot-ros2:latest
SERIAL_PORT=/dev/ttyACM0
BAUDRATE=115200
ROS_DOMAIN_ID=0
```

Start or update the robot runtime:

```bash
docker compose pull
docker compose up -d
```

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
