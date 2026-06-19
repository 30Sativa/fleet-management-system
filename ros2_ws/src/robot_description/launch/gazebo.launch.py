# =============================================================================
# gazebo.launch.py
# Spawn robot vào Gazebo Classic + nạp ros2_control controllers.
#   ros2 launch robot_description gazebo.launch.py
# Sau khi chạy, lái thử:
#   ros2 run teleop_twist_keyboard teleop_twist_keyboard \
#        --ros-args -r /cmd_vel:=/diff_drive_controller/cmd_vel_unstamped
# =============================================================================
import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (DeclareLaunchArgument, IncludeLaunchDescription,
                            RegisterEventHandler)
from launch.event_handlers import OnProcessExit
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command, LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    pkg = get_package_share_directory('robot_description')
    gazebo_ros = get_package_share_directory('gazebo_ros')
    xacro_file = os.path.join(pkg, 'urdf', 'robot.urdf.xacro')

    robot_description = ParameterValue(
        Command(['xacro ', xacro_file, ' use_sim:=true']),
        value_type=str,
    )

    rsp = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        output='screen',
        parameters=[{'robot_description': robot_description,
                     'use_sim_time': True}],
    )

    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(gazebo_ros, 'launch', 'gazebo.launch.py')),
    )

    spawn = Node(
        package='gazebo_ros',
        executable='spawn_entity.py',
        arguments=['-topic', 'robot_description', '-entity', 'amr_robot',
                   '-z', '0.15'],
        output='screen',
    )

    # nạp controllers SAU khi entity spawn xong
    jsb = Node(
        package='controller_manager', executable='spawner',
        arguments=['joint_state_broadcaster'],
        output='screen',
    )
    ddc = Node(
        package='controller_manager', executable='spawner',
        arguments=['diff_drive_controller'],
        output='screen',
    )

    return LaunchDescription([
        rsp,
        gazebo,
        spawn,
        RegisterEventHandler(OnProcessExit(target_action=spawn,
                                           on_exit=[jsb])),
        RegisterEventHandler(OnProcessExit(target_action=jsb,
                                           on_exit=[ddc])),
    ])
