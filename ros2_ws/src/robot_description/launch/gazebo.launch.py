# =============================================================================
# gazebo.launch.py
# Spawn robot vao Gazebo Classic + nap ros2_control controllers.
#   ros2 launch robot_description gazebo.launch.py
# Lai thu:
#   ros2 run teleop_twist_keyboard teleop_twist_keyboard \
#        --ros-args -r /cmd_vel:=/diff_drive_controller/cmd_vel_unstamped
# =============================================================================
import os
from ament_index_python.packages import get_package_share_directory, get_package_prefix
from launch import LaunchDescription
from launch.actions import (DeclareLaunchArgument, IncludeLaunchDescription,
                            RegisterEventHandler, SetEnvironmentVariable,
                            TimerAction)
from launch.event_handlers import OnProcessExit
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command, LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    pkg = get_package_share_directory('robot_description')
    gazebo_ros = get_package_share_directory('gazebo_ros')
    xacro_file = os.path.join(pkg, 'urdf', 'robot.urdf.xacro')

    # ===== QUAN TRONG: bao Gazebo biet cho tim plugin .so =====
    # Vi mac dinh GAZEBO_PLUGIN_PATH thuong rong -> Gazebo khong nap duoc
    # libgazebo_ros2_control.so -> khong co controller_manager -> robot khong chay.
    ros_lib = os.path.join(get_package_prefix('gazebo_ros2_control'), 'lib')
    set_plugin_path = SetEnvironmentVariable(
        name='GAZEBO_PLUGIN_PATH',
        value=ros_lib + ':' + os.environ.get('GAZEBO_PLUGIN_PATH', ''),
    )

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

    # nap controllers SAU khi entity spawn xong
    jsb = Node(
        package='controller_manager', executable='spawner',
        arguments=['joint_state_broadcaster',
                   '--controller-manager', '/controller_manager'],
        output='screen',
    )
    ddc = Node(
        package='controller_manager', executable='spawner',
        arguments=['diff_drive_controller',
                   '--controller-manager', '/controller_manager'],
        output='screen',
    )

    return LaunchDescription([
        set_plugin_path,
        rsp,
        gazebo,
        spawn,
        # cho spawn xong roi nap joint_state_broadcaster, roi toi diff_drive
        RegisterEventHandler(OnProcessExit(target_action=spawn,
                                           on_exit=[jsb])),
        RegisterEventHandler(OnProcessExit(target_action=jsb,
                                           on_exit=[ddc])),
    ])
