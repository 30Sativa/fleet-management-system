# Third-party ROS sources

Place cloned vendor ROS packages here temporarily when building the robot image.
The robot uses an Orbbec Astra Pro. Clone `ros2_astra_camera` and place the
matching OpenNI SDK here as described in `../orbbec_bringup/README.md`.

Do not commit a vendor checkout here unless the project intentionally pins it
as a Git submodule or vendored dependency.
