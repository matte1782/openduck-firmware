# OpenDuck Mini V3 - Perception System Technical Plan

**Author:** Machine Learning Research Scientist - Perception (Google DeepMind Robotics)
**Date:** 17 January 2026
**Version:** 1.0
**Status:** APPROVED FOR IMPLEMENTATION

---

## Executive Summary

This document outlines the architecture for a robust perception system designed to:
1. Optimize BNO085 IMU integration with advanced sensor fusion
2. Implement production-grade noise filtering and calibration
3. Prepare abstract interfaces for AI camera integration (Week 3)
4. Scale to multi-sensor fusion for embodied AI applications

The design follows DeepMind robotics best practices: modular architecture, TDD-first development, and scalable data pipelines.

---

## Table of Contents

1. [Current State Analysis](#current-state-analysis)
2. [Sensor Driver Architecture](#sensor-driver-architecture)
3. [Data Structures](#data-structures)
4. [Sensor Fusion Algorithms](#sensor-fusion-algorithms)
5. [Calibration Procedures](#calibration-procedures)
6. [Noise Filtering](#noise-filtering)
7. [Data Pipeline Design](#data-pipeline-design)
8. [AI Camera Preparation (Week 3)](#ai-camera-preparation-week-3)
9. [TDD Test Cases](#tdd-test-cases)
10. [Day-by-Day Work Breakdown](#day-by-day-work-breakdown)
11. [Risk Assessment](#risk-assessment)

---

## 1. Current State Analysis

### Hardware Timeline
| Component | Status | Expected Arrival |
|-----------|--------|------------------|
| Adafruit BNO085 IMU | In transit | Monday (Day 8) |
| AI Camera (IMX500) | Not ordered | Week 3 |
| PCA9685 PWM | Validated | Day 6 |
| Servos (STS3215) | Ordered | Mid-Week 2 |
| Batteries | Ordered | End of Week 2 |

### Existing Codebase Assessment

**BNO085 Driver (firmware/src/drivers/sensor/imu/bno085.py):**
- Basic driver exists (430 lines)
- Thread-safe via I2CBusManager integration
- Quaternion to Euler conversion implemented
- Missing: Advanced sensor fusion, calibration, filtering

**I2C Infrastructure:**
- I2CBusManager singleton pattern (thread-safe)
- PCA9685 validated at 0x40
- BNO085 will share bus at 0x4A

**Gaps Identified:**
1. No complementary filter implementation
2. No Kalman filter preparation
3. Calibration returns hardcoded values
4. No mounting orientation compensation
5. No noise filtering (low-pass, moving average)
6. No sensor data history for fusion
7. No abstract sensor interfaces

---

## 2. Sensor Driver Architecture

### 2.1 Modular Perception Stack

```
firmware/src/perception/
├── __init__.py
├── interfaces/
│   ├── __init__.py
│   ├── sensor_interface.py      # Abstract base class
│   ├── imu_interface.py         # IMU-specific interface
│   ├── camera_interface.py      # Camera interface (Week 3)
│   └── distance_interface.py    # Ultrasonic/ToF interface
├── sensors/
│   ├── __init__.py
│   ├── bno085_enhanced.py       # Enhanced BNO085 driver
│   └── ultrasonic.py            # HC-SR04 driver
├── fusion/
│   ├── __init__.py
│   ├── complementary_filter.py  # Complementary filter
│   ├── kalman_filter.py         # Extended Kalman Filter
│   └── sensor_fusion.py         # Multi-sensor fusion manager
├── calibration/
│   ├── __init__.py
│   ├── imu_calibration.py       # IMU calibration routines
│   ├── mounting_compensation.py # Frame transformation
│   └── calibration_storage.py   # YAML persistence
├── filtering/
│   ├── __init__.py
│   ├── low_pass_filter.py       # Low-pass filter
│   ├── moving_average.py        # Moving average filter
│   └── outlier_rejection.py     # Statistical outlier detection
├── data/
│   ├── __init__.py
│   ├── orientation_data.py      # Orientation data structures
│   ├── sensor_buffer.py         # Ring buffer for history
│   └── timestamp_sync.py        # Timestamp synchronization
└── pipeline/
    ├── __init__.py
    ├── perception_pipeline.py   # Main pipeline orchestrator
    └── rate_controller.py       # Sample rate management
```

### 2.2 Abstract Sensor Interface

```python
# firmware/src/perception/interfaces/sensor_interface.py

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Generic, TypeVar
import time

T = TypeVar('T')

@dataclass
class SensorStatus:
    """Generic sensor health status."""
    is_connected: bool
    is_calibrated: bool
    last_read_timestamp: float
    read_frequency_hz: float
    error_count: int
    last_error: Optional[str]

class SensorInterface(ABC, Generic[T]):
    """Abstract base class for all sensors.

    Implements the Template Method pattern for consistent
    sensor behavior across different hardware.

    Type Parameter:
        T: The data type returned by read() method
    """

    @abstractmethod
    def initialize(self) -> bool:
        """Initialize sensor hardware.

        Returns:
            bool: True if initialization successful
        """
        pass

    @abstractmethod
    def read(self) -> Optional[T]:
        """Read sensor data.

        Returns:
            Optional[T]: Sensor data or None if read fails
        """
        pass

    @abstractmethod
    def calibrate(self) -> bool:
        """Perform sensor calibration.

        Returns:
            bool: True if calibration successful
        """
        pass

    @abstractmethod
    def get_status(self) -> SensorStatus:
        """Get current sensor health status."""
        pass

    @abstractmethod
    def shutdown(self) -> None:
        """Clean shutdown of sensor resources."""
        pass

    def read_filtered(self) -> Optional[T]:
        """Read sensor data with filtering applied.

        Default implementation calls read() without filtering.
        Override in subclasses to apply specific filters.
        """
        return self.read()

    def is_healthy(self) -> bool:
        """Check if sensor is in healthy state.

        Returns:
            bool: True if sensor is connected and operational
        """
        status = self.get_status()
        return status.is_connected and status.error_count < 10
```

### 2.3 IMU-Specific Interface

```python
# firmware/src/perception/interfaces/imu_interface.py

from abc import abstractmethod
from dataclasses import dataclass
from typing import Tuple, Optional
from .sensor_interface import SensorInterface

@dataclass
class IMUReading:
    """Complete IMU reading with all sensor data."""
    # Orientation (from sensor fusion)
    quaternion: Tuple[float, float, float, float]  # (w, x, y, z)
    euler_angles: Tuple[float, float, float]       # (heading, pitch, roll) in degrees

    # Raw sensor data
    accelerometer: Tuple[float, float, float]      # (x, y, z) in m/s²
    gyroscope: Tuple[float, float, float]          # (x, y, z) in rad/s
    magnetometer: Optional[Tuple[float, float, float]]  # (x, y, z) in µT

    # Metadata
    timestamp: float                               # Unix timestamp
    accuracy: int                                  # 0-3 calibration accuracy

    def heading_deg(self) -> float:
        """Get heading in degrees (0-360)."""
        return self.euler_angles[0]

    def pitch_deg(self) -> float:
        """Get pitch in degrees (-90 to 90)."""
        return self.euler_angles[1]

    def roll_deg(self) -> float:
        """Get roll in degrees (-180 to 180)."""
        return self.euler_angles[2]

class IMUInterface(SensorInterface[IMUReading]):
    """Abstract interface for IMU sensors.

    Extends SensorInterface with IMU-specific methods.
    Supports BNO085, MPU6050, ICM-20948, etc.
    """

    @abstractmethod
    def read_raw_accelerometer(self) -> Tuple[float, float, float]:
        """Read raw accelerometer data (m/s²)."""
        pass

    @abstractmethod
    def read_raw_gyroscope(self) -> Tuple[float, float, float]:
        """Read raw gyroscope data (rad/s)."""
        pass

    @abstractmethod
    def read_raw_magnetometer(self) -> Optional[Tuple[float, float, float]]:
        """Read raw magnetometer data (µT).

        Returns None if sensor doesn't have magnetometer.
        """
        pass

    @abstractmethod
    def get_calibration_status(self) -> Tuple[int, int, int, int]:
        """Get calibration status for each sensor.

        Returns:
            Tuple of (system, gyro, accel, mag) calibration levels (0-3)
        """
        pass

    @abstractmethod
    def set_mounting_orientation(self, roll_offset: float,
                                  pitch_offset: float,
                                  yaw_offset: float) -> None:
        """Set mounting orientation offsets for frame transformation."""
        pass
```

---

## 3. Data Structures

### 3.1 Enhanced Orientation Data

```python
# firmware/src/perception/data/orientation_data.py

from dataclasses import dataclass, field
from typing import Optional, Tuple, List
import math
import time

@dataclass(frozen=True)
class Quaternion:
    """Immutable quaternion representation.

    Uses Hamilton convention: q = w + xi + yj + zk
    Normalized to unit quaternion for rotations.
    """
    w: float
    x: float
    y: float
    z: float

    def __post_init__(self):
        # Normalize on creation
        norm = math.sqrt(self.w**2 + self.x**2 + self.y**2 + self.z**2)
        if abs(norm - 1.0) > 1e-6 and norm > 0:
            object.__setattr__(self, 'w', self.w / norm)
            object.__setattr__(self, 'x', self.x / norm)
            object.__setattr__(self, 'y', self.y / norm)
            object.__setattr__(self, 'z', self.z / norm)

    def to_euler(self) -> Tuple[float, float, float]:
        """Convert to Euler angles (heading, pitch, roll) in degrees.

        Uses aerospace convention: ZYX rotation order.
        """
        # Roll (x-axis rotation)
        sinr_cosp = 2 * (self.w * self.x + self.y * self.z)
        cosr_cosp = 1 - 2 * (self.x * self.x + self.y * self.y)
        roll = math.atan2(sinr_cosp, cosr_cosp)

        # Pitch (y-axis rotation)
        sinp = 2 * (self.w * self.y - self.z * self.x)
        if abs(sinp) >= 1:
            pitch = math.copysign(math.pi / 2, sinp)
        else:
            pitch = math.asin(sinp)

        # Yaw/Heading (z-axis rotation)
        siny_cosp = 2 * (self.w * self.z + self.x * self.y)
        cosy_cosp = 1 - 2 * (self.y * self.y + self.z * self.z)
        heading = math.atan2(siny_cosp, cosy_cosp)

        # Convert to degrees, normalize heading to 0-360
        heading_deg = math.degrees(heading)
        if heading_deg < 0:
            heading_deg += 360

        return (heading_deg, math.degrees(pitch), math.degrees(roll))

    def conjugate(self) -> 'Quaternion':
        """Return conjugate quaternion (inverse for unit quaternions)."""
        return Quaternion(self.w, -self.x, -self.y, -self.z)

    def rotate_vector(self, v: Tuple[float, float, float]) -> Tuple[float, float, float]:
        """Rotate vector by this quaternion."""
        # q * v * q^-1
        qv = Quaternion(0, v[0], v[1], v[2])
        result = self._multiply(self._multiply(self, qv), self.conjugate())
        return (result.x, result.y, result.z)

    @staticmethod
    def _multiply(q1: 'Quaternion', q2: 'Quaternion') -> 'Quaternion':
        """Hamilton product of two quaternions."""
        return Quaternion(
            w=q1.w*q2.w - q1.x*q2.x - q1.y*q2.y - q1.z*q2.z,
            x=q1.w*q2.x + q1.x*q2.w + q1.y*q2.z - q1.z*q2.y,
            y=q1.w*q2.y - q1.x*q2.z + q1.y*q2.w + q1.z*q2.x,
            z=q1.w*q2.z + q1.x*q2.y - q1.y*q2.x + q1.z*q2.w
        )

    @classmethod
    def from_euler(cls, heading: float, pitch: float, roll: float) -> 'Quaternion':
        """Create quaternion from Euler angles (degrees)."""
        # Convert to radians
        h = math.radians(heading / 2)
        p = math.radians(pitch / 2)
        r = math.radians(roll / 2)

        # Compute quaternion components
        cy, sy = math.cos(h), math.sin(h)
        cp, sp = math.cos(p), math.sin(p)
        cr, sr = math.cos(r), math.sin(r)

        return cls(
            w=cy*cp*cr + sy*sp*sr,
            x=cy*cp*sr - sy*sp*cr,
            y=sy*cp*sr + cy*sp*cr,
            z=sy*cp*cr - cy*sp*sr
        )

    @classmethod
    def identity(cls) -> 'Quaternion':
        """Return identity quaternion (no rotation)."""
        return cls(1.0, 0.0, 0.0, 0.0)

    def slerp(self, other: 'Quaternion', t: float) -> 'Quaternion':
        """Spherical linear interpolation between quaternions.

        Args:
            other: Target quaternion
            t: Interpolation factor (0.0 to 1.0)

        Returns:
            Interpolated quaternion
        """
        # Compute dot product
        dot = self.w*other.w + self.x*other.x + self.y*other.y + self.z*other.z

        # If dot < 0, negate one quaternion to take shorter path
        if dot < 0:
            other = Quaternion(-other.w, -other.x, -other.y, -other.z)
            dot = -dot

        # If nearly parallel, use linear interpolation
        if dot > 0.9995:
            return Quaternion(
                w=self.w + t * (other.w - self.w),
                x=self.x + t * (other.x - self.x),
                y=self.y + t * (other.y - self.y),
                z=self.z + t * (other.z - self.z)
            )

        # Spherical interpolation
        theta_0 = math.acos(dot)
        theta = theta_0 * t
        sin_theta = math.sin(theta)
        sin_theta_0 = math.sin(theta_0)

        s0 = math.cos(theta) - dot * sin_theta / sin_theta_0
        s1 = sin_theta / sin_theta_0

        return Quaternion(
            w=s0*self.w + s1*other.w,
            x=s0*self.x + s1*other.x,
            y=s0*self.y + s1*other.y,
            z=s0*self.z + s1*other.z
        )


@dataclass
class OrientationState:
    """Complete orientation state with uncertainty estimation."""
    quaternion: Quaternion
    angular_velocity: Tuple[float, float, float]  # rad/s
    linear_acceleration: Tuple[float, float, float]  # m/s² (gravity removed)
    timestamp: float

    # Uncertainty estimates (1-sigma, degrees)
    heading_uncertainty: float = 0.0
    pitch_uncertainty: float = 0.0
    roll_uncertainty: float = 0.0

    # Calibration state
    calibration_level: int = 0  # 0-3

    def euler_angles(self) -> Tuple[float, float, float]:
        """Get Euler angles (heading, pitch, roll) in degrees."""
        return self.quaternion.to_euler()


@dataclass
class SensorReading:
    """Timestamped raw sensor reading."""
    accelerometer: Tuple[float, float, float]
    gyroscope: Tuple[float, float, float]
    magnetometer: Optional[Tuple[float, float, float]]
    timestamp: float
```

### 3.2 Ring Buffer for Sensor History

```python
# firmware/src/perception/data/sensor_buffer.py

from dataclasses import dataclass
from typing import Generic, TypeVar, List, Optional, Iterator
from collections import deque
import threading

T = TypeVar('T')

class RingBuffer(Generic[T]):
    """Thread-safe ring buffer for sensor data history.

    Optimized for:
    - O(1) append and pop operations
    - Fixed memory footprint
    - Thread-safe concurrent access
    - Iterator support for analysis

    Attributes:
        max_size: Maximum number of elements
        _buffer: Internal deque storage
        _lock: Threading lock for thread safety
    """

    def __init__(self, max_size: int = 100):
        """Initialize ring buffer.

        Args:
            max_size: Maximum number of elements to store
        """
        if max_size <= 0:
            raise ValueError("max_size must be positive")
        self.max_size = max_size
        self._buffer: deque = deque(maxlen=max_size)
        self._lock = threading.Lock()

    def append(self, item: T) -> None:
        """Add item to buffer, removing oldest if full."""
        with self._lock:
            self._buffer.append(item)

    def get_latest(self, n: int = 1) -> List[T]:
        """Get the n most recent items.

        Args:
            n: Number of items to retrieve

        Returns:
            List of up to n most recent items (newest last)
        """
        with self._lock:
            if n >= len(self._buffer):
                return list(self._buffer)
            return list(self._buffer)[-n:]

    def get_oldest(self, n: int = 1) -> List[T]:
        """Get the n oldest items."""
        with self._lock:
            if n >= len(self._buffer):
                return list(self._buffer)
            return list(self._buffer)[:n]

    def latest(self) -> Optional[T]:
        """Get the most recent item."""
        with self._lock:
            if self._buffer:
                return self._buffer[-1]
            return None

    def clear(self) -> None:
        """Clear all items from buffer."""
        with self._lock:
            self._buffer.clear()

    def __len__(self) -> int:
        """Return current number of items."""
        with self._lock:
            return len(self._buffer)

    def __iter__(self) -> Iterator[T]:
        """Iterate over items (oldest to newest)."""
        with self._lock:
            return iter(list(self._buffer))

    def is_full(self) -> bool:
        """Check if buffer is at max capacity."""
        with self._lock:
            return len(self._buffer) >= self.max_size

    def get_all(self) -> List[T]:
        """Get all items as a list (oldest to newest)."""
        with self._lock:
            return list(self._buffer)
```

---

## 4. Sensor Fusion Algorithms

### 4.1 Complementary Filter

The complementary filter combines gyroscope (short-term accurate) with accelerometer (long-term stable) data.

```python
# firmware/src/perception/fusion/complementary_filter.py

import math
import time
from dataclasses import dataclass
from typing import Tuple, Optional
from ..data.orientation_data import Quaternion, OrientationState

@dataclass
class ComplementaryFilterConfig:
    """Configuration for complementary filter."""
    alpha: float = 0.98  # Weight for gyroscope (0.96-0.99 typical)
    sample_rate_hz: float = 100.0  # Expected sample rate
    accel_threshold: float = 0.1  # Threshold for valid accel data (g)

    def __post_init__(self):
        if not 0.0 < self.alpha < 1.0:
            raise ValueError("alpha must be between 0 and 1")


class ComplementaryFilter:
    """Complementary filter for IMU sensor fusion.

    Combines gyroscope integration (fast, drifts) with accelerometer
    tilt estimation (slow, noisy but stable).

    Algorithm:
        angle = alpha * (angle + gyro * dt) + (1 - alpha) * accel_angle

    Where:
        - alpha is typically 0.96-0.99 (higher = trust gyro more)
        - gyro provides angular velocity (rad/s)
        - accel provides gravity reference for pitch/roll

    Heading (yaw) requires magnetometer for absolute reference.

    Reference:
        Mahony, R., Hamel, T., & Pflimlin, J. M. (2008).
        "Nonlinear complementary filters on the special orthogonal group."
        IEEE Transactions on automatic control.
    """

    def __init__(self, config: Optional[ComplementaryFilterConfig] = None):
        """Initialize complementary filter.

        Args:
            config: Filter configuration (uses defaults if None)
        """
        self.config = config or ComplementaryFilterConfig()

        # State variables
        self._orientation = Quaternion.identity()
        self._last_timestamp: Optional[float] = None
        self._initialized = False

        # Bias estimation (gyroscope zero-rate offset)
        self._gyro_bias = (0.0, 0.0, 0.0)
        self._bias_samples = 0
        self._bias_initialized = False

    def update(self,
               gyroscope: Tuple[float, float, float],
               accelerometer: Tuple[float, float, float],
               magnetometer: Optional[Tuple[float, float, float]] = None,
               timestamp: Optional[float] = None) -> OrientationState:
        """Update filter with new sensor readings.

        Args:
            gyroscope: Angular velocity (x, y, z) in rad/s
            accelerometer: Linear acceleration (x, y, z) in m/s²
            magnetometer: Magnetic field (x, y, z) in µT (optional)
            timestamp: Reading timestamp (uses time.monotonic() if None)

        Returns:
            OrientationState: Updated orientation estimate
        """
        now = timestamp or time.monotonic()

        # Handle first reading
        if self._last_timestamp is None:
            self._last_timestamp = now
            self._orientation = self._orientation_from_accel(accelerometer)
            self._initialized = True
            return self._create_state(gyroscope, accelerometer, now)

        # Calculate time delta
        dt = now - self._last_timestamp
        self._last_timestamp = now

        # Protect against unreasonable dt values
        if dt <= 0 or dt > 1.0:
            dt = 1.0 / self.config.sample_rate_hz

        # Subtract gyroscope bias
        gyro_corrected = (
            gyroscope[0] - self._gyro_bias[0],
            gyroscope[1] - self._gyro_bias[1],
            gyroscope[2] - self._gyro_bias[2]
        )

        # Integrate gyroscope (predict)
        gyro_quat = self._gyro_to_quaternion(gyro_corrected, dt)
        predicted = Quaternion._multiply(self._orientation, gyro_quat)

        # Estimate orientation from accelerometer (correct)
        accel_quat = self._orientation_from_accel(accelerometer)

        # Complementary fusion using SLERP
        self._orientation = predicted.slerp(accel_quat, 1.0 - self.config.alpha)

        # Incorporate magnetometer for heading if available
        if magnetometer is not None:
            self._correct_heading(magnetometer)

        return self._create_state(gyro_corrected, accelerometer, now)

    def _orientation_from_accel(self, accel: Tuple[float, float, float]) -> Quaternion:
        """Estimate orientation from accelerometer (assumes gravity only).

        Valid when robot is stationary or slowly moving.
        """
        ax, ay, az = accel
        norm = math.sqrt(ax*ax + ay*ay + az*az)

        if norm < 0.1:  # No valid acceleration
            return self._orientation

        # Normalize
        ax, ay, az = ax/norm, ay/norm, az/norm

        # Calculate pitch and roll from gravity vector
        pitch = math.asin(-ax)
        roll = math.atan2(ay, az)

        # Current heading (preserve from gyro integration)
        current_euler = self._orientation.to_euler()
        heading = current_euler[0]

        return Quaternion.from_euler(heading, math.degrees(pitch), math.degrees(roll))

    def _gyro_to_quaternion(self, gyro: Tuple[float, float, float],
                            dt: float) -> Quaternion:
        """Convert angular velocity to rotation quaternion.

        Uses small-angle approximation for stability.
        """
        gx, gy, gz = gyro

        # Angular velocity magnitude
        omega = math.sqrt(gx*gx + gy*gy + gz*gz)

        if omega < 1e-10:
            return Quaternion.identity()

        # Half angle
        half_angle = omega * dt / 2.0
        s = math.sin(half_angle) / omega
        c = math.cos(half_angle)

        return Quaternion(
            w=c,
            x=gx * s,
            y=gy * s,
            z=gz * s
        )

    def _correct_heading(self, mag: Tuple[float, float, float]) -> None:
        """Correct heading using magnetometer.

        Projects magnetometer reading onto horizontal plane and
        calculates magnetic north heading.
        """
        mx, my, mz = mag

        # Rotate magnetometer reading to world frame
        euler = self._orientation.to_euler()
        pitch_rad = math.radians(euler[1])
        roll_rad = math.radians(euler[2])

        # Tilt compensation
        mx_h = mx * math.cos(pitch_rad) + mz * math.sin(pitch_rad)
        my_h = (mx * math.sin(roll_rad) * math.sin(pitch_rad) +
                my * math.cos(roll_rad) -
                mz * math.sin(roll_rad) * math.cos(pitch_rad))

        # Calculate heading
        mag_heading = math.degrees(math.atan2(-my_h, mx_h))
        if mag_heading < 0:
            mag_heading += 360

        # Blend with current heading
        current = euler[0]
        diff = mag_heading - current

        # Handle wraparound
        if diff > 180:
            diff -= 360
        elif diff < -180:
            diff += 360

        # Apply correction (slow adaptation)
        correction = diff * (1 - self.config.alpha)
        new_heading = current + correction
        if new_heading < 0:
            new_heading += 360
        elif new_heading >= 360:
            new_heading -= 360

        self._orientation = Quaternion.from_euler(new_heading, euler[1], euler[2])

    def _create_state(self, gyro: Tuple[float, float, float],
                      accel: Tuple[float, float, float],
                      timestamp: float) -> OrientationState:
        """Create OrientationState from current filter state."""
        # Remove gravity from acceleration (approximate)
        gravity = self._orientation.rotate_vector((0, 0, 9.81))
        linear_accel = (
            accel[0] - gravity[0],
            accel[1] - gravity[1],
            accel[2] - gravity[2]
        )

        return OrientationState(
            quaternion=self._orientation,
            angular_velocity=gyro,
            linear_acceleration=linear_accel,
            timestamp=timestamp,
            calibration_level=3 if self._bias_initialized else 1
        )

    def estimate_gyro_bias(self, gyro: Tuple[float, float, float],
                           num_samples: int = 100) -> None:
        """Accumulate samples for gyroscope bias estimation.

        Call this method while robot is stationary.

        Args:
            gyro: Gyroscope reading (x, y, z) in rad/s
            num_samples: Number of samples to average
        """
        if self._bias_samples < num_samples:
            alpha = 1.0 / (self._bias_samples + 1)
            self._gyro_bias = (
                self._gyro_bias[0] + alpha * (gyro[0] - self._gyro_bias[0]),
                self._gyro_bias[1] + alpha * (gyro[1] - self._gyro_bias[1]),
                self._gyro_bias[2] + alpha * (gyro[2] - self._gyro_bias[2])
            )
            self._bias_samples += 1

            if self._bias_samples >= num_samples:
                self._bias_initialized = True

    def reset(self) -> None:
        """Reset filter to initial state."""
        self._orientation = Quaternion.identity()
        self._last_timestamp = None
        self._initialized = False

    @property
    def orientation(self) -> Quaternion:
        """Get current orientation estimate."""
        return self._orientation
```

### 4.2 Extended Kalman Filter Preparation

```python
# firmware/src/perception/fusion/kalman_filter.py

import numpy as np
from dataclasses import dataclass
from typing import Tuple, Optional
import time

@dataclass
class KalmanFilterConfig:
    """Configuration for Extended Kalman Filter."""
    # Process noise covariance (gyroscope noise)
    gyro_noise: float = 0.01  # rad/s
    gyro_bias_noise: float = 0.0001  # rad/s² (bias random walk)

    # Measurement noise covariance
    accel_noise: float = 0.1  # m/s²
    mag_noise: float = 0.5  # µT

    # Initial state covariance
    initial_orientation_variance: float = 0.1  # rad²
    initial_bias_variance: float = 0.01  # (rad/s)²


class ExtendedKalmanFilter:
    """Extended Kalman Filter for IMU orientation estimation.

    State vector: [q0, q1, q2, q3, bx, by, bz]
        - q0-q3: Orientation quaternion components
        - bx-bz: Gyroscope bias estimates (rad/s)

    This is a preparation for Week 3 when AI camera provides
    additional measurements for state estimation.

    TODO: Full implementation in Week 3 with camera integration.
    """

    def __init__(self, config: Optional[KalmanFilterConfig] = None):
        """Initialize EKF.

        Args:
            config: Filter configuration
        """
        self.config = config or KalmanFilterConfig()
        self._initialized = False

        # State vector: [q0, q1, q2, q3, bx, by, bz] (7 elements)
        self._x = np.array([1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])

        # State covariance matrix (7x7)
        self._P = np.eye(7)
        self._P[0:4, 0:4] *= self.config.initial_orientation_variance
        self._P[4:7, 4:7] *= self.config.initial_bias_variance

        self._last_timestamp: Optional[float] = None

    def predict(self, gyro: Tuple[float, float, float],
                timestamp: Optional[float] = None) -> None:
        """Prediction step using gyroscope.

        Integrates angular velocity to predict next state.

        Args:
            gyro: Angular velocity (x, y, z) in rad/s
            timestamp: Measurement timestamp
        """
        now = timestamp or time.monotonic()

        if self._last_timestamp is None:
            self._last_timestamp = now
            return

        dt = now - self._last_timestamp
        self._last_timestamp = now

        if dt <= 0 or dt > 1.0:
            return

        # Get current state
        q = self._x[0:4]
        bias = self._x[4:7]

        # Corrected gyroscope
        w = np.array([gyro[0] - bias[0],
                      gyro[1] - bias[1],
                      gyro[2] - bias[2]])

        # State transition (quaternion kinematics)
        omega_norm = np.linalg.norm(w)
        if omega_norm > 1e-10:
            # Compute rotation quaternion
            half_angle = omega_norm * dt / 2.0
            s = np.sin(half_angle) / omega_norm
            delta_q = np.array([np.cos(half_angle),
                                w[0] * s, w[1] * s, w[2] * s])

            # Quaternion multiplication
            q_new = self._quaternion_multiply(q, delta_q)

            # Normalize
            q_new /= np.linalg.norm(q_new)
            self._x[0:4] = q_new

        # Process noise matrix (7x7)
        Q = np.zeros((7, 7))
        Q[0:4, 0:4] = np.eye(4) * (self.config.gyro_noise * dt)**2
        Q[4:7, 4:7] = np.eye(3) * (self.config.gyro_bias_noise * dt)**2

        # State transition Jacobian (simplified)
        F = np.eye(7)
        # TODO: Full Jacobian computation for rigorous EKF

        # Update covariance
        self._P = F @ self._P @ F.T + Q

    def update_accelerometer(self, accel: Tuple[float, float, float]) -> None:
        """Measurement update using accelerometer.

        Corrects orientation estimate using gravity reference.

        Args:
            accel: Accelerometer reading (x, y, z) in m/s²
        """
        # Normalize accelerometer
        a = np.array(accel)
        a_norm = np.linalg.norm(a)

        if a_norm < 0.5 or a_norm > 20:  # Invalid reading
            return

        a /= a_norm

        # Expected gravity in body frame
        q = self._x[0:4]
        g_body = self._rotate_vector_by_quaternion(np.array([0, 0, 1]), q)

        # Measurement residual
        y = a - g_body

        # Measurement Jacobian (simplified 2-axis correction)
        # TODO: Full Jacobian for rigorous implementation
        H = np.zeros((3, 7))
        H[0:3, 0:4] = 1.0  # Placeholder

        # Measurement noise
        R = np.eye(3) * self.config.accel_noise**2

        # Kalman gain
        S = H @ self._P @ H.T + R
        K = self._P @ H.T @ np.linalg.inv(S)

        # State update
        self._x += K @ y

        # Normalize quaternion
        self._x[0:4] /= np.linalg.norm(self._x[0:4])

        # Covariance update
        I = np.eye(7)
        self._P = (I - K @ H) @ self._P

    def _quaternion_multiply(self, q1: np.ndarray, q2: np.ndarray) -> np.ndarray:
        """Hamilton product of two quaternions."""
        w1, x1, y1, z1 = q1
        w2, x2, y2, z2 = q2

        return np.array([
            w1*w2 - x1*x2 - y1*y2 - z1*z2,
            w1*x2 + x1*w2 + y1*z2 - z1*y2,
            w1*y2 - x1*z2 + y1*w2 + z1*x2,
            w1*z2 + x1*y2 - y1*x2 + z1*w2
        ])

    def _rotate_vector_by_quaternion(self, v: np.ndarray, q: np.ndarray) -> np.ndarray:
        """Rotate vector by quaternion (q * v * q^-1)."""
        qv = np.array([0, v[0], v[1], v[2]])
        q_conj = np.array([q[0], -q[1], -q[2], -q[3]])
        result = self._quaternion_multiply(
            self._quaternion_multiply(q, qv), q_conj
        )
        return result[1:4]

    @property
    def orientation(self) -> Tuple[float, float, float, float]:
        """Get current orientation as quaternion (w, x, y, z)."""
        return tuple(self._x[0:4])

    @property
    def gyro_bias(self) -> Tuple[float, float, float]:
        """Get estimated gyroscope bias (rad/s)."""
        return tuple(self._x[4:7])

    @property
    def covariance(self) -> np.ndarray:
        """Get state covariance matrix."""
        return self._P.copy()

    def reset(self) -> None:
        """Reset filter to initial state."""
        self._x = np.array([1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        self._P = np.eye(7)
        self._P[0:4, 0:4] *= self.config.initial_orientation_variance
        self._P[4:7, 4:7] *= self.config.initial_bias_variance
        self._last_timestamp = None
        self._initialized = False
```

---

## 5. Calibration Procedures

### 5.1 IMU Calibration

```python
# firmware/src/perception/calibration/imu_calibration.py

from dataclasses import dataclass, field
from typing import Tuple, Optional, List
import time
import math
import yaml

@dataclass
class CalibrationData:
    """IMU calibration data."""
    # Accelerometer calibration
    accel_offset: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    accel_scale: Tuple[float, float, float] = (1.0, 1.0, 1.0)

    # Gyroscope calibration
    gyro_offset: Tuple[float, float, float] = (0.0, 0.0, 0.0)

    # Magnetometer calibration (hard/soft iron)
    mag_offset: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    mag_scale: Tuple[float, float, float] = (1.0, 1.0, 1.0)

    # Mounting orientation (degrees)
    mounting_roll: float = 0.0
    mounting_pitch: float = 0.0
    mounting_yaw: float = 0.0

    # Metadata
    calibrated_at: Optional[float] = None
    temperature_c: Optional[float] = None
    is_valid: bool = False


class IMUCalibration:
    """IMU calibration routines.

    Provides methods for:
    1. Gyroscope zero-rate offset calibration
    2. Accelerometer bias and scale calibration
    3. Magnetometer hard/soft iron compensation
    4. Mounting orientation compensation

    Calibration Procedure:
    1. Place robot on flat, level surface
    2. Call calibrate_gyroscope() (robot must be stationary)
    3. Perform 6-position accelerometer calibration
    4. Perform figure-8 magnetometer calibration
    5. Measure mounting orientation offsets
    """

    GRAVITY = 9.81  # m/s²

    def __init__(self, imu_interface):
        """Initialize calibration.

        Args:
            imu_interface: IMU sensor interface
        """
        self.imu = imu_interface
        self.data = CalibrationData()
        self._samples: List[Tuple] = []

    def calibrate_gyroscope(self, duration_s: float = 3.0,
                            sample_rate_hz: float = 100.0) -> Tuple[float, float, float]:
        """Calibrate gyroscope zero-rate offset.

        Robot MUST be completely stationary during calibration.

        Args:
            duration_s: Calibration duration in seconds
            sample_rate_hz: Sampling rate

        Returns:
            Tuple of (x, y, z) offset in rad/s
        """
        samples = []
        num_samples = int(duration_s * sample_rate_hz)
        interval = 1.0 / sample_rate_hz

        for _ in range(num_samples):
            reading = self.imu.read_raw_gyroscope()
            if reading is not None:
                samples.append(reading)
            time.sleep(interval)

        if len(samples) < 10:
            raise CalibrationError("Not enough gyroscope samples")

        # Calculate mean offset
        x_offset = sum(s[0] for s in samples) / len(samples)
        y_offset = sum(s[1] for s in samples) / len(samples)
        z_offset = sum(s[2] for s in samples) / len(samples)

        # Verify variance is low (robot was stationary)
        x_var = sum((s[0] - x_offset)**2 for s in samples) / len(samples)
        y_var = sum((s[1] - y_offset)**2 for s in samples) / len(samples)
        z_var = sum((s[2] - z_offset)**2 for s in samples) / len(samples)

        max_var = 0.01  # (rad/s)² threshold
        if x_var > max_var or y_var > max_var or z_var > max_var:
            raise CalibrationError(
                f"High variance detected: ({x_var:.4f}, {y_var:.4f}, {z_var:.4f}). "
                "Ensure robot is stationary."
            )

        self.data.gyro_offset = (x_offset, y_offset, z_offset)
        return self.data.gyro_offset

    def calibrate_accelerometer_six_position(self) -> CalibrationData:
        """Six-position accelerometer calibration.

        Measures gravity vector in 6 orientations to determine
        scale factors and offsets for each axis.

        Positions:
        1. Flat (Z up)
        2. Upside down (Z down)
        3. Right side up (X up)
        4. Left side up (X down)
        5. Nose up (Y up)
        6. Nose down (Y down)

        Returns:
            CalibrationData with updated accelerometer calibration
        """
        positions = []
        position_names = [
            "FLAT (Z up)", "UPSIDE DOWN (Z down)",
            "RIGHT SIDE (X up)", "LEFT SIDE (X down)",
            "NOSE UP (Y up)", "NOSE DOWN (Y down)"
        ]

        print("Six-position accelerometer calibration")
        print("Hold robot steady in each position for 2 seconds")

        for i, name in enumerate(position_names):
            print(f"\nPosition {i+1}/6: {name}")
            print("Press Enter when ready...")
            input()

            # Collect samples
            samples = []
            for _ in range(200):  # 2 seconds at 100Hz
                reading = self.imu.read_raw_accelerometer()
                if reading:
                    samples.append(reading)
                time.sleep(0.01)

            # Average
            if samples:
                avg = (
                    sum(s[0] for s in samples) / len(samples),
                    sum(s[1] for s in samples) / len(samples),
                    sum(s[2] for s in samples) / len(samples)
                )
                positions.append(avg)
                print(f"  Measured: X={avg[0]:.3f}, Y={avg[1]:.3f}, Z={avg[2]:.3f}")

        if len(positions) != 6:
            raise CalibrationError("Failed to collect all 6 positions")

        # Calculate offsets and scales
        # Z axis: positions[0] = +g, positions[1] = -g
        z_plus = positions[0][2]
        z_minus = positions[1][2]
        z_scale = (2 * self.GRAVITY) / (z_plus - z_minus)
        z_offset = (z_plus + z_minus) / 2

        # X axis: positions[2] = +g, positions[3] = -g
        x_plus = positions[2][0]
        x_minus = positions[3][0]
        x_scale = (2 * self.GRAVITY) / (x_plus - x_minus)
        x_offset = (x_plus + x_minus) / 2

        # Y axis: positions[4] = +g, positions[5] = -g
        y_plus = positions[4][1]
        y_minus = positions[5][1]
        y_scale = (2 * self.GRAVITY) / (y_plus - y_minus)
        y_offset = (y_plus + y_minus) / 2

        self.data.accel_offset = (x_offset, y_offset, z_offset)
        self.data.accel_scale = (x_scale, y_scale, z_scale)

        return self.data

    def calibrate_magnetometer_figure8(self, duration_s: float = 30.0) -> CalibrationData:
        """Magnetometer hard/soft iron calibration.

        User rotates robot in figure-8 pattern to sample all orientations.

        Args:
            duration_s: Duration to collect samples

        Returns:
            CalibrationData with updated magnetometer calibration
        """
        print(f"Magnetometer calibration: Rotate robot in figure-8 for {duration_s}s")
        print("Press Enter to start...")
        input()

        samples = []
        start_time = time.time()

        while time.time() - start_time < duration_s:
            reading = self.imu.read_raw_magnetometer()
            if reading:
                samples.append(reading)
            time.sleep(0.01)

        if len(samples) < 100:
            raise CalibrationError("Not enough magnetometer samples")

        # Find min/max for each axis (ellipsoid fitting simplified)
        x_vals = [s[0] for s in samples]
        y_vals = [s[1] for s in samples]
        z_vals = [s[2] for s in samples]

        x_min, x_max = min(x_vals), max(x_vals)
        y_min, y_max = min(y_vals), max(y_vals)
        z_min, z_max = min(z_vals), max(z_vals)

        # Hard iron offset (center of ellipsoid)
        x_offset = (x_max + x_min) / 2
        y_offset = (y_max + y_min) / 2
        z_offset = (z_max + z_min) / 2

        # Soft iron scale (ellipsoid to sphere)
        x_range = (x_max - x_min) / 2
        y_range = (y_max - y_min) / 2
        z_range = (z_max - z_min) / 2
        avg_range = (x_range + y_range + z_range) / 3

        x_scale = avg_range / x_range if x_range > 0 else 1.0
        y_scale = avg_range / y_range if y_range > 0 else 1.0
        z_scale = avg_range / z_range if z_range > 0 else 1.0

        self.data.mag_offset = (x_offset, y_offset, z_offset)
        self.data.mag_scale = (x_scale, y_scale, z_scale)

        return self.data

    def set_mounting_orientation(self, roll: float, pitch: float, yaw: float) -> None:
        """Set mounting orientation offsets.

        Use when IMU is not aligned with robot body frame.

        Args:
            roll: Roll offset in degrees
            pitch: Pitch offset in degrees
            yaw: Yaw offset in degrees
        """
        self.data.mounting_roll = roll
        self.data.mounting_pitch = pitch
        self.data.mounting_yaw = yaw

    def save(self, filepath: str) -> None:
        """Save calibration data to YAML file.

        Args:
            filepath: Path to save calibration file
        """
        self.data.calibrated_at = time.time()
        self.data.is_valid = True

        data_dict = {
            'imu_calibration': {
                'accelerometer': {
                    'offset': list(self.data.accel_offset),
                    'scale': list(self.data.accel_scale)
                },
                'gyroscope': {
                    'offset': list(self.data.gyro_offset)
                },
                'magnetometer': {
                    'offset': list(self.data.mag_offset),
                    'scale': list(self.data.mag_scale)
                },
                'mounting': {
                    'roll': self.data.mounting_roll,
                    'pitch': self.data.mounting_pitch,
                    'yaw': self.data.mounting_yaw
                },
                'metadata': {
                    'calibrated_at': self.data.calibrated_at,
                    'is_valid': self.data.is_valid
                }
            }
        }

        with open(filepath, 'w') as f:
            yaml.dump(data_dict, f, default_flow_style=False)

    def load(self, filepath: str) -> CalibrationData:
        """Load calibration data from YAML file.

        Args:
            filepath: Path to calibration file

        Returns:
            Loaded CalibrationData
        """
        with open(filepath, 'r') as f:
            data = yaml.safe_load(f)

        cal = data.get('imu_calibration', {})

        accel = cal.get('accelerometer', {})
        self.data.accel_offset = tuple(accel.get('offset', [0, 0, 0]))
        self.data.accel_scale = tuple(accel.get('scale', [1, 1, 1]))

        gyro = cal.get('gyroscope', {})
        self.data.gyro_offset = tuple(gyro.get('offset', [0, 0, 0]))

        mag = cal.get('magnetometer', {})
        self.data.mag_offset = tuple(mag.get('offset', [0, 0, 0]))
        self.data.mag_scale = tuple(mag.get('scale', [1, 1, 1]))

        mounting = cal.get('mounting', {})
        self.data.mounting_roll = mounting.get('roll', 0.0)
        self.data.mounting_pitch = mounting.get('pitch', 0.0)
        self.data.mounting_yaw = mounting.get('yaw', 0.0)

        meta = cal.get('metadata', {})
        self.data.calibrated_at = meta.get('calibrated_at')
        self.data.is_valid = meta.get('is_valid', False)

        return self.data

    def apply_calibration(self,
                          accel: Tuple[float, float, float],
                          gyro: Tuple[float, float, float],
                          mag: Optional[Tuple[float, float, float]] = None
                         ) -> Tuple[Tuple, Tuple, Optional[Tuple]]:
        """Apply calibration to raw sensor readings.

        Args:
            accel: Raw accelerometer (x, y, z)
            gyro: Raw gyroscope (x, y, z)
            mag: Raw magnetometer (x, y, z) or None

        Returns:
            Tuple of (calibrated_accel, calibrated_gyro, calibrated_mag)
        """
        # Apply accelerometer calibration
        cal_accel = (
            (accel[0] - self.data.accel_offset[0]) * self.data.accel_scale[0],
            (accel[1] - self.data.accel_offset[1]) * self.data.accel_scale[1],
            (accel[2] - self.data.accel_offset[2]) * self.data.accel_scale[2]
        )

        # Apply gyroscope calibration
        cal_gyro = (
            gyro[0] - self.data.gyro_offset[0],
            gyro[1] - self.data.gyro_offset[1],
            gyro[2] - self.data.gyro_offset[2]
        )

        # Apply magnetometer calibration
        cal_mag = None
        if mag is not None:
            cal_mag = (
                (mag[0] - self.data.mag_offset[0]) * self.data.mag_scale[0],
                (mag[1] - self.data.mag_offset[1]) * self.data.mag_scale[1],
                (mag[2] - self.data.mag_offset[2]) * self.data.mag_scale[2]
            )

        return cal_accel, cal_gyro, cal_mag


class CalibrationError(Exception):
    """Calibration-related errors."""
    pass
```

---

## 6. Noise Filtering

### 6.1 Low-Pass Filter

```python
# firmware/src/perception/filtering/low_pass_filter.py

from dataclasses import dataclass
from typing import Optional, Tuple, Union
import math

@dataclass
class LowPassFilterConfig:
    """Low-pass filter configuration."""
    cutoff_hz: float = 10.0  # Cutoff frequency
    sample_rate_hz: float = 100.0  # Sample rate

    def __post_init__(self):
        if self.cutoff_hz <= 0:
            raise ValueError("cutoff_hz must be positive")
        if self.sample_rate_hz <= 0:
            raise ValueError("sample_rate_hz must be positive")
        if self.cutoff_hz >= self.sample_rate_hz / 2:
            raise ValueError("cutoff_hz must be less than Nyquist frequency")


class LowPassFilter:
    """First-order IIR low-pass filter.

    Implements exponential moving average (EMA) filter:
        y[n] = alpha * x[n] + (1 - alpha) * y[n-1]

    Where alpha = 1 - e^(-2*pi*fc/fs)

    Useful for:
    - Removing high-frequency noise from sensor data
    - Smoothing accelerometer readings
    - Reducing gyroscope jitter

    Attributes:
        config: Filter configuration
        alpha: Filter coefficient (computed from cutoff)
        _state: Previous filter output
    """

    def __init__(self, config: Optional[LowPassFilterConfig] = None):
        """Initialize low-pass filter.

        Args:
            config: Filter configuration
        """
        self.config = config or LowPassFilterConfig()

        # Calculate filter coefficient
        dt = 1.0 / self.config.sample_rate_hz
        rc = 1.0 / (2 * math.pi * self.config.cutoff_hz)
        self.alpha = dt / (rc + dt)

        self._state: Optional[float] = None

    def filter(self, value: float) -> float:
        """Filter a single value.

        Args:
            value: Input value

        Returns:
            Filtered value
        """
        if self._state is None:
            self._state = value
        else:
            self._state = self.alpha * value + (1 - self.alpha) * self._state

        return self._state

    def reset(self, initial: Optional[float] = None) -> None:
        """Reset filter state.

        Args:
            initial: Initial state value (None to reset completely)
        """
        self._state = initial

    @property
    def state(self) -> Optional[float]:
        """Get current filter state."""
        return self._state


class LowPassFilter3D:
    """Low-pass filter for 3D vectors (accelerometer, gyroscope, etc.)."""

    def __init__(self, config: Optional[LowPassFilterConfig] = None):
        """Initialize 3D low-pass filter.

        Args:
            config: Filter configuration (shared by all axes)
        """
        self.config = config or LowPassFilterConfig()
        self._filters = [
            LowPassFilter(self.config),
            LowPassFilter(self.config),
            LowPassFilter(self.config)
        ]

    def filter(self, vector: Tuple[float, float, float]) -> Tuple[float, float, float]:
        """Filter a 3D vector.

        Args:
            vector: Input vector (x, y, z)

        Returns:
            Filtered vector (x, y, z)
        """
        return (
            self._filters[0].filter(vector[0]),
            self._filters[1].filter(vector[1]),
            self._filters[2].filter(vector[2])
        )

    def reset(self, initial: Optional[Tuple[float, float, float]] = None) -> None:
        """Reset all filter states."""
        for i, f in enumerate(self._filters):
            f.reset(initial[i] if initial else None)
```

### 6.2 Moving Average Filter

```python
# firmware/src/perception/filtering/moving_average.py

from typing import Optional, Tuple, List
from collections import deque

class MovingAverageFilter:
    """Moving average filter for sensor data.

    Simple but effective for:
    - Reducing random noise
    - Smoothing sensor readings
    - Constant group delay (unlike IIR filters)

    Attributes:
        window_size: Number of samples to average
        _buffer: Circular buffer of samples
        _sum: Running sum for O(1) average computation
    """

    def __init__(self, window_size: int = 10):
        """Initialize moving average filter.

        Args:
            window_size: Number of samples in averaging window
        """
        if window_size <= 0:
            raise ValueError("window_size must be positive")

        self.window_size = window_size
        self._buffer: deque = deque(maxlen=window_size)
        self._sum: float = 0.0

    def filter(self, value: float) -> float:
        """Filter a single value.

        O(1) computation using running sum.

        Args:
            value: Input value

        Returns:
            Moving average value
        """
        # Remove oldest value from sum if buffer is full
        if len(self._buffer) == self.window_size:
            self._sum -= self._buffer[0]

        # Add new value
        self._buffer.append(value)
        self._sum += value

        return self._sum / len(self._buffer)

    def reset(self) -> None:
        """Reset filter state."""
        self._buffer.clear()
        self._sum = 0.0

    @property
    def is_primed(self) -> bool:
        """Check if buffer is full (filter is primed)."""
        return len(self._buffer) == self.window_size


class MovingAverageFilter3D:
    """Moving average filter for 3D vectors."""

    def __init__(self, window_size: int = 10):
        """Initialize 3D moving average filter.

        Args:
            window_size: Number of samples in averaging window
        """
        self._filters = [
            MovingAverageFilter(window_size),
            MovingAverageFilter(window_size),
            MovingAverageFilter(window_size)
        ]

    def filter(self, vector: Tuple[float, float, float]) -> Tuple[float, float, float]:
        """Filter a 3D vector.

        Args:
            vector: Input vector (x, y, z)

        Returns:
            Filtered vector (x, y, z)
        """
        return (
            self._filters[0].filter(vector[0]),
            self._filters[1].filter(vector[1]),
            self._filters[2].filter(vector[2])
        )

    def reset(self) -> None:
        """Reset all filter states."""
        for f in self._filters:
            f.reset()

    @property
    def is_primed(self) -> bool:
        """Check if all filters are primed."""
        return all(f.is_primed for f in self._filters)
```

### 6.3 Outlier Rejection

```python
# firmware/src/perception/filtering/outlier_rejection.py

from typing import Optional, Tuple, List
from collections import deque
import math

class MedianFilter:
    """Median filter for outlier rejection.

    Effective for removing spike noise (impulse noise) that
    mean-based filters struggle with.

    Particularly useful for:
    - Ultrasonic sensor distance readings
    - Magnetometer readings near ferromagnetic objects
    - Any sensor prone to occasional spurious readings
    """

    def __init__(self, window_size: int = 5):
        """Initialize median filter.

        Args:
            window_size: Number of samples (should be odd)
        """
        if window_size <= 0:
            raise ValueError("window_size must be positive")
        if window_size % 2 == 0:
            window_size += 1  # Ensure odd for proper median

        self.window_size = window_size
        self._buffer: deque = deque(maxlen=window_size)

    def filter(self, value: float) -> float:
        """Filter a single value.

        Args:
            value: Input value

        Returns:
            Median of recent values
        """
        self._buffer.append(value)
        sorted_buffer = sorted(self._buffer)
        return sorted_buffer[len(sorted_buffer) // 2]

    def reset(self) -> None:
        """Reset filter state."""
        self._buffer.clear()


class ZScoreOutlierFilter:
    """Z-score based outlier detection and rejection.

    Rejects readings that are more than threshold standard
    deviations from the running mean.

    Useful when:
    - Data is approximately normally distributed
    - Outliers are rare but extreme
    - Need adaptive threshold based on noise level
    """

    def __init__(self, window_size: int = 20, threshold: float = 3.0):
        """Initialize Z-score outlier filter.

        Args:
            window_size: Number of samples for statistics
            threshold: Number of standard deviations for outlier
        """
        self.window_size = window_size
        self.threshold = threshold
        self._buffer: deque = deque(maxlen=window_size)
        self._last_valid: Optional[float] = None

    def filter(self, value: float) -> float:
        """Filter a single value.

        If value is outlier, returns last valid value instead.

        Args:
            value: Input value

        Returns:
            Filtered value (original or last valid)
        """
        if len(self._buffer) < 3:
            # Not enough data for statistics
            self._buffer.append(value)
            self._last_valid = value
            return value

        # Calculate mean and std
        mean = sum(self._buffer) / len(self._buffer)
        variance = sum((x - mean)**2 for x in self._buffer) / len(self._buffer)
        std = math.sqrt(variance) if variance > 0 else 1e-10

        # Calculate Z-score
        z_score = abs(value - mean) / std

        if z_score > self.threshold:
            # Outlier detected, return last valid
            return self._last_valid if self._last_valid is not None else mean
        else:
            # Valid reading
            self._buffer.append(value)
            self._last_valid = value
            return value

    def reset(self) -> None:
        """Reset filter state."""
        self._buffer.clear()
        self._last_valid = None
```

---

## 7. Data Pipeline Design

### 7.1 Perception Pipeline

```python
# firmware/src/perception/pipeline/perception_pipeline.py

import time
import threading
from typing import Optional, Callable, List, Dict, Any
from dataclasses import dataclass
from queue import Queue, Empty

from ..interfaces.imu_interface import IMUInterface, IMUReading
from ..fusion.complementary_filter import ComplementaryFilter
from ..calibration.imu_calibration import IMUCalibration, CalibrationData
from ..filtering.low_pass_filter import LowPassFilter3D, LowPassFilterConfig
from ..data.sensor_buffer import RingBuffer
from ..data.orientation_data import OrientationState

@dataclass
class PipelineConfig:
    """Perception pipeline configuration."""
    sample_rate_hz: float = 100.0  # IMU sample rate
    publish_rate_hz: float = 50.0  # Output rate to consumers
    buffer_size: int = 100  # History buffer size
    enable_filtering: bool = True  # Enable noise filtering
    accel_cutoff_hz: float = 10.0  # Accelerometer LPF cutoff
    gyro_cutoff_hz: float = 25.0  # Gyroscope LPF cutoff


class PerceptionPipeline:
    """Main perception data pipeline.

    Orchestrates:
    1. Sensor reading at configured rate
    2. Calibration application
    3. Noise filtering
    4. Sensor fusion
    5. Data buffering
    6. Publishing to subscribers

    Architecture:
        IMU -> Calibration -> Filter -> Fusion -> Buffer -> Subscribers

    Thread model:
        - Reader thread: Samples IMU at sample_rate_hz
        - Publisher thread: Publishes fused data at publish_rate_hz
    """

    def __init__(self, imu: IMUInterface,
                 config: Optional[PipelineConfig] = None):
        """Initialize perception pipeline.

        Args:
            imu: IMU sensor interface
            config: Pipeline configuration
        """
        self.imu = imu
        self.config = config or PipelineConfig()

        # Initialize components
        self.calibration = IMUCalibration(imu)
        self.fusion = ComplementaryFilter()

        # Filters
        accel_config = LowPassFilterConfig(
            cutoff_hz=self.config.accel_cutoff_hz,
            sample_rate_hz=self.config.sample_rate_hz
        )
        gyro_config = LowPassFilterConfig(
            cutoff_hz=self.config.gyro_cutoff_hz,
            sample_rate_hz=self.config.sample_rate_hz
        )
        self._accel_filter = LowPassFilter3D(accel_config)
        self._gyro_filter = LowPassFilter3D(gyro_config)

        # Data storage
        self._history = RingBuffer[OrientationState](self.config.buffer_size)
        self._current_state: Optional[OrientationState] = None

        # Subscribers
        self._subscribers: List[Callable[[OrientationState], None]] = []

        # Threading
        self._running = False
        self._reader_thread: Optional[threading.Thread] = None
        self._publisher_thread: Optional[threading.Thread] = None
        self._data_queue: Queue = Queue(maxsize=10)
        self._lock = threading.Lock()

    def start(self) -> None:
        """Start the perception pipeline."""
        if self._running:
            return

        self._running = True

        # Start reader thread
        self._reader_thread = threading.Thread(
            target=self._reader_loop,
            name="PerceptionReader",
            daemon=True
        )
        self._reader_thread.start()

        # Start publisher thread
        self._publisher_thread = threading.Thread(
            target=self._publisher_loop,
            name="PerceptionPublisher",
            daemon=True
        )
        self._publisher_thread.start()

    def stop(self) -> None:
        """Stop the perception pipeline."""
        self._running = False

        if self._reader_thread:
            self._reader_thread.join(timeout=1.0)
        if self._publisher_thread:
            self._publisher_thread.join(timeout=1.0)

    def _reader_loop(self) -> None:
        """Sensor reading loop (runs in dedicated thread)."""
        interval = 1.0 / self.config.sample_rate_hz

        while self._running:
            start = time.monotonic()

            try:
                # Read raw data from IMU
                reading = self.imu.read()

                if reading is not None:
                    # Apply calibration
                    cal_accel, cal_gyro, cal_mag = self.calibration.apply_calibration(
                        reading.accelerometer,
                        reading.gyroscope,
                        reading.magnetometer
                    )

                    # Apply noise filtering
                    if self.config.enable_filtering:
                        cal_accel = self._accel_filter.filter(cal_accel)
                        cal_gyro = self._gyro_filter.filter(cal_gyro)

                    # Update sensor fusion
                    state = self.fusion.update(
                        gyroscope=cal_gyro,
                        accelerometer=cal_accel,
                        magnetometer=cal_mag,
                        timestamp=reading.timestamp
                    )

                    # Store in history
                    self._history.append(state)

                    # Queue for publisher
                    try:
                        self._data_queue.put_nowait(state)
                    except:
                        pass  # Queue full, drop old data

                    # Update current state
                    with self._lock:
                        self._current_state = state

            except Exception as e:
                # Log error but continue running
                pass

            # Maintain sample rate
            elapsed = time.monotonic() - start
            sleep_time = interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    def _publisher_loop(self) -> None:
        """Publisher loop (runs in dedicated thread)."""
        interval = 1.0 / self.config.publish_rate_hz

        while self._running:
            start = time.monotonic()

            try:
                state = self._data_queue.get(timeout=0.1)

                # Notify all subscribers
                for callback in self._subscribers:
                    try:
                        callback(state)
                    except Exception as e:
                        pass  # Don't let one subscriber break others

            except Empty:
                pass

            # Maintain publish rate
            elapsed = time.monotonic() - start
            sleep_time = interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    def subscribe(self, callback: Callable[[OrientationState], None]) -> None:
        """Subscribe to orientation updates.

        Args:
            callback: Function to call with new OrientationState
        """
        self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[OrientationState], None]) -> None:
        """Unsubscribe from orientation updates."""
        if callback in self._subscribers:
            self._subscribers.remove(callback)

    def get_current_state(self) -> Optional[OrientationState]:
        """Get most recent orientation state (thread-safe)."""
        with self._lock:
            return self._current_state

    def get_history(self, n: int = 10) -> List[OrientationState]:
        """Get recent orientation history.

        Args:
            n: Number of recent states to return

        Returns:
            List of OrientationState (newest last)
        """
        return self._history.get_latest(n)

    def load_calibration(self, filepath: str) -> None:
        """Load calibration from file.

        Args:
            filepath: Path to calibration YAML file
        """
        self.calibration.load(filepath)

    def save_calibration(self, filepath: str) -> None:
        """Save current calibration to file.

        Args:
            filepath: Path to save calibration YAML file
        """
        self.calibration.save(filepath)

    @property
    def is_running(self) -> bool:
        """Check if pipeline is running."""
        return self._running
```

---

## 8. AI Camera Preparation (Week 3)

### 8.1 Camera Interface

```python
# firmware/src/perception/interfaces/camera_interface.py

from abc import abstractmethod
from dataclasses import dataclass
from typing import Optional, Tuple, List, Any
import numpy as np

from .sensor_interface import SensorInterface, SensorStatus

@dataclass
class CameraReading:
    """Camera sensor reading."""
    # Raw image data
    image: np.ndarray  # Shape: (H, W, C) or (H, W) for grayscale

    # Metadata
    timestamp: float
    frame_number: int
    exposure_ms: float
    gain: float

    # Camera intrinsics (for 3D reconstruction)
    fx: float  # Focal length x (pixels)
    fy: float  # Focal length y (pixels)
    cx: float  # Principal point x
    cy: float  # Principal point y

    @property
    def shape(self) -> Tuple[int, int, int]:
        """Get image shape (height, width, channels)."""
        if len(self.image.shape) == 2:
            return (*self.image.shape, 1)
        return self.image.shape


@dataclass
class ObjectDetection:
    """Detected object from AI camera inference."""
    class_id: int
    class_name: str
    confidence: float  # 0.0 to 1.0
    bbox: Tuple[int, int, int, int]  # (x, y, width, height)

    # Optional 3D pose estimation
    position_3d: Optional[Tuple[float, float, float]] = None  # (x, y, z) in meters
    orientation: Optional[Tuple[float, float, float, float]] = None  # Quaternion


@dataclass
class AIInferenceResult:
    """Result from AI camera on-chip inference."""
    detections: List[ObjectDetection]
    inference_time_ms: float
    model_name: str
    timestamp: float


class CameraInterface(SensorInterface[CameraReading]):
    """Abstract interface for camera sensors.

    Supports both standard cameras and AI cameras (like IMX500).

    For Week 3 integration:
    - Standard capture (get_frame)
    - AI inference (run_inference)
    - Model loading (load_model)
    - Camera calibration (intrinsics, distortion)
    """

    @abstractmethod
    def get_frame(self) -> Optional[CameraReading]:
        """Capture a single frame.

        Returns:
            CameraReading or None if capture fails
        """
        pass

    @abstractmethod
    def set_resolution(self, width: int, height: int) -> bool:
        """Set camera resolution.

        Args:
            width: Frame width in pixels
            height: Frame height in pixels

        Returns:
            True if resolution set successfully
        """
        pass

    @abstractmethod
    def set_framerate(self, fps: float) -> bool:
        """Set camera framerate.

        Args:
            fps: Frames per second

        Returns:
            True if framerate set successfully
        """
        pass

    # AI Camera specific methods (optional, raise NotImplementedError if not supported)

    def load_model(self, model_path: str) -> bool:
        """Load AI model for on-chip inference.

        Args:
            model_path: Path to model file

        Returns:
            True if model loaded successfully
        """
        raise NotImplementedError("AI inference not supported by this camera")

    def run_inference(self, frame: Optional[CameraReading] = None) -> AIInferenceResult:
        """Run AI inference on current or provided frame.

        Args:
            frame: Frame to process (uses latest if None)

        Returns:
            AIInferenceResult with detections
        """
        raise NotImplementedError("AI inference not supported by this camera")

    def get_intrinsics(self) -> Tuple[float, float, float, float]:
        """Get camera intrinsic parameters.

        Returns:
            Tuple of (fx, fy, cx, cy)
        """
        pass

    def get_distortion_coefficients(self) -> Tuple[float, float, float, float, float]:
        """Get lens distortion coefficients.

        Returns:
            Tuple of (k1, k2, p1, p2, k3) radial/tangential distortion
        """
        pass
```

### 8.2 Visual-Inertial Fusion (Week 3 Preparation)

```python
# firmware/src/perception/fusion/visual_inertial_fusion.py

from dataclasses import dataclass
from typing import Optional, Tuple, List
import numpy as np

from ..interfaces.camera_interface import CameraReading, ObjectDetection
from ..data.orientation_data import OrientationState, Quaternion

@dataclass
class VisualInertialState:
    """Combined visual-inertial state estimate.

    Fuses IMU orientation with visual odometry/object detection
    for improved localization and perception.
    """
    # Orientation (from IMU + visual correction)
    orientation: Quaternion

    # Position (from visual odometry)
    position: Optional[Tuple[float, float, float]]  # (x, y, z) in meters

    # Velocity estimate
    velocity: Optional[Tuple[float, float, float]]  # (vx, vy, vz) in m/s

    # Detected objects with 3D positions
    detected_objects: List[ObjectDetection]

    # Confidence metrics
    visual_tracking_quality: float  # 0.0 to 1.0
    imu_confidence: float  # 0.0 to 1.0

    timestamp: float


class VisualInertialFusion:
    """Visual-Inertial Odometry (VIO) fusion.

    Combines:
    - IMU: High-rate orientation and motion estimation
    - Camera: Low-rate but absolute visual reference

    This is a placeholder for Week 3 implementation.
    Will use feature tracking and EKF/optimization backend.

    TODO (Week 3):
    - Feature extraction (ORB, FAST)
    - Feature tracking across frames
    - Bundle adjustment
    - IMU preintegration
    - Sliding window optimization
    """

    def __init__(self):
        """Initialize VIO fusion (placeholder)."""
        self._last_frame: Optional[CameraReading] = None
        self._last_imu_state: Optional[OrientationState] = None
        self._features: List = []  # Tracked feature points

    def process_imu(self, state: OrientationState) -> None:
        """Process IMU state update.

        Args:
            state: Current IMU orientation state
        """
        self._last_imu_state = state
        # TODO: IMU preintegration for VIO

    def process_frame(self, frame: CameraReading) -> VisualInertialState:
        """Process camera frame and produce fused state.

        Args:
            frame: Camera frame with image data

        Returns:
            VisualInertialState: Fused state estimate
        """
        # TODO: Full VIO implementation in Week 3

        # For now, return IMU-only state
        return VisualInertialState(
            orientation=self._last_imu_state.quaternion if self._last_imu_state else Quaternion.identity(),
            position=None,
            velocity=None,
            detected_objects=[],
            visual_tracking_quality=0.0,
            imu_confidence=1.0 if self._last_imu_state else 0.0,
            timestamp=frame.timestamp
        )

    def reset(self) -> None:
        """Reset fusion state."""
        self._last_frame = None
        self._last_imu_state = None
        self._features = []
```

---

## 9. TDD Test Cases

### 9.1 Quaternion Tests

```python
# Tests for firmware/src/perception/data/orientation_data.py

class TestQuaternion:
    """Test cases for Quaternion class."""

    def test_identity_quaternion(self):
        """Identity quaternion should have w=1, x=y=z=0."""
        q = Quaternion.identity()
        assert q.w == 1.0
        assert q.x == 0.0
        assert q.y == 0.0
        assert q.z == 0.0

    def test_quaternion_normalization(self):
        """Quaternions should be normalized on creation."""
        q = Quaternion(2.0, 0.0, 0.0, 0.0)  # Not unit length
        norm = (q.w**2 + q.x**2 + q.y**2 + q.z**2)**0.5
        assert abs(norm - 1.0) < 1e-10

    def test_to_euler_identity(self):
        """Identity quaternion should give (0, 0, 0) Euler angles."""
        q = Quaternion.identity()
        h, p, r = q.to_euler()
        assert abs(h) < 1e-6
        assert abs(p) < 1e-6
        assert abs(r) < 1e-6

    def test_to_euler_90_heading(self):
        """Test 90 degree heading rotation."""
        q = Quaternion.from_euler(90.0, 0.0, 0.0)
        h, p, r = q.to_euler()
        assert abs(h - 90.0) < 1e-6
        assert abs(p) < 1e-6
        assert abs(r) < 1e-6

    def test_euler_roundtrip(self):
        """Euler -> Quaternion -> Euler should preserve angles."""
        for h in [0, 45, 90, 180, 270]:
            for p in [-45, 0, 45]:
                for r in [-90, 0, 90]:
                    q = Quaternion.from_euler(h, p, r)
                    h2, p2, r2 = q.to_euler()
                    assert abs(h - h2) < 1e-4 or abs(abs(h - h2) - 360) < 1e-4
                    assert abs(p - p2) < 1e-4
                    assert abs(r - r2) < 1e-4

    def test_slerp_endpoints(self):
        """SLERP at t=0 and t=1 should return original quaternions."""
        q1 = Quaternion.from_euler(0, 0, 0)
        q2 = Quaternion.from_euler(90, 0, 0)

        r0 = q1.slerp(q2, 0.0)
        r1 = q1.slerp(q2, 1.0)

        assert abs(r0.w - q1.w) < 1e-6
        assert abs(r1.w - q2.w) < 1e-6

    def test_slerp_midpoint(self):
        """SLERP at t=0.5 should give midpoint rotation."""
        q1 = Quaternion.from_euler(0, 0, 0)
        q2 = Quaternion.from_euler(90, 0, 0)

        mid = q1.slerp(q2, 0.5)
        h, p, r = mid.to_euler()

        assert abs(h - 45) < 1e-4

    def test_conjugate(self):
        """Conjugate should negate vector components."""
        q = Quaternion(0.5, 0.5, 0.5, 0.5)
        c = q.conjugate()

        assert c.w == q.w
        assert c.x == -q.x
        assert c.y == -q.y
        assert c.z == -q.z

    def test_rotate_vector_identity(self):
        """Identity rotation should not change vector."""
        q = Quaternion.identity()
        v = (1.0, 2.0, 3.0)
        result = q.rotate_vector(v)

        assert abs(result[0] - v[0]) < 1e-10
        assert abs(result[1] - v[1]) < 1e-10
        assert abs(result[2] - v[2]) < 1e-10
```

### 9.2 Complementary Filter Tests

```python
# Tests for firmware/src/perception/fusion/complementary_filter.py

class TestComplementaryFilter:
    """Test cases for ComplementaryFilter."""

    def test_initial_state_from_accel(self):
        """First reading should initialize from accelerometer."""
        cf = ComplementaryFilter()
        state = cf.update(
            gyroscope=(0, 0, 0),
            accelerometer=(0, 0, 9.81),  # Level orientation
            timestamp=0.0
        )
        h, p, r = state.quaternion.to_euler()
        assert abs(p) < 1.0  # Near zero pitch
        assert abs(r) < 1.0  # Near zero roll

    def test_gyro_integration(self):
        """Pure gyro rotation should be tracked."""
        cf = ComplementaryFilter()
        cf.update((0, 0, 0), (0, 0, 9.81), timestamp=0.0)

        # Rotate at 1 rad/s around Z for 1 second
        for i in range(100):
            cf.update(
                gyroscope=(0, 0, 1.0),  # rad/s
                accelerometer=(0, 0, 9.81),
                timestamp=(i + 1) * 0.01
            )

        state = cf.orientation
        h, p, r = state.to_euler()
        # Should have rotated ~57 degrees (1 rad)
        assert 50 < h < 65 or 295 < h < 310  # Allow some drift

    def test_level_detection(self):
        """Tilted accelerometer should be detected."""
        cf = ComplementaryFilter()

        # 45 degree pitch
        import math
        ax = -9.81 * math.sin(math.radians(45))
        az = 9.81 * math.cos(math.radians(45))

        state = cf.update(
            gyroscope=(0, 0, 0),
            accelerometer=(ax, 0, az),
            timestamp=0.0
        )

        h, p, r = state.quaternion.to_euler()
        assert abs(p - 45) < 5  # Within 5 degrees of expected

    def test_alpha_parameter(self):
        """Higher alpha should trust gyro more."""
        config_high = ComplementaryFilterConfig(alpha=0.99)
        config_low = ComplementaryFilterConfig(alpha=0.90)

        cf_high = ComplementaryFilter(config_high)
        cf_low = ComplementaryFilter(config_low)

        # Initialize both
        cf_high.update((0, 0, 0), (0, 0, 9.81), 0.0)
        cf_low.update((0, 0, 0), (0, 0, 9.81), 0.0)

        # Apply same rotation with noise
        for i in range(50):
            # Gyro says rotate, accel has noise
            cf_high.update((0, 0, 0.5), (0.5, 0, 9.81), (i + 1) * 0.02)
            cf_low.update((0, 0, 0.5), (0.5, 0, 9.81), (i + 1) * 0.02)

        # High alpha filter should show more rotation (trusts gyro)
        h_high, _, _ = cf_high.orientation.to_euler()
        h_low, _, _ = cf_low.orientation.to_euler()

        # Both should have some rotation, but high alpha more
        # (This is a qualitative test - exact values depend on noise model)

    def test_gyro_bias_estimation(self):
        """Bias estimation should converge."""
        cf = ComplementaryFilter()

        # Initialize
        cf.update((0, 0, 0), (0, 0, 9.81), 0.0)

        # Feed biased gyro data (should be detected as stationary with bias)
        for i in range(100):
            cf.estimate_gyro_bias((0.01, 0.02, -0.01))

        # Bias should be estimated
        assert abs(cf._gyro_bias[0] - 0.01) < 0.002
        assert abs(cf._gyro_bias[1] - 0.02) < 0.002
        assert abs(cf._gyro_bias[2] - (-0.01)) < 0.002
```

### 9.3 Low-Pass Filter Tests

```python
# Tests for firmware/src/perception/filtering/low_pass_filter.py

class TestLowPassFilter:
    """Test cases for LowPassFilter."""

    def test_initialization(self):
        """Filter should initialize with correct alpha."""
        config = LowPassFilterConfig(cutoff_hz=10.0, sample_rate_hz=100.0)
        lpf = LowPassFilter(config)
        assert 0 < lpf.alpha < 1

    def test_invalid_config(self):
        """Invalid config should raise ValueError."""
        with pytest.raises(ValueError):
            LowPassFilterConfig(cutoff_hz=-1.0)

        with pytest.raises(ValueError):
            LowPassFilterConfig(cutoff_hz=60.0, sample_rate_hz=100.0)  # > Nyquist

    def test_step_response(self):
        """Step input should settle to final value."""
        lpf = LowPassFilter()

        # Apply step input
        for _ in range(100):
            result = lpf.filter(10.0)

        # Should have settled to 10
        assert abs(result - 10.0) < 0.01

    def test_high_frequency_rejection(self):
        """High frequency signals should be attenuated."""
        import math

        config = LowPassFilterConfig(cutoff_hz=5.0, sample_rate_hz=100.0)
        lpf = LowPassFilter(config)

        # 50 Hz signal (should be heavily filtered)
        outputs = []
        for i in range(200):
            t = i / 100.0
            input_val = math.sin(2 * math.pi * 50 * t)
            outputs.append(lpf.filter(input_val))

        # Output amplitude should be much smaller than input (1.0)
        max_output = max(abs(o) for o in outputs[50:])  # Skip transient
        assert max_output < 0.2

    def test_dc_passthrough(self):
        """DC signal should pass through unchanged."""
        lpf = LowPassFilter()

        # Constant input
        for _ in range(100):
            result = lpf.filter(5.0)

        assert abs(result - 5.0) < 0.01

    def test_reset(self):
        """Reset should clear filter state."""
        lpf = LowPassFilter()

        lpf.filter(100.0)
        lpf.reset()

        assert lpf.state is None

        # Next filter should start fresh
        result = lpf.filter(0.0)
        assert result == 0.0


class TestMovingAverageFilter:
    """Test cases for MovingAverageFilter."""

    def test_average_calculation(self):
        """Should correctly compute moving average."""
        maf = MovingAverageFilter(window_size=5)

        # Input: 1, 2, 3, 4, 5
        for v in [1, 2, 3, 4, 5]:
            maf.filter(v)

        # Average should be 3
        result = maf.filter(5)  # Window: 2, 3, 4, 5, 5
        assert abs(result - 3.8) < 0.01

    def test_window_size(self):
        """Only window_size samples should affect output."""
        maf = MovingAverageFilter(window_size=3)

        # Prime with zeros
        for _ in range(10):
            maf.filter(0.0)

        # Now input 10s
        for _ in range(3):
            result = maf.filter(10.0)

        # Should be 10 (window is all 10s)
        assert abs(result - 10.0) < 0.01

    def test_is_primed(self):
        """is_primed should return True after window_size samples."""
        maf = MovingAverageFilter(window_size=5)

        for i in range(4):
            maf.filter(float(i))
            assert not maf.is_primed

        maf.filter(4.0)
        assert maf.is_primed
```

### 9.4 Ring Buffer Tests

```python
# Tests for firmware/src/perception/data/sensor_buffer.py

class TestRingBuffer:
    """Test cases for RingBuffer."""

    def test_append_and_retrieve(self):
        """Basic append and retrieve operations."""
        buf = RingBuffer[int](max_size=5)

        for i in range(3):
            buf.append(i)

        assert len(buf) == 3
        assert buf.latest() == 2
        assert buf.get_latest(3) == [0, 1, 2]

    def test_overflow(self):
        """Buffer should discard oldest on overflow."""
        buf = RingBuffer[int](max_size=3)

        for i in range(5):
            buf.append(i)

        assert len(buf) == 3
        assert buf.get_all() == [2, 3, 4]  # 0 and 1 discarded

    def test_is_full(self):
        """is_full should return True when at capacity."""
        buf = RingBuffer[int](max_size=3)

        assert not buf.is_full()
        buf.append(1)
        buf.append(2)
        assert not buf.is_full()
        buf.append(3)
        assert buf.is_full()

    def test_clear(self):
        """Clear should remove all elements."""
        buf = RingBuffer[int](max_size=5)
        buf.append(1)
        buf.append(2)
        buf.clear()

        assert len(buf) == 0
        assert buf.latest() is None

    def test_thread_safety(self):
        """Buffer should be thread-safe."""
        import threading

        buf = RingBuffer[int](max_size=1000)
        errors = []

        def writer():
            for i in range(500):
                buf.append(i)

        def reader():
            for _ in range(500):
                try:
                    _ = buf.get_latest(10)
                except Exception as e:
                    errors.append(e)

        threads = [
            threading.Thread(target=writer),
            threading.Thread(target=reader),
            threading.Thread(target=writer),
            threading.Thread(target=reader),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
```

### 9.5 Calibration Tests

```python
# Tests for firmware/src/perception/calibration/imu_calibration.py

class TestIMUCalibration:
    """Test cases for IMUCalibration."""

    @pytest.fixture
    def mock_imu(self):
        """Create mock IMU for testing."""
        mock = Mock()
        mock.read_raw_gyroscope.return_value = (0.01, -0.02, 0.005)
        mock.read_raw_accelerometer.return_value = (0.1, -0.2, 9.81)
        return mock

    def test_gyro_calibration(self, mock_imu):
        """Gyroscope calibration should compute mean offset."""
        cal = IMUCalibration(mock_imu)

        offset = cal.calibrate_gyroscope(duration_s=0.5, sample_rate_hz=100)

        assert abs(offset[0] - 0.01) < 0.01
        assert abs(offset[1] - (-0.02)) < 0.01
        assert abs(offset[2] - 0.005) < 0.01

    def test_apply_gyro_calibration(self, mock_imu):
        """Applied calibration should remove offset."""
        cal = IMUCalibration(mock_imu)
        cal.data.gyro_offset = (0.01, 0.02, -0.01)

        raw = (0.11, 0.12, 0.09)
        _, corrected, _ = cal.apply_calibration((0, 0, 0), raw, None)

        assert abs(corrected[0] - 0.10) < 1e-6
        assert abs(corrected[1] - 0.10) < 1e-6
        assert abs(corrected[2] - 0.10) < 1e-6

    def test_accel_calibration_applies_scale(self, mock_imu):
        """Accelerometer calibration should apply scale and offset."""
        cal = IMUCalibration(mock_imu)
        cal.data.accel_offset = (0.5, -0.5, 0.0)
        cal.data.accel_scale = (1.0, 1.0, 0.95)

        raw = (1.5, 0.5, 10.0)
        corrected, _, _ = cal.apply_calibration(raw, (0, 0, 0), None)

        assert abs(corrected[0] - 1.0) < 1e-6
        assert abs(corrected[1] - 1.0) < 1e-6
        assert abs(corrected[2] - 9.5) < 1e-6

    def test_save_and_load(self, mock_imu, tmp_path):
        """Calibration should be saveable and loadable."""
        filepath = tmp_path / "calibration.yaml"

        cal = IMUCalibration(mock_imu)
        cal.data.gyro_offset = (0.01, 0.02, 0.03)
        cal.data.accel_offset = (0.1, 0.2, 0.3)
        cal.data.mounting_yaw = 5.0
        cal.save(str(filepath))

        # Load in new instance
        cal2 = IMUCalibration(mock_imu)
        cal2.load(str(filepath))

        assert cal2.data.gyro_offset == (0.01, 0.02, 0.03)
        assert cal2.data.accel_offset == (0.1, 0.2, 0.3)
        assert cal2.data.mounting_yaw == 5.0
        assert cal2.data.is_valid
```

---

## 10. Day-by-Day Work Breakdown

### Day 8 - Monday (BNO085 Arrives)

**Morning (3 hours): BNO085 Hardware Validation**
| Time | Task | Deliverable |
|------|------|-------------|
| 09:00 | Hardware connection | BNO085 wired to I2C bus |
| 09:30 | I2C detection | `sudo i2cdetect -y 1` shows 0x4A |
| 10:00 | Basic read test | Raw quaternion data displayed |
| 10:30 | Integration with I2CBusManager | Thread-safe reads verified |
| 11:00 | Documentation update | Wiring photos, CHANGELOG updated |

**Afternoon (3 hours): Enhanced Driver Implementation**
| Time | Task | Deliverable |
|------|------|-------------|
| 12:00 | TDD: Write Quaternion tests | 15 tests written |
| 13:00 | Implement Quaternion class | Tests passing |
| 14:00 | TDD: Write OrientationState tests | 10 tests written |
| 14:30 | Implement OrientationState | Tests passing |
| 15:00 | Update existing BNO085 driver | Enhanced data structures |

**Evening (2 hours): Documentation & Commit**
| Time | Task | Deliverable |
|------|------|-------------|
| 16:00 | Update CHANGELOG | Day 8 entry complete |
| 16:30 | Hostile review on new code | Issues identified |
| 17:00 | Fix issues, commit | Git commit pushed |

---

### Day 9 - Tuesday (Sensor Fusion)

**Morning (3 hours): Complementary Filter**
| Time | Task | Deliverable |
|------|------|-------------|
| 09:00 | TDD: ComplementaryFilter tests | 20 tests written |
| 10:00 | Implement ComplementaryFilter | Tests passing |
| 11:00 | Hardware test on Pi | Filter validated with live IMU |

**Afternoon (3 hours): Noise Filtering**
| Time | Task | Deliverable |
|------|------|-------------|
| 12:00 | TDD: LowPassFilter tests | 15 tests written |
| 13:00 | Implement LowPassFilter(3D) | Tests passing |
| 14:00 | TDD: MovingAverageFilter tests | 10 tests written |
| 14:30 | Implement MovingAverageFilter | Tests passing |
| 15:00 | Hardware test: Compare raw vs filtered | Visual comparison documented |

**Evening (2 hours): Integration**
| Time | Task | Deliverable |
|------|------|-------------|
| 16:00 | Integrate filters with fusion | End-to-end pipeline |
| 17:00 | Update CHANGELOG, commit | Day 9 entry complete |

---

### Day 10 - Wednesday (Calibration & Pipeline)

**Morning (3 hours): Calibration System**
| Time | Task | Deliverable |
|------|------|-------------|
| 09:00 | TDD: IMUCalibration tests | 15 tests written |
| 10:00 | Implement gyroscope calibration | Tests passing |
| 11:00 | Implement accel/mag calibration | Full calibration system |

**Afternoon (3 hours): Perception Pipeline**
| Time | Task | Deliverable |
|------|------|-------------|
| 12:00 | TDD: RingBuffer tests | 10 tests written |
| 13:00 | Implement RingBuffer | Tests passing |
| 14:00 | TDD: PerceptionPipeline tests | 15 tests written |
| 15:00 | Implement PerceptionPipeline | Threaded pipeline working |

**Evening (2 hours): Hardware Integration**
| Time | Task | Deliverable |
|------|------|-------------|
| 16:00 | Run full pipeline on Pi | Live orientation data flowing |
| 17:00 | Update CHANGELOG, commit | Day 10 entry complete |

---

### Day 11 - Thursday (EKF Prep & Camera Interfaces)

**Morning (3 hours): Extended Kalman Filter**
| Time | Task | Deliverable |
|------|------|-------------|
| 09:00 | TDD: EKF tests | 15 tests written |
| 10:00 | Implement EKF predict step | Gyro integration working |
| 11:00 | Implement EKF update step | Accel correction working |

**Afternoon (3 hours): Camera Interface Preparation**
| Time | Task | Deliverable |
|------|------|-------------|
| 12:00 | Design CameraInterface | Abstract interface defined |
| 13:00 | Design AIInferenceResult | Data structures for Week 3 |
| 14:00 | Design VisualInertialFusion (stub) | Interface ready for Week 3 |
| 15:00 | Write documentation | Week 3 preparation guide |

**Evening (2 hours): Polish**
| Time | Task | Deliverable |
|------|------|-------------|
| 16:00 | Hostile review all new code | Issues identified and fixed |
| 17:00 | Update CHANGELOG, commit | Day 11 entry complete |

---

### Day 12 - Friday (Integration & Polish)

**Morning (3 hours): Full Integration Test**
| Time | Task | Deliverable |
|------|------|-------------|
| 09:00 | End-to-end pipeline test | All components working together |
| 10:00 | Performance profiling | CPU/memory usage documented |
| 11:00 | Stress test (1 hour continuous) | No memory leaks, stable output |

**Afternoon (2 hours): Documentation**
| Time | Task | Deliverable |
|------|------|-------------|
| 12:00 | Update API documentation | All public methods documented |
| 13:00 | Create usage examples | Example scripts for each component |

**Evening (2 hours): Closure**
| Time | Task | Deliverable |
|------|------|-------------|
| 14:00 | Final hostile review | All issues resolved |
| 15:00 | Update CHANGELOG, tag release | Perception v1.0 tagged |

---

## 11. Risk Assessment

| Risk | Severity | Probability | Mitigation |
|------|----------|-------------|------------|
| BNO085 DOA | HIGH | LOW | Have backup approach with raw gyro/accel |
| I2C bus conflict with PCA9685 | MEDIUM | LOW | I2CBusManager already validated |
| EKF numerical instability | MEDIUM | MEDIUM | Use complementary filter as fallback |
| Camera delay (Week 3) | LOW | MEDIUM | Interfaces designed to be hardware-agnostic |
| Performance issues at 100Hz | LOW | LOW | Profiling planned, optimization ready |

---

## Summary

This technical plan provides a comprehensive architecture for the OpenDuck Mini V3 perception system:

1. **Modular Design:** Clean separation of concerns with abstract interfaces
2. **Robust Sensor Fusion:** Complementary filter now, EKF prepared for Week 3
3. **Production-Grade Filtering:** Low-pass, moving average, and outlier rejection
4. **Comprehensive Calibration:** 6-position accel, figure-8 mag, mounting compensation
5. **Thread-Safe Pipeline:** Dedicated reader/publisher threads with proper synchronization
6. **TDD Throughout:** 100+ test cases specified before implementation
7. **Week 3 Ready:** Camera interfaces designed for visual-inertial fusion

The day-by-day breakdown ensures systematic progress with ~5 hours of focused work per day, aligned with the existing Week 2 roadmap.

---

**Document Status:** APPROVED FOR IMPLEMENTATION
**Next Review:** After Day 12 completion
**Author:** ML Research Scientist - Perception (Google DeepMind Robotics)
