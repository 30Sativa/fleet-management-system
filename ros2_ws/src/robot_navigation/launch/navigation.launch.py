# =============================================================================
# navigation.launch.py
# REAL ROBOT: navigate on a SAVED map (no SLAM, no explorer).
#
# Chain:
#   goal (RViz "Nav2 Goal" / bus_manager stop_navigator) -> Nav2 -> /cmd_vel_nav
#     -> mode_manager (explore mode accepts nav; manual teleop overrides)
#     -> /cmd_vel -> STM32 bridge
#   Localization: map_server + AMCL (map -> odom TF), scan from RPLiDAR.
#
# Prerequisite: a map saved earlier with either mapping mode:
#   ros2 launch robot_control manual_mapping.launch.py   (drive by hand)
#   ros2 launch robot_control auto_explore.launch.py     (vacuum-style)
# then:
#   ros2 run nav2_map_server map_saver_cli -f <path>/my_map
#
# Run:
#   ros2 launch robot_navigation navigation.launch.py map:=/path/to/my_map.yaml
# =============================================================================
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, GroupAction, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node, SetRemap
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    port = LaunchConfiguration('port')
    baudrate = LaunchConfiguration('baudrate')
    use_sim_time = LaunchConfiguration('use_sim_time')
    lidar_serial_port = LaunchConfiguration('lidar_serial_port')
    lidar_serial_baudrate = LaunchConfiguration('lidar_serial_baudrate')
    lidar_frame = LaunchConfiguration('lidar_frame')
    scan_mode = LaunchConfiguration('scan_mode')
    enable_lidar = LaunchConfiguration('enable_lidar')
    enable_teleop = LaunchConfiguration('enable_teleop')
    map_yaml = LaunchConfiguration('map')
    localization_params_file = LaunchConfiguration('localization_params_file')
    nav2_params_file = LaunchConfiguration('nav2_params_file')

    manual_launch = PathJoinSubstitution([
        FindPackageShare('robot_control'),
        'launch',
        'manual_mode.launch.py',
    ])
    localization_launch = PathJoinSubstitution([
        FindPackageShare('robot_navigation'),
        'launch',
        'localization.launch.py',
    ])
    nav2_launch = PathJoinSubstitution([
        FindPackageShare('nav2_bringup'),
        'launch',
        'navigation_launch.py',
    ])
    default_map = PathJoinSubstitution([
        FindPackageShare('robot_navigation'),
        'maps',
        'map.yaml',
    ])
    default_localization_params = PathJoinSubstitution([
        FindPackageShare('robot_navigation'),
        'config',
        'localization_params.yaml',
    ])
    default_nav2_params = PathJoinSubstitution([
        FindPackageShare('robot_control'),
        'config',
        'nav2_params.yaml',
    ])

    return LaunchDescription([
        DeclareLaunchArgument('port', default_value='/dev/ttyACM0',
                              description='STM32 USB CDC serial port.'),
        DeclareLaunchArgument('baudrate', default_value='115200',
                              description='STM32 serial baudrate.'),
        DeclareLaunchArgument('use_sim_time', default_value='false',
                              description='Use simulation clock.'),
        DeclareLaunchArgument('lidar_serial_port', default_value='/dev/ttyUSB0',
                              description='RPLiDAR serial port.'),
        DeclareLaunchArgument('lidar_serial_baudrate', default_value='256000',
                              description='RPLiDAR A3M1 serial baudrate.'),
        DeclareLaunchArgument('lidar_frame', default_value='lidar_link',
                              description='LaserScan frame_id.'),
        DeclareLaunchArgument('scan_mode', default_value='Sensitivity',
                              description='RPLiDAR scan mode (A3: Sensitivity/Boost).'),
        DeclareLaunchArgument('enable_lidar', default_value='true',
                              description='Launch rplidar_ros node.'),
        DeclareLaunchArgument('enable_teleop', default_value='false',
                              description='Optional manual override teleop.'),
        DeclareLaunchArgument('map', default_value=default_map,
                              description='Full path to the saved map .yaml.'),
        DeclareLaunchArgument('localization_params_file',
                              default_value=default_localization_params,
                              description='AMCL / map_server parameter file.'),
        DeclareLaunchArgument('nav2_params_file',
                              default_value=default_nav2_params,
                              description='Nav2 parameter file.'),

        # 1) Base bringup: robot_state_publisher + STM32 bridge + mode manager.
        #    initial_mode=explore so Nav2's /cmd_vel_nav drives the robot;
        #    manual teleop still overrides (manual_priority_in_explore).
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(manual_launch),
            launch_arguments={
                'port': port,
                'baudrate': baudrate,
                'initial_mode': 'explore',
                'use_sim_time': use_sim_time,
                'enable_teleop': enable_teleop,
            }.items(),
        ),

        # 2) LiDAR -> /scan (AMCL + costmaps).
        Node(
            package='rplidar_ros',
            executable='rplidar_node',
            name='rplidar_node',
            output='screen',
            condition=IfCondition(enable_lidar),
            parameters=[{
                'channel_type': 'serial',
                'serial_port': lidar_serial_port,
                'serial_baudrate': ParameterValue(
                    lidar_serial_baudrate, value_type=int),
                'frame_id': lidar_frame,
                'inverted': False,
                'angle_compensate': True,
                'scan_mode': scan_mode,
            }],
        ),

        # 3) Localization on the saved map (replaces slam_toolbox).
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(localization_launch),
            launch_arguments={
                'map': map_yaml,
                'use_sim_time': use_sim_time,
                'params_file': localization_params_file,
            }.items(),
        ),

        # 4) Nav2, velocity output remapped to /cmd_vel_nav for the mux.
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
    ])
