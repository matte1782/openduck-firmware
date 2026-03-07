"""
Emotion Definitions for OpenDuck Mini V3

Defines LED patterns, colors, and servo positions for each emotion state.

Author: Boston Dynamics Emotion Engineer
Created: 22 January 2026
"""

from typing import Any, Dict

# Standard emotion definitions mapping emotion names to their properties
EMOTION_DEFINITIONS: Dict[str, Dict[str, Any]] = {
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
