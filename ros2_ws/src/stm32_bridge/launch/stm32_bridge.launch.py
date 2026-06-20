# =============================================================================
# stm32_bridge.launch.py
# Run /cmd_vel -> USB Serial -> STM32 bridge for the real robot.
# =============================================================================
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    port = LaunchConfiguration('port')
    baudrate = LaunchConfiguration('baudrate')
    wheel_base = LaunchConfiguration('wheel_base')
    max_wheel_speed_mm_s = LaunchConfiguration('max_wheel_speed_mm_s')
    send_rate_hz = LaunchConfiguration('send_rate_hz')
    cmd_timeout = LaunchConfiguration('cmd_timeout')
    invert_left = LaunchConfiguration('invert_left')
    invert_right = LaunchConfiguration('invert_right')
    speed_scale = LaunchConfiguration('speed_scale')

    return LaunchDescription([
        DeclareLaunchArgument(
            'port',
            default_value='/dev/ttyACM0',
            description='USB CDC serial port connected to the STM32.'),
        DeclareLaunchArgument(
            'baudrate',
            default_value='115200',
            description='Serial baudrate. USB CDC may ignore it, but keep it stable.'),
        DeclareLaunchArgument(
            'wheel_base',
            default_value='0.60',
            description='Distance between left and right wheels in meters.'),
        DeclareLaunchArgument(
            'max_wheel_speed_mm_s',
            default_value='1000.0',
            description='Clamp each wheel command to +/- this speed in mm/s.'),
        DeclareLaunchArgument(
            'send_rate_hz',
            default_value='20.0',
            description='How often to send commands to the STM32.'),
        DeclareLaunchArgument(
            'cmd_timeout',
            default_value='0.5',
            description='Send stop if no /cmd_vel arrives for this many seconds.'),
        DeclareLaunchArgument(
            'invert_left',
            default_value='false',
            description='Invert left wheel command sign.'),
        DeclareLaunchArgument(
            'invert_right',
            default_value='false',
            description='Invert right wheel command sign.'),
        DeclareLaunchArgument(
            'speed_scale',
            default_value='1.0',
            description='Scale wheel commands before invert and clamp.'),

        Node(
            package='stm32_bridge',
            executable='stm32_bridge_node',
            name='stm32_bridge_node',
            output='screen',
            parameters=[{
                'port': port,
                'baudrate': ParameterValue(baudrate, value_type=int),
                'wheel_base': ParameterValue(wheel_base, value_type=float),
                'max_wheel_speed_mm_s': ParameterValue(
                    max_wheel_speed_mm_s, value_type=float),
                'send_rate_hz': ParameterValue(send_rate_hz, value_type=float),
                'cmd_timeout': ParameterValue(cmd_timeout, value_type=float),
                'invert_left': ParameterValue(invert_left, value_type=bool),
                'invert_right': ParameterValue(invert_right, value_type=bool),
                'speed_scale': ParameterValue(speed_scale, value_type=float),
            }],
        ),
    ])
