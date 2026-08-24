# =============================================================================
# navigation.launch.py
# REAL ROBOT: navigate on a SAVED map (no SLAM, no explorer).
#
# Chain:
#   goal (RViz "Nav2 Goal" / bus_manager stop_navigator) -> Nav2 -> /cmd_vel_nav
#     -> mode_manager (explore mode accepts nav; manual teleop overrides)
#     -> /cmd_vel -> STM32 bridge
#   Localization: map_server + AMCL (map -> odom TF), scan from RPLiDAR.
#
# Obstacle sensing (Phase 3):
#   RPLiDAR   -> /scan                  -> local + global costmap
#   Astra Pro -> /camera/depth/points   -> local costmap ONLY
#   The camera covers what a single LiDAR plane misses: low boxes, pallet
#   edges, overhangs. enable_camera:=false falls back to LiDAR-only.
#   camera_* args MUST be the values Phase 2 calibrated - see
#   docs/phase2-perception.md section 3. Wrong pitch turns the floor into a wall.
#
# Prerequisite: a map saved earlier with either mapping mode:
#   ros2 launch robot_control manual_mapping.launch.py   (drive by hand)
#   ros2 launch robot_control auto_explore.launch.py     (vacuum-style)
# then:
#   ros2 run nav2_map_server map_saver_cli -f <path>/my_map
#
# Run:
#   ros2 launch robot_navigation navigation.launch.py map:=/path/to/my_map.yaml
# =============================================================================
from launch import LaunchDescription
import os

from launch.actions import (DeclareLaunchArgument, GroupAction,
                            IncludeLaunchDescription, LogInfo, OpaqueFunction)
from launch.actions import Shutdown
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node, SetRemap
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare


def _check_map(context, *args, **kwargs):
    """Fail early and clearly when map:= is missing or the file is not there.

    Without this, map_server just errors deep in its own logs and it looks like
    Nav2 is broken, when really you forgot to build/pass a map."""
    path = LaunchConfiguration('map').perform(context)
    if not path:
        return [LogInfo(msg=(
            '\n[navigation] CHUA CO MAP. Robot that khong co map mac dinh.\n'
            '  1) Build map:  ros2 launch robot_control manual_mapping.launch.py\n'
            '                 (hoac auto_explore.launch.py de robot tu quet)\n'
            '  2) Luu map:    ros2 run nav2_map_server map_saver_cli -f <duong/dan>/my_map\n'
            '  3) Chay lai:   ros2 launch robot_navigation navigation.launch.py '
            'map:=<duong/dan>/my_map.yaml\n'
            'Xem robot_navigation/README.md.')),
            Shutdown(reason='map launch argument is required')]
    if not os.path.isfile(path):
        return [LogInfo(msg=f'\n[navigation] Khong tim thay file map: {path}\n'
                            '  Kiem tra lai duong dan (phai la file .yaml da luu).'),
                Shutdown(reason=f'map file not found: {path}')]
    return [LogInfo(msg=f'[navigation] Dung map: {path}')]


def generate_launch_description():
    port = LaunchConfiguration('port')
    baudrate = LaunchConfiguration('baudrate')
    use_sim_time = LaunchConfiguration('use_sim_time')
    lidar_serial_port = LaunchConfiguration('lidar_serial_port')
    lidar_serial_baudrate = LaunchConfiguration('lidar_serial_baudrate')
    lidar_frame = LaunchConfiguration('lidar_frame')
    scan_mode = LaunchConfiguration('scan_mode')
    enable_lidar = LaunchConfiguration('enable_lidar')
    enable_teleop = LaunchConfiguration('enable_teleop')
    map_yaml = LaunchConfiguration('map')
    localization_params_file = LaunchConfiguration('localization_params_file')
    nav2_params_file = LaunchConfiguration('nav2_params_file')
    enable_camera = LaunchConfiguration('enable_camera')
    rviz = LaunchConfiguration('rviz')

    manual_launch = PathJoinSubstitution([
        FindPackageShare('robot_control'),
        'launch',
        'manual_mode.launch.py',
    ])
    localization_launch = PathJoinSubstitution([
        FindPackageShare('robot_navigation'),
        'launch',
        'localization.launch.py',
    ])
    camera_launch = PathJoinSubstitution([
        FindPackageShare('orbbec_bringup'),
        'launch',
        'orbbec_with_mount.launch.py',
    ])
    nav2_launch = PathJoinSubstitution([
        FindPackageShare('nav2_bringup'),
        'launch',
        'navigation_launch.py',
    ])
    rviz_config = PathJoinSubstitution([
        FindPackageShare('robot_navigation'),
        'rviz',
        'navigation.rviz',
    ])
    default_localization_params = PathJoinSubstitution([
        FindPackageShare('robot_navigation'),
        'config',
        'localization_params.yaml',
    ])
    default_nav2_params = PathJoinSubstitution([
        FindPackageShare('robot_control'),
        'config',
        'nav2_params.yaml',
    ])
    scan_filter_params = PathJoinSubstitution([
        FindPackageShare('robot_control'),
        'config',
        'scan_range_filter.yaml',
    ])

    return LaunchDescription([
        DeclareLaunchArgument('port', default_value='/dev/ttyACM0',
                              description='STM32 USB CDC serial port.'),
        DeclareLaunchArgument('baudrate', default_value='115200',
                              description='STM32 serial baudrate.'),
        DeclareLaunchArgument('use_sim_time', default_value='false',
                              description='Use simulation clock.'),
        DeclareLaunchArgument('lidar_serial_port', default_value='/dev/ttyUSB0',
                              description='RPLiDAR serial port.'),
        DeclareLaunchArgument('lidar_serial_baudrate', default_value='256000',
                              description='RPLiDAR A3M1 serial baudrate.'),
        DeclareLaunchArgument('lidar_frame', default_value='lidar_link',
                              description='LaserScan frame_id.'),
        DeclareLaunchArgument('scan_mode', default_value='Sensitivity',
                              description='RPLiDAR scan mode (A3: Sensitivity/Boost).'),
        DeclareLaunchArgument('enable_lidar', default_value='true',
                              description='Launch rplidar_ros node.'),
        DeclareLaunchArgument('enable_teleop', default_value='false',
                              description='Optional manual override teleop.'),
        DeclareLaunchArgument(
            'map', default_value='',
            description='Full path to the saved map .yaml. REQUIRED: there is no '
                        'default real-world map -- build one first with '
                        'manual_mapping.launch.py (or let the robot explore with '
                        'auto_explore.launch.py), save it with map_saver_cli, '
                        'then pass its path here.'),
        OpaqueFunction(function=_check_map),
        DeclareLaunchArgument('localization_params_file',
                              default_value=default_localization_params,
                              description='AMCL / map_server parameter file.'),
        DeclareLaunchArgument('nav2_params_file',
                              default_value=default_nav2_params,
                              description='Nav2 parameter file.'),
        DeclareLaunchArgument('enable_camera', default_value='true',
                              description='Feed the Astra point cloud into the '
                                          'local costmap.'),
        DeclareLaunchArgument(
            'rviz', default_value='false',
            description='Open RViz with the navigation layout. Default false: '
                        'the robot mini PC is usually headless and you run RViz '
                        'on your dev machine. rviz:=true opens it here.'),
        DeclareLaunchArgument('camera_x', default_value='0.25',
                              description='PLACEHOLDER - replace with the Phase 2 '
                                          'calibrated mount, base_link -> camera_link.'),
        DeclareLaunchArgument('camera_y', default_value='0.0'),
        DeclareLaunchArgument('camera_z', default_value='0.35'),
        DeclareLaunchArgument('camera_roll', default_value='0.0'),
        DeclareLaunchArgument('camera_pitch', default_value='0.17',
                              description='Radians, nose-down positive. ~10 deg.'),
        DeclareLaunchArgument('camera_yaw', default_value='0.0'),
        DeclareLaunchArgument('camera_depth_width', default_value='320'),
        DeclareLaunchArgument('camera_depth_height', default_value='240'),
        DeclareLaunchArgument(
            'camera_enable_color', default_value='false',
            description='PHASE 4 only. Costmaps need geometry, not colour, and '
                        'the RGB stream is a separate UVC device sharing the same '
                        'USB bus as depth - turning it on is what made depth '
                        'stutter in Phase 1. Set true when running '
                        'robot_perception, and watch the depth rate.'),
        DeclareLaunchArgument(
            'camera_color_info_url', default_value='',
            description='PHASE 4. file:// URL of the RGB intrinsics from '
                        'camera_calibration. Empty means color/camera_info is '
                        'the factory guess, and every detection range is off.'),
        DeclareLaunchArgument('camera_depth_fps', default_value='10',
                              description='320x240 @ 10 Hz is ~77k points per '
                                          'frame. 640x480 @ 30 is 9x that and the '
                                          'costmap update falls behind on a mini PC.'),

        # 1) Base bringup: robot_state_publisher + STM32 bridge + mode manager.
        #    initial_mode=explore so Nav2's /cmd_vel_nav drives the robot;
        #    manual teleop still overrides (manual_priority_in_explore).
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(manual_launch),
            launch_arguments={
                'port': port,
                'baudrate': baudrate,
                'initial_mode': 'explore',
                'use_sim_time': use_sim_time,
                'enable_teleop': enable_teleop,
            }.items(),
        ),

        # 2) LiDAR -> /scan_raw, then range filter -> /scan (AMCL + costmaps).
        #    The filter drops points that hit the robot's own body so they are
        #    not localized against or treated as obstacles.
        Node(
            package='rplidar_ros',
            executable='rplidar_node',
            name='rplidar_node',
            output='screen',
            condition=IfCondition(enable_lidar),
            parameters=[{
                'channel_type': 'serial',
                'serial_port': lidar_serial_port,
                'serial_baudrate': ParameterValue(
                    lidar_serial_baudrate, value_type=int),
                'frame_id': lidar_frame,
                'inverted': False,
                'angle_compensate': True,
                'scan_mode': scan_mode,
            }],
            remappings=[('scan', 'scan_raw')],
        ),

        # 2a) Range filter: /scan_raw -> filter -> /scan. Removes robot-body
        #     returns. Needs ros-humble-laser-filters.
        Node(
            package='laser_filters',
            executable='scan_to_scan_filter_chain',
            name='scan_range_filter',
            output='screen',
            condition=IfCondition(enable_lidar),
            parameters=[scan_filter_params],
            remappings=[
                ('scan', 'scan_raw'),
                ('scan_filtered', 'scan'),
            ],
        ),

        # 2b) Astra Pro -> /camera/depth/points, plus base_link -> camera_link.
        #     RGB stays off: the costmap only reads geometry, and dropping the
        #     colour stream is what keeps depth stable over one USB bus.
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(camera_launch),
            condition=IfCondition(enable_camera),
            launch_arguments={
                'enable_color': LaunchConfiguration('camera_enable_color'),
                'color_info_url': LaunchConfiguration('camera_color_info_url'),
                'enable_ir': 'false',
                'enable_point_cloud': 'true',
                'depth_width': LaunchConfiguration('camera_depth_width'),
                'depth_height': LaunchConfiguration('camera_depth_height'),
                'depth_fps': LaunchConfiguration('camera_depth_fps'),
                'parent_frame': 'base_link',
                'child_frame': 'camera_link',
                'x': LaunchConfiguration('camera_x'),
                'y': LaunchConfiguration('camera_y'),
                'z': LaunchConfiguration('camera_z'),
                'roll': LaunchConfiguration('camera_roll'),
                'pitch': LaunchConfiguration('camera_pitch'),
                'yaw': LaunchConfiguration('camera_yaw'),
                'rviz': 'false',
            }.items(),
        ),

        # 3) Localization on the saved map (replaces slam_toolbox).
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(localization_launch),
            launch_arguments={
                'map': map_yaml,
                'use_sim_time': use_sim_time,
                'params_file': localization_params_file,
            }.items(),
        ),

        # 4) Nav2, velocity output remapped to /cmd_vel_nav for the mux.
        GroupAction([
            # Nav2 Humble's navigation_launch.py already wires an internal
            # chain, and it uses BOTH of the names this stack cares about:
            #
            #   controller_server  pub "cmd_vel"           -\
            #   behavior_server    pub "cmd_vel"            |-> nav2 remaps to
            #   velocity_smoother  sub "cmd_vel"           -/   cmd_vel_nav
            #   velocity_smoother  pub "cmd_vel_smoothed"  ---> nav2 remaps to
            #                                                   cmd_vel
            #
            # SetRemap rules are inserted BEFORE a node's own remappings, and
            # rcl applies the FIRST matching rule. So remapping cmd_vel_smoothed
            # to /cmd_vel_nav made velocity_smoother publish onto the very topic
            # it subscribes to: a feedback loop. Its own output kept refreshing
            # last_command_time_, so the velocity_timeout stop never fired, and
            # /cmd_vel_nav ended up with two competing publishers (raw 10 Hz
            # controller + smoothed 20 Hz echo), which also defeats
            # mode_manager's nav_timeout watchdog.
            #
            # Fix: rename nav2's INTERNAL topic instead of its output, so each
            # topic has exactly one publisher:
            #
            #   controller_server -\
            #                       >-> /cmd_vel_ctrl -> velocity_smoother
            #   behavior_server   -/                          |
            #                                                 v
            #                     /cmd_vel_nav -> mode_manager -> /cmd_vel
            #
            # NOTE: SetRemap only reaches plain Node actions. Composable nodes
            # ignore it. navigation_launch.py defaults to use_composition:=False
            # so this works - but never pass use_composition:=True here or every
            # rule below is silently dropped and Nav2 drives /cmd_vel directly,
            # bypassing mode_manager and the e-stop.
            SetRemap(src='cmd_vel', dst='/cmd_vel_ctrl'),
            SetRemap(src='cmd_vel_smoothed', dst='/cmd_vel_nav'),
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(nav2_launch),
                launch_arguments={
                    'use_sim_time': use_sim_time,
                    'params_file': nav2_params_file,
                    'autostart': 'true',
                }.items(),
            ),
        ]),

        # Optional viewer. OFF by default so a headless robot does not try to
        # open a window and hang the launch. Run RViz on your dev machine, or
        # pass rviz:=true here when you do have a screen.
        Node(
            package='rviz2',
            executable='rviz2',
            name='rviz2',
            arguments=['-d', rviz_config],
            output='screen',
            condition=IfCondition(rviz),
        ),
    ])
