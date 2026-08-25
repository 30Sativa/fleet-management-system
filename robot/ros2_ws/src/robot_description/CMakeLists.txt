cmake_minimum_required(VERSION 3.8)
project(robot_description)

find_package(ament_cmake REQUIRED)

# Install resource directories so other packages / launch files can find them
install(
  DIRECTORY urdf launch config rviz meshes
  DESTINATION share/${PROJECT_NAME}
)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  ament_lint_auto_find_test_dependencies()

  find_package(Python3 REQUIRED COMPONENTS Interpreter)
  enable_testing()
  add_test(
    NAME robot_description_mesh_references
    COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/test/test_mesh_references.py"
  )
endif()

ament_package()
