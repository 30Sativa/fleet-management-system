import math
import struct
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parents[1]
MESH_DIR = PACKAGE_DIR / "meshes"
ROBOT_XACRO = PACKAGE_DIR / "urdf" / "robot.urdf.xacro"
SENSORS_XACRO = PACKAGE_DIR / "urdf" / "sensors.xacro"
COMMON_XACRO = PACKAGE_DIR / "urdf" / "common_properties.xacro"
XACRO_NS = "http://www.ros.org/wiki/xacro"


def read_stl_bounds(path):
    data = path.read_bytes()
    if len(data) < 84:
        raise ValueError("binary STL header is incomplete")

    triangle_count = struct.unpack_from("<I", data, 80)[0]
    expected_size = 84 + triangle_count * 50
    if len(data) != expected_size:
        raise ValueError(
            f"binary STL size is {len(data)} bytes, expected {expected_size}"
        )

    minimum = [math.inf, math.inf, math.inf]
    maximum = [-math.inf, -math.inf, -math.inf]
    for triangle in struct.iter_unpack("<12fH", data[84:]):
        for vertex_offset in (3, 6, 9):
            for axis in range(3):
                value = triangle[vertex_offset + axis]
                if not math.isfinite(value):
                    raise ValueError("STL contains a non-finite coordinate")
                minimum[axis] = min(minimum[axis], value)
                maximum[axis] = max(maximum[axis], value)

    if triangle_count == 0:
        raise ValueError("STL contains no triangles")
    return minimum, maximum


class RobotDescriptionMeshTest(unittest.TestCase):
    def test_xacro_references_every_mesh_once(self):
        root = ET.parse(ROBOT_XACRO).getroot()
        reference_tags = {
            f"{{{XACRO_NS}}}body_visual",
            f"{{{XACRO_NS}}}assembly_visual",
            f"{{{XACRO_NS}}}drive_wheel",
            f"{{{XACRO_NS}}}caster_wheel",
        }
        references = [
            element.attrib["mesh_file"]
            for element in root.iter()
            if element.tag in reference_tags
        ]
        sensors_root = ET.parse(SENSORS_XACRO).getroot()
        references.extend(
            element.attrib["filename"].rsplit("/", 1)[-1]
            for element in sensors_root.iter("mesh")
            if element.attrib["filename"].endswith(".stl")
        )
        mesh_files = sorted(path.name for path in MESH_DIR.glob("*.stl"))

        self.assertEqual(37, len(references))
        self.assertEqual(len(references), len(set(references)))
        self.assertEqual(mesh_files, sorted(references))

    def test_stl_files_are_valid_and_match_body_envelope(self):
        root = ET.parse(ROBOT_XACRO).getroot()
        body_tag = f"{{{XACRO_NS}}}body_visual"
        body_meshes = [
            MESH_DIR / element.attrib["mesh_file"]
            for element in root.iter(body_tag)
        ]
        self.assertEqual(28, len(body_meshes))

        aggregate_min = [math.inf, math.inf, math.inf]
        aggregate_max = [-math.inf, -math.inf, -math.inf]
        for mesh_path in sorted(MESH_DIR.glob("*.stl")):
            minimum, maximum = read_stl_bounds(mesh_path)
            if mesh_path in body_meshes:
                for axis in range(3):
                    aggregate_min[axis] = min(aggregate_min[axis], minimum[axis])
                    aggregate_max[axis] = max(aggregate_max[axis], maximum[axis])

        dimensions = [
            (aggregate_max[2] - aggregate_min[2]) / 1000,
            (aggregate_max[0] - aggregate_min[0]) / 1000,
            (aggregate_max[1] - aggregate_min[1]) / 1000,
        ]
        common_root = ET.parse(COMMON_XACRO).getroot()
        property_tag = f"{{{XACRO_NS}}}property"
        properties = {
            element.attrib["name"]: element.attrib["value"]
            for element in common_root.iter(property_tag)
        }
        expected_dimensions = [
            float(properties["base_length"]),
            float(properties["base_width"]),
            float(properties["base_height"]),
        ]
        for actual, expected_value in zip(dimensions, expected_dimensions):
            self.assertAlmostEqual(expected_value, actual, places=6)

        body_origin = [
            float(value) for value in properties["body_mesh_origin"].split()
        ]
        cad_center = [
            (aggregate_min[axis] + aggregate_max[axis]) / 2
            for axis in range(3)
        ]
        collision_center = [
            cad_center[2] / 1000 + body_origin[0],
            cad_center[0] / 1000 + body_origin[1],
            cad_center[1] / 1000 + body_origin[2],
        ]
        expected_center = [
            float(properties["base_collision_x"]),
            float(properties["base_collision_y"]),
            float(properties["base_collision_z"]),
        ]
        for actual, expected_value in zip(collision_center, expected_center):
            self.assertAlmostEqual(expected_value, actual, places=6)

    def test_mesh_origins_match_cad_assembly(self):
        root = ET.parse(ROBOT_XACRO).getroot()
        common_root = ET.parse(COMMON_XACRO).getroot()
        property_tag = f"{{{XACRO_NS}}}property"
        properties = {
            element.attrib["name"]: element.attrib["value"]
            for element in common_root.iter(property_tag)
        }

        chassis_min, chassis_max = read_stl_bounds(MESH_DIR / "chassis.stl")
        chassis_center = [
            (chassis_min[axis] + chassis_max[axis]) / 2 for axis in range(3)
        ]
        body_origin = [
            float(value) for value in properties["body_mesh_origin"].split()
        ]
        expected_body_origin = [
            -chassis_center[2] / 1000,
            -chassis_center[0] / 1000,
            -chassis_center[1] / 1000,
        ]
        for actual, expected_value in zip(body_origin, expected_body_origin):
            self.assertAlmostEqual(expected_value, actual, places=6)

        drive_tag = f"{{{XACRO_NS}}}drive_wheel"
        caster_tag = f"{{{XACRO_NS}}}caster_wheel"
        caster_positions = {
            "front_left": ("caster_front_x", "caster_left_y"),
            "front_right": ("caster_front_x", "caster_right_y"),
            "rear_left": ("caster_rear_x", "caster_left_y"),
            "rear_right": ("caster_rear_x", "caster_right_y"),
        }

        for element in list(root.iter(drive_tag)) + list(root.iter(caster_tag)):
            minimum, maximum = read_stl_bounds(
                MESH_DIR / element.attrib["mesh_file"]
            )
            cad_center = [
                (minimum[axis] + maximum[axis]) / 2 for axis in range(3)
            ]
            expected_mesh_origin = [
                -cad_center[2] / 1000,
                -cad_center[0] / 1000,
                -cad_center[1] / 1000,
            ]
            actual_mesh_origin = [
                float(element.attrib[name])
                for name in ("mesh_x", "mesh_y", "mesh_z")
            ]
            for actual, expected_value in zip(
                actual_mesh_origin, expected_mesh_origin
            ):
                self.assertAlmostEqual(expected_value, actual, places=6)

            relative_center = [
                cad_center[2] / 1000 + body_origin[0],
                cad_center[0] / 1000 + body_origin[1],
            ]
            if element.tag == drive_tag:
                expected_y = (
                    float(element.attrib["reflect"])
                    * float(properties["wheel_separation"])
                    / 2
                )
                self.assertAlmostEqual(0.0, relative_center[0], places=6)
                self.assertAlmostEqual(expected_y, relative_center[1], places=6)
            else:
                x_property, y_property = caster_positions[element.attrib["prefix"]]
                self.assertAlmostEqual(
                    float(properties[x_property]), relative_center[0], delta=0.0001
                )
                self.assertAlmostEqual(
                    float(properties[y_property]), relative_center[1], delta=0.0001
                )

        sensors_root = ET.parse(SENSORS_XACRO).getroot()
        lidar_origin = sensors_root.find("./link[@name='lidar_link']/visual/origin")
        lidar_min, lidar_max = read_stl_bounds(MESH_DIR / "lidar_body.stl")
        lidar_center = [
            (lidar_min[axis] + lidar_max[axis]) / 2 for axis in range(3)
        ]
        expected_lidar_origin = [
            -lidar_center[2] / 1000,
            -lidar_center[0] / 1000,
            -lidar_center[1] / 1000,
        ]
        actual_lidar_origin = [
            float(value) for value in lidar_origin.attrib["xyz"].split()
        ]
        for actual, expected_value in zip(
            actual_lidar_origin, expected_lidar_origin
        ):
            self.assertAlmostEqual(expected_value, actual, places=6)

        sensor_properties = {
            element.attrib["name"]: element.attrib["value"]
            for element in sensors_root.iter(property_tag)
        }
        expected_lidar_position = [
            lidar_center[2] / 1000 + body_origin[0],
            lidar_center[0] / 1000 + body_origin[1],
            lidar_center[1] / 1000 + body_origin[2],
        ]
        actual_lidar_position = [
            float(sensor_properties[name])
            for name in ("lidar_x", "lidar_y", "lidar_z")
        ]
        for actual, expected_value in zip(
            actual_lidar_position, expected_lidar_position
        ):
            self.assertAlmostEqual(expected_value, actual, places=6)


if __name__ == "__main__":
    unittest.main()
