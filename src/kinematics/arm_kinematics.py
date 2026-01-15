"""
2-DOF Planar Arm Inverse Kinematics for OpenDuck Mini V3.

This module implements analytical inverse and forward kinematics for a 2-DOF
planar robotic arm using the law of cosines approach.

Coordinate Frame:
    - Origin at shoulder joint
    - X-axis points forward (positive direction)
    - Y-axis points up (positive direction)
    - Angles measured counter-clockwise from positive X-axis

Mathematical Foundation:
    Uses law of cosines for IK solver:
    - distance = sqrt(x^2 + y^2)
    - cos(elbow) = (l1^2 + l2^2 - d^2) / (2 * l1 * l2)
    - shoulder = atan2(y, x) +/- acos((d^2 + l1^2 - l2^2) / (2 * d * l1))
"""

from __future__ import annotations

import math
from typing import Optional, Tuple

import numpy as np

# Tolerance for floating-point comparisons (standardized across module)
_EPSILON: float = 1e-10


class ArmKinematics:
    """
    2-DOF planar arm kinematics solver.

    This class provides inverse kinematics (IK) and forward kinematics (FK)
    solutions for a 2-link planar robotic arm.

    Attributes:
        l1: Length of first link (shoulder to elbow) in millimeters.
        l2: Length of second link (elbow to end effector) in millimeters.

    Example:
        >>> arm = ArmKinematics(l1=80.0, l2=60.0)
        >>> angles = arm.solve_ik(100.0, 50.0, elbow_up=True)
        >>> if angles:
        ...     shoulder, elbow = angles
        ...     print(f"Shoulder: {math.degrees(shoulder):.2f} deg")
        ...     print(f"Elbow: {math.degrees(elbow):.2f} deg")
    """

    def __init__(self, l1: float, l2: float) -> None:
        """
        Initialize the arm kinematics solver with link lengths.

        Args:
            l1: Length of first link (shoulder to elbow) in millimeters.
                Must be a positive finite number.
            l2: Length of second link (elbow to end effector) in millimeters.
                Must be a positive finite number.

        Raises:
            ValueError: If l1 or l2 is not positive, or is NaN/infinity.
        """
        # Validate l1
        if not isinstance(l1, (int, float)):
            raise ValueError(f"l1 must be a number, got {type(l1).__name__}")
        if math.isnan(l1) or math.isinf(l1):
            raise ValueError(f"l1 must be finite, got {l1}")
        if l1 <= 0:
            raise ValueError(f"l1 must be positive, got {l1}")

        # Validate l2
        if not isinstance(l2, (int, float)):
            raise ValueError(f"l2 must be a number, got {type(l2).__name__}")
        if math.isnan(l2) or math.isinf(l2):
            raise ValueError(f"l2 must be finite, got {l2}")
        if l2 <= 0:
            raise ValueError(f"l2 must be positive, got {l2}")

        self._l1 = float(l1)
        self._l2 = float(l2)
        self._max_reach = self._l1 + self._l2
        self._min_reach = abs(self._l1 - self._l2)

    @property
    def l1(self) -> float:
        """Get the length of the first link (shoulder to elbow)."""
        return self._l1

    @property
    def l2(self) -> float:
        """Get the length of the second link (elbow to end effector)."""
        return self._l2

    @property
    def max_reach(self) -> float:
        """Get the maximum reach of the arm (l1 + l2)."""
        return self._max_reach

    @property
    def min_reach(self) -> float:
        """Get the minimum reach of the arm (|l1 - l2|)."""
        return self._min_reach

    def is_reachable(self, x: float, y: float) -> bool:
        """
        Check if a target position is within the workspace of the arm.

        Args:
            x: Target X coordinate in millimeters.
            y: Target Y coordinate in millimeters.

        Returns:
            True if the target is reachable, False otherwise.
            Returns False for NaN or infinite inputs.
        """
        # Handle invalid inputs
        if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
            return False
        if math.isnan(x) or math.isnan(y) or math.isinf(x) or math.isinf(y):
            return False

        distance = math.sqrt(x * x + y * y)

        # Check if within workspace (between min and max reach)
        # Use standardized epsilon for floating point comparison at boundaries
        return (self._min_reach - _EPSILON) <= distance <= (self._max_reach + _EPSILON)

    def solve_ik(
        self, x: float, y: float, elbow_up: bool = True
    ) -> Optional[Tuple[float, float]]:
        """
        Solve inverse kinematics for target position.

        Computes joint angles (shoulder, elbow) to reach the target (x, y)
        position using the law of cosines approach.

        Args:
            x: Target X coordinate in millimeters.
            y: Target Y coordinate in millimeters.
            elbow_up: If True, return elbow-up solution (elbow above the
                line from shoulder to end effector). If False, return
                elbow-down solution. Default is True.

        Returns:
            A tuple (shoulder_angle, elbow_angle) in radians if the target
            is reachable, or None if the target is outside the workspace.
            Angles are measured counter-clockwise from positive X-axis.
            Shoulder angle is the absolute angle of the first link.
            Elbow angle is the relative angle between links (0 = straight).

        Raises:
            None - returns None for unreachable targets or invalid inputs.

        Note:
            - Both angles are in radians
            - Shoulder angle is in range [-pi, pi]
            - Elbow angle is in range [-pi, pi] (negative = elbow down)
        """
        # Validate inputs
        if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
            return None
        if math.isnan(x) or math.isnan(y) or math.isinf(x) or math.isinf(y):
            return None

        # Calculate distance to target
        distance_squared = x * x + y * y
        distance = math.sqrt(distance_squared)

        # Handle origin case (division by zero risk)
        if distance < _EPSILON:
            # At origin - technically reachable only if l1 == l2
            # Return folded arm configuration pointing along +X axis
            if abs(self._l1 - self._l2) < _EPSILON:
                return (0.0, math.pi)  # Shoulder at 0, elbow fully folded back
            return None

        # Check reachability
        if not self.is_reachable(x, y):
            return None

        # Law of cosines to find elbow angle
        # cos(elbow) = (l1^2 + l2^2 - d^2) / (2 * l1 * l2)
        cos_elbow = (self._l1**2 + self._l2**2 - distance_squared) / (
            2 * self._l1 * self._l2
        )
        # Clamp to [-1, 1] to handle floating point errors at boundaries
        cos_elbow = max(-1.0, min(1.0, cos_elbow))

        # Calculate elbow angle (interior angle)
        # pi - acos gives the exterior angle (elbow deflection from straight)
        elbow_interior = math.acos(cos_elbow)
        if elbow_up:
            # Elbow-up: negative elbow angle (elbow bends upward/counterclockwise)
            elbow_angle = elbow_interior - math.pi
        else:
            # Elbow-down: positive elbow angle (elbow bends downward/clockwise)
            elbow_angle = math.pi - elbow_interior

        # Calculate shoulder angle
        # First, angle to target
        angle_to_target = math.atan2(y, x)

        # Then, angle offset due to elbow configuration
        # cos(alpha) = (d^2 + l1^2 - l2^2) / (2 * d * l1)
        cos_alpha = (distance_squared + self._l1**2 - self._l2**2) / (
            2 * distance * self._l1
        )
        # Clamp to [-1, 1] to handle floating point errors
        cos_alpha = max(-1.0, min(1.0, cos_alpha))
        alpha = math.acos(cos_alpha)

        if elbow_up:
            shoulder_angle = angle_to_target + alpha
        else:
            shoulder_angle = angle_to_target - alpha

        # Normalize shoulder angle to [-pi, pi] using atan2 (O(1) vs O(k) where k = number of 2π wraps for while-loop)
        shoulder_angle = math.atan2(math.sin(shoulder_angle), math.cos(shoulder_angle))

        return (shoulder_angle, elbow_angle)

    def solve_fk(
        self, shoulder_angle: float, elbow_angle: float
    ) -> Tuple[float, float]:
        """
        Solve forward kinematics to get end effector position.

        Computes the (x, y) position of the end effector given joint angles.

        Args:
            shoulder_angle: Angle of the first link in radians, measured
                counter-clockwise from positive X-axis.
            elbow_angle: Relative angle of the second link in radians,
                measured from the first link direction (0 = straight,
                positive = clockwise, negative = counterclockwise).

        Returns:
            A tuple (x, y) of the end effector position in millimeters.

        Raises:
            ValueError: If angles are NaN or infinity.
        """
        # Validate inputs
        if not isinstance(shoulder_angle, (int, float)) or not isinstance(
            elbow_angle, (int, float)
        ):
            raise ValueError(
                f"Angles must be numbers, got {type(shoulder_angle).__name__} "
                f"and {type(elbow_angle).__name__}"
            )
        if math.isnan(shoulder_angle) or math.isnan(elbow_angle):
            raise ValueError("Angles must not be NaN")
        if math.isinf(shoulder_angle) or math.isinf(elbow_angle):
            raise ValueError("Angles must be finite")

        # Calculate elbow position
        elbow_x = self._l1 * math.cos(shoulder_angle)
        elbow_y = self._l1 * math.sin(shoulder_angle)

        # Calculate end effector position
        # The second link angle is shoulder_angle + elbow_angle
        total_angle = shoulder_angle + elbow_angle
        end_x = elbow_x + self._l2 * math.cos(total_angle)
        end_y = elbow_y + self._l2 * math.sin(total_angle)

        return (end_x, end_y)

    def get_workspace_boundary(self, num_points: int = 100) -> np.ndarray:
        """
        Generate points along the workspace boundary.

        The workspace boundary consists of two circular arcs:
        1. Outer arc: radius = l1 + l2 (arm fully extended)
        2. Inner arc: radius = |l1 - l2| (arm fully folded)

        Args:
            num_points: Total number of points to generate along the
                boundary. Points are distributed between outer and inner
                arcs. Default is 100.

        Returns:
            A numpy array of shape (N, 2) containing (x, y) coordinates
            of boundary points in millimeters. Points trace the full
            workspace boundary.

        Raises:
            ValueError: If num_points is less than 4.
        """
        if num_points < 4:
            raise ValueError(f"num_points must be at least 4, got {num_points}")

        # Distribute points between outer and inner arcs
        outer_points = num_points // 2
        inner_points = num_points - outer_points

        boundary = []

        # Outer boundary (maximum reach) - full circle
        for i in range(outer_points):
            angle = 2 * math.pi * i / outer_points
            x = self._max_reach * math.cos(angle)
            y = self._max_reach * math.sin(angle)
            boundary.append([x, y])

        # Inner boundary (minimum reach) - full circle if min_reach > 0
        if self._min_reach > _EPSILON:
            for i in range(inner_points):
                # Traverse in opposite direction for continuous boundary
                angle = 2 * math.pi * (inner_points - 1 - i) / inner_points
                x = self._min_reach * math.cos(angle)
                y = self._min_reach * math.sin(angle)
                boundary.append([x, y])
        else:
            # If min_reach is ~0, just add origin points
            for _ in range(inner_points):
                boundary.append([0.0, 0.0])

        return np.array(boundary, dtype=np.float64)

    def __repr__(self) -> str:
        """Return string representation of the kinematics solver."""
        return (
            f"ArmKinematics(l1={self._l1}, l2={self._l2}, "
            f"max_reach={self._max_reach}, min_reach={self._min_reach})"
        )
