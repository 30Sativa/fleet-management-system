# Orbbec depth-camera bringup

This package owns only robot-specific integration: the static transform from
`base_link` to the **Orbbec Astra Pro** and a stable launch entry point. Keep
the vendor driver in `ros2_ws/src/third_party/`; do not copy its launch files
into `robot_control`.

## 1. Driver selected for this camera

The label identifies this camera as **Astra Pro**, which is part of the legacy
OpenNI family. Use Orbbec's `ros2_astra_camera` repository, which builds the
`astra_camera` package and launches it with `astra_pro.launch.xml`. Do **not**
use the `orbbec_camera` / `astra2.launch.py` defaults intended for Astra 2.

Before first launch, capture the USB IDs on the miniPC:

```bash
lsusb -d 2bc5:
```

The driver defaults to the Astra Pro RGB UVC product ID `0x0501`. If `lsusb`
shows an Astra Pro FHD RGB device with product ID `0502`, pass
`uvc_product_id:=0x0502` in the launch command below.

## 2. Put the legacy source and SDK in one predictable location

```bash
cd ~/fleet-management-system/ros2_ws/src
mkdir -p third_party
git clone https://github.com/orbbec/ros2_astra_camera.git third_party/ros2_astra_camera
```

The legacy driver also needs its matching `openNISDK_ROS2_*.tar.gz` package
from Orbbec. Extract that SDK under `ros2_ws/src/` as instructed by the driver
README, then install its udev rules on the **miniPC host**:

```bash
cd ~/fleet-management-system/ros2_ws/src/third_party/ros2_astra_camera/astra_camera/scripts
sudo bash install.sh
sudo udevadm control --reload-rules && sudo udevadm trigger
```

That driver requires `libuvc`, too. Build/install it on the miniPC image before
building the ROS workspace, following the vendor driver's instructions. After
adding the driver and SDK, rebuild the Docker image because `Dockerfile` copies
all of `ros2_ws/src`.

```bash
cd ~/fleet-management-system
docker build -t robot-ros2:orbbec .
```

## 3. Start the camera and robot mount transform

Measure the camera origin relative to `base_link` in metres.  The template is
at `config/mount.example.yaml`.  Start with the real values below rather than
the zero placeholders:

```bash
ros2 launch orbbec_bringup orbbec_with_mount.launch.py \
  x:=0.25 y:=0.0 z:=0.35 roll:=0.0 pitch:=0.0 yaw:=0.0
```

Example for the FHD UVC variant:

```bash
ros2 launch orbbec_bringup orbbec_with_mount.launch.py \
  uvc_product_id:=0x0502 \
  x:=0.25 y:=0.0 z:=0.35
```

Do not launch this through the production `docker-compose.yml` yet: that
compose service currently only forwards the STM32 serial device.  First verify
the camera in an interactive container with the needed `/dev/video*` and USB
devices passed through.  Once the exact model is confirmed and topics are
validated, add its device mapping and the camera launch to the production
bringup deliberately.

## 4. Validate before using depth data

```bash
ros2 topic list | grep -E 'camera|depth|color|points'
ros2 run tf2_ros tf2_echo base_link camera_link
ros2 service call /camera/get_device_info astra_camera_msgs/srv/GetDeviceInfo '{}'
rviz2
```

In RViz, set the fixed frame to `base_link`, then add the driver's depth image
and point cloud topics.  Confirm the image axes and TF orientation before
using the data for obstacle avoidance or Nav2.
