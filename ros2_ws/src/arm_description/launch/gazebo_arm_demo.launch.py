# =============================================================================
# gazebo_arm_demo.launch.py
# ALL-IN-ONE: mo Gazebo + spawn tay + nap controller + TU CHAY pick_demo.
# Chi 1 lenh la tay tu dien chuoi gap. Tach biet hoan toan voi xe.
#   ros2 launch arm_description gazebo_arm_demo.launch.py
# =============================================================================
import os
import re
import subprocess
from ament_index_python.packages import (get_package_share_directory,
                                         get_package_prefix)
from launch import LaunchDescription
from launch.actions import (DeclareLaunchArgument, IncludeLaunchDescription,
                            RegisterEventHandler, SetEnvironmentVariable,
                            TimerAction, ExecuteProcess)
from launch.event_handlers import OnProcessExit
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg = get_package_share_directory('arm_description')
    gazebo_ros = get_package_share_directory('gazebo_ros')
    xacro_file = os.path.join(pkg, 'urdf', 'arm_sim.urdf.xacro')
    default_world = os.path.join(pkg, 'worlds', 'arm_demo.world')

    world = LaunchConfiguration('world')
    auto_demo = LaunchConfiguration('auto_demo')

    ros_lib = os.path.join(get_package_prefix('gazebo_ros2_control'), 'lib')
    set_plugin_path = SetEnvironmentVariable(
        name='GAZEBO_PLUGIN_PATH',
        value=ros_lib + ':' + os.environ.get('GAZEBO_PLUGIN_PATH', ''),
    )

    raw = subprocess.check_output(['xacro', xacro_file]).decode('utf-8')
    clean_urdf = re.sub(r'<!--.*?-->', '', raw, flags=re.DOTALL).strip()

    rsp = Node(
        package='robot_state_publisher', executable='robot_state_publisher',
        output='screen',
        parameters=[{'robot_description': clean_urdf, 'use_sim_time': True}],
    )

    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(gazebo_ros, 'launch', 'gazebo.launch.py')),
        launch_arguments={'world': world}.items(),
    )

    spawn = Node(
        package='gazebo_ros', executable='spawn_entity.py',
        arguments=['-topic', 'robot_description', '-entity', 'scara_arm',
                   '-z', '0.0'],
        output='screen',
    )

    jsb = Node(
        package='controller_manager', executable='spawner',
        arguments=['joint_state_broadcaster',
                   '--controller-manager', '/controller_manager'],
        output='screen',
    )
    arm_ctrl = Node(
        package='controller_manager', executable='spawner',
        arguments=['arm_controller',
                   '--controller-manager', '/controller_manager'],
        output='screen',
    )

    # pick_demo: chay sau khi arm_controller san sang + cho them 3s cho on dinh
    pick = Node(
        package='arm_description', executable='pick_demo',
        output='screen',
    )

    return LaunchDescription([
        DeclareLaunchArgument(
            'world', default_value=default_world,
            description='Gazebo .world file (mac dinh = arm_demo, co 1 lon).'),
        DeclareLaunchArgument(
            'auto_demo', default_value='true',
            description='true = tu chay pick_demo sau khi controller san sang.'),
        set_plugin_path,
        rsp,
        gazebo,
        spawn,
        RegisterEventHandler(OnProcessExit(target_action=spawn, on_exit=[jsb])),
        RegisterEventHandler(OnProcessExit(
            target_action=jsb,
            on_exit=[arm_ctrl,
                     # doi 4s sau khi controller len roi moi chay demo
                     TimerAction(period=4.0, actions=[pick])])),
    ])
