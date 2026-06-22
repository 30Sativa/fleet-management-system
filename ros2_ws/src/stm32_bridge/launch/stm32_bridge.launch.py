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
    wheel_radius = LaunchConfiguration('wheel_radius')
    steps_per_rev = LaunchConfiguration('steps_per_rev')
    microstep = LaunchConfiguration('microstep')
    gear_ratio = LaunchConfiguration('gear_ratio')
    max_steps_per_sec = LaunchConfiguration('max_steps_per_sec')
    max_wheel_speed_mm_s = LaunchConfiguration('max_wheel_speed_mm_s')
    send_rate_hz = LaunchConfiguration('send_rate_hz')
    cmd_timeout = LaunchConfiguration('cmd_timeout')
    invert_left = LaunchConfiguration('invert_left')
    invert_right = LaunchConfiguration('invert_right')
    speed_scale = LaunchConfiguration('speed_scale')
    publish_odom = LaunchConfiguration('publish_odom')
    publish_tf = LaunchConfiguration('publish_tf')
    odom_frame = LaunchConfiguration('odom_frame')
    base_frame = LaunchConfiguration('base_frame')
    feedback_timeout = LaunchConfiguration('feedback_timeout')
    feedback_counts_are_cumulative = LaunchConfiguration(
        'feedback_counts_are_cumulative')
    feedback_rate_warn_hz = LaunchConfiguration('feedback_rate_warn_hz')
    reset_odom_on_start = LaunchConfiguration('reset_odom_on_start')
    odom_covariance_diagonal = LaunchConfiguration('odom_covariance_diagonal')
    twist_covariance_diagonal = LaunchConfiguration('twist_covariance_diagonal')

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
            'wheel_radius',
            default_value='0.095',
            description='Wheel radius in meters, used for odometry.'),
        DeclareLaunchArgument(
            'steps_per_rev',
            default_value='200.0',
            description='Motor full steps per revolution, used for odometry.'),
        DeclareLaunchArgument(
            'microstep',
            default_value='8.0',
            description='Driver microstep multiplier, used for odometry.'),
        DeclareLaunchArgument(
            'gear_ratio',
            default_value='10.0',
            description='Motor-to-wheel gear ratio, used for odometry.'),
        DeclareLaunchArgument(
            'max_steps_per_sec',
            default_value='12000.0',
            description='Expected maximum step rate for feedback jump warnings.'),
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
        DeclareLaunchArgument(
            'publish_odom',
            default_value='true',
            description='Publish nav_msgs/Odometry on /odom.'),
        DeclareLaunchArgument(
            'publish_tf',
            default_value='true',
            description='Broadcast odom -> base_link TF.'),
        DeclareLaunchArgument(
            'odom_frame',
            default_value='odom',
            description='Odometry parent frame.'),
        DeclareLaunchArgument(
            'base_frame',
            default_value='base_link',
            description='Robot base child frame.'),
        DeclareLaunchArgument(
            'feedback_timeout',
            default_value='1.0',
            description='Warn if no STM32 feedback is received for this many seconds.'),
        DeclareLaunchArgument(
            'feedback_counts_are_cumulative',
            default_value='true',
            description='Treat feedback counts as cumulative instead of per-sample delta.'),
        DeclareLaunchArgument(
            'feedback_rate_warn_hz',
            default_value='2.0',
            description='Maximum warning rate for feedback timeout/count issues.'),
        DeclareLaunchArgument(
            'reset_odom_on_start',
            default_value='true',
            description='Use the first cumulative feedback sample as the zero baseline.'),
        DeclareLaunchArgument(
            'odom_covariance_diagonal',
            default_value='[0.01, 0.01, 99999.0, 99999.0, 99999.0, 0.1]',
            description='Six diagonal covariance values for odom pose.'),
        DeclareLaunchArgument(
            'twist_covariance_diagonal',
            default_value='[0.01, 99999.0, 99999.0, 99999.0, 99999.0, 0.1]',
            description='Six diagonal covariance values for odom twist.'),

        Node(
            package='stm32_bridge',
            executable='stm32_bridge_node',
            name='stm32_bridge_node',
            output='screen',
            parameters=[{
                'port': port,
                'baudrate': ParameterValue(baudrate, value_type=int),
                'wheel_base': ParameterValue(wheel_base, value_type=float),
                'wheel_radius': ParameterValue(wheel_radius, value_type=float),
                'steps_per_rev': ParameterValue(steps_per_rev, value_type=float),
                'microstep': ParameterValue(microstep, value_type=float),
                'gear_ratio': ParameterValue(gear_ratio, value_type=float),
                'max_steps_per_sec': ParameterValue(
                    max_steps_per_sec, value_type=float),
                'max_wheel_speed_mm_s': ParameterValue(
                    max_wheel_speed_mm_s, value_type=float),
                'send_rate_hz': ParameterValue(send_rate_hz, value_type=float),
                'cmd_timeout': ParameterValue(cmd_timeout, value_type=float),
                'invert_left': ParameterValue(invert_left, value_type=bool),
                'invert_right': ParameterValue(invert_right, value_type=bool),
                'speed_scale': ParameterValue(speed_scale, value_type=float),
                'publish_odom': ParameterValue(publish_odom, value_type=bool),
                'publish_tf': ParameterValue(publish_tf, value_type=bool),
                'odom_frame': odom_frame,
                'base_frame': base_frame,
                'feedback_timeout': ParameterValue(
                    feedback_timeout, value_type=float),
                'feedback_counts_are_cumulative': ParameterValue(
                    feedback_counts_are_cumulative, value_type=bool),
                'feedback_rate_warn_hz': ParameterValue(
                    feedback_rate_warn_hz, value_type=float),
                'reset_odom_on_start': ParameterValue(
                    reset_odom_on_start, value_type=bool),
                'odom_covariance_diagonal': odom_covariance_diagonal,
                'twist_covariance_diagonal': twist_covariance_diagonal,
            }],
        ),
    ])
