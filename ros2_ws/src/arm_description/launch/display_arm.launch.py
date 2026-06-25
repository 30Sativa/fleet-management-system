# =============================================================================
# display_arm.launch.py
# Xem RIENG tay SCARA trong RViz (chua gan len xe).
# Chay: ros2 launch arm_description display_arm.launch.py
# Keo cac thanh truot (joint_state_publisher_gui) de xem J1/J2/Z/gripper dong.
# =============================================================================
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch.substitutions import Command


def generate_launch_description():
    pkg = get_package_share_directory('arm_description')
    xacro_file = os.path.join(pkg, 'urdf', 'arm_standalone.urdf.xacro')
    rviz_file = os.path.join(pkg, 'rviz', 'arm.rviz')

    robot_description = ParameterValue(
        Command(['xacro ', xacro_file]), value_type=str)

    return LaunchDescription([
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            name='robot_state_publisher',
            output='screen',
            parameters=[{'robot_description': robot_description}],
        ),
        Node(
            package='joint_state_publisher_gui',
            executable='joint_state_publisher_gui',
            name='joint_state_publisher_gui',
            output='screen',
        ),
        Node(
            package='rviz2',
            executable='rviz2',
            name='rviz2',
            output='screen',
            arguments=['-d', rviz_file],
        ),
    ])
