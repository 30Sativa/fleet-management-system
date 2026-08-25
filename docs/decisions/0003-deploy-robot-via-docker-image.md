# ADR-0003: The robot runs a prebuilt Docker image

## Context

The robot miniPC is a Dell OptiPlex 3050 Micro (i3-7100T, 8 GB, no discrete
GPU). Building a ROS 2 workspace on it is slow, and a build that fails halfway
leaves the robot in a state where nothing runs.

Development happens on a laptop, sometimes inside a VM, with a different USB
stack and different package versions from the miniPC — so "it built on my
machine" is not evidence it will run on the robot.

## Decision

The deployment artifact is a Docker image.

1. Develop and test on the laptop.
2. Push to GitHub.
3. GitHub Actions builds the ROS 2 image (build context `robot/`).
4. Pull requests build only. Pushes to `main`/`master` push `latest` and a
   short-SHA tag to DockerHub.
5. The miniPC runs `docker compose pull && docker compose up -d`.

There is no "git pull and colcon build on the robot" path.

Maps are stored on the host and bind-mounted (`./robot_maps:/maps`) so a map
the robot built survives an image update. The Astra Pro runs natively on the
host, not in the container; `network_mode: host` plus a shared `ROS_DOMAIN_ID`
keeps discovery working across that boundary.

## Consequences

Positive:

- What runs on the robot is byte-identical to what CI built.
- Rollback is retagging to an earlier short SHA.
- The miniPC never spends its CPU on compilation.

Negative:

- Every code change requires a CI round trip before it can run on the robot,
  which is slow for a one-line fix.
- Requires network on the robot to pull an update.
- The container/host split for the camera is a real source of confusion and has
  to be remembered whenever discovery breaks.
- Image size and DockerHub rate limits become operational concerns.
