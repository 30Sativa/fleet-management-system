cmake_minimum_required(VERSION 3.8)
project(arm_description)

find_package(ament_cmake REQUIRED)

install(
  DIRECTORY urdf launch rviz config worlds
  DESTINATION share/${PROJECT_NAME}
)

# Demo gap theo kich ban co dinh (chay: ros2 run arm_description pick_demo)
install(
  PROGRAMS scripts/pick_demo.py
  DESTINATION lib/${PROJECT_NAME}
  RENAME pick_demo
)

ament_package()
