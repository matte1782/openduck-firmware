"""Servo control drivers for OpenDuck Mini V3.

Provides hardware abstraction for servo controllers including:
- PCA9685: 16-channel PWM driver for standard hobby servos
- Future: STS3215 serial bus servo driver
"""

from .pca9685 import PCA9685Driver, ServoController

__all__ = ['PCA9685Driver', 'ServoController']
