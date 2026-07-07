# =============================================================================
# stop_navigator.launch.py
# Chay stop navigator (tang "ben bus" tren Nav2). Yeu cau navigation stack
# (robot_navigation navigation.launch.py / sim_navigation.launch.py) da chay.
#
#   ros2 launch bus_manager stop_navigator.launch.py
#   ros2 action send_goal /go_to_stop bus_interfaces/action/GoToStop \
#       "{stop_id: library}" --feedback
# =============================================================================
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    bus_id = LaunchConfiguration('bus_id')
    stops_file = LaunchConfiguration('stops_file')
    use_sim_time = LaunchConfiguration('use_sim_time')

    default_stops = PathJoinSubstitution([
        FindPackageShare('bus_manager'),
        'config',
        'bus_stops.yaml',
    ])

    return LaunchDescription([
        DeclareLaunchArgument('bus_id', default_value='bus1',
                              description='Bus ID in BusStatus.'),
        DeclareLaunchArgument('stops_file', default_value=default_stops,
                              description='YAML file with named stop poses.'),
        DeclareLaunchArgument('use_sim_time', default_value='false',
                              description='Use simulation clock.'),

        Node(
            package='bus_manager',
            executable='stop_navigator',
            name='stop_navigator',
            output='screen',
            parameters=[{
                'bus_id': bus_id,
                'stops_file': stops_file,
                'use_sim_time': use_sim_time,
            }],
        ),
    ])
