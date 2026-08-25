# =============================================================================
# view_world.launch.py
# Open the warehouse world in Gazebo with the robot spawned, but WITHOUT
# SLAM/Nav2/explorer. Use this to sanity-check the world and drive manually.
#
#   ros2 launch simulation view_world.launch.py
# Drive:
#   ros2 run teleop_twist_keyboard teleop_twist_keyboard \
#     --ros-args -r /cmd_vel:=/diff_drive_controller/cmd_vel_unstamped
# =============================================================================
import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    default_world = os.path.join(
        get_package_share_directory('simulation'),
        'worlds', 'warehouse_12x12.world')

    world = LaunchConfiguration('world')

    gazebo_launch = PathJoinSubstitution([
        FindPackageShare('robot_description'), 'launch', 'gazebo.launch.py',
    ])

    return LaunchDescription([
        DeclareLaunchArgument(
            'world', default_value=default_world,
            description='Gazebo .world file to load.'),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(gazebo_launch),
            launch_arguments={'world': world}.items(),
        ),
    ])
