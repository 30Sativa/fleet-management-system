# =============================================================================
# localization.launch.py
# map_server + AMCL + lifecycle manager. Localizes the robot on a SAVED map
# (no SLAM). Include this from navigation.launch.py, or run standalone:
#
#   ros2 launch robot_navigation localization.launch.py \
#       map:=/path/to/my_map.yaml
#
# After startup, if the robot did not start at the mapping origin, give it a
# "2D Pose Estimate" in RViz (publishes /initialpose to AMCL).
# =============================================================================
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    map_yaml = LaunchConfiguration('map')
    use_sim_time = LaunchConfiguration('use_sim_time')
    params_file = LaunchConfiguration('params_file')
    autostart = LaunchConfiguration('autostart')

    default_params = PathJoinSubstitution([
        FindPackageShare('robot_navigation'),
        'config',
        'localization_params.yaml',
    ])
    default_map = PathJoinSubstitution([
        FindPackageShare('robot_navigation'),
        'maps',
        'map.yaml',
    ])

    return LaunchDescription([
        DeclareLaunchArgument(
            'map', default_value=default_map,
            description='Full path to the saved map .yaml file.'),
        DeclareLaunchArgument(
            'use_sim_time', default_value='false',
            description='Use simulation clock.'),
        DeclareLaunchArgument(
            'params_file', default_value=default_params,
            description='AMCL / map_server parameter file.'),
        DeclareLaunchArgument(
            'autostart', default_value='true',
            description='Auto-activate the lifecycle nodes.'),

        Node(
            package='nav2_map_server',
            executable='map_server',
            name='map_server',
            output='screen',
            parameters=[
                params_file,
                {
                    'yaml_filename': map_yaml,
                    'use_sim_time': use_sim_time,
                },
            ],
        ),

        Node(
            package='nav2_amcl',
            executable='amcl',
            name='amcl',
            output='screen',
            parameters=[
                params_file,
                {'use_sim_time': use_sim_time},
            ],
        ),

        Node(
            package='nav2_lifecycle_manager',
            executable='lifecycle_manager',
            name='lifecycle_manager_localization',
            output='screen',
            parameters=[{
                'use_sim_time': use_sim_time,
                'autostart': autostart,
                'node_names': ['map_server', 'amcl'],
            }],
        ),
    ])
