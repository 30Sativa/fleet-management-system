"""Phase 2: depth -> PointCloud2 -> RViz2, with the numbers to back it up.

Same driver and mount as Phase 1.  What Phase 2 adds is the measurement:
`depth_check` reads the depth image and reports depth accuracy, TF sanity,
ground-plane tilt/height error, and ground noise per distance band.

    ros2 launch orbbec_bringup phase2_perception.launch.py \
        z:=0.35 pitch:=0.20 expected_center_m:=1.00

RGB is off by default: Phase 2 needs depth only, and dropping the colour
stream frees the USB bandwidth that makes the depth stream unstable on a VM.
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


# Starting point, not the answer.  A camera mounted level (pitch 0) at 0.35 m
# does not see the floor until 0.83 m ahead, so the ground-plane fit finds
# nothing and reports "qua it diem san" -- which reads like a camera fault and
# is not one.  0.17 rad ~ 10 deg nose-down puts the floor in frame from the
# start.  Replace all six with the values section 3 of docs/phase2-perception.md
# converges on.
MOUNT_ARGS = [
    ('parent_frame', 'base_link'),
    ('child_frame', 'camera_link'),
    ('x', '0.25'),
    ('y', '0.0'),
    ('z', '0.35'),
    ('roll', '0.0'),
    ('pitch', '0.17'),
    ('yaw', '0.0'),
]


def generate_launch_description():
    pkg = FindPackageShare('orbbec_bringup')
    driver_launch = PathJoinSubstitution([pkg, 'launch', 'astra_pro.launch.py'])
    mount_launch = PathJoinSubstitution([pkg, 'launch', 'camera_mount.launch.py'])
    rviz_config = PathJoinSubstitution([pkg, 'rviz', 'phase2_pointcloud.rviz'])

    declared = [DeclareLaunchArgument(n, default_value=d) for n, d in MOUNT_ARGS]
    declared += [
        DeclareLaunchArgument('camera_name', default_value='camera'),
        DeclareLaunchArgument(
            'enable_color', default_value='false',
            description='Phase 2 needs depth only; colour just eats USB bandwidth.'),
        DeclareLaunchArgument('depth_fps', default_value='15'),
        DeclareLaunchArgument(
            'expected_center_m', default_value='0.0',
            description='Measured distance to a flat target filling the view centre. '
                        '0 skips the absolute-accuracy check.'),
        DeclareLaunchArgument(
            'rviz', default_value='false',
            description='Open RViz2 with the Phase 2 point-cloud layout. '
                        'Off by default; rviz:=true to inspect.'),
        DeclareLaunchArgument(
            'check', default_value='true',
            description='Run the depth_check diagnostic node.'),
        DeclareLaunchArgument('report_period', default_value='3.0'),
    ]

    return LaunchDescription(declared + [
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(driver_launch),
            launch_arguments={
                'camera_name': LaunchConfiguration('camera_name'),
                'enable_color': LaunchConfiguration('enable_color'),
                'depth_fps': LaunchConfiguration('depth_fps'),
                'enable_point_cloud': 'true',
                'enable_ir': 'false',
            }.items(),
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(mount_launch),
            launch_arguments={n: LaunchConfiguration(n) for n, _ in MOUNT_ARGS}.items(),
        ),
        Node(
            package='orbbec_bringup',
            executable='depth_check',
            name='depth_check',
            output='screen',
            emulate_tty=True,
            condition=IfCondition(LaunchConfiguration('check')),
            parameters=[{
                'camera_name': LaunchConfiguration('camera_name'),
                'base_frame': LaunchConfiguration('parent_frame'),
                'expected_center_m': LaunchConfiguration('expected_center_m'),
                'report_period': LaunchConfiguration('report_period'),
                # Passed through so the report can print corrected absolutes.
                'mount_z': LaunchConfiguration('z'),
                'mount_pitch': LaunchConfiguration('pitch'),
                'mount_roll': LaunchConfiguration('roll'),
            }],
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
