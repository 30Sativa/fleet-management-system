"""Phase 1 bringup for the Orbbec Astra Pro.

The Astra Pro is a split device: depth/IR come from the OpenNI2 sensor
(USB id 2bc5:0403) while RGB is an ordinary UVC webcam (2bc5:0501, or
2bc5:0502 on the FHD variant).  ``astra_camera_node`` drives both, but only
when ``use_uvc_camera`` is true and the UVC ids match what ``lsusb`` reports.

This file intentionally does NOT include the vendor ``astra_pro.launch.xml``.
That launch file hard-codes a parameter list we cannot extend, and its
defaults (IR enabled together with depth) are wrong for this robot.  Keeping
our own launch means every parameter that matters is visible and overridable
from one place.
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def _as_int(text):
    """Accept both decimal (11205) and hex (0x2bc5) USB ids."""
    text = str(text).strip()
    return int(text, 16) if text.lower().startswith('0x') else int(text)


def _as_bool(text):
    return str(text).strip().lower() in ('1', 'true', 'yes', 'on')


LAUNCH_ARGS = [
    ('camera_name', 'camera', 'Namespace and TF prefix for the camera.'),
    ('color_width', '640', 'RGB width; the UVC stream must support this exact mode.'),
    ('color_height', '480', 'RGB height.'),
    ('color_fps', '30', 'RGB frame rate.'),
    ('depth_width', '640', 'Depth width.'),
    ('depth_height', '480', 'Depth height.'),
    ('depth_fps', '30', 'Depth frame rate.'),
    ('enable_color', 'true', 'Publish color/image_raw + color/camera_info.'),
    ('enable_depth', 'true', 'Publish depth/image_raw + depth/camera_info.'),
    ('enable_ir', 'false',
     'Publish ir/image_raw.  Depth and IR share one sensor on the Astra Pro; '
     'enabling both is the most common cause of a driver that starts and then '
     'stalls.  Keep this false unless you are deliberately debugging IR.'),
    ('enable_point_cloud', 'true', 'Publish depth/points (XYZ, depth frame).'),
    ('enable_colored_point_cloud', 'false',
     'Needs hardware depth-to-color registration, which the Astra Pro does not '
     'have because RGB is a separate UVC device.  Leave false.'),
    ('depth_registration', 'false',
     'Hardware D2C alignment.  Not available on the Astra Pro - see above.'),
    ('color_depth_synchronization', 'false',
     'OpenNI-side sync; has no effect while RGB comes from UVC.'),
    ('uvc_vendor_id', '0x2bc5', 'RGB (UVC) vendor id from `lsusb -d 2bc5:`.'),
    ('uvc_product_id', '0x0501',
     'RGB (UVC) product id.  0x0501 on most Astra Pro units, 0x0502 on the FHD '
     'variant.  A wrong value here is why RGB stays silent while depth works.'),
    ('uvc_camera_format', 'mjpeg', 'mjpeg or uncompressed.'),
    ('uvc_retry_count', '100', 'UVC open retries before giving up.'),
    ('uvc_flip', 'false', 'Flip the RGB image.'),
    ('connection_delay', '100', 'Milliseconds to wait after opening the device.'),
    ('publish_tf', 'true', 'Publish the camera-internal TF tree.'),
    ('tf_publish_rate', '10.0', 'Rate for the camera-internal TF tree.'),
    ('color_info_url', '',
     'file:// URL of the RGB intrinsics produced by camera_calibration.  Until '
     'this is set, color/camera_info carries the factory guess, not a '
     'calibration of this unit.'),
    ('ir_info_url', '', 'file:// URL of the IR/depth intrinsics.'),
    ('serial_number', '', 'Pin a specific device when more than one is attached.'),
    ('device_num', '1', 'Number of Astra devices expected on the bus.'),
    ('color_qos', 'default', 'default | sensor_data | ...'),
    ('depth_qos', 'default', ''),
    ('ir_qos', 'default', ''),
    ('point_cloud_qos', 'default', ''),
    ('color_camera_info_qos', 'default', ''),
    ('depth_camera_info_qos', 'default', ''),
    ('ir_camera_info_qos', 'default', ''),
]


def _launch_setup(context, *args, **kwargs):
    def val(name):
        return LaunchConfiguration(name).perform(context)

    camera_name = val('camera_name')

    params = {
        'camera_name': camera_name,
        'serial_number': val('serial_number'),
        'device_num': _as_int(val('device_num')),
        'vendor_id': 0,
        'product_id': 0,
        'connection_delay': _as_int(val('connection_delay')),

        'enable_color': _as_bool(val('enable_color')),
        'color_width': _as_int(val('color_width')),
        'color_height': _as_int(val('color_height')),
        'color_fps': _as_int(val('color_fps')),
        'flip_color': False,
        'color_qos': val('color_qos'),
        'color_camera_info_qos': val('color_camera_info_qos'),
        'color_info_url': val('color_info_url'),

        'enable_depth': _as_bool(val('enable_depth')),
        'depth_width': _as_int(val('depth_width')),
        'depth_height': _as_int(val('depth_height')),
        'depth_fps': _as_int(val('depth_fps')),
        'flip_depth': False,
        'depth_qos': val('depth_qos'),
        'depth_camera_info_qos': val('depth_camera_info_qos'),
        'depth_scale': 1,

        'enable_ir': _as_bool(val('enable_ir')),
        'ir_width': 640,
        'ir_height': 480,
        'ir_fps': 30,
        'flip_ir': False,
        'ir_qos': val('ir_qos'),
        'ir_camera_info_qos': val('ir_camera_info_qos'),
        'ir_info_url': val('ir_info_url'),

        'enable_point_cloud': _as_bool(val('enable_point_cloud')),
        'enable_colored_point_cloud': _as_bool(val('enable_colored_point_cloud')),
        'point_cloud_qos': val('point_cloud_qos'),

        'depth_registration': _as_bool(val('depth_registration')),
        'color_depth_synchronization': _as_bool(val('color_depth_synchronization')),

        'use_uvc_camera': True,
        'uvc_vendor_id': _as_int(val('uvc_vendor_id')),
        'uvc_product_id': _as_int(val('uvc_product_id')),
        'uvc_camera_format': val('uvc_camera_format'),
        'uvc_retry_count': _as_int(val('uvc_retry_count')),
        'uvc_flip': _as_bool(val('uvc_flip')),

        'publish_tf': _as_bool(val('publish_tf')),
        'tf_publish_rate': float(val('tf_publish_rate')),
        'enable_publish_extrinsic': False,
        'enable_d2c_viewer': False,

        'oni_log_level': 'verbose',
        'oni_log_to_console': False,
        'oni_log_to_file': False,
    }

    return [
        Node(
            package='astra_camera',
            executable='astra_camera_node',
            name='camera',
            namespace=camera_name,
            output='screen',
            parameters=[params],
            remappings=[
                ('/%s/depth/color/points' % camera_name,
                 '/%s/depth_registered/points' % camera_name),
            ],
        ),
    ]


def generate_launch_description():
    declared = [
        DeclareLaunchArgument(name, default_value=default, description=description)
        for name, default, description in LAUNCH_ARGS
    ]
    return LaunchDescription(declared + [OpaqueFunction(function=_launch_setup)])
