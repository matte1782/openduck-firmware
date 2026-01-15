"""
Kinematics module for OpenDuck Mini V3 robot.

This module provides inverse and forward kinematics solvers for the robot's
manipulator arms and legs.

Week 01: 2-DOF planar arm kinematics
Future: 3-DOF leg kinematics for quadruped locomotion
"""

from .arm_kinematics import ArmKinematics

__version__ = "0.1.0"

# Default link lengths for OpenDuck Mini V3 (in millimeters)
DEFAULT_L1 = 80.0  # Shoulder to elbow
DEFAULT_L2 = 60.0  # Elbow to end effector

# Exports: class first, then version, then constants
__all__ = ["ArmKinematics", "__version__", "DEFAULT_L1", "DEFAULT_L2"]
