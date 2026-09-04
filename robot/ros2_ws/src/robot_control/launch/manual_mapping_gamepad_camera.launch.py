"""Manual mapping test stack for the real robot.

This launch intentionally contains no Nav2.  A gamepad drives the existing
manual command path, LiDAR feeds slam_toolbox, and the Astra Pro camera runs
alongside the mapping stack for a hardware smoke test.

The STM32 bridge also publishes both SR04T readings carried in its feedback as
sensor_msgs/Range. The URDF places LiDAR at the centre of the roof,
SONAR1 at the front centre, and SONAR2 at the rear centre; they are not inputs
to SLAM in this test.
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    robot_control = FindPackageShare('robot_control')
    orbbec = FindPackageShare('orbbec_bringup')

    mapping_launch = PathJoinSubstitution([
        robot_control, 'launch', 'manual_mapping.launch.py',
    ])
    camera_launch = PathJoinSubstitution([
        orbbec, 'launch', 'orbbec_with_mount.launch.py',
    ])
    gamepad_config = PathJoinSubstitution([
        robot_control, 'config', 'gamepad_teleop.yaml',
    ])
    rviz_config = PathJoinSubstitution([
        robot_control, 'rviz', 'manual_mapping.rviz',
    ])

    return LaunchDescription([
        DeclareLaunchArgument(
            'port', default_value='/dev/ttyACM0',
            description='STM32 USB CDC serial port.'),
        DeclareLaunchArgument(
            'lidar_serial_port', default_value='/dev/ttyUSB0',
            description='RPLiDAR serial port.'),
        DeclareLaunchArgument(
            'lidar_serial_baudrate', default_value='256000',
            description='RPLiDAR serial baudrate.'),
        DeclareLaunchArgument(
            'joy_dev', default_value='/dev/input/js0',
            description='Linux joystick device exposed by VMware.'),
        DeclareLaunchArgument(
            'enable_gamepad', default_value='true',
            description='Start joy_node and teleop_twist_joy.'),
        DeclareLaunchArgument(
            'enable_camera', default_value='true',
            description='Start the Astra Pro camera bringup.'),
        DeclareLaunchArgument(
            'rviz', default_value='false',
            description='Open the mapping view on this laptop.'),
        DeclareLaunchArgument(
            'camera_name', default_value='camera',
            description='Camera namespace.'),
        DeclareLaunchArgument(
            'uvc_product_id', default_value='0x0501',
            description='Astra Pro RGB id; use 0x0502 for the FHD variant.'),
        DeclareLaunchArgument(
            'camera_enable_color', default_value='true',
            description='Publish RGB while mapping.'),
        DeclareLaunchArgument(
            'camera_depth_fps', default_value='15',
            description='Depth FPS; 15 is safer for VMware USB bandwidth.'),
        DeclareLaunchArgument(
            'camera_color_fps', default_value='15',
            description='RGB FPS; lower this if the VM drops frames.'),
        DeclareLaunchArgument(
            'camera_x', default_value='0.25',
            description='Measured camera mount x in metres.'),
        DeclareLaunchArgument(
            'camera_y', default_value='0.0',
            description='Measured camera mount y in metres.'),
        DeclareLaunchArgument(
            'camera_z', default_value='0.35',
            description='Measured camera mount z in metres.'),
        DeclareLaunchArgument(
            'camera_pitch', default_value='0.17',
            description='Camera pitch in radians; positive is down.'),
        # Existing real-robot manual mapping: STM32 + LiDAR + SLAM only.
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(mapping_launch),
            launch_arguments={
                'port': LaunchConfiguration('port'),
                'lidar_serial_port': LaunchConfiguration('lidar_serial_port'),
                'lidar_serial_baudrate': LaunchConfiguration('lidar_serial_baudrate'),
            }.items(),
        ),

        Node(
            package='joy_linux',
            executable='joy_linux_node',
            name='joy_linux_node',
            output='screen',
            condition=IfCondition(LaunchConfiguration('enable_gamepad')),
            parameters=[{
                'dev': LaunchConfiguration('joy_dev'),
                'deadzone': 0.10,
                'autorepeat_rate': 20.0,
            }],
        ),
        Node(
            package='teleop_twist_joy',
            executable='teleop_node',
            name='teleop_twist_joy_node',
            output='screen',
            condition=IfCondition(LaunchConfiguration('enable_gamepad')),
            parameters=[gamepad_config],
            remappings=[
                ('cmd_vel', '/cmd_vel_manual'),
            ],
        ),

        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(camera_launch),
            condition=IfCondition(LaunchConfiguration('enable_camera')),
            launch_arguments={
                'camera_name': LaunchConfiguration('camera_name'),
                'uvc_product_id': LaunchConfiguration('uvc_product_id'),
                'enable_color': LaunchConfiguration('camera_enable_color'),
                'depth_fps': LaunchConfiguration('camera_depth_fps'),
                'color_fps': LaunchConfiguration('camera_color_fps'),
                'enable_ir': 'false',
                'enable_point_cloud': 'true',
                'x': LaunchConfiguration('camera_x'),
                'y': LaunchConfiguration('camera_y'),
                'z': LaunchConfiguration('camera_z'),
                'pitch': LaunchConfiguration('camera_pitch'),
            }.items(),
        ),
        Node(
            package='rviz2',
            executable='rviz2',
            name='manual_mapping_rviz',
            arguments=['-d', rviz_config],
            output='screen',
            condition=IfCondition(LaunchConfiguration('rviz')),
        ),
    ])
