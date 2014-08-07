#!/usr/bin/env python

import rospy
import baxter_interface
from baxter_interface import CHECK_VERSION
import os
import argparse

from visual_servo import VisualCommand
import common
import ik_command

from geometry_msgs.msg import Pose

class DepthCaller:
    def __init__(self, limb, iksvc):
        self.done = False
        self.iksvc = iksvc
        self.limb = limb

        self.depth_handler = rospy.Subscriber("object_tracker/"+limb+"/goal_pose", Pose, self.depth_callback)

    def depth_callback(self, data):
        print "Estimating depth"
        pose = data
        p = [pose.position.x, pose.position.y, pose.position.z]+[pose.orientation.x, pose.orientation.y, pose.orientation.z, pose.orientation.w]
        ik_command.service_request(self.iksvc, p, self.limb, blocking=True)
        print p

        self.done = True
        print "unregistering"
        self.depth_handler.unregister()


def main():
    arg_fmt = argparse.RawDescriptionHelpFormatter
    parser = argparse.ArgumentParser(formatter_class=arg_fmt,
                                     description=main.__doc__)
    required = parser.add_argument_group('required arguments')
    required.add_argument(
        '-l', '--limb', required=True, choices=['left', 'right'],
        help='send joint trajectory to which limb'
    )

    args = parser.parse_args(rospy.myargv()[1:])
    print args
    limb = args.limb

    print("Initializing node... ")
    rospy.init_node("_%s" % (limb,))
    print("Getting robot state... ")
    rs = baxter_interface.RobotEnable(CHECK_VERSION)
    print("Enabling robot... ")
    rs.enable()

    #Calibrate gripper
    gripper_if = baxter_interface.Gripper(limb)
    if not gripper_if.calibrated():
        print "Calibrating gripper"
        gripper_if.calibrate()


    limbInterface = baxter_interface.Limb(limb)

    iksvc, ns = ik_command.connect_service(limb)
    rate = rospy.Rate(100)


    # TODO: Get goal pose from kinect
    """dc = DepthCaller(limb, iksvc)"""

    # Subscribe to estimate_depth
    # Move to pose published by estimate_depth
    while (not dc.done) and (not rospy.is_shutdown()):
        rate.sleep()
        #pass

    print "Start visual servoing to first object"
    
    # Subscribe to object_finder and start visual servoing/grasping
    vc = VisualCommand(iksvc, limb)
    vc.subscribe()

    while (not vc.done) and (not rospy.is_shutdown()):
        rate.sleep()

    limbInterface.move_to_joint_positions(points[1])

    # Let go
    gripper_if.open()

if __name__ == "__main__":
    main()
