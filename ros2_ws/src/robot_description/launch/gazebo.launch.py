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
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (DeclareLaunchArgument, IncludeLaunchDescription,
                            OpaqueFunction, RegisterEventHandler)
from launch.conditions import IfCondition
from launch.event_handlers import OnProcessExit
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def setup_gazebo(context):
    pkg = get_package_share_directory('robot_description')
    gazebo_ros = get_package_share_directory('gazebo_ros')
    xacro_file = os.path.join(pkg, 'urdf', 'robot.urdf.xacro')

    world = LaunchConfiguration('world')
    gui = LaunchConfiguration('gui')
    load_controllers = LaunchConfiguration('load_controllers')
    use_ros2_control = LaunchConfiguration('use_ros2_control')

    # ===== Chay xacro ROI XOA HET COMMENT =====
    # Ly do: gazebo_ros2_control tren Humble bi loi 'Couldn't parse param
    # override rule' khi URDF co comment XML (dau '<', xuong dong) o dau file.
    # Strip comment -> URDF sach -> plugin nap controller_manager thanh cong.
    raw = subprocess.check_output(
        ['xacro', xacro_file, 'use_sim:=true',
         'use_ros2_control:=' + use_ros2_control.perform(context)]).decode('utf-8')
    clean_urdf = re.sub(r'<!--.*?-->', '', raw, flags=re.DOTALL).strip()

    # Doi 'package://robot_description/' -> duong dan TUYET DOI trong install.
    # Ly do: gzclient chay rieng khong phan giai duoc 'package://' -> khong tim
    # thay mesh STL -> robot vo hinh (chi thay lidar/imu la primitive). Duong
    # dan tuyet doi thi gzclient/gzserver/RViz deu load duoc.
    clean_urdf = clean_urdf.replace('package://robot_description/', pkg + '/')

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
                   '-z', '0.05', '-timeout', '120.0'],
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

    return [
        rsp,
        gazebo,
        spawn,
        RegisterEventHandler(OnProcessExit(target_action=spawn,
                                           on_exit=[jsb])),
        RegisterEventHandler(OnProcessExit(target_action=jsb,
                                           on_exit=[ddc])),
    ]


def generate_launch_description():
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
        DeclareLaunchArgument(
            'use_ros2_control', default_value='true',
            description='Load gazebo_ros2_control from the robot URDF when true.'),
        # gazebo_ros tu nap init/factory plugin va tu thiet lap cac duong dan
        # Gazebo. Khong override GAZEBO_* o day: tren VMware, override co the
        # khien libgazebo_ros_factory.so khong dang ky /spawn_entity.
        # Mesh cua robot da duoc doi thanh duong dan tuyet doi trong setup_gazebo.
        OpaqueFunction(function=setup_gazebo),
    ])
