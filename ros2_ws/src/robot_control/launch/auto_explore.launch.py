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
    enable_explorer = LaunchConfiguration('enable_explorer')
    slam_params_file = LaunchConfiguration('slam_params_file')
    nav2_params_file = LaunchConfiguration('nav2_params_file')
    explorer_params_file = LaunchConfiguration('explorer_params_file')

    manual_launch = PathJoinSubstitution([
        FindPackageShare('robot_control'),
        'launch',
        'manual_mode.launch.py',
    ])
    rviz_config = PathJoinSubstitution([
        FindPackageShare('robot_control'),
        'rviz',
        'manual_mapping.rviz',
    ])
    slam_launch = PathJoinSubstitution([
        FindPackageShare('slam_toolbox'),
        'launch',
        'online_async_launch.py',
    ])
    nav2_launch = PathJoinSubstitution([
        FindPackageShare('nav2_bringup'),
        'launch',
        'navigation_launch.py',
    ])
    default_slam_params = PathJoinSubstitution([
        FindPackageShare('robot_control'),
        'config',
        'slam_toolbox_online_async.yaml',
    ])
    default_nav2_params = PathJoinSubstitution([
        FindPackageShare('robot_control'),
        'config',
        'nav2_params.yaml',
    ])
    default_explorer_params = PathJoinSubstitution([
        FindPackageShare('robot_control'),
        'config',
        'frontier_explorer.yaml',
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
        DeclareLaunchArgument('enable_explorer', default_value='true',
                              description='Launch simple frontier explorer.'),
        DeclareLaunchArgument('slam_params_file',
                              default_value=default_slam_params,
                              description='slam_toolbox parameter file.'),
        DeclareLaunchArgument(
            'rviz', default_value='false',
            description='Open RViz with the mapping layout. Default false so a '
                        'headless robot does not hang; run RViz on your dev '
                        'machine, or pass rviz:=true when you have a screen.'),
        DeclareLaunchArgument('nav2_params_file',
                              default_value=default_nav2_params,
                              description='Nav2 parameter file.'),
        DeclareLaunchArgument('explorer_params_file',
                              default_value=default_explorer_params,
                              description='Frontier explorer parameter file.'),

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

        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(slam_launch),
            launch_arguments={
                'use_sim_time': use_sim_time,
                'slam_params_file': slam_params_file,
            }.items(),
        ),

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

        Node(
            package='robot_control',
            executable='simple_frontier_explorer',
            name='simple_frontier_explorer',
            output='screen',
            condition=IfCondition(enable_explorer),
            parameters=[explorer_params_file],
        ),
        Node(
            package='rviz2',
            executable='rviz2',
            name='rviz2',
            arguments=['-d', rviz_config],
            output='screen',
            condition=IfCondition(LaunchConfiguration('rviz')),
        ),
    ])
