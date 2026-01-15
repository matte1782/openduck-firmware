"""PCA9685 16-Channel PWM Driver for Servo Control

This module provides a hardware abstraction layer for the PCA9685 PWM controller,
commonly used for controlling multiple servos in robotics applications.

Hardware:
    - Adafruit PCA9685 16-Channel 12-bit PWM/Servo Driver
    - I2C interface (default address: 0x40)
    - 5V logic compatible

Connections:
    - SDA -> Raspberry Pi GPIO 2 (Pin 3)
    - SCL -> Raspberry Pi GPIO 3 (Pin 5)
    - VCC -> 5V (Pi Pin 2 or 4)
    - GND -> GND (Pi Pin 6)
"""

import time
from typing import Optional
try:
    import board
    import busio
    from adafruit_pca9685 import PCA9685
except ImportError:
    # Mock imports for development on non-Pi systems
    board = None
    busio = None
    PCA9685 = None


class PCA9685Driver:
    """Driver for PCA9685 16-channel PWM controller.

    Provides servo control with angle-to-PWM conversion, frequency management,
    and multi-servo coordination capabilities.

    Attributes:
        i2c: I2C bus instance
        pca: PCA9685 controller instance
        frequency: PWM frequency in Hz (default: 50Hz for servos)
        channels: Dictionary tracking channel states
    """

    # PWM pulse width constants (in microseconds)
    SERVO_MIN_PULSE = 1000  # Minimum pulse width (0 degrees)
    SERVO_MAX_PULSE = 2000  # Maximum pulse width (180 degrees)
    SERVO_FREQUENCY = 50    # Standard servo frequency (50Hz = 20ms period)

    def __init__(
        self,
        address: int = 0x40,
        frequency: int = 50,
        i2c_bus: Optional[int] = 1
    ):
        """Initialize PCA9685 driver.

        Args:
            address: I2C address of PCA9685 (default: 0x40)
            frequency: PWM frequency in Hz (default: 50Hz for servos)
            i2c_bus: I2C bus number (default: 1 for Raspberry Pi)

        Raises:
            RuntimeError: If I2C communication fails
            ImportError: If required libraries not installed
        """
        self.address = address
        self.frequency = frequency
        self.channels = {}  # Track channel states

        # Initialize I2C and PCA9685
        if board is None or busio is None or PCA9685 is None:
            raise ImportError(
                "Required libraries not installed. Run: "
                "pip install adafruit-circuitpython-pca9685"
            )

        try:
            self.i2c = busio.I2C(board.SCL, board.SDA)
            self.pca = PCA9685(self.i2c, address=address)
            self.pca.frequency = frequency

            # Initialize all channels to safe state (off)
            for channel in range(16):
                self.pca.channels[channel].duty_cycle = 0
                self.channels[channel] = {
                    'angle': None,
                    'enabled': False
                }

        except Exception as e:
            raise RuntimeError(f"Failed to initialize PCA9685 at 0x{address:02x}: {e}")

    def set_pwm(self, channel: int, on: int, off: int) -> None:
        """Set raw PWM values for a channel.

        Args:
            channel: Channel number (0-15)
            on: 12-bit value when signal goes HIGH (0-4095)
            off: 12-bit value when signal goes LOW (0-4095)

        Raises:
            ValueError: If channel out of range
        """
        if not 0 <= channel <= 15:
            raise ValueError(f"Channel must be 0-15, got {channel}")

        # Convert to duty cycle (0-65535)
        duty_cycle = int((off / 4095) * 65535)
        self.pca.channels[channel].duty_cycle = duty_cycle

    def set_servo_angle(self, channel: int, angle: float) -> None:
        """Set servo to specific angle.

        Converts angle (0-180 degrees) to appropriate PWM pulse width
        and sets the servo position.

        Args:
            channel: Servo channel (0-15)
            angle: Target angle in degrees (0-180)

        Raises:
            ValueError: If angle out of range or channel invalid
        """
        if not 0 <= channel <= 15:
            raise ValueError(f"Channel must be 0-15, got {channel}")
        if not 0 <= angle <= 180:
            raise ValueError(f"Angle must be 0-180°, got {angle}")

        # Convert angle to pulse width (microseconds)
        pulse_width = self._angle_to_pulse(angle)

        # Convert pulse width to PWM duty cycle
        pulse_length = 1_000_000 // self.frequency  # Period in microseconds
        duty_cycle = int((pulse_width / pulse_length) * 65535)

        # Set PWM
        self.pca.channels[channel].duty_cycle = duty_cycle

        # Update channel state
        self.channels[channel]['angle'] = angle
        self.channels[channel]['enabled'] = True

    def _angle_to_pulse(self, angle: float) -> int:
        """Convert angle to pulse width in microseconds.

        Args:
            angle: Angle in degrees (0-180)

        Returns:
            Pulse width in microseconds (1000-2000)
        """
        return int(
            self.SERVO_MIN_PULSE +
            (self.SERVO_MAX_PULSE - self.SERVO_MIN_PULSE) * (angle / 180)
        )

    def set_servo_pulse(self, channel: int, pulse_us: int) -> None:
        """Set servo using pulse width in microseconds.

        Useful for fine-tuning servo positions beyond standard 0-180° range.

        Args:
            channel: Servo channel (0-15)
            pulse_us: Pulse width in microseconds (typically 500-2500)
        """
        if not 0 <= channel <= 15:
            raise ValueError(f"Channel must be 0-15, got {channel}")

        pulse_length = 1_000_000 // self.frequency
        duty_cycle = int((pulse_us / pulse_length) * 65535)
        self.pca.channels[channel].duty_cycle = duty_cycle

    def disable_channel(self, channel: int) -> None:
        """Disable (power off) a servo channel.

        Args:
            channel: Channel to disable (0-15)
        """
        if not 0 <= channel <= 15:
            raise ValueError(f"Channel must be 0-15, got {channel}")

        self.pca.channels[channel].duty_cycle = 0
        self.channels[channel]['enabled'] = False

    def disable_all(self) -> None:
        """Disable all servo channels (emergency stop)."""
        for channel in range(16):
            self.disable_channel(channel)

    def get_channel_state(self, channel: int) -> dict:
        """Get current state of a channel.

        Args:
            channel: Channel number (0-15)

        Returns:
            Dict with 'angle' and 'enabled' keys
        """
        if not 0 <= channel <= 15:
            raise ValueError(f"Channel must be 0-15, got {channel}")

        return self.channels[channel].copy()

    def deinit(self) -> None:
        """Deinitialize driver and disable all channels."""
        self.disable_all()
        self.pca.deinit()


class ServoController:
    """High-level servo controller using PCA9685.

    Provides coordinated multi-servo control, movement profiles,
    and safety features.
    """

    def __init__(self, pca9685: PCA9685Driver):
        """Initialize servo controller.

        Args:
            pca9685: Configured PCA9685Driver instance
        """
        self.driver = pca9685
        self.servo_limits = {}  # Per-servo angle limits

    def set_servo_limits(self, channel: int, min_angle: float, max_angle: float) -> None:
        """Set software angle limits for a servo.

        Args:
            channel: Servo channel (0-15)
            min_angle: Minimum allowed angle
            max_angle: Maximum allowed angle
        """
        self.servo_limits[channel] = (min_angle, max_angle)

    def move_servo(self, channel: int, angle: float) -> None:
        """Move servo with limit checking.

        Args:
            channel: Servo channel (0-15)
            angle: Target angle in degrees

        Raises:
            ValueError: If angle exceeds configured limits
        """
        if channel in self.servo_limits:
            min_angle, max_angle = self.servo_limits[channel]
            if not min_angle <= angle <= max_angle:
                raise ValueError(
                    f"Angle {angle}° outside limits [{min_angle}°, {max_angle}°] "
                    f"for channel {channel}"
                )

        self.driver.set_servo_angle(channel, angle)

    def move_multiple(self, moves: dict, delay: float = 0.0) -> None:
        """Move multiple servos simultaneously.

        Args:
            moves: Dict of {channel: angle} pairs
            delay: Optional delay after movement (seconds)
        """
        for channel, angle in moves.items():
            self.move_servo(channel, angle)

        if delay > 0:
            time.sleep(delay)

    def sweep(self, channel: int, start: float, end: float, steps: int, delay: float) -> None:
        """Sweep servo through range.

        Args:
            channel: Servo channel
            start: Start angle
            end: End angle
            steps: Number of steps
            delay: Delay between steps (seconds)
        """
        for angle in range(int(start), int(end) + 1, (int(end) - int(start)) // steps):
            self.move_servo(channel, angle)
            time.sleep(delay)
