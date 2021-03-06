#!/usr/bin/env python
import roslib
roslib.load_manifest('cob_hardware_test')
#from mpmath.functions.functions import fabs
import sys
import time
import unittest
import math

import rospy
import rostest
from cob_hardware_test.srv import *
from trajectory_msgs.msg import *
from simple_script_server import *
from pr2_controllers_msgs.msg import *


def dialog_client(dialog_type, message):
    #dialog type: 0=confirm 1=question
    rospy.wait_for_service('dialog')
    try:
        dialog = rospy.ServiceProxy('dialog', Dialog)
        resp1 = dialog(dialog_type, message)
        return resp1.answer
    except rospy.ServiceException, e:
        print "Service call failed: %s" % e

class UnitTest(unittest.TestCase):
    def __init__(self, *args):
        super(UnitTest, self).__init__(*args)
        rospy.init_node('component_test')
        self.message_received = False
        self.sss = simple_script_server()
        self.command_traj = JointTrajectory()
        # get parameters
        try:
            # component
            if not rospy.has_param('~component'):
                self.fail('Parameter component does not exist on ROS Parameter Server')
            self.component = rospy.get_param('~component')
            # movement command
            if not rospy.has_param('~test_target'):
                self.fail('Parameter test_target does not exist on ROS Parameter Server')
            self.test_target = rospy.get_param('~test_target')
            # movement command
            if not rospy.has_param('~default_target'):
                 self.fail('Parameter default_target does not exist on ROS Parameter Server')
            self.default_target = rospy.get_param('~default_target')
            # time to wait before
            self.wait_time = rospy.get_param('~wait_time', 5)
            # error range
            if not rospy.has_param('~error_range'):
                self.fail('Parameter error_range does not exist on ROS Parameter Server')
            self.error_range = rospy.get_param('~error_range')
        except KeyError, e:
            self.fail('Parameters not set properly')
        print """
              Component: %s  
              Targets: %s , %s
              Wait Time: %s
              Error Range: %s""" % (self.component, self.default_target, self.test_target, self.wait_time, self.error_range)
        # check parameters
        # \todo do more parameter tests
        if self.error_range < 0.0:
            error_msg = "Parameter error_range should be positive, but is " + self.error_range
            self.fail(error_msg)
        if self.wait_time < 0.0:
            error_msg = "Parameter wait_time should be positive, but is " + self.wait_time
            self.fail(error_msg)

        # init subscribers
        state_topic = "/" + self.component + "_controller/state"
        sub_state_topic = rospy.Subscriber(state_topic, JointTrajectoryControllerState, self.cb_state)

    def test_component(self):
        
        # init component
        init_handle = self.sss.init(self.component)
        if init_handle.get_error_code() != 0:
          error_msg = 'Could not initialize ' + self.component
          self.fail(error_msg)

        # start actual test
        print "Waiting for messages"
        #give the topics some seconds to receive messages
        abort_time = rospy.Time.now() + rospy.Duration(self.wait_time)
        while not self.message_received and rospy.get_rostime() < abort_time:
         #   print "###debug here###"
            rospy.sleep(0.1)
                        
        if not self.message_received:
            self.fail('No state message received within wait_time(%s) from /%s_controller/state' % (self.wait_time, self.component))

        self.assertTrue(dialog_client(0, 'Ready to move %s to %s ?' % (self.component, self.test_target)))

        # send commands to component
        move_handle = self.sss.move(self.component, self.test_target)

        self.assertEqual(move_handle.get_state(), 3)
        #state 3 equals errorcode 0 therefore the following will never be executed
        if move_handle.get_error_code() != 0:
            error_msg = 'Could not move ' + self.component
            self.fail(error_msg + "; errorCode: " + str(move_handle.get_error_code()))

        self.check_target_reached(self.test_target)
#move end

        self.assertTrue(dialog_client(1, ' EM Pressed and Released? \n Ready to move %s to %s ?' % (self.component, self.default_target)))

        recover_handle = self.sss.recover(self.component)
        if recover_handle.get_error_code() != 0 :
           error_msg = 'Could not recover ' + self.component
           self.fail(error_msg)

#move start
        # send commands to component
        move_handle = self.sss.move(self.component, self.default_target)
        self.assertEqual(move_handle.get_state(), 3)

        if move_handle.get_error_code() != 0:
            error_msg = 'Could not move ' + self.component
            self.fail(error_msg + "; errorCode: " + str(move_handle.get_error_code()))

        self.check_target_reached(self.default_target)

#move end

    def check_target_reached(self,target):
        # get commanded trajectory
        command_traj = rospy.get_param("/script_server/" + self.component + "/" + target)
        print command_traj

        # get last point out of trajectory
        traj_endpoint = command_traj[len(command_traj) - 1]
        print traj_endpoint

        actual_pos = self.actual_pos # fix current position configuration for later evaluation

        # checking if target position is really reached
        print "actual_pos = ", actual_pos
        print "traj_endpoint = ", traj_endpoint
        for i in range(len(traj_endpoint)):
            self.assert_(((math.fabs(traj_endpoint[i] - actual_pos[i])) < self.error_range), "Target position out of error_range")

        self.assertTrue(dialog_client(1, 'Did %s move to %s ?' % (self.component, target)))

    # callback functions

    def cb_state(self, msg):
        self.actual_pos = msg.actual.positions
        self.message_received = True


if __name__ == '__main__':
    try:
        rostest.run('rostest', 'component_test', UnitTest, sys.argv)
    except KeyboardInterrupt, e:
        pass
    print "exiting"

