"""Phase 1 entry point: Astra Pro driver + base_link->camera_link mount TF.

This is the launch file the rest of the robot should include.  It owns two
things and nothing else:

1. the camera driver (``astra_pro.launch.py`` in this package), and
2. the static transform from ``base_link`` to the camera, which is robot
   geometry and therefore ours, not the vendor's.

Nav2, SLAM and the depth->laserscan conversion are deliberately NOT here.
Phase 1 is "the camera is trustworthy"; wiring it into navigation is Phase 2.
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


# Forwarded verbatim to astra_pro.launch.py so callers can override the
# camera without this file re-declaring every driver parameter.
DRIVER_ARGS = [
    ('camera_name', 'camera'),
    ('uvc_product_id', '0x0501'),
    ('uvc_vendor_id', '0x2bc5'),
    ('color_width', '640'),
    ('color_height', '480'),
    ('color_fps', '30'),
    ('depth_width', '640'),
    ('depth_height', '480'),
    ('depth_fps', '30'),
    ('enable_color', 'true'),
    ('enable_depth', 'true'),
    ('enable_ir', 'false'),
    ('enable_point_cloud', 'true'),
    ('color_info_url', ''),
]

MOUNT_ARGS = [
    ('parent_frame', 'base_link'),
    ('child_frame', 'camera_link'),
    ('x', '0.0'),
    ('y', '0.0'),
    ('z', '0.0'),
    ('roll', '0.0'),
    ('pitch', '0.0'),
    ('yaw', '0.0'),
]


def generate_launch_description():
    pkg = FindPackageShare('orbbec_bringup')
    driver_launch = PathJoinSubstitution([pkg, 'launch', 'astra_pro.launch.py'])
    mount_launch = PathJoinSubstitution([pkg, 'launch', 'camera_mount.launch.py'])
    rviz_config = PathJoinSubstitution([pkg, 'rviz', 'astra_pro.rviz'])

    declared = [
        DeclareLaunchArgument(name, default_value=default)
        for name, default in DRIVER_ARGS + MOUNT_ARGS
    ]
    declared.append(DeclareLaunchArgument(
        'rviz', default_value='false',
        description='Open RViz2 with the Phase 1 verification layout.'))

    return LaunchDescription(declared + [
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(driver_launch),
            launch_arguments={n: LaunchConfiguration(n) for n, _ in DRIVER_ARGS}.items(),
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(mount_launch),
            launch_arguments={n: LaunchConfiguration(n) for n, _ in MOUNT_ARGS}.items(),
        ),
        Node(
            package='rviz2',
            executable='rviz2',
            name='rviz2',
            arguments=['-d', rviz_config],
            output='screen',
            condition=IfCondition(LaunchConfiguration('rviz')),
        ),
    ])
