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

        self.assertEqual(35, len(references))
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


if __name__ == "__main__":
    unittest.main()
