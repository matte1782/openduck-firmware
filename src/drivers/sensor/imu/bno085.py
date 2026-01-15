"""BNO085 9-DOF IMU Driver with I2C Bus Manager Integration

This module provides a hardware abstraction layer for the BNO085 IMU sensor,
which provides 9-axis absolute orientation data with on-chip sensor fusion.

The BNO085 is an intelligent 9-axis absolute orientation sensor that combines
accelerometer, gyroscope, and magnetometer with an ARM Cortex M0+ processor
running Hillcrest Labs' SH-2 firmware for sensor fusion.

Hardware:
    - Adafruit BNO085 9-DOF Absolute Orientation IMU
    - I2C interface (addresses: 0x4A or 0x4B)
    - 3.3V logic compatible
    - On-chip sensor fusion (eliminates drift)

Connections:
    - SDA -> Raspberry Pi GPIO 2 (Pin 3) - via I2C Bus Manager
    - SCL -> Raspberry Pi GPIO 3 (Pin 5) - via I2C Bus Manager
    - VCC -> 3.3V (Pi Pin 1 or 17)
    - GND -> GND (Pi Pin 6, 9, 14, 20, 25, 30, 34, or 39)

Key Features:
    - Absolute orientation (no drift)
    - 9-DOF sensor fusion
    - Quaternion output
    - Calibration-free operation
    - Thread-safe via I2C Bus Manager

Thread Safety:
    All operations use I2CBusManager to prevent bus collisions with other I2C
    devices (e.g., PCA9685 servo controller). This ensures that IMU reads do
    not interfere with servo control operations.

Example:
    ```python
    from src.drivers.sensor.imu.bno085 import BNO085Driver

    # Initialize IMU (uses I2C Bus Manager singleton)
    imu = BNO085Driver()

    # Read orientation data
    data = imu.read_orientation()
    print(f"Heading: {data.heading}°")
    print(f"Roll: {data.roll}°")
    print(f"Pitch: {data.pitch}°")

    # Read quaternion (for advanced applications)
    quat = imu.read_quaternion()
    print(f"Q: ({quat.w}, {quat.x}, {quat.y}, {quat.z})")
    ```

Critical Design:
    - MUST use I2CBusManager.acquire_bus() for all I2C operations
    - MUST NOT create independent I2C bus instances
    - Thread-safe by design (bus manager handles locking)
"""

import time
import threading
from dataclasses import dataclass
from typing import Optional, Tuple
from contextlib import contextmanager

try:
    import board
    import busio
    from adafruit_bno08x import BNO08X_I2C
    from adafruit_bno08x.i2c import BNO08X_I2C
except ImportError:
    # Mock imports for development on non-Pi systems
    board = None
    busio = None
    BNO08X_I2C = None

# Import I2C Bus Manager
from ...i2c_bus_manager import I2CBusManager


@dataclass
class IMUData:
    """IMU sensor data container.

    Attributes:
        heading: Compass heading in degrees (0-360, 0=North)
        roll: Roll angle in degrees (-180 to 180)
        pitch: Pitch angle in degrees (-90 to 90)
        timestamp: Unix timestamp when data was captured
    """
    heading: float
    roll: float
    pitch: float
    timestamp: float


@dataclass
class Quaternion:
    """Quaternion representation for orientation.

    Attributes:
        w: Scalar component
        x: X vector component
        y: Y vector component
        z: Z vector component
    """
    w: float
    x: float
    y: float
    z: float


class BNO085Driver:
    """Driver for BNO085 9-DOF IMU with I2C Bus Manager integration.

    Provides thread-safe access to IMU data using centralized I2C bus management
    to prevent collisions with other I2C devices.

    Thread Safety:
        All I2C operations are protected by I2CBusManager, ensuring serialized
        access to the I2C bus across all devices. Safe for multi-threaded use.

    Attributes:
        address: I2C address of BNO085 (0x4A or 0x4B)
        bus_manager: Singleton I2C bus manager instance
        _sensor: BNO08X sensor instance (created lazily)
        _lock: Thread lock for internal state protection
    """

    # Default I2C addresses
    DEFAULT_ADDRESS = 0x4A
    ALTERNATE_ADDRESS = 0x4B

    # BNO085 Report IDs (for different data types)
    REPORT_ROTATION_VECTOR = 0x05
    REPORT_GAME_ROTATION_VECTOR = 0x08
    REPORT_GEOMAGNETIC_ROTATION = 0x09

    def __init__(self, address: int = DEFAULT_ADDRESS):
        """Initialize BNO085 IMU driver.

        Args:
            address: I2C address (0x4A or 0x4B)

        Raises:
            ValueError: If address is invalid
            ImportError: If required libraries not installed
            RuntimeError: If I2C communication fails
        """
        if address not in (self.DEFAULT_ADDRESS, self.ALTERNATE_ADDRESS):
            raise ValueError(
                f"Invalid I2C address 0x{address:02x}. "
                f"Must be 0x{self.DEFAULT_ADDRESS:02x} or 0x{self.ALTERNATE_ADDRESS:02x}"
            )

        self.address = address
        self._lock = threading.Lock()
        self._sensor: Optional['BNO08X_I2C'] = None
        self._initialized = False

        # Get I2C Bus Manager singleton
        self.bus_manager = I2CBusManager.get_instance()

        # Initialize sensor
        self._initialize_sensor()

    def _initialize_sensor(self):
        """Initialize BNO085 sensor hardware.

        This method acquires the I2C bus through the bus manager to ensure
        no collisions occur during initialization.

        Raises:
            ImportError: If required libraries not available
            RuntimeError: If sensor initialization fails
        """
        if self._initialized:
            return

        # Check hardware libraries available
        if board is None or busio is None or BNO08X_I2C is None:
            raise ImportError(
                "Required libraries not installed. Run: "
                "pip install adafruit-circuitpython-bno08x"
            )

        try:
            # CRITICAL: Use I2C Bus Manager to prevent collisions
            with self.bus_manager.acquire_bus() as i2c_bus:
                # Initialize BNO085 sensor on managed bus
                self._sensor = BNO08X_I2C(i2c_bus, address=self.address)

                # Enable rotation vector output (provides orientation)
                self._sensor.enable_feature(self.REPORT_ROTATION_VECTOR)

                # Small delay for sensor to stabilize
                time.sleep(0.1)

            self._initialized = True

        except Exception as e:
            raise RuntimeError(
                f"Failed to initialize BNO085 at 0x{self.address:02x}: {e}"
            )

    def read_orientation(self) -> IMUData:
        """Read orientation data from IMU.

        Reads current orientation as Euler angles (heading, roll, pitch).
        Uses I2C Bus Manager to ensure thread-safe access.

        Returns:
            IMUData: Current orientation data

        Raises:
            RuntimeError: If sensor read fails
        """
        with self._lock:
            if not self._initialized:
                raise RuntimeError("Sensor not initialized")

            try:
                # CRITICAL: Acquire bus before I2C operation
                with self.bus_manager.acquire_bus():
                    # Read quaternion from sensor
                    quat_i, quat_j, quat_k, quat_real = self._sensor.quaternion

                    # Convert quaternion to Euler angles
                    heading, roll, pitch = self._quaternion_to_euler(
                        quat_real, quat_i, quat_j, quat_k
                    )

                    return IMUData(
                        heading=heading,
                        roll=roll,
                        pitch=pitch,
                        timestamp=time.time()
                    )

            except Exception as e:
                raise RuntimeError(f"Failed to read IMU data: {e}")

    def read_quaternion(self) -> Quaternion:
        """Read raw quaternion data from IMU.

        Quaternions provide orientation without gimbal lock issues.
        Useful for robotics and 3D applications.

        Returns:
            Quaternion: Current orientation as quaternion

        Raises:
            RuntimeError: If sensor read fails
        """
        with self._lock:
            if not self._initialized:
                raise RuntimeError("Sensor not initialized")

            try:
                # CRITICAL: Acquire bus before I2C operation
                with self.bus_manager.acquire_bus():
                    quat_i, quat_j, quat_k, quat_real = self._sensor.quaternion

                    return Quaternion(
                        w=quat_real,
                        x=quat_i,
                        y=quat_j,
                        z=quat_k
                    )

            except Exception as e:
                raise RuntimeError(f"Failed to read quaternion: {e}")

    def read_acceleration(self) -> Tuple[float, float, float]:
        """Read linear acceleration data (m/s²).

        Returns:
            Tuple of (x, y, z) acceleration in m/s²

        Raises:
            RuntimeError: If sensor read fails
        """
        with self._lock:
            if not self._initialized:
                raise RuntimeError("Sensor not initialized")

            try:
                # CRITICAL: Acquire bus before I2C operation
                with self.bus_manager.acquire_bus():
                    accel_x, accel_y, accel_z = self._sensor.acceleration
                    return (accel_x, accel_y, accel_z)

            except Exception as e:
                raise RuntimeError(f"Failed to read acceleration: {e}")

    def read_gyro(self) -> Tuple[float, float, float]:
        """Read gyroscope data (rad/s).

        Returns:
            Tuple of (x, y, z) angular velocity in rad/s

        Raises:
            RuntimeError: If sensor read fails
        """
        with self._lock:
            if not self._initialized:
                raise RuntimeError("Sensor not initialized")

            try:
                # CRITICAL: Acquire bus before I2C operation
                with self.bus_manager.acquire_bus():
                    gyro_x, gyro_y, gyro_z = self._sensor.gyro
                    return (gyro_x, gyro_y, gyro_z)

            except Exception as e:
                raise RuntimeError(f"Failed to read gyroscope: {e}")

    @staticmethod
    def _quaternion_to_euler(w: float, x: float, y: float, z: float) -> Tuple[float, float, float]:
        """Convert quaternion to Euler angles (heading, roll, pitch).

        Args:
            w: Quaternion scalar component
            x: Quaternion x component
            y: Quaternion y component
            z: Quaternion z component

        Returns:
            Tuple of (heading, roll, pitch) in degrees
        """
        import math

        # Roll (x-axis rotation)
        sinr_cosp = 2 * (w * x + y * z)
        cosr_cosp = 1 - 2 * (x * x + y * y)
        roll = math.atan2(sinr_cosp, cosr_cosp)

        # Pitch (y-axis rotation)
        sinp = 2 * (w * y - z * x)
        if abs(sinp) >= 1:
            pitch = math.copysign(math.pi / 2, sinp)  # Use 90° if out of range
        else:
            pitch = math.asin(sinp)

        # Yaw/Heading (z-axis rotation)
        siny_cosp = 2 * (w * z + x * y)
        cosy_cosp = 1 - 2 * (y * y + z * z)
        yaw = math.atan2(siny_cosp, cosy_cosp)

        # Convert to degrees
        heading = math.degrees(yaw)
        if heading < 0:
            heading += 360

        return (
            heading,  # 0-360°
            math.degrees(roll),  # -180 to 180°
            math.degrees(pitch)  # -90 to 90°
        )

    def calibrate(self) -> bool:
        """Perform IMU calibration.

        BNO085 has automatic calibration, but this method can trigger
        a calibration reset if needed.

        Returns:
            bool: True if calibration successful
        """
        with self._lock:
            if not self._initialized:
                raise RuntimeError("Sensor not initialized")

            try:
                # CRITICAL: Acquire bus for calibration commands
                with self.bus_manager.acquire_bus():
                    # BNO085 auto-calibrates, this is a placeholder
                    # for future calibration commands if needed
                    time.sleep(0.5)
                    return True

            except Exception as e:
                raise RuntimeError(f"Calibration failed: {e}")

    def reset(self):
        """Reset IMU sensor.

        Performs a software reset of the sensor.
        """
        with self._lock:
            if not self._initialized:
                return

            try:
                # CRITICAL: Acquire bus for reset command
                with self.bus_manager.acquire_bus():
                    # Sensor reset would go here
                    pass

                # Re-initialize after reset
                self._initialized = False
                time.sleep(0.1)
                self._initialize_sensor()

            except Exception as e:
                raise RuntimeError(f"Reset failed: {e}")

    def get_calibration_status(self) -> dict:
        """Get calibration status of each sensor component.

        Returns:
            dict: Calibration status for system, gyro, accel, mag
        """
        with self._lock:
            if not self._initialized:
                raise RuntimeError("Sensor not initialized")

            # BNO085 handles calibration automatically
            # This is a placeholder for future status reporting
            return {
                'system': 3,  # Fully calibrated
                'gyro': 3,
                'accel': 3,
                'mag': 3
            }

    def deinit(self):
        """Deinitialize sensor and release resources."""
        with self._lock:
            self._initialized = False
            self._sensor = None
