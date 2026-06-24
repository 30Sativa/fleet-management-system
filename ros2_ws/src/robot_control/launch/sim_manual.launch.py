# =============================================================================
# sim_manual.launch.py
# Manual-mode test in Gazebo (no real STM32 / LiDAR needed).
#
# Chain:
#   teleop -> /cmd_vel_manual -> mode_manager -> /cmd_vel
#          -> relay -> /diff_drive_controller/cmd_vel_unstamped -> Gazebo robot
#
# The mode_manager mux (manual priority, timeout-to-zero, emergency stop) is
# exercised exactly like on the real robot; only the final hop differs:
# instead of stm32_bridge driving motors over USB, a topic relay feeds the
# Gazebo diff_drive_controller.
#
# Run:
#   ros2 launch robot_control sim_manual.launch.py
# Drive with the teleop window (i/,/j/l/k). Stop test:
#   ros2 service call /emergency_stop std_srvs/srv/SetBool "{data: true}"
# =============================================================================
import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    default_world = os.path.join(
        get_package_share_directory('simulation'),
        'worlds', 'warehouse_12x12.world')
    world = LaunchConfiguration('world')
    enable_teleop = LaunchConfiguration('enable_teleop')
    drive_cmd_topic = LaunchConfiguration('drive_cmd_topic')

    gazebo_launch = PathJoinSubstitution([
        FindPackageShare('robot_description'),
        'launch',
        'gazebo.launch.py',
    ])
    mode_manager_config = PathJoinSubstitution([
        FindPackageShare('robot_control'),
        'config',
        'mode_manager.yaml',
    ])

    return LaunchDescription([
        DeclareLaunchArgument(
            'enable_teleop', default_value='true',
            description='Launch teleop_twist_keyboard mapped to /cmd_vel_manual.'),
        DeclareLaunchArgument(
            'drive_cmd_topic',
            default_value='/diff_drive_controller/cmd_vel_unstamped',
            description='Gazebo diff_drive_controller command topic.'),

        # 1) Gazebo + robot + ros2_control diff_drive_controller.
        DeclareLaunchArgument(
            'world', default_value=default_world,
            description='Gazebo .world file to load.'),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(gazebo_launch),
            launch_arguments={'world': world}.items(),
        ),

        # 2) Mode manager: selects /cmd_vel_manual vs /cmd_vel_nav -> /cmd_vel.
        #    use_sim_time so timeouts use the Gazebo clock.
        Node(
            package='robot_control',
            executable='mode_manager_node',
            name='mode_manager_node',
            output='screen',
            parameters=[
                mode_manager_config,
                {
                    'initial_mode': 'manual',
                    'use_sim_time': True,
                },
            ],
        ),

        # 3) Bridge the mux output into the Gazebo controller.
        #    /cmd_vel (Twist) -> /diff_drive_controller/cmd_vel_unstamped (Twist).
        Node(
            package='topic_tools',
            executable='relay',
            name='cmd_vel_sim_relay',
            output='screen',
            arguments=['/cmd_vel', drive_cmd_topic],
        ),

        # 4) Teleop keyboard -> /cmd_vel_manual (NOT /cmd_vel directly).
        Node(
            package='teleop_twist_keyboard',
            executable='teleop_twist_keyboard',
            name='teleop_keyboard',
            output='screen',
            emulate_tty=True,
            condition=IfCondition(enable_teleop),
            remappings=[
                ('cmd_vel', '/cmd_vel_manual'),
                ('/cmd_vel', '/cmd_vel_manual'),
            ],
        ),
    ])
