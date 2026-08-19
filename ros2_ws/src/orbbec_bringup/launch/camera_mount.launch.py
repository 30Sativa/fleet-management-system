from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    """Publish the measured static transform from the robot to the camera."""
    parent_frame = LaunchConfiguration('parent_frame')
    child_frame = LaunchConfiguration('child_frame')

    return LaunchDescription([
        DeclareLaunchArgument('parent_frame', default_value='base_link',
                              description='Robot frame that the camera is mounted on.'),
        DeclareLaunchArgument('child_frame', default_value='camera_link',
                              description='Camera optical-body frame published by the driver.'),
        DeclareLaunchArgument('x', default_value='0.0', description='Mount x in metres (forward).'),
        DeclareLaunchArgument('y', default_value='0.0', description='Mount y in metres (left).'),
        DeclareLaunchArgument('z', default_value='0.0', description='Mount z in metres (up).'),
        DeclareLaunchArgument('roll', default_value='0.0', description='Mount roll in radians.'),
        DeclareLaunchArgument('pitch', default_value='0.0', description='Mount pitch in radians.'),
        DeclareLaunchArgument('yaw', default_value='0.0', description='Mount yaw in radians.'),
        Node(
            package='tf2_ros',
            executable='static_transform_publisher',
            name='base_to_orbbec_camera',
            output='screen',
            arguments=[
                '--x', LaunchConfiguration('x'),
                '--y', LaunchConfiguration('y'),
                '--z', LaunchConfiguration('z'),
                '--roll', LaunchConfiguration('roll'),
                '--pitch', LaunchConfiguration('pitch'),
                '--yaw', LaunchConfiguration('yaw'),
                '--frame-id', parent_frame,
                '--child-frame-id', child_frame,
            ],
        ),
    ])
