"""Pytest fixtures for animation timing tests.

Provides utilities for testing easing functions and keyframe animations.

Author: Boston Dynamics Test Engineer
Created: 17 January 2026
"""

import pytest


@pytest.fixture
def easing_tolerance():
    """Standard tolerance for easing function comparisons."""
    return 0.01  # 1% tolerance for floating point comparisons


@pytest.fixture
def simple_keyframe_sequence():
    """Create a simple 3-keyframe sequence for testing.

    Returns:
        Dictionary with keyframe data
    """
    return {
        'name': 'test_sequence',
        'keyframes': [
            {'time_ms': 0, 'positions': {'servo1': 0.0}, 'easing': 'linear'},
            {'time_ms': 500, 'positions': {'servo1': 50.0}, 'easing': 'linear'},
            {'time_ms': 1000, 'positions': {'servo1': 100.0}, 'easing': 'linear'},
        ]
    }


@pytest.fixture
def multi_property_sequence():
    """Create sequence with multiple animated properties.

    Returns:
        Dictionary with keyframe data
    """
    return {
        'name': 'multi_prop',
        'keyframes': [
            {
                'time_ms': 0,
                'positions': {'servo1': 0.0, 'servo2': 100.0, 'servo3': 50.0},
                'easing': 'ease_in_out'
            },
            {
                'time_ms': 1000,
                'positions': {'servo1': 100.0, 'servo2': 0.0, 'servo3': 75.0},
                'easing': 'ease_in_out'
            },
        ]
    }


@pytest.fixture
def performance_thresholds():
    """Performance requirements for animation system.

    Returns:
        Dictionary of timing thresholds
    """
    return {
        'max_easing_lookup_us': 10,      # Max 10 microseconds per easing lookup
        'max_interpolation_us': 100,     # Max 100 microseconds per interpolation
        'max_player_update_us': 500,     # Max 500 microseconds per player update
    }
