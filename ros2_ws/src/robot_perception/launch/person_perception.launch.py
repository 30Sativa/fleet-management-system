"""Phase 4: person perception on top of a running Phase 3 navigation stack.

    ros2 launch robot_navigation navigation.launch.py \
        map:=... camera_enable_color:=true
    ros2 launch robot_perception person_perception.launch.py \
        model_xml:=/opt/models/yolo26n_int8_openvino_model/yolo26n.xml

RGB is off by default in Phase 3 on purpose (USB bandwidth), so Phase 4 has to
ask for it back with camera_enable_color:=true.
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


# Only these are overridable from the command line; everything else lives in
# the yaml.  An empty value means "not given", so it must NOT reach the node -
# an empty override would wipe a path the user set in the yaml.
CLI_OVERRIDES = ('model_xml', 'device', 'publish_speed_limit')


def _setup(context, *args, **kwargs):
    overrides = {}
    for name in CLI_OVERRIDES:
        value = LaunchConfiguration(name).perform(context)
        if value != '':
            overrides[name] = value
    if 'publish_speed_limit' in overrides:
        overrides['publish_speed_limit'] = \
            overrides['publish_speed_limit'].lower() in ('1', 'true', 'yes', 'on')

    return [Node(
        package='robot_perception',
        executable='person_perception',
        name='person_perception',
        output='screen',
        emulate_tty=True,
        parameters=[LaunchConfiguration('params_file'), overrides],
    )]


def generate_launch_description():
    default_params = PathJoinSubstitution([
        FindPackageShare('robot_perception'), 'config', 'person_perception.yaml',
    ])

    return LaunchDescription([
        DeclareLaunchArgument('params_file', default_value=default_params),
        DeclareLaunchArgument(
            'model_xml', default_value='',
            description='Absolute path to the OpenVINO .xml. Empty = use the yaml.'),
        DeclareLaunchArgument(
            'device', default_value='',
            description='CPU or GPU. Empty = use the yaml.'),
        DeclareLaunchArgument(
            'publish_speed_limit', default_value='',
            description='false = publish /people only and leave Nav2 alone. '
                        'Run it like that the first time.'),
        OpaqueFunction(function=_setup),
    ])
