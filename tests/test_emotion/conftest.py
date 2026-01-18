"""Pytest fixtures for emotion system testing.

Provides mock dependencies for emotion state machine testing.

Author: Boston Dynamics Test Engineer
Created: 17 January 2026
"""

from unittest.mock import Mock, MagicMock
import pytest


@pytest.fixture
def mock_led_controller():
    """Mock LED controller for emotion system testing."""
    controller = Mock()
    controller.set_pattern = Mock()
    controller.set_color = Mock()
    controller.set_brightness = Mock()
    controller.clear = Mock()
    return controller


@pytest.fixture
def mock_servo_controller():
    """Mock servo controller for emotion expressions."""
    controller = Mock()
    controller.set_position = Mock()
    controller.set_sequence = Mock()
    controller.get_position = Mock(return_value=0.0)
    return controller


@pytest.fixture
def emotion_config():
    """Standard emotion system configuration."""
    return {
        'transition_duration_ms': 500,
        'idle_timeout_ms': 5000,
        'max_intensity': 1.0,
        'default_brightness': 0.8,
    }


@pytest.fixture
def emotion_definitions():
    """Standard emotion definitions for testing.

    Returns:
        Dictionary mapping emotion names to their properties
    """
    return {
        'idle': {
            'pattern': 'breathing',
            'color': (100, 150, 255),
            'speed': 1.0,
            'servo_position': 0.0,
        },
        'happy': {
            'pattern': 'pulse',
            'color': (255, 200, 0),
            'speed': 1.2,
            'servo_position': 0.3,
        },
        'thinking': {
            'pattern': 'spin',
            'color': (200, 200, 255),
            'speed': 1.5,
            'servo_position': -0.2,
        },
        'alert': {
            'pattern': 'pulse',
            'color': (255, 100, 100),
            'speed': 2.0,
            'servo_position': 0.5,
        },
        'error': {
            'pattern': 'pulse',
            'color': (255, 0, 0),
            'speed': 3.0,
            'servo_position': 0.0,
        },
    }
