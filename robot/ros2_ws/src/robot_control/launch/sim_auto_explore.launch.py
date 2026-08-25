# =============================================================================
# sim_auto_explore.launch.py
# Autonomous explore test in Gazebo (no real STM32 / LiDAR needed).
#
# Chain:
#   frontier_explorer -> Nav2 goal -> Nav2 -> /cmd_vel_nav
#     -> mode_manager (explore) -> /cmd_vel
#     -> relay -> /diff_drive_controller/cmd_vel_unstamped -> Gazebo robot
#   SLAM: Gazebo /scan + odom/tf -> slam_toolbox -> /map
#
# Everything runs on the Gazebo clock (use_sim_time:=true). The mode_manager
# starts in 'explore'; manual teleop can still override if enable_teleop:=true.
#
# Run:
#   ros2 launch robot_control sim_auto_explore.launch.py
# Watch in RViz: add Map, LaserScan, TF, and the Nav2 plugins.
#
# NOTE: Nav2 nodes need use_sim_time. nav2_bringup/navigation_launch.py and
# slam_toolbox both honor the use_sim_time launch argument and override the
# value baked into the params files, so we do not have to edit nav2_params.yaml.
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
    enable_explorer = LaunchConfiguration('enable_explorer')
    drive_cmd_topic = LaunchConfiguration('drive_cmd_topic')
    slam_params_file = LaunchConfiguration('slam_params_file')
    nav2_params_file = LaunchConfiguration('nav2_params_file')
    explorer_params_file = LaunchConfiguration('explorer_params_file')

    gazebo_launch = PathJoinSubstitution([
        FindPackageShare('robot_description'), 'launch', 'gazebo.launch.py',
    ])
    slam_launch = PathJoinSubstitution([
        FindPackageShare('slam_toolbox'), 'launch', 'online_async_launch.py',
    ])
    nav2_launch = PathJoinSubstitution([
        FindPackageShare('nav2_bringup'), 'launch', 'navigation_launch.py',
    ])
    mode_manager_config = PathJoinSubstitution([
        FindPackageShare('robot_control'), 'config', 'mode_manager.yaml',
    ])
    default_slam_params = PathJoinSubstitution([
        FindPackageShare('robot_control'), 'config',
        'slam_toolbox_online_async.yaml',
    ])
    default_nav2_params = PathJoinSubstitution([
        FindPackageShare('robot_control'), 'config', 'nav2_params.yaml',
    ])
    default_explorer_params = PathJoinSubstitution([
        FindPackageShare('robot_control'), 'config', 'frontier_explorer.yaml',
    ])

    return LaunchDescription([
        DeclareLaunchArgument(
            'use_sim_time', default_value='true',
            description='Use the Gazebo clock for all nodes.'),
        DeclareLaunchArgument(
            'enable_teleop', default_value='false',
            description='Optional manual override teleop -> /cmd_vel_manual.'),
        DeclareLaunchArgument(
            'enable_explorer', default_value='true',
            description='Launch the simple frontier explorer.'),
        DeclareLaunchArgument(
            'drive_cmd_topic',
            default_value='/diff_drive_controller/cmd_vel_unstamped',
            description='Gazebo diff_drive_controller command topic.'),
        DeclareLaunchArgument(
            'slam_params_file', default_value=default_slam_params,
            description='slam_toolbox parameter file.'),
        DeclareLaunchArgument(
            'nav2_params_file', default_value=default_nav2_params,
            description='Nav2 parameter file.'),
        DeclareLaunchArgument(
            'explorer_params_file', default_value=default_explorer_params,
            description='Frontier explorer parameter file.'),

        # 1) Gazebo + robot + diff_drive_controller (publishes /scan, odom, tf).
        DeclareLaunchArgument(
            'world', default_value=default_world,
            description='Gazebo .world file to load.'),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(gazebo_launch),
            launch_arguments={'world': world}.items(),
        ),

        # 2) Mode manager mux -> /cmd_vel, starting in explore.
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

        # 4) SLAM (online async mapping).
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(slam_launch),
            launch_arguments={
                'use_sim_time': use_sim_time,
                'slam_params_file': slam_params_file,
            }.items(),
        ),

        # 5) Nav2, with controller/smoother velocity output remapped to
        #    /cmd_vel_nav so it feeds the mux instead of /cmd_vel directly.
        GroupAction([
            # Nav2 Humble's navigation_launch.py already wires an internal
            # chain, and it uses BOTH of the names this stack cares about:
            #
            #   controller_server  pub "cmd_vel"           -\
            #   behavior_server    pub "cmd_vel"            |-> nav2 remaps to
            #   velocity_smoother  sub "cmd_vel"           -/   cmd_vel_nav
            #   velocity_smoother  pub "cmd_vel_smoothed"  ---> nav2 remaps to
            #                                                   cmd_vel
            #
            # SetRemap rules are inserted BEFORE a node's own remappings, and
            # rcl applies the FIRST matching rule. So remapping cmd_vel_smoothed
            # to /cmd_vel_nav made velocity_smoother publish onto the very topic
            # it subscribes to: a feedback loop. Its own output kept refreshing
            # last_command_time_, so the velocity_timeout stop never fired, and
            # /cmd_vel_nav ended up with two competing publishers (raw 10 Hz
            # controller + smoothed 20 Hz echo), which also defeats
            # mode_manager's nav_timeout watchdog.
            #
            # Fix: rename nav2's INTERNAL topic instead of its output, so each
            # topic has exactly one publisher:
            #
            #   controller_server -\
            #                       >-> /cmd_vel_ctrl -> velocity_smoother
            #   behavior_server   -/                          |
            #                                                 v
            #                     /cmd_vel_nav -> mode_manager -> /cmd_vel
            #
            # NOTE: SetRemap only reaches plain Node actions. Composable nodes
            # ignore it. navigation_launch.py defaults to use_composition:=False
            # so this works - but never pass use_composition:=True here or every
            # rule below is silently dropped and Nav2 drives /cmd_vel directly,
            # bypassing mode_manager and the e-stop.
            SetRemap(src='cmd_vel', dst='/cmd_vel_ctrl'),
            SetRemap(src='cmd_vel_smoothed', dst='/cmd_vel_nav'),
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(nav2_launch),
                launch_arguments={
                    'use_sim_time': use_sim_time,
                    'params_file': nav2_params_file,
                    'autostart': 'true',
                }.items(),
            ),
        ]),

        # 6) Frontier explorer -> sends NavigateToPose goals to Nav2.
        Node(
            package='robot_control',
            executable='simple_frontier_explorer',
            name='simple_frontier_explorer',
            output='screen',
            condition=IfCondition(enable_explorer),
            parameters=[
                explorer_params_file,
                {'use_sim_time': True},
            ],
        ),

        # 7) Optional manual override teleop -> /cmd_vel_manual (priority in mux).
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
