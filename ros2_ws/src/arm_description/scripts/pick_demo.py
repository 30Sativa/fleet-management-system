#!/usr/bin/env python3
# =============================================================================
# pick_demo.py
# Demo GAP THEO KICH BAN CO DINH cho tay SCARA trong Gazebo.
# Khong dung camera/AI: lon o vi tri biet truoc, tay dien chuoi dong tac:
#   home -> vuon toi tren lon -> ha xuong -> kep -> nang len -> xoay -> tha.
#
# Cac tu the la GOC KHOP dat san (hard-code). Tinh chinh cac so trong POSES
# cho khop voi tay/lon cua ban (xem Gazebo roi sua).
#
# Chay (sau khi da launch gazebo_arm.launch.py):
#   ros2 run arm_description pick_demo
# Hoac:
#   python3 pick_demo.py
# =============================================================================
import time
import rclpy
from rclpy.node import Node
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint
from builtin_interfaces.msg import Duration

JOINTS = ['J_z', 'J1', 'J2', 'J_wrist', 'J_grip']

# Moi tu the: [J_z(m), J1(rad), J2(rad), J_wrist(rad), J_grip(m)]
# J_grip: 0.0 = khep (kep chac) ; 0.05 = mo het.
# >>> DAY LA SO UOC LUONG - chinh lai sau khi xem Gazebo. <<<
POSES = [
    ('1. Home (tu the nghi)',        [ 0.00, 0.0,  0.0, 0.0, 0.05]),
    ('2. Vuon toi phia lon, mo kep', [ 0.00, 0.0,  0.0, 0.0, 0.05]),
    ('3. Ha truc Z xuong ngang lon', [-0.30, 0.0,  0.0, 0.0, 0.05]),
    ('4. Khep gripper (kep lon)',    [-0.30, 0.0,  0.0, 0.0, 0.00]),
    ('5. Nang lon len',              [-0.05, 0.0,  0.0, 0.0, 0.00]),
    ('6. Xoay mang lon di cho khac', [-0.05, 1.2,  0.0, 1.5, 0.00]),
    ('7. Ha xuong, tha lon',         [-0.25, 1.2,  0.0, 1.5, 0.05]),
    ('8. Ve home',                   [ 0.00, 0.0,  0.0, 0.0, 0.05]),
]


class PickDemo(Node):
    def __init__(self):
        super().__init__('pick_demo')
        self.pub = self.create_publisher(
            JointTrajectory, '/arm_controller/joint_trajectory', 10)
        # cho publisher ket noi
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
            # cho tay toi noi (2s di chuyen + 0.5s on dinh)
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
