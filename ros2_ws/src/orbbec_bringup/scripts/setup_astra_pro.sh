#!/usr/bin/env bash
# Host-side preparation for the Orbbec Astra Pro on ROS 2 Humble (Ubuntu 22.04).
#
# Run this ONCE on the machine that will physically hold the USB cable - the
# Ubuntu VM during bring-up, the miniPC later.  udev rules and libuvc live on
# the host; they are not something a Docker image can provide for you.
#
#   bash ros2_ws/src/orbbec_bringup/scripts/setup_astra_pro.sh
#
# It is safe to re-run.
set -euo pipefail

ROS_DISTRO="${ROS_DISTRO:-humble}"
WS_SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
DRIVER_DIR="${WS_SRC}/third_party/ros2_astra_camera"

echo "==> workspace src : ${WS_SRC}"
echo "==> ROS distro    : ${ROS_DISTRO}"

echo "==> [1/5] apt dependencies"
sudo apt-get update
sudo apt-get install -y --no-install-recommends \
  build-essential cmake git pkg-config \
  libgflags-dev libgoogle-glog-dev libusb-1.0-0-dev libeigen3-dev \
  "ros-${ROS_DISTRO}-image-geometry" \
  "ros-${ROS_DISTRO}-camera-info-manager" \
  "ros-${ROS_DISTRO}-image-transport" \
  "ros-${ROS_DISTRO}-image-publisher" \
  "ros-${ROS_DISTRO}-cv-bridge" \
  "ros-${ROS_DISTRO}-tf2-sensor-msgs" \
  usbutils v4l-utils

echo "==> [2/5] libuvc (built from source; no apt package carries the API the driver needs)"
if pkg-config --exists libuvc; then
  echo "    libuvc already installed: $(pkg-config --modversion libuvc)"
else
  TMP="$(mktemp -d)"
  git clone --depth 1 https://github.com/libuvc/libuvc.git "${TMP}/libuvc"
  cmake -S "${TMP}/libuvc" -B "${TMP}/libuvc/build" -DCMAKE_BUILD_TYPE=Release
  cmake --build "${TMP}/libuvc/build" -j"$(nproc)"
  sudo cmake --install "${TMP}/libuvc/build"
  sudo ldconfig
  rm -rf "${TMP}"
fi

echo "==> [3/5] vendor driver source"
if [ -d "${DRIVER_DIR}/.git" ]; then
  echo "    already present at ${DRIVER_DIR}"
else
  mkdir -p "${WS_SRC}/third_party"
  git clone --depth 1 https://github.com/orbbec/ros2_astra_camera.git "${DRIVER_DIR}"
fi
# The OpenNI2 redistributable (x64 / arm / arm64) ships inside this repo under
# astra_camera/openni2_redist.  There is no separate SDK tarball to download.

echo "==> [4/5] udev rules"
sudo bash "${DRIVER_DIR}/astra_camera/scripts/install.sh"
sudo udevadm control --reload-rules
sudo udevadm trigger

echo "==> [5/5] what the kernel currently sees"
lsusb -d 2bc5: || echo "    !! no 2bc5 device on the bus - see the README troubleshooting table"
ls -l /dev/video* 2>/dev/null || echo "    !! no /dev/video* node - the RGB (UVC) half is not attached"

cat <<'NEXT'

Done.  Next:

  cd <workspace root>
  colcon build --symlink-install --cmake-args -DCMAKE_BUILD_TYPE=Release
  source install/setup.bash
  ros2 launch orbbec_bringup orbbec_with_mount.launch.py rviz:=true

Unplug and replug the camera once after the udev step, otherwise the rules do
not apply to the already-enumerated device.
NEXT
