# =============================================================================
# display.launch.py
# Xem robot trong RViz (KHONG can Gazebo). Dung de kiem tra hinh dang + frames.
#   ros2 launch robot_description display.launch.py
# =============================================================================
import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import Command, LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    pkg = get_package_share_directory('robot_description')
    xacro_file = os.path.join(pkg, 'urdf', 'robot.urdf.xacro')
    rviz_file = os.path.join(pkg, 'rviz', 'display.rviz')

    # use_sim=false o che do display de khong nap plugin gazebo
    robot_description = ParameterValue(
        Command(['xacro ', xacro_file, ' use_sim:=false']),
        value_type=str,
    )

    use_gui = LaunchConfiguration('gui')

    return LaunchDescription([
        DeclareLaunchArgument('gui', default_value='true',
                              description='Bat joint_state_publisher_gui de xoay banh tay'),

        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            output='screen',
            parameters=[{'robot_description': robot_description}],
        ),
        # GUI keo thanh truot de quay banh (chi khi gui:=true)
        Node(
            package='joint_state_publisher_gui',
            executable='joint_state_publisher_gui',
            condition=IfCondition(use_gui),
        ),
        Node(
            package='rviz2',
            executable='rviz2',
            name='rviz2',
            output='screen',
            arguments=['-d', rviz_file] if os.path.exists(rviz_file) else [],
        ),
    ])
