from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command, LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    port = LaunchConfiguration('port')
    baudrate = LaunchConfiguration('baudrate')
    wheel_base = LaunchConfiguration('wheel_base')
    wheel_radius = LaunchConfiguration('wheel_radius')
    max_wheel_speed_mm_s = LaunchConfiguration('max_wheel_speed_mm_s')
    speed_scale = LaunchConfiguration('speed_scale')
    invert_left = LaunchConfiguration('invert_left')
    invert_right = LaunchConfiguration('invert_right')
    base_frame = LaunchConfiguration('base_frame')
    odom_frame = LaunchConfiguration('odom_frame')
    initial_mode = LaunchConfiguration('initial_mode')
    use_sim_time = LaunchConfiguration('use_sim_time')
    enable_teleop = LaunchConfiguration('enable_teleop')

    robot_xacro = PathJoinSubstitution([
        FindPackageShare('robot_description'),
        'urdf',
        'robot.urdf.xacro',
    ])
    robot_description = ParameterValue(
        Command(['xacro ', robot_xacro, ' use_sim:=false']),
        value_type=str,
    )

    stm32_bridge_launch = PathJoinSubstitution([
        FindPackageShare('stm32_bridge'),
        'launch',
        'stm32_bridge.launch.py',
    ])
    mode_manager_config = PathJoinSubstitution([
        FindPackageShare('robot_control'),
        'config',
        'mode_manager.yaml',
    ])

    return LaunchDescription([
        DeclareLaunchArgument('port', default_value='/dev/ttyACM0',
                              description='STM32 USB CDC serial port.'),
        DeclareLaunchArgument('baudrate', default_value='115200',
                              description='STM32 serial baudrate.'),
        DeclareLaunchArgument('wheel_base', default_value='0.46',
                              description='Distance between driven wheels '
                                          '(center-to-center: ~46 cm).'),
        DeclareLaunchArgument('wheel_radius', default_value='0.095',
                              description='Real wheel radius for odometry.'),
        DeclareLaunchArgument('max_wheel_speed_mm_s', default_value='250.0',
                              description='Per-wheel safety clamp.'),
        DeclareLaunchArgument('speed_scale', default_value='0.3',
                              description='Bench-safe command scale.'),
        DeclareLaunchArgument(
            'invert_left', default_value='true',
            description='Invert left wheel command for the installed drivetrain.'),
        DeclareLaunchArgument(
            'invert_right', default_value='true',
            description='Invert right wheel command for the installed drivetrain.'),
        DeclareLaunchArgument('base_frame', default_value='base_footprint',
                              description='Bridge odometry child frame.'),
        DeclareLaunchArgument('odom_frame', default_value='odom',
                              description='Bridge odometry parent frame.'),
        DeclareLaunchArgument('initial_mode', default_value='manual',
                              description='manual or explore.'),
        DeclareLaunchArgument('use_sim_time', default_value='false',
                              description='Use simulation clock.'),
        DeclareLaunchArgument('enable_teleop', default_value='true',
                              description='Launch teleop_twist_keyboard.'),

        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            name='robot_state_publisher',
            output='screen',
            parameters=[{
                'robot_description': robot_description,
                'use_sim_time': ParameterValue(
                    use_sim_time, value_type=bool),
            }],
        ),

        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(stm32_bridge_launch),
            launch_arguments={
                'port': port,
                'baudrate': baudrate,
                'wheel_base': wheel_base,
                'wheel_radius': wheel_radius,
                'max_wheel_speed_mm_s': max_wheel_speed_mm_s,
                'speed_scale': speed_scale,
                'invert_left': invert_left,
                'invert_right': invert_right,
                'odom_frame': odom_frame,
                'base_frame': base_frame,
                'publish_odom': 'true',
                'publish_tf': 'true',
            }.items(),
        ),

        Node(
            package='robot_control',
            executable='mode_manager_node',
            name='mode_manager_node',
            output='screen',
            parameters=[
                mode_manager_config,
                {
                    'initial_mode': initial_mode,
                    'manual_timeout': 0.5,
                    'nav_timeout': 0.5,
                },
            ],
        ),

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
