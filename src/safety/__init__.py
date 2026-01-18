"""Safety module for OpenDuck Mini V3 robot.

This module provides comprehensive safety mechanisms for protecting the robot
hardware and ensuring safe operation during all operating modes.

Components:
    - EmergencyStop: Hardware and software emergency stop handling
    - SafetyState: Enumeration of safety system states
    - ServoWatchdog: Communication timeout and servo health monitoring
    - CurrentLimiter: Per-servo current estimation and thermal protection
    - ServoCurrentProfile: Servo electrical characteristics configuration
    - StallCondition: Stall detection state enumeration
    - LEDSafetyManager: LED power management and fail-safe mechanisms
    - LEDRingProfile: LED ring electrical characteristics configuration
    - PowerSource: LED power source enumeration
    - SafetyLevel: LED safety level enumeration
"""

# Emergency stop system
from .emergency_stop import EmergencyStop, SafetyState

# Servo communication watchdog
from .watchdog import ServoWatchdog

# Current limiting and stall detection
from .current_limiter import CurrentLimiter, ServoCurrentProfile, StallCondition

# LED safety system
from .led_safety import (
    LEDSafetyManager,
    LEDRingProfile,
    PowerSource,
    SafetyLevel,
    CurrentEstimate,
)

__version__ = "0.1.0"

__all__ = [
    # Emergency stop
    "EmergencyStop",
    "SafetyState",
    # Watchdog
    "ServoWatchdog",
    # Current limiting
    "CurrentLimiter",
    "ServoCurrentProfile",
    "StallCondition",
    # LED safety
    "LEDSafetyManager",
    "LEDRingProfile",
    "PowerSource",
    "SafetyLevel",
    "CurrentEstimate",
    # Module version
    "__version__",
]
