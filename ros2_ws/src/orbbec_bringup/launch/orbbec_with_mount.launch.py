from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import AnyLaunchDescriptionSource, PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    """Start a vendor driver launch file and the robot-to-camera static TF."""
    driver_package = LaunchConfiguration('driver_package')
    driver_launch_file = LaunchConfiguration('driver_launch_file')
    mount_launch = PathJoinSubstitution([
        FindPackageShare('orbbec_bringup'), 'launch', 'camera_mount.launch.py',
    ])
    driver_launch = PathJoinSubstitution([
        FindPackageShare(driver_package), 'launch', driver_launch_file,
    ])

    return LaunchDescription([
        DeclareLaunchArgument(
            'driver_package', default_value='astra_camera',
            description='Installed package that owns this camera model.'),
        DeclareLaunchArgument(
            'driver_launch_file', default_value='astra_pro.launch.xml',
            description='Driver launch file for the detected camera model.'),
        DeclareLaunchArgument(
            'uvc_product_id', default_value='0x0501',
            description='Astra Pro RGB UVC product ID from lsusb (commonly 0x0501 or 0x0502).'),
        DeclareLaunchArgument('parent_frame', default_value='base_link'),
        DeclareLaunchArgument('child_frame', default_value='camera_link'),
        DeclareLaunchArgument('x', default_value='0.0'),
        DeclareLaunchArgument('y', default_value='0.0'),
        DeclareLaunchArgument('z', default_value='0.0'),
        DeclareLaunchArgument('roll', default_value='0.0'),
        DeclareLaunchArgument('pitch', default_value='0.0'),
        DeclareLaunchArgument('yaw', default_value='0.0'),
        # The Astra Pro legacy driver supplies XML launch files; newer Orbbec
        # drivers usually use Python.  Select the source type by file suffix.
        IncludeLaunchDescription(
            AnyLaunchDescriptionSource(driver_launch),
            launch_arguments={
                'uvc_product_id': LaunchConfiguration('uvc_product_id'),
            }.items(),
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(mount_launch),
            launch_arguments={
                'parent_frame': LaunchConfiguration('parent_frame'),
                'child_frame': LaunchConfiguration('child_frame'),
                'x': LaunchConfiguration('x'),
                'y': LaunchConfiguration('y'),
                'z': LaunchConfiguration('z'),
                'roll': LaunchConfiguration('roll'),
                'pitch': LaunchConfiguration('pitch'),
                'yaw': LaunchConfiguration('yaw'),
            }.items(),
        ),
    ])
