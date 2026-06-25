#!/usr/bin/env python3
# =============================================================================
# pick_demo.py  (TANG 2 - kich ban co dinh, da can theo toa do thuc)
# Demo gap lon DAT TREN BAN truoc tay SCARA.
#
# DA BIET (do tf2_echo): voi J1=0, J2=0, J_z=0 -> gripper o ~ (x=0.50, z=0.54).
# Lon tren ban o (x=0.50, z=0.51). Vay gripper DA o ngay tren lon theo x!
# Chi can ha Z xuong ~3-4cm cho ngam om than lon, roi khep.
#
# Moi tu the: [J_z(m), J1(rad), J2(rad), J_wrist(rad), J_grip(m)]
#   J_z  : 0 = cao nhat ; cang am cang ha xuong (toi -0.40)
#   J_grip: 0.05 = mo het ; 0.0 = khep (kep)
# =============================================================================
import time
import rclpy
from rclpy.node import Node
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint
from builtin_interfaces.msg import Duration

JOINTS = ['J_z', 'J1', 'J2', 'J_wrist', 'J_grip']

POSES = [
    ('1. Home, mo gripper',          [ 0.00, 0.0, 0.0, 0.0, 0.05]),
    ('2. Ha Z xuong ngang than lon', [-0.06, 0.0, 0.0, 0.0, 0.05]),
    ('3. Khep gripper (kep lon)',    [-0.06, 0.0, 0.0, 0.0, 0.00]),
    ('4. Nang lon len',              [ 0.00, 0.0, 0.0, 0.0, 0.00]),
    ('5. Xoay mang lon sang ben',    [ 0.00, 1.2, 0.0, 0.0, 0.00]),
    ('6. Ha xuong, tha lon',        [-0.04, 1.2, 0.0, 0.0, 0.05]),
    ('7. Ve home',                   [ 0.00, 0.0, 0.0, 0.0, 0.05]),
]


class PickDemo(Node):
    def __init__(self):
        super().__init__('pick_demo')
        self.pub = self.create_publisher(
            JointTrajectory, '/arm_controller/joint_trajectory', 10)
        time.sleep(1.0)

    def go(self, positions, secs):
        msg = JointTrajectory()
        msg.joint_names = JOINTS
        pt = JointTrajectoryPoint()
        pt.positions = [float(x) for x in positions]
        pt.time_from_start = Duration(sec=int(secs), nanosec=0)
        msg.points = [pt]
        self.pub.publish(msg)

    def run(self):
        for label, pose in POSES:
            self.get_logger().info(f'>>> {label}')
            self.go(pose, secs=2)
            time.sleep(2.5)
        self.get_logger().info('=== Demo gap xong ===')


def main(args=None):
    rclpy.init(args=args)
    node = PickDemo()
    try:
        node.run()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
