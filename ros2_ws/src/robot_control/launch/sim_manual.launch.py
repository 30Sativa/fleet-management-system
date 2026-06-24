# =============================================================================
# sim_manual.launch.py
# Manual-mode test in Gazebo (no real STM32 / LiDAR needed), with optional SLAM
# so you can DRIVE AND BUILD A MAP at the same time (manual mapping).
#
# Chain:
#   teleop -> /cmd_vel_manual -> mode_manager -> /cmd_vel
#          -> relay -> /diff_drive_controller/cmd_vel_unstamped -> Gazebo robot
#   SLAM (optional): Gazebo /scan + odom/tf -> slam_toolbox -> /map
#
# The mode_manager mux (manual priority, timeout-to-zero, emergency stop) is
# exercised exactly like on the real robot; only the final hop differs:
# instead of stm32_bridge driving motors over USB, a topic relay feeds the
# Gazebo diff_drive_controller.
#
# Run (drive + build map):
#   ros2 launch robot_control sim_manual.launch.py enable_teleop:=false
#   # then in another terminal:
#   ros2 run teleop_twist_keyboard teleop_twist_keyboard \
#     --ros-args -r /cmd_vel:=/cmd_vel_manual
#   # watch the map grow in rviz2 (Fixed Frame: map, add Map + LaserScan)
#   # save it when done:
#   ros2 run nav2_map_server map_saver_cli -f ~/maps/manual_map
#
# Drive without mapping:
#   ros2 launch robot_control sim_manual.launch.py enable_slam:=false
# Emergency stop test:
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
    use_sim_time = LaunchConfiguration('use_sim_time')
    enable_teleop = LaunchConfiguration('enable_teleop')
    enable_slam = LaunchConfiguration('enable_slam')
    drive_cmd_topic = LaunchConfiguration('drive_cmd_topic')
    slam_params_file = LaunchConfiguration('slam_params_file')

    gazebo_launch = PathJoinSubstitution([
        FindPackageShare('robot_description'),
        'launch',
        'gazebo.launch.py',
    ])
    slam_launch = PathJoinSubstitution([
        FindPackageShare('slam_toolbox'),
        'launch',
        'online_async_launch.py',
    ])
    mode_manager_config = PathJoinSubstitution([
        FindPackageShare('robot_control'),
        'config',
        'mode_manager.yaml',
    ])
    default_slam_params = PathJoinSubstitution([
        FindPackageShare('robot_control'),
        'config',
        'slam_toolbox_online_async.yaml',
    ])

    return LaunchDescription([
        DeclareLaunchArgument(
            'world', default_value=default_world,
            description='Gazebo .world file to load.'),
        DeclareLaunchArgument(
            'use_sim_time', default_value='true',
            description='Use the Gazebo clock for all nodes.'),
        DeclareLaunchArgument(
            'enable_teleop', default_value='true',
            description='Launch teleop_twist_keyboard mapped to /cmd_vel_manual.'),
        DeclareLaunchArgument(
            'enable_slam', default_value='true',
            description='Launch slam_toolbox to build a map while driving.'),
        DeclareLaunchArgument(
            'drive_cmd_topic',
            default_value='/diff_drive_controller/cmd_vel_unstamped',
            description='Gazebo diff_drive_controller command topic.'),
        DeclareLaunchArgument(
            'slam_params_file', default_value=default_slam_params,
            description='slam_toolbox parameter file.'),

        # 1) Gazebo + robot + ros2_control diff_drive_controller.
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(gazebo_launch),
            launch_arguments={'world': world}.items(),
        ),

        # 2) Mode manager: selects /cmd_vel_manual vs /cmd_vel_nav -> /cmd_vel.
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
        Node(
            package='topic_tools',
            executable='relay',
            name='cmd_vel_sim_relay',
            output='screen',
            arguments=['/cmd_vel', drive_cmd_topic],
        ),

        # 4) SLAM (optional) -> builds /map from /scan while you drive.
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(slam_launch),
            condition=IfCondition(enable_slam),
            launch_arguments={
                'use_sim_time': use_sim_time,
                'slam_params_file': slam_params_file,
            }.items(),
        ),

        # 5) Teleop keyboard -> /cmd_vel_manual (NOT /cmd_vel directly).
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
