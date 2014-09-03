#!/usr/bin/env python

import argparse
import sys
import copy
import rospy
import numpy
import cv2
import tf
import moveit_commander

from std_msgs.msg import Header

from moveit_msgs.msg import (
    AttachedCollisionObject,
    CollisionObject,
    PlanningScene,
    Grasp,
    GripperTranslation,
)

from trajectory_msgs.msg import(
    JointTrajectory,
    JointTrajectoryPoint
)

from baxter_demos.msg import (
    CollisionObjectArray,
    BlobInfo,
    BlobInfoArray
)

from geometry_msgs.msg import (
    Point,
    Polygon,
    Pose,
    PoseStamped,
    Quaternion,
    Vector3,
    Vector3Stamped
)

import baxter_interface
from baxter_interface import CHECK_VERSION
import yaml
from super_stacker import incrementPoseMsgZ
from object_finder import ObjectFinder
from visual_servo import VisualCommand
import ik_command

class ObjectManager:
    # Subscribe to the /object_tracker/collision_objects topic
    # Make any necessary modifications received from this object's owner
    # Publish collision_objects to planning_scene

    def callback(self, data):
        collision_objects = data.objects
        self.collision_objects = collision_objects

        for obj in collision_objects:
            self.id_operations[obj.id] = obj.operation
        if not self.published:
            self.publish_all()
            self.published = True

    def publish(self, obj):
        obj.operation = self.id_operations[obj.id]
        self.pub.publish(obj)

        
    def publish_all(self):
        for obj in self.collision_objects:
            self.publish(obj)

    def publish_attached(self, attached_obj, side):
        attached_obj.operation = CollisionObject.ADD
        msg = AttachedCollisionObject()
        msg.object = attached_obj
        msg.link_name = side+"_gripper" 
        touch_links = [side+"_gripper", side+"_gripper_base", side+"_hand_camera", side+"_hand_range", "octomap"]
        self.attached_pub.publish(msg)

    def remove_known_objects(self):
        rate = rospy.Rate(1)
        for obj in self.collision_objects:
            obj.operation = CollisionObject.REMOVE
            self.publish(obj)
            rate.sleep()


    def __init__(self):
        self.object_sub = rospy.Subscriber("object_tracker/collision_objects",
                                     CollisionObjectArray, self.callback)
        self.pub = rospy.Publisher("/collision_object", CollisionObject)
        self.attached_pub = rospy.Publisher("/attached_collision_object", AttachedCollisionObject)
        self.id_operations = {}
        self.collision_objects = []
        self.published = False
        

config_folder = rospy.get_param('object_tracker/config_folder')

with open(config_folder+'servo_to_object.yaml', 'r') as f:
    params = yaml.load(f)

"""Project the given pose into a sensible position for the Baxter gripper
   Want the gripper to point downwards (z=(0, 0, -1))"""
# Violates orientation constraint for gripper
def projectPose(pose):
    pose.orientation = Quaternion(0.6509160466, 0.758886809948,
                                 -0.0180992582839, -0.0084573527776)
    
    return pose

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
    limb = args.limb

    rospy.init_node('stackit')

    iksvc, ns = ik_command.connect_service(limb)
    moveit_commander.roscpp_initialize(sys.argv)

    rate = rospy.Rate(1)
    
    robot = moveit_commander.RobotCommander()
    scene = moveit_commander.PlanningSceneInterface()
    group = moveit_commander.MoveGroupCommander(limb+"_arm")
    group.allow_replanning(True)

    print("Getting robot state... ")
    rs = baxter_interface.RobotEnable(CHECK_VERSION)
    print("Enabling robot... ")
    rs.enable()

    #Calibrate gripper
    gripper_if = baxter_interface.Gripper(limb)
    if not gripper_if.calibrated():
        print "Calibrating gripper"
        gripper_if.calibrate()

    obj_manager = ObjectManager()
    while len(obj_manager.collision_objects) <= 0:
        rate.sleep()
    objects = obj_manager.collision_objects

    object_height = params['object_height']
    
    """if len(objects) > 1:
        stack_pose = projectPose(objects[len(objects)-1].primitive_poses[0])
        stack_pose = incrementPoseMsgZ(stack_pose, object_height*2.0)
        objects.pop(len(objects)-1)
    elif len(objects) == 1:
        stack_pose = projectPose(objects[0].primitive_poses[0])"""
    stack_pose = Pose(position=Point(0.593, -0.212, object_height-0.130),
                      orientation=Quaternion(0.6509160466, 0.758886809948,
                                 -0.0180992582839, -0.0084573527776) )

    processed_win = "Processed image"
    raw_win = "Hand camera"
    cv2.namedWindow(processed_win)
    #cv2.namedWindow(raw_win)

    rospy.on_shutdown(obj_manager.remove_known_objects)

    for obj in objects:
        obj_pose = obj.primitive_poses[0]

        #group.pick(obj.id)
        #group.place(obj.id, stack_pose)

        print "Got pose:", obj.primitive_poses[0]
        pose = projectPose(obj.primitive_poses[0])
        pose = incrementPoseMsgZ(pose, object_height*1.7)
        print "Modified pose:", pose
        #if obj.id in obj_manager.id_operations:
        #    obj_manager.id_operations[obj.id] = CollisionObject.REMOVE 
        #obj_manager.publish(obj)

        print "setting target to pose"
        # Move to the next block
        group.clear_pose_targets()
        group.set_start_state_to_current_state()
        group.set_pose_target(pose)

        plan = group.plan()

        # is there a better way of checking this?
        plan_found = len(plan.joint_trajectory.points) > 0

        if plan_found:
            #print "============ Waiting while RVIZ displays plan1..."
            #rospy.sleep(3)
            group.go(wait=True)

            imgproc = ObjectFinder("star", None, None)
            imgproc.subscribe("/cameras/"+limb+"_hand_camera/image")
            imgproc.publish(limb)

            vc = VisualCommand(iksvc, limb)
            vc.subscribe()

            while (not vc.done) and (not rospy.is_shutdown()):
                blobArray = []
                
                for centroid, axis in zip(imgproc.centroids, imgproc.axes):
                    blob = BlobInfo()
                    centroid = Point(*centroid)
                    blob.centroid = centroid
                    if axis is None:
                        axis = -1*numpy.ones(6)
                    blob.axis = Polygon([Point(*axis[0:3].tolist()),
                                         Point(*axis[3:6].tolist())])
                    blobArray.append(blob)

                msg = BlobInfoArray()
                msg.blobs = blobArray
                imgproc.handler_pub.publish(msg)
                if imgproc.processed is not None:
                    cv2.imshow(processed_win, imgproc.processed)
                cv2.waitKey(10)
            vc.unsubscribe()
            imgproc.unsubscribe()

            print "Adding attached message"
            #Add attached message
            #obj.primitive_poses[0] = incrementPoseMsgZ(obj.primitive_poses[0], *object_height) #this is in the base frame...?
            obj_manager.publish_attached(obj, limb)
            #touch_links = [limb+"_gripper", limb+"_gripper_base", limb+"_hand_camera", limb+"_hand_range"]
            #group.attach_object(obj.id, limb+"_gripper", touch_links = touch_links)
            # Carefully rise away from the object before we plan another path
            pose = incrementPoseMsgZ(pose, 2*object_height) # test this
            ik_command.service_request_pose(iksvc, pose, limb, blocking = True)
            
        else:
            print "Unable to plan path"
            continue
            # what to do?

        # Move to the stacking position
        group.clear_pose_targets()
        group.set_start_state_to_current_state()
        group.set_pose_target(stack_pose)
        plan = group.plan()
        plan_found = len(plan.joint_trajectory.points) > 0

        if plan_found:
            #print "============ Waiting while RVIZ displays plan2..."
            #rospy.sleep(3)
            group.go(wait=True)
            gripper_if.open(block=True)
            group.detach_object(obj.id)
            # Carefully rise away from the object before we plan another path
            pose = incrementPoseMsgZ(stack_pose, 2*object_height)
            ik_command.service_request_pose(iksvc, pose, limb, blocking = True)
            
        
        obj.operation = CollisionObject.REMOVE
        obj_manager.publish(obj)
        # Get the next stack pose
        stack_pose = incrementPoseMsgZ(stack_pose, object_height*3/4)

        """if obj.id in obj_manager.id_operations:
            obj_manager.id_operations[obj.id] = CollisionObject.ADD

        obj_manager.publish()"""

if __name__ == "__main__":
    main()
