# =============================================================================
# gazebo.launch.py
# Spawn robot vao Gazebo Classic + nap ros2_control controllers.
#   ros2 launch robot_description gazebo.launch.py
# Lai thu:
#   ros2 run teleop_twist_keyboard teleop_twist_keyboard \
#        --ros-args -r /cmd_vel:=/diff_drive_controller/cmd_vel_unstamped
# =============================================================================
import os
import re
import subprocess
from ament_index_python.packages import get_package_share_directory, get_package_prefix
from launch import LaunchDescription
from launch.actions import (DeclareLaunchArgument, IncludeLaunchDescription,
                            RegisterEventHandler, SetEnvironmentVariable)
from launch.conditions import IfCondition
from launch.event_handlers import OnProcessExit
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg = get_package_share_directory('robot_description')
    gazebo_ros = get_package_share_directory('gazebo_ros')
    xacro_file = os.path.join(pkg, 'urdf', 'robot.urdf.xacro')

    # Optional Gazebo world (.world). Empty -> default empty world.
    world = LaunchConfiguration('world')
    gui = LaunchConfiguration('gui')
    load_controllers = LaunchConfiguration('load_controllers')

    # ===== Bao Gazebo cho tim plugin .so (mac dinh GAZEBO_PLUGIN_PATH thuong rong) =====
    ros_lib = os.path.join(get_package_prefix('gazebo_ros2_control'), 'lib')
    set_plugin_path = SetEnvironmentVariable(
        name='GAZEBO_PLUGIN_PATH',
        value=ros_lib + ':' + os.environ.get('GAZEBO_PLUGIN_PATH', ''),
    )

    # ===== Chay xacro ROI XOA HET COMMENT =====
    # Ly do: gazebo_ros2_control tren Humble bi loi 'Couldn't parse param
    # override rule' khi URDF co comment XML (dau '<', xuong dong) o dau file.
    # Strip comment -> URDF sach -> plugin nap controller_manager thanh cong.
    raw = subprocess.check_output(
        ['xacro', xacro_file, 'use_sim:=true']).decode('utf-8')
    clean_urdf = re.sub(r'<!--.*?-->', '', raw, flags=re.DOTALL).strip()

    rsp = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        output='screen',
        parameters=[{'robot_description': clean_urdf,
                     'use_sim_time': True}],
    )

    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(gazebo_ros, 'launch', 'gazebo.launch.py')),
        launch_arguments={'world': world, 'gui': gui}.items(),
    )

    spawn = Node(
        package='gazebo_ros',
        executable='spawn_entity.py',
        arguments=['-topic', 'robot_description', '-entity', 'amr_robot',
                   '-z', '0.15'],
        output='screen',
    )

    jsb = Node(
        package='controller_manager', executable='spawner',
        arguments=['joint_state_broadcaster',
                   '--controller-manager', '/controller_manager'],
        condition=IfCondition(load_controllers),
        output='screen',
    )
    ddc = Node(
        package='controller_manager', executable='spawner',
        arguments=['diff_drive_controller',
                   '--controller-manager', '/controller_manager'],
        condition=IfCondition(load_controllers),
        output='screen',
    )

    return LaunchDescription([
        DeclareLaunchArgument(
            'world', default_value='',
            description='Path to a Gazebo .world file. Empty = empty world.'),
        DeclareLaunchArgument(
            'gui', default_value='true',
            description='Start gzclient GUI when true.'),
        DeclareLaunchArgument(
            'load_controllers', default_value='true',
            description='Spawn ros2_control controllers when true.'),
        set_plugin_path,
        rsp,
        gazebo,
        spawn,
        RegisterEventHandler(OnProcessExit(target_action=spawn,
                                           on_exit=[jsb])),
        RegisterEventHandler(OnProcessExit(target_action=jsb,
                                           on_exit=[ddc])),
    ])
