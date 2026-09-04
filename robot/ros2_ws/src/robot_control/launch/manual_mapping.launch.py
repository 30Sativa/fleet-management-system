from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
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
    slam_params_file = LaunchConfiguration('slam_params_file')

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
    default_slam_params = PathJoinSubstitution([
        FindPackageShare('robot_control'),
        'config',
        'slam_toolbox_online_async.yaml',
    ])
    scan_filter_params = PathJoinSubstitution([
        FindPackageShare('robot_control'),
        'config',
        'scan_range_filter.yaml',
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
        DeclareLaunchArgument('slam_params_file',
                              default_value=default_slam_params,
                              description='slam_toolbox parameter file.'),
        DeclareLaunchArgument(
            'rviz', default_value='false',
            description='Open RViz with the mapping layout. Default false so a '
                        'headless robot does not hang; run RViz on your dev '
                        'machine, or pass rviz:=true when you have a screen.'),

        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(manual_launch),
            launch_arguments={
                'port': port,
                'baudrate': baudrate,
                'initial_mode': 'manual',
                'use_sim_time': use_sim_time,
            }.items(),
        ),

        # RPLiDAR publishes the RAW scan onto /scan_raw. The range filter below
        # reads /scan_raw, drops every point closer than the vehicle body
        # radius, and republishes the clean scan onto /scan. SLAM and both
        # costmaps still read /scan, so nothing downstream needs to change.
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
            remappings=[('scan', 'scan_raw')],
        ),

        # Range filter: removes LiDAR returns that hit the robot's own body
        # (everything closer than lower_threshold in scan_range_filter.yaml).
        # /scan_raw -> filter -> /scan. Needs: sudo apt install ros-humble-laser-filters
        Node(
            package='laser_filters',
            executable='scan_to_scan_filter_chain',
            name='scan_range_filter',
            output='screen',
            condition=IfCondition(enable_lidar),
            parameters=[scan_filter_params],
            remappings=[
                ('scan', 'scan_raw'),
                ('scan_filtered', 'scan'),
            ],
        ),

        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(slam_launch),
            launch_arguments={
                'use_sim_time': use_sim_time,
                'slam_params_file': slam_params_file,
            }.items(),
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
