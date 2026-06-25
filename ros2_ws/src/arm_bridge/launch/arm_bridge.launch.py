# =============================================================================
# arm_bridge.launch.py
# Bridge high-level arm commands -> SCARA controller.
# transport:=serial  (now, USB CDC to Arduino Uno + CNC Shield)
# transport:=can     (later, when the arm moves onto the CAN bus)
# Independent of the car bridge: uses the arm's OWN port (default /dev/ttyUSB0).
# =============================================================================
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    transport = LaunchConfiguration('transport')
    port = LaunchConfiguration('port')
    baudrate = LaunchConfiguration('baudrate')
    can_channel = LaunchConfiguration('can_channel')
    can_bitrate = LaunchConfiguration('can_bitrate')
    poll_rate_hz = LaunchConfiguration('poll_rate_hz')
    cmd_timeout = LaunchConfiguration('cmd_timeout')

    return LaunchDescription([
        DeclareLaunchArgument(
            'transport',
            default_value='serial',
            description="Arm transport: 'serial' (now) or 'can' (later)."),
        DeclareLaunchArgument(
            'port',
            default_value='/dev/ttyUSB0',
            description="Arm's OWN serial port. Keep different from the car "
                        "STM32 (usually /dev/ttyACM0)."),
        DeclareLaunchArgument(
            'baudrate',
            default_value='115200',
            description='Serial baudrate for the arm controller.'),
        DeclareLaunchArgument(
            'can_channel',
            default_value='can0',
            description='SocketCAN channel (used only when transport:=can).'),
        DeclareLaunchArgument(
            'can_bitrate',
            default_value='500000',
            description='CAN bitrate (used only when transport:=can).'),
        DeclareLaunchArgument(
            'poll_rate_hz',
            default_value='50.0',
            description='Feedback poll / reconnect rate.'),
        DeclareLaunchArgument(
            'cmd_timeout',
            default_value='1.0',
            description='Reserved for future watchdog behavior.'),

        Node(
            package='arm_bridge',
            executable='arm_bridge_node',
            name='arm_bridge_node',
            output='screen',
            parameters=[{
                'transport': transport,
                'port': port,
                'baudrate': ParameterValue(baudrate, value_type=int),
                'can_channel': can_channel,
                'can_bitrate': ParameterValue(can_bitrate, value_type=int),
                'poll_rate_hz': ParameterValue(poll_rate_hz, value_type=float),
                'cmd_timeout': ParameterValue(cmd_timeout, value_type=float),
            }],
        ),
    ])
