# orbbec_bringup — Orbbec Astra Pro (Phase 1)

This package owns the robot-specific half of the depth camera: a launch entry
point with sane parameters, the `base_link -> camera_link` mount transform, an
RViz layout for verification, and the host setup/verify scripts.  The vendor
driver stays untouched in `ros2_ws/src/third_party/`.

## 1. What the Astra Pro actually is

The Astra Pro is **two USB devices in one plastic shell**:

| Half | Protocol | USB id | Driven by |
|---|---|---|---|
| Depth + IR | OpenNI2 | `2bc5:0403` | `astra_camera_node` via the bundled OpenNI2 redist |
| RGB | plain UVC webcam | `2bc5:0501` (`0502` on FHD units) | `astra_camera_node` via libuvc |

Three consequences that shape everything below:

- The driver is Orbbec's **legacy** [`ros2_astra_camera`](https://github.com/orbbec/ros2_astra_camera).
  `OrbbecSDK_ROS2` is for Astra 2 / Gemini / Femto and does **not** cover this camera.
- `use_uvc_camera` must be `true` and `uvc_product_id` must match `lsusb`, or
  depth works and RGB is silently missing.
- **Hardware depth-to-color registration does not exist on this camera.**  The
  colour sensor is not visible to OpenNI2, so there is nothing to align against
  in hardware.  `depth_registration` and `enable_colored_point_cloud` stay
  `false`; an aligned/coloured cloud is a Phase 2 problem solved by calibrating
  both cameras and running `depth_image_proc::RegisterNode`.

The OpenNI2 redistributable (`x64`, `arm`, `arm64`) ships **inside** the driver
repository under `astra_camera/openni2_redist`.  There is no separate
`openNISDK_ROS2_*.tar.gz` to download.

## 2. One-time host setup

udev rules and libuvc belong to the machine holding the USB cable — the Ubuntu
VM now, the miniPC later.  A Docker image cannot supply them for you.

```bash
bash ros2_ws/src/orbbec_bringup/scripts/setup_astra_pro.sh
```

It installs the apt dependencies, builds libuvc from source, clones the vendor
driver into `ros2_ws/src/third_party/ros2_astra_camera`, installs
`56-orbbec-usb.rules`, and prints what the kernel currently sees.

**Unplug and replug the camera after this step** — udev rules do not apply
retroactively to an already-enumerated device.

Then build:

```bash
cd ros2_ws
colcon build --symlink-install --cmake-args -DCMAKE_BUILD_TYPE=Release
source install/setup.bash
```

## 3. Running

```bash
ros2 launch orbbec_bringup orbbec_with_mount.launch.py \
  x:=0.25 y:=0.0 z:=0.35 \
  rviz:=true
```

`x/y/z/roll/pitch/yaw` are the **measured** offset from `base_link` to the
camera body, in metres and radians, ROS convention (x forward, y left, z up).
Measure them; do not leave the zeros.

FHD variant (check `lsusb -d 2bc5:` first):

```bash
ros2 launch orbbec_bringup orbbec_with_mount.launch.py uvc_product_id:=0x0502
```

Driver only, no mount TF:

```bash
ros2 launch orbbec_bringup astra_pro.launch.py
```

### Parameter defaults chosen here and why

| Parameter | Vendor default | Ours | Reason |
|---|---|---|---|
| `enable_ir` | `true` | `false` | Depth and IR share one sensor; requesting both is the most common cause of a driver that opens and then stalls |
| `depth_registration` | `false` | `false` | Not supported on this camera — kept explicit so nobody "fixes" it |
| `enable_colored_point_cloud` | `false` | `false` | Requires the above |
| `uvc_product_id` | `0x0501` | `0x0501` | Override to `0x0502` on FHD units |

## 4. Phase 1 acceptance

With the launch running, in a second terminal:

```bash
source install/setup.bash
bash ros2_ws/src/orbbec_bringup/scripts/verify_astra_pro.sh
```

Phase 1 is done when every check passes **and holds for 60 seconds** — a driver
that streams for five seconds and dies is the normal Astra Pro failure mode, so
a snapshot check is not enough.

Expected interface:

```
/camera/color/image_raw        sensor_msgs/Image        ~30 Hz
/camera/color/camera_info      sensor_msgs/CameraInfo
/camera/depth/image_raw        sensor_msgs/Image        ~30 Hz  (16UC1, mm)
/camera/depth/camera_info      sensor_msgs/CameraInfo
/camera/depth/points           sensor_msgs/PointCloud2
/camera/ir/image_raw           (only when enable_ir:=true)
```

TF published by the driver, under `camera_link`:

```
camera_link
├── camera_depth_frame  → camera_depth_optical_frame
└── camera_color_frame  → camera_color_optical_frame
```

and `base_link -> camera_link` from `camera_mount.launch.py`.

Note: the driver publishes `camera_color_frame` with two parents
(`camera_link` and `camera_depth_frame`).  That is a quirk of the vendor code,
not a bug in this package, and it does not block Phase 1 — but it is why you
should read the tree with `ros2 run tf2_tools view_frames` rather than trusting
it by eye.

## 5. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `lsusb -d 2bc5:` shows nothing | VM did not claim the device / cable is charge-only | Connect **both** Astra entries to the guest; use a data cable |
| Only `2bc5:0403` shows | The UVC half went to the host, or to a different VM device slot | Attach the second entry too |
| Depth streams, RGB never appears | Wrong `uvc_product_id` | `ros2 launch ... uvc_product_id:=0x0502` |
| `Permission denied` / `uvc_open failed` | udev rules not applied | Re-run `install.sh`, `udevadm trigger`, then **replug** |
| `libuvc is not found` at build time | libuvc not installed or not on the pkg-config path | Re-run `setup_astra_pro.sh`, then `sudo ldconfig` |
| Driver starts then hangs after a few frames | USB bandwidth, or IR enabled with depth | `enable_ir:=false`; drop to `depth_fps:=15`; give the VM a USB 3.x controller |
| Topics list but RViz shows nothing | QoS mismatch | `ros2 topic info -v /camera/depth/points`; set RViz reliability to match |
| RViz2 crashes / black 3D view in the VM | No GPU passthrough | `export LIBGL_ALWAYS_SOFTWARE=1` before `rviz2` |
| `color/camera_info` looks wrong | It is the factory guess, not this unit | Calibrate with `camera_calibration`, pass `color_info_url:=file:///...` |

## 6. Not in Phase 1, deliberately

Docker packaging, depth→laserscan, Nav2 integration, RGB intrinsic
calibration, and depth-to-colour alignment are all Phase 2+.  The production
`docker-compose.yml` currently forwards only the STM32 serial device; add the
camera's `/dev/bus/usb` and `/dev/video*` mappings **after** the camera is
proven on bare metal, not before.
