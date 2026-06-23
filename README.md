# fleet-management-system

## Architecture

This repository contains the robot-side software for a small autonomous
vehicle:

- `ros2_ws/` is the ROS2 workspace used by the miniPC.
- `ros2_ws/src/stm32_bridge` is the current real-robot bridge from `/cmd_vel`
  to the STM32 motor controller over USB CDC serial.
- `ros2_ws/src/robot_description` contains the URDF/xacro robot model and
  simulation/display launch files.
- `firmware/stm32/motor_controller` contains the STM32G431 firmware project for
  the HBS57H STEP/DIR motor controller.

The miniPC runs the ROS2 side in Docker. The STM32 remains a separately flashed
motor-control board. ROS2 sends high-level wheel speed commands over USB serial;
the STM32 owns the real-time motor stepping logic.

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

The robot compose file is `docker-compose.yml`.

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
firmware/stm32/motor_controller/Debug/makefile
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
