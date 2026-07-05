# =============================================================================
# sim_navigation.launch.py
# GAZEBO: navigate on a SAVED map (no SLAM, no explorer, no real hardware).
#
# Chain:
#   RViz "Nav2 Goal" -> Nav2 -> /cmd_vel_nav
#     -> mode_manager (explore) -> /cmd_vel
#     -> relay -> /diff_drive_controller/cmd_vel_unstamped -> Gazebo robot
#   Localization: map_server + AMCL using Gazebo /scan.
#
# Prerequisite: save a map of the sim world first, e.g.
#   ros2 launch robot_control sim_manual.launch.py   (or sim_auto_explore)
#   ros2 run nav2_map_server map_saver_cli -f \
#       <ros2_ws>/src/robot_navigation/maps/warehouse_12x12
#
# Run:
#   ros2 launch robot_navigation sim_navigation.launch.py \
#       map:=/path/to/warehouse_12x12.yaml
#
# NOTE: the robot spawns at the world origin, which matches AMCL's default
# initial pose (0,0,0) IF the map was recorded starting from the same spawn
# point. Otherwise use RViz "2D Pose Estimate".
# =============================================================================
import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (DeclareLaunchArgument, GroupAction,
                            IncludeLaunchDescription)
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node, SetRemap
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    default_world = os.path.join(
        get_package_share_directory('simulation'),
        'worlds', 'warehouse_12x12.world')
    world = LaunchConfiguration('world')
    use_sim_time = LaunchConfiguration('use_sim_time')
    enable_teleop = LaunchConfiguration('enable_teleop')
    drive_cmd_topic = LaunchConfiguration('drive_cmd_topic')
    map_yaml = LaunchConfiguration('map')
    localization_params_file = LaunchConfiguration('localization_params_file')
    nav2_params_file = LaunchConfiguration('nav2_params_file')

    gazebo_launch = PathJoinSubstitution([
        FindPackageShare('robot_description'), 'launch', 'gazebo.launch.py',
    ])
    localization_launch = PathJoinSubstitution([
        FindPackageShare('robot_navigation'), 'launch',
        'localization.launch.py',
    ])
    nav2_launch = PathJoinSubstitution([
        FindPackageShare('nav2_bringup'), 'launch', 'navigation_launch.py',
    ])
    mode_manager_config = PathJoinSubstitution([
        FindPackageShare('robot_control'), 'config', 'mode_manager.yaml',
    ])
    default_map = PathJoinSubstitution([
        FindPackageShare('robot_navigation'), 'maps', 'warehouse_12x12.yaml',
    ])
    default_localization_params = PathJoinSubstitution([
        FindPackageShare('robot_navigation'), 'config',
        'localization_params.yaml',
    ])
    default_nav2_params = PathJoinSubstitution([
        FindPackageShare('robot_control'), 'config', 'nav2_params.yaml',
    ])

    return LaunchDescription([
        DeclareLaunchArgument(
            'use_sim_time', default_value='true',
            description='Use the Gazebo clock for all nodes.'),
        DeclareLaunchArgument(
            'enable_teleop', default_value='false',
            description='Optional manual override teleop -> /cmd_vel_manual.'),
        DeclareLaunchArgument(
            'drive_cmd_topic',
            default_value='/diff_drive_controller/cmd_vel_unstamped',
            description='Gazebo diff_drive_controller command topic.'),
        DeclareLaunchArgument(
            'map', default_value=default_map,
            description='Full path to the saved map .yaml.'),
        DeclareLaunchArgument(
            'localization_params_file',
            default_value=default_localization_params,
            description='AMCL / map_server parameter file.'),
        DeclareLaunchArgument(
            'nav2_params_file', default_value=default_nav2_params,
            description='Nav2 parameter file.'),
        DeclareLaunchArgument(
            'world', default_value=default_world,
            description='Gazebo .world file to load.'),

        # 1) Gazebo + robot + diff_drive_controller (publishes /scan, odom, tf).
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(gazebo_launch),
            launch_arguments={'world': world}.items(),
        ),

        # 2) Mode manager mux -> /cmd_vel, starting in explore (nav source).
        Node(
            package='robot_control',
            executable='mode_manager_node',
            name='mode_manager_node',
            output='screen',
            parameters=[
                mode_manager_config,
                {
                    'initial_mode': 'explore',
                    'use_sim_time': True,
                },
            ],
        ),

        # 3) Relay /cmd_vel -> Gazebo controller command topic.
        Node(
            package='topic_tools',
            executable='relay',
            name='cmd_vel_sim_relay',
            output='screen',
            arguments=['/cmd_vel', drive_cmd_topic],
        ),

        # 4) Localization on the saved map (replaces slam_toolbox).
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(localization_launch),
            launch_arguments={
                'map': map_yaml,
                'use_sim_time': use_sim_time,
                'params_file': localization_params_file,
            }.items(),
        ),

        # 5) Nav2, velocity output remapped to /cmd_vel_nav for the mux.
        GroupAction([
            SetRemap(src='cmd_vel', dst='/cmd_vel_nav'),
            SetRemap(src='/cmd_vel', dst='/cmd_vel_nav'),
            SetRemap(src='cmd_vel_smoothed', dst='/cmd_vel_nav'),
            SetRemap(src='/cmd_vel_smoothed', dst='/cmd_vel_nav'),
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(nav2_launch),
                launch_arguments={
                    'use_sim_time': use_sim_time,
                    'params_file': nav2_params_file,
                    'autostart': 'true',
                }.items(),
            ),
        ]),

        # 6) Optional manual override teleop -> /cmd_vel_manual (mux priority).
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
