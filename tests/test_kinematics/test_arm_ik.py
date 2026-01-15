"""
Comprehensive unit tests for 2-DOF arm inverse kinematics.

Tests cover:
- Inverse kinematics (IK) solutions for various target positions
- Forward kinematics (FK) verification
- FK/IK roundtrip accuracy
- Workspace boundary generation
- Edge cases (origin, boundaries, singularities)
- Input validation and error handling
"""

import math
import sys
from typing import Tuple

import numpy as np
import pytest

from src.kinematics import ArmKinematics, DEFAULT_L1, DEFAULT_L2


class TestArmKinematicsInitialization:
    """Tests for ArmKinematics constructor and validation."""

    def test_valid_initialization(self) -> None:
        """Test initialization with valid link lengths."""
        arm = ArmKinematics(l1=80.0, l2=60.0)
        assert arm.l1 == 80.0
        assert arm.l2 == 60.0
        assert arm.max_reach == 140.0
        assert arm.min_reach == 20.0

    def test_integer_link_lengths(self) -> None:
        """Test initialization with integer link lengths."""
        arm = ArmKinematics(l1=80, l2=60)
        assert arm.l1 == 80.0
        assert arm.l2 == 60.0

    def test_equal_link_lengths(self) -> None:
        """Test initialization with equal link lengths (min_reach = 0)."""
        arm = ArmKinematics(l1=50.0, l2=50.0)
        assert arm.l1 == 50.0
        assert arm.l2 == 50.0
        assert arm.max_reach == 100.0
        assert arm.min_reach == 0.0

    def test_invalid_link_lengths_zero_l1(self) -> None:
        """Test ValueError for l1 = 0."""
        with pytest.raises(ValueError, match="l1 must be positive"):
            ArmKinematics(l1=0.0, l2=60.0)

    def test_invalid_link_lengths_zero_l2(self) -> None:
        """Test ValueError for l2 = 0."""
        with pytest.raises(ValueError, match="l2 must be positive"):
            ArmKinematics(l1=80.0, l2=0.0)

    def test_invalid_link_lengths_negative_l1(self) -> None:
        """Test ValueError for negative l1."""
        with pytest.raises(ValueError, match="l1 must be positive"):
            ArmKinematics(l1=-80.0, l2=60.0)

    def test_invalid_link_lengths_negative_l2(self) -> None:
        """Test ValueError for negative l2."""
        with pytest.raises(ValueError, match="l2 must be positive"):
            ArmKinematics(l1=80.0, l2=-60.0)

    def test_invalid_link_lengths_nan_l1(self) -> None:
        """Test ValueError for NaN l1."""
        with pytest.raises(ValueError, match="l1 must be finite"):
            ArmKinematics(l1=float("nan"), l2=60.0)

    def test_invalid_link_lengths_nan_l2(self) -> None:
        """Test ValueError for NaN l2."""
        with pytest.raises(ValueError, match="l2 must be finite"):
            ArmKinematics(l1=80.0, l2=float("nan"))

    def test_invalid_link_lengths_inf_l1(self) -> None:
        """Test ValueError for infinity l1."""
        with pytest.raises(ValueError, match="l1 must be finite"):
            ArmKinematics(l1=float("inf"), l2=60.0)

    def test_invalid_link_lengths_inf_l2(self) -> None:
        """Test ValueError for infinity l2."""
        with pytest.raises(ValueError, match="l2 must be finite"):
            ArmKinematics(l1=80.0, l2=float("inf"))

    def test_repr(self) -> None:
        """Test string representation."""
        arm = ArmKinematics(l1=80.0, l2=60.0)
        repr_str = repr(arm)
        assert "ArmKinematics" in repr_str
        assert "l1=80.0" in repr_str
        assert "l2=60.0" in repr_str


class TestIsReachable:
    """Tests for workspace reachability checking."""

    @pytest.fixture
    def arm(self) -> ArmKinematics:
        """Create arm kinematics instance with default link lengths."""
        return ArmKinematics(l1=DEFAULT_L1, l2=DEFAULT_L2)

    def test_reachable_center_workspace(self, arm: ArmKinematics) -> None:
        """Test point in center of workspace is reachable."""
        assert arm.is_reachable(80.0, 50.0)

    def test_reachable_max_reach(self, arm: ArmKinematics) -> None:
        """Test point at maximum reach is reachable."""
        assert arm.is_reachable(140.0, 0.0)  # max_reach = 140

    def test_reachable_min_reach(self, arm: ArmKinematics) -> None:
        """Test point at minimum reach is reachable."""
        assert arm.is_reachable(20.0, 0.0)  # min_reach = 20

    def test_unreachable_beyond_max(self, arm: ArmKinematics) -> None:
        """Test point beyond maximum reach is not reachable."""
        assert not arm.is_reachable(150.0, 0.0)

    def test_unreachable_inside_min(self, arm: ArmKinematics) -> None:
        """Test point inside minimum reach is not reachable."""
        assert not arm.is_reachable(10.0, 0.0)

    def test_reachable_negative_x(self, arm: ArmKinematics) -> None:
        """Test point with negative X is reachable."""
        assert arm.is_reachable(-80.0, 50.0)

    def test_reachable_negative_y(self, arm: ArmKinematics) -> None:
        """Test point with negative Y is reachable."""
        assert arm.is_reachable(80.0, -50.0)

    def test_reachable_negative_both(self, arm: ArmKinematics) -> None:
        """Test point with both negative coordinates is reachable."""
        assert arm.is_reachable(-80.0, -50.0)

    def test_unreachable_nan_x(self, arm: ArmKinematics) -> None:
        """Test NaN X returns not reachable."""
        assert not arm.is_reachable(float("nan"), 50.0)

    def test_unreachable_nan_y(self, arm: ArmKinematics) -> None:
        """Test NaN Y returns not reachable."""
        assert not arm.is_reachable(80.0, float("nan"))

    def test_unreachable_inf_x(self, arm: ArmKinematics) -> None:
        """Test infinity X returns not reachable."""
        assert not arm.is_reachable(float("inf"), 50.0)

    def test_unreachable_inf_y(self, arm: ArmKinematics) -> None:
        """Test infinity Y returns not reachable."""
        assert not arm.is_reachable(80.0, float("inf"))


class TestInverseKinematics:
    """Tests for inverse kinematics solver."""

    @pytest.fixture
    def arm(self) -> ArmKinematics:
        """Create arm kinematics instance with default link lengths."""
        return ArmKinematics(l1=DEFAULT_L1, l2=DEFAULT_L2)

    def test_ik_fully_extended(self, arm: ArmKinematics) -> None:
        """Test IK for target at maximum reach (fully extended arm)."""
        # Target at max reach along X-axis
        result = arm.solve_ik(140.0, 0.0, elbow_up=True)
        assert result is not None

        shoulder, elbow = result
        # At max reach, elbow should be nearly straight (0 or close to 0)
        assert abs(elbow) < 0.01 or abs(abs(elbow) - math.pi) < 0.01
        # Shoulder should point towards target
        assert abs(shoulder) < 0.01

    def test_ik_vertical_reach(self, arm: ArmKinematics) -> None:
        """Test IK for target straight up."""
        # Target straight up at a reachable distance
        result = arm.solve_ik(0.0, 100.0, elbow_up=True)
        assert result is not None

        shoulder, elbow = result
        # Verify via FK
        x, y = arm.solve_fk(shoulder, elbow)
        assert abs(x - 0.0) < 1.0  # Within 1mm
        assert abs(y - 100.0) < 1.0

    def test_ik_unreachable_beyond_max(self, arm: ArmKinematics) -> None:
        """Test IK returns None for target beyond maximum reach."""
        result = arm.solve_ik(200.0, 0.0)
        assert result is None

    def test_ik_unreachable_inside_min(self, arm: ArmKinematics) -> None:
        """Test IK returns None for target inside minimum reach."""
        result = arm.solve_ik(5.0, 0.0)
        assert result is None

    def test_ik_elbow_up_solution(self, arm: ArmKinematics) -> None:
        """Test elbow-up IK solution."""
        result = arm.solve_ik(80.0, 60.0, elbow_up=True)
        assert result is not None

        shoulder, elbow = result
        # Verify FK produces correct position
        x, y = arm.solve_fk(shoulder, elbow)
        assert abs(x - 80.0) < 1.0
        assert abs(y - 60.0) < 1.0

    def test_ik_elbow_down_solution(self, arm: ArmKinematics) -> None:
        """Test elbow-down IK solution."""
        result = arm.solve_ik(80.0, 60.0, elbow_up=False)
        assert result is not None

        shoulder, elbow = result
        # Verify FK produces correct position
        x, y = arm.solve_fk(shoulder, elbow)
        assert abs(x - 80.0) < 1.0
        assert abs(y - 60.0) < 1.0

    def test_ik_elbow_up_vs_down_different(self, arm: ArmKinematics) -> None:
        """Test that elbow-up and elbow-down give different solutions."""
        result_up = arm.solve_ik(80.0, 60.0, elbow_up=True)
        result_down = arm.solve_ik(80.0, 60.0, elbow_up=False)

        assert result_up is not None
        assert result_down is not None

        # Solutions should be different (unless at a singularity)
        shoulder_up, elbow_up = result_up
        shoulder_down, elbow_down = result_down

        # At least one angle should be different
        angles_different = (
            abs(shoulder_up - shoulder_down) > 0.01
            or abs(elbow_up - elbow_down) > 0.01
        )
        assert angles_different

    def test_ik_negative_coordinates_x(self, arm: ArmKinematics) -> None:
        """Test IK for target with negative X coordinate."""
        result = arm.solve_ik(-80.0, 60.0, elbow_up=True)
        assert result is not None

        shoulder, elbow = result
        x, y = arm.solve_fk(shoulder, elbow)
        assert abs(x - (-80.0)) < 1.0
        assert abs(y - 60.0) < 1.0

    def test_ik_negative_coordinates_y(self, arm: ArmKinematics) -> None:
        """Test IK for target with negative Y coordinate."""
        result = arm.solve_ik(80.0, -60.0, elbow_up=True)
        assert result is not None

        shoulder, elbow = result
        x, y = arm.solve_fk(shoulder, elbow)
        assert abs(x - 80.0) < 1.0
        assert abs(y - (-60.0)) < 1.0

    def test_ik_negative_coordinates_both(self, arm: ArmKinematics) -> None:
        """Test IK for target with both negative coordinates."""
        result = arm.solve_ik(-80.0, -60.0, elbow_up=True)
        assert result is not None

        shoulder, elbow = result
        x, y = arm.solve_fk(shoulder, elbow)
        assert abs(x - (-80.0)) < 1.0
        assert abs(y - (-60.0)) < 1.0

    def test_ik_origin_equal_links(self) -> None:
        """Test IK for target at origin with equal link lengths."""
        arm = ArmKinematics(l1=50.0, l2=50.0)
        result = arm.solve_ik(0.0, 0.0)
        assert result is not None

        shoulder, elbow = result
        # At origin, arm should be fully folded
        assert abs(elbow - math.pi) < 0.01 or abs(elbow + math.pi) < 0.01

    def test_ik_origin_unequal_links(self, arm: ArmKinematics) -> None:
        """Test IK for target at origin with unequal link lengths."""
        # Origin is unreachable when l1 != l2
        result = arm.solve_ik(0.0, 0.0)
        assert result is None

    def test_ik_nan_input_x(self, arm: ArmKinematics) -> None:
        """Test IK returns None for NaN X input."""
        result = arm.solve_ik(float("nan"), 50.0)
        assert result is None

    def test_ik_nan_input_y(self, arm: ArmKinematics) -> None:
        """Test IK returns None for NaN Y input."""
        result = arm.solve_ik(50.0, float("nan"))
        assert result is None

    def test_ik_inf_input_x(self, arm: ArmKinematics) -> None:
        """Test IK returns None for infinity X input."""
        result = arm.solve_ik(float("inf"), 50.0)
        assert result is None

    def test_ik_inf_input_y(self, arm: ArmKinematics) -> None:
        """Test IK returns None for infinity Y input."""
        result = arm.solve_ik(50.0, float("inf"))
        assert result is None

    def test_ik_at_boundary_max_reach(self, arm: ArmKinematics) -> None:
        """Test IK exactly at maximum reach boundary."""
        # Test at various angles on the max reach circle
        angles = [0, math.pi / 4, math.pi / 2, math.pi, -math.pi / 2]
        for angle in angles:
            x = 140.0 * math.cos(angle)
            y = 140.0 * math.sin(angle)
            result = arm.solve_ik(x, y)
            assert result is not None, f"Failed at angle {math.degrees(angle)} deg"

    def test_ik_at_boundary_min_reach(self, arm: ArmKinematics) -> None:
        """Test IK exactly at minimum reach boundary."""
        # Test at various angles on the min reach circle
        angles = [0, math.pi / 4, math.pi / 2, math.pi, -math.pi / 2]
        for angle in angles:
            x = 20.0 * math.cos(angle)
            y = 20.0 * math.sin(angle)
            result = arm.solve_ik(x, y)
            assert result is not None, f"Failed at angle {math.degrees(angle)} deg"


class TestForwardKinematics:
    """Tests for forward kinematics solver."""

    @pytest.fixture
    def arm(self) -> ArmKinematics:
        """Create arm kinematics instance with default link lengths."""
        return ArmKinematics(l1=DEFAULT_L1, l2=DEFAULT_L2)

    def test_fk_zero_angles(self, arm: ArmKinematics) -> None:
        """Test FK with both angles at zero (arm extended along X-axis)."""
        x, y = arm.solve_fk(0.0, 0.0)
        assert abs(x - 140.0) < 0.01  # l1 + l2 = 140
        assert abs(y - 0.0) < 0.01

    def test_fk_shoulder_90_degrees(self, arm: ArmKinematics) -> None:
        """Test FK with shoulder at 90 degrees."""
        x, y = arm.solve_fk(math.pi / 2, 0.0)
        assert abs(x - 0.0) < 0.01
        assert abs(y - 140.0) < 0.01

    def test_fk_elbow_90_degrees(self, arm: ArmKinematics) -> None:
        """Test FK with elbow at 90 degrees."""
        x, y = arm.solve_fk(0.0, math.pi / 2)
        # l1 along X-axis, l2 along Y-axis
        assert abs(x - 80.0) < 0.01  # l1
        assert abs(y - 60.0) < 0.01  # l2

    def test_fk_elbow_negative_90_degrees(self, arm: ArmKinematics) -> None:
        """Test FK with elbow at -90 degrees."""
        x, y = arm.solve_fk(0.0, -math.pi / 2)
        assert abs(x - 80.0) < 0.01  # l1
        assert abs(y - (-60.0)) < 0.01  # -l2

    def test_fk_elbow_180_degrees(self, arm: ArmKinematics) -> None:
        """Test FK with elbow at 180 degrees (folded back)."""
        x, y = arm.solve_fk(0.0, math.pi)
        # l2 points back opposite to l1
        assert abs(x - 20.0) < 0.01  # l1 - l2 = 20
        assert abs(y - 0.0) < 0.01

    def test_fk_nan_shoulder(self, arm: ArmKinematics) -> None:
        """Test FK raises ValueError for NaN shoulder angle."""
        with pytest.raises(ValueError, match="must not be NaN"):
            arm.solve_fk(float("nan"), 0.0)

    def test_fk_nan_elbow(self, arm: ArmKinematics) -> None:
        """Test FK raises ValueError for NaN elbow angle."""
        with pytest.raises(ValueError, match="must not be NaN"):
            arm.solve_fk(0.0, float("nan"))

    def test_fk_inf_shoulder(self, arm: ArmKinematics) -> None:
        """Test FK raises ValueError for infinity shoulder angle."""
        with pytest.raises(ValueError, match="must be finite"):
            arm.solve_fk(float("inf"), 0.0)

    def test_fk_inf_elbow(self, arm: ArmKinematics) -> None:
        """Test FK raises ValueError for infinity elbow angle."""
        with pytest.raises(ValueError, match="must be finite"):
            arm.solve_fk(0.0, float("inf"))


class TestFKIKRoundtrip:
    """Tests for FK/IK roundtrip accuracy."""

    @pytest.fixture
    def arm(self) -> ArmKinematics:
        """Create arm kinematics instance with default link lengths."""
        return ArmKinematics(l1=DEFAULT_L1, l2=DEFAULT_L2)

    def test_fk_roundtrip_center_workspace(self, arm: ArmKinematics) -> None:
        """Test FK(IK(x, y)) = (x, y) for center of workspace."""
        target_x, target_y = 80.0, 50.0

        result = arm.solve_ik(target_x, target_y, elbow_up=True)
        assert result is not None

        shoulder, elbow = result
        recovered_x, recovered_y = arm.solve_fk(shoulder, elbow)

        # Accuracy should be within 1mm
        assert abs(recovered_x - target_x) < 1.0
        assert abs(recovered_y - target_y) < 1.0

    def test_fk_roundtrip_accuracy_submillimeter(self, arm: ArmKinematics) -> None:
        """Test FK(IK(x, y)) accuracy is better than 1mm."""
        # Test multiple points in workspace
        test_points = [
            (100.0, 50.0),
            (50.0, 80.0),
            (-60.0, 70.0),
            (80.0, -40.0),
            (-70.0, -50.0),
        ]

        for target_x, target_y in test_points:
            for elbow_up in [True, False]:
                result = arm.solve_ik(target_x, target_y, elbow_up=elbow_up)
                assert result is not None, f"IK failed for ({target_x}, {target_y})"

                shoulder, elbow = result
                recovered_x, recovered_y = arm.solve_fk(shoulder, elbow)

                error = math.sqrt(
                    (recovered_x - target_x) ** 2 + (recovered_y - target_y) ** 2
                )
                assert error < 1.0, (
                    f"Roundtrip error {error:.4f}mm > 1mm for "
                    f"({target_x}, {target_y}), elbow_up={elbow_up}"
                )

    def test_fk_roundtrip_at_boundaries(self, arm: ArmKinematics) -> None:
        """Test FK(IK(x, y)) at workspace boundaries."""
        # Max reach boundary points
        max_points = [
            (140.0, 0.0),
            (0.0, 140.0),
            (-140.0, 0.0),
            (0.0, -140.0),
        ]

        # Min reach boundary points
        min_points = [
            (20.0, 0.0),
            (0.0, 20.0),
            (-20.0, 0.0),
            (0.0, -20.0),
        ]

        for target_x, target_y in max_points + min_points:
            result = arm.solve_ik(target_x, target_y)
            assert result is not None

            shoulder, elbow = result
            recovered_x, recovered_y = arm.solve_fk(shoulder, elbow)

            error = math.sqrt(
                (recovered_x - target_x) ** 2 + (recovered_y - target_y) ** 2
            )
            assert error < 1.0, f"Boundary error {error:.4f}mm for ({target_x}, {target_y})"


class TestWorkspaceBoundary:
    """Tests for workspace boundary generation."""

    @pytest.fixture
    def arm(self) -> ArmKinematics:
        """Create arm kinematics instance with default link lengths."""
        return ArmKinematics(l1=DEFAULT_L1, l2=DEFAULT_L2)

    def test_workspace_boundary_shape(self, arm: ArmKinematics) -> None:
        """Test workspace boundary array has correct shape."""
        boundary = arm.get_workspace_boundary(num_points=100)
        assert boundary.shape == (100, 2)
        assert boundary.dtype == np.float64

    def test_workspace_boundary_custom_points(self, arm: ArmKinematics) -> None:
        """Test workspace boundary with custom number of points."""
        for num_points in [10, 50, 200]:
            boundary = arm.get_workspace_boundary(num_points=num_points)
            assert boundary.shape == (num_points, 2)

    def test_workspace_boundary_min_points(self, arm: ArmKinematics) -> None:
        """Test workspace boundary with minimum number of points."""
        boundary = arm.get_workspace_boundary(num_points=4)
        assert boundary.shape == (4, 2)

    def test_workspace_boundary_too_few_points(self, arm: ArmKinematics) -> None:
        """Test ValueError for fewer than 4 points."""
        with pytest.raises(ValueError, match="num_points must be at least 4"):
            arm.get_workspace_boundary(num_points=3)

    def test_workspace_boundary_outer_radius(self, arm: ArmKinematics) -> None:
        """Test outer boundary points are at max reach."""
        boundary = arm.get_workspace_boundary(num_points=100)

        # First half of points should be on outer boundary
        outer_points = boundary[: 100 // 2]
        for point in outer_points:
            distance = np.linalg.norm(point)
            assert abs(distance - 140.0) < 0.01  # max_reach = 140

    def test_workspace_boundary_inner_radius(self, arm: ArmKinematics) -> None:
        """Test inner boundary points are at min reach."""
        boundary = arm.get_workspace_boundary(num_points=100)

        # Second half of points should be on inner boundary
        inner_points = boundary[100 // 2 :]
        for point in inner_points:
            distance = np.linalg.norm(point)
            assert abs(distance - 20.0) < 0.01  # min_reach = 20

    def test_workspace_boundary_equal_links(self) -> None:
        """Test workspace boundary when l1 == l2 (inner radius = 0)."""
        arm = ArmKinematics(l1=50.0, l2=50.0)
        boundary = arm.get_workspace_boundary(num_points=100)

        # Inner points should all be at origin
        inner_points = boundary[100 // 2 :]
        for point in inner_points:
            distance = np.linalg.norm(point)
            assert distance < 0.01  # Should be at origin

    def test_workspace_boundary_all_reachable(self, arm: ArmKinematics) -> None:
        """Test all boundary points are reachable."""
        boundary = arm.get_workspace_boundary(num_points=100)

        for point in boundary:
            x, y = point
            assert arm.is_reachable(x, y), f"Boundary point ({x}, {y}) not reachable"


class TestEdgeCases:
    """Tests for edge cases and singularities."""

    def test_singularity_at_max_reach(self) -> None:
        """Test behavior at maximum reach singularity."""
        arm = ArmKinematics(l1=80.0, l2=60.0)

        # At max reach, there's only one solution (arm fully extended)
        result = arm.solve_ik(140.0, 0.0)
        assert result is not None

        shoulder, elbow = result
        # Elbow should be near 0 (straight arm)
        assert abs(elbow) < 0.1 or abs(abs(elbow) - math.pi) < 0.1

    def test_singularity_at_min_reach(self) -> None:
        """Test behavior at minimum reach singularity."""
        arm = ArmKinematics(l1=80.0, l2=60.0)

        # At min reach, there's only one solution (arm fully folded)
        result = arm.solve_ik(20.0, 0.0)
        assert result is not None

        shoulder, elbow = result
        # Elbow should be near pi (fully folded)
        assert abs(abs(elbow) - math.pi) < 0.1

    def test_very_small_target_distance(self) -> None:
        """Test target very close to min reach."""
        arm = ArmKinematics(l1=80.0, l2=60.0)

        # Just barely reachable
        result = arm.solve_ik(20.001, 0.0)
        assert result is not None

    def test_very_large_target_distance(self) -> None:
        """Test target very close to max reach."""
        arm = ArmKinematics(l1=80.0, l2=60.0)

        # Just barely reachable
        result = arm.solve_ik(139.999, 0.0)
        assert result is not None

    def test_full_360_coverage(self) -> None:
        """Test IK works for targets in all quadrants."""
        arm = ArmKinematics(l1=80.0, l2=60.0)

        # Test at 45 degree increments around workspace
        radius = 100.0  # Within workspace
        for angle_deg in range(0, 360, 45):
            angle = math.radians(angle_deg)
            x = radius * math.cos(angle)
            y = radius * math.sin(angle)

            result = arm.solve_ik(x, y)
            assert result is not None, f"Failed at {angle_deg} degrees"

            # Verify roundtrip
            shoulder, elbow = result
            rx, ry = arm.solve_fk(shoulder, elbow)
            error = math.sqrt((rx - x) ** 2 + (ry - y) ** 2)
            assert error < 1.0, f"Roundtrip error at {angle_deg} degrees: {error}mm"

    def test_very_small_link_lengths(self) -> None:
        """Test with very small link lengths."""
        arm = ArmKinematics(l1=0.001, l2=0.001)

        result = arm.solve_ik(0.002, 0.0)
        assert result is not None

    def test_asymmetric_links(self) -> None:
        """Test with very asymmetric link lengths."""
        arm = ArmKinematics(l1=100.0, l2=10.0)

        # Test in valid workspace
        result = arm.solve_ik(100.0, 0.0)
        assert result is not None

        # Verify roundtrip
        shoulder, elbow = result
        x, y = arm.solve_fk(shoulder, elbow)
        assert abs(x - 100.0) < 1.0
        assert abs(y - 0.0) < 1.0


class TestExtendedEdgeCases:
    """Extended edge case tests identified by hostile reviewer (TC-1/2/3)."""

    @pytest.fixture
    def arm(self) -> ArmKinematics:
        """Create arm kinematics instance with default link lengths."""
        return ArmKinematics(l1=DEFAULT_L1, l2=DEFAULT_L2)

    def test_very_large_value_10000mm(self, arm: ArmKinematics) -> None:
        """TC-1: Test IK with very large coordinate values (10000mm)."""
        # Way beyond max reach - should return None, not crash
        result = arm.solve_ik(10000.0, 0.0)
        assert result is None

        # Test reachability returns False for large values
        assert not arm.is_reachable(10000.0, 0.0)
        assert not arm.is_reachable(10000.0, 10000.0)
        assert not arm.is_reachable(-10000.0, -10000.0)

    def test_very_large_value_1e100(self, arm: ArmKinematics) -> None:
        """TC-1: Test IK with extremely large values (1e100, not overflow)."""
        # Very large but not infinity - should return None, not crash
        result = arm.solve_ik(1e100, 0.0)
        assert result is None

        result = arm.solve_ik(0.0, 1e100)
        assert result is None

        result = arm.solve_ik(1e100, 1e100)
        assert result is None

        # Test reachability returns False for extremely large values
        assert not arm.is_reachable(1e100, 0.0)
        assert not arm.is_reachable(0.0, 1e100)
        assert not arm.is_reachable(1e100, 1e100)

    def test_extreme_boundary_float_max(self, arm: ArmKinematics) -> None:
        """Test IK with sys.float_info.max (maximum float value, near overflow)."""
        max_float = sys.float_info.max

        # Maximum float value - should return None, not crash or overflow
        result = arm.solve_ik(max_float, 0.0)
        assert result is None

        result = arm.solve_ik(0.0, max_float)
        assert result is None

        result = arm.solve_ik(max_float, max_float)
        assert result is None

        # Test reachability returns False for max float values
        assert not arm.is_reachable(max_float, 0.0)
        assert not arm.is_reachable(0.0, max_float)
        assert not arm.is_reachable(max_float, max_float)

        # Negative max float
        assert not arm.is_reachable(-max_float, 0.0)
        assert not arm.is_reachable(0.0, -max_float)

    def test_negative_infinity_inputs(self) -> None:
        """TC-2: Test IK with negative infinity inputs."""
        arm = ArmKinematics(l1=80.0, l2=60.0)

        # Negative infinity should return None/False, not crash
        result = arm.solve_ik(float("-inf"), 50.0)
        assert result is None

        result = arm.solve_ik(50.0, float("-inf"))
        assert result is None

        result = arm.solve_ik(float("-inf"), float("-inf"))
        assert result is None

        # Reachability should also handle negative infinity
        assert not arm.is_reachable(float("-inf"), 50.0)
        assert not arm.is_reachable(50.0, float("-inf"))

    def test_string_inputs_is_reachable(self) -> None:
        """TC-3: Test is_reachable with string inputs returns False."""
        arm = ArmKinematics(l1=80.0, l2=60.0)

        # String inputs should return False, not raise
        assert not arm.is_reachable("80.0", 50.0)  # type: ignore[arg-type]
        assert not arm.is_reachable(80.0, "50.0")  # type: ignore[arg-type]
        assert not arm.is_reachable("hello", "world")  # type: ignore[arg-type]

    def test_string_inputs_solve_ik(self) -> None:
        """TC-3: Test solve_ik with string inputs returns None."""
        arm = ArmKinematics(l1=80.0, l2=60.0)

        # String inputs should return None, not raise
        result = arm.solve_ik("80.0", 50.0)  # type: ignore[arg-type]
        assert result is None

        result = arm.solve_ik(80.0, "50.0")  # type: ignore[arg-type]
        assert result is None

    def test_string_inputs_constructor_raises(self) -> None:
        """TC-3: Test constructor with string inputs raises ValueError."""
        with pytest.raises(ValueError, match="l1 must be a number"):
            ArmKinematics(l1="80.0", l2=60.0)  # type: ignore[arg-type]

        with pytest.raises(ValueError, match="l2 must be a number"):
            ArmKinematics(l1=80.0, l2="60.0")  # type: ignore[arg-type]

    def test_none_inputs(self) -> None:
        """Test with None inputs (similar to string, type check)."""
        arm = ArmKinematics(l1=80.0, l2=60.0)

        # None should be handled gracefully
        assert not arm.is_reachable(None, 50.0)  # type: ignore[arg-type]
        assert not arm.is_reachable(80.0, None)  # type: ignore[arg-type]

        result = arm.solve_ik(None, 50.0)  # type: ignore[arg-type]
        assert result is None

        result = arm.solve_ik(80.0, None)  # type: ignore[arg-type]
        assert result is None

    def test_string_inputs_solve_fk(self) -> None:
        """Test solve_fk with string inputs raises ValueError."""
        arm = ArmKinematics(l1=80.0, l2=60.0)

        # String inputs should raise ValueError
        with pytest.raises(ValueError, match="Angles must be numbers"):
            arm.solve_fk("0.0", 0.0)  # type: ignore[arg-type]

        with pytest.raises(ValueError, match="Angles must be numbers"):
            arm.solve_fk(0.0, "0.0")  # type: ignore[arg-type]

    def test_none_inputs_solve_fk(self) -> None:
        """Test solve_fk with None inputs raises ValueError."""
        arm = ArmKinematics(l1=80.0, l2=60.0)

        # None inputs should raise ValueError
        with pytest.raises(ValueError, match="Angles must be numbers"):
            arm.solve_fk(None, 0.0)  # type: ignore[arg-type]

        with pytest.raises(ValueError, match="Angles must be numbers"):
            arm.solve_fk(0.0, None)  # type: ignore[arg-type]

    def test_negative_infinity_solve_fk(self) -> None:
        """Test solve_fk with negative infinity raises ValueError."""
        arm = ArmKinematics(l1=80.0, l2=60.0)

        # Negative infinity should raise ValueError
        with pytest.raises(ValueError, match="Angles must be finite"):
            arm.solve_fk(float("-inf"), 0.0)

        with pytest.raises(ValueError, match="Angles must be finite"):
            arm.solve_fk(0.0, float("-inf"))
