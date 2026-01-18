"""Robot Orchestrator for OpenDuck Mini V3.

This module provides the main Robot class that ties together all subsystems:
- Servo control via PCA9685Driver
- Safety coordination via SafetyCoordinator
- Arm kinematics via ArmKinematics
- Optional IMU via BNO085Driver

Design Philosophy:
    - Impossible to misuse: state machine enforces valid operations
    - Fails safely: all errors trigger E-stop
    - Self-documenting: comprehensive logging and diagnostics
    - Testable: mock-friendly design with dependency injection

Thread Model:
    - Main control loop is single-threaded for determinism
    - Safety systems run in daemon threads (watchdog, GPIO monitor)
    - IMU failure is non-fatal (logged, continues)
    - Servo failure IS fatal (triggers E-stop)

Example:
    >>> from src.core.robot import Robot
    >>> with Robot() as robot:
    ...     robot.start()
    ...     robot.run_control_loop(
    ...         iteration_callback=lambda r: r.set_servo_angle(0, 90),
    ...         max_iterations=100
    ...     )
"""

import logging
import math
import time
import threading
from typing import Any, Callable, Dict, Optional

from .robot_state import (
    RobotState,
    validate_transition,
    RobotError,
    RobotStateError,
    SafetyViolationError,
    HardwareError,
)
from .safety_coordinator import SafetyCoordinator
from kinematics.arm_kinematics import ArmKinematics

_logger = logging.getLogger(__name__)


class Robot:
    """Main robot orchestrator class.

    Coordinates all robot subsystems and provides a unified interface
    for controlling the OpenDuck Mini V3 quadruped.

    Thread Safety:
        The Robot class is designed for single-threaded control loop
        operation. State machine transitions are protected by a lock.
        Safety systems run in background daemon threads.

    State Machine:
        INIT -> READY: start() called
        READY -> E_STOPPED: emergency_stop() or safety trigger
        E_STOPPED -> READY: reset() when conditions are safe

    Attributes:
        state: Current robot state (RobotState enum)
        is_operational: True if robot can accept commands
    """

    # Class constants
    DEFAULT_CONTROL_LOOP_HZ: int = 50
    DEFAULT_WATCHDOG_TIMEOUT_MS: int = 500
    DEFAULT_ARM_L1_MM: float = 80.0
    DEFAULT_ARM_L2_MM: float = 60.0

    def __init__(
        self,
        servo_driver: Optional[Any] = None,
        imu: Optional[Any] = None,
        gpio_provider: Optional[Any] = None,
        control_loop_hz: int = DEFAULT_CONTROL_LOOP_HZ,
        watchdog_timeout_ms: int = DEFAULT_WATCHDOG_TIMEOUT_MS,
        arm_l1_mm: float = DEFAULT_ARM_L1_MM,
        arm_l2_mm: float = DEFAULT_ARM_L2_MM,
        enable_hardware: bool = True,
    ) -> None:
        """Initialize robot orchestrator.

        Args:
            servo_driver: PCA9685Driver instance. If None and enable_hardware
                is True, creates default driver.
            imu: Optional BNO085Driver instance for orientation sensing.
            gpio_provider: GPIO provider for E-stop button. None uses default.
            control_loop_hz: Target control loop frequency (default: 50Hz).
            watchdog_timeout_ms: Watchdog timeout in milliseconds.
            arm_l1_mm: First arm link length in millimeters.
            arm_l2_mm: Second arm link length in millimeters.
            enable_hardware: If False, skips hardware initialization (testing).

        Raises:
            ValueError: If control_loop_hz or watchdog_timeout_ms is not positive.
        """
        if control_loop_hz <= 0:
            raise ValueError(
                f"control_loop_hz must be positive, got {control_loop_hz}"
            )
        if watchdog_timeout_ms <= 0:
            raise ValueError(
                f"watchdog_timeout_ms must be positive, got {watchdog_timeout_ms}"
            )

        # Configuration
        self._control_loop_hz = control_loop_hz
        self._control_loop_period_s = 1.0 / control_loop_hz
        self._enable_hardware = enable_hardware

        # Thread safety for state machine (RLock for reentrant access)
        self._state_lock = threading.RLock()
        self._state = RobotState.INIT

        # Create or store servo driver
        self._servo_driver: Optional[Any] = None
        if enable_hardware and servo_driver is None:
            try:
                from drivers.servo.pca9685 import PCA9685Driver
                self._servo_driver = PCA9685Driver()
            except Exception as e:
                _logger.warning("Failed to create default servo driver: %s", e)
        else:
            self._servo_driver = servo_driver

        # Store IMU (optional)
        self._imu = imu
        self._last_imu_data: Optional[Any] = None

        # Create safety coordinator
        self._safety: Optional[SafetyCoordinator] = None
        if self._servo_driver is not None:
            self._safety = SafetyCoordinator(
                servo_driver=self._servo_driver,
                gpio_provider=gpio_provider,
                watchdog_timeout_ms=watchdog_timeout_ms,
            )

        # Create arm kinematics
        self._arm = ArmKinematics(l1=arm_l1_mm, l2=arm_l2_mm)

        # Control loop state
        self._iteration_count: int = 0
        self._last_step_time: float = 0.0

        _logger.debug(
            "Robot initialized: hz=%d, watchdog=%dms, arm=%.1fx%.1fmm",
            control_loop_hz,
            watchdog_timeout_ms,
            arm_l1_mm,
            arm_l2_mm,
        )

    # =========================================================================
    # Properties
    # =========================================================================

    @property
    def state(self) -> RobotState:
        """Get current robot state."""
        with self._state_lock:
            return self._state

    @property
    def is_operational(self) -> bool:
        """Check if robot can accept commands.

        Returns:
            True if in READY state and safety systems are OK.
        """
        with self._state_lock:
            if self._state != RobotState.READY:
                return False
            if self._safety is None:
                return False
            return self._safety.is_safe

    @property
    def servo_driver(self) -> Optional[Any]:
        """Get servo driver instance."""
        return self._servo_driver

    @property
    def imu(self) -> Optional[Any]:
        """Get IMU instance."""
        return self._imu

    @property
    def arm(self) -> ArmKinematics:
        """Get arm kinematics solver."""
        return self._arm

    # =========================================================================
    # Lifecycle Methods
    # =========================================================================

    def start(self) -> bool:
        """Start robot and all subsystems.

        Transitions from INIT to READY state. Starts safety monitoring
        and prepares servos for commands.

        Returns:
            True if started successfully, False on failure.

        Raises:
            RobotStateError: If not in INIT state.
        """
        with self._state_lock:
            if self._state != RobotState.INIT:
                raise RobotStateError(
                    f"Cannot start from state {self._state.name}",
                    from_state=self._state,
                    to_state=RobotState.READY,
                )

            # Validate transition
            if not validate_transition(self._state, RobotState.READY):
                raise RobotStateError(
                    "Invalid transition INIT -> READY",
                    from_state=self._state,
                    to_state=RobotState.READY,
                )

            # Check prerequisites
            if self._servo_driver is None:
                _logger.error("Cannot start: no servo driver")
                return False

            if self._safety is None:
                _logger.error("Cannot start: no safety coordinator")
                return False

            safety_started = False
            try:
                # Start safety systems
                if not self._safety.start():
                    _logger.error("Failed to start safety systems")
                    return False
                safety_started = True

                # Transition state
                self._state = RobotState.READY
                self._iteration_count = 0
                _logger.info("Robot started successfully")
                return True

            except Exception as e:
                _logger.error("Robot start failed: %s", e)
                # CRITICAL: Clean up if safety was started but exception occurred
                if safety_started:
                    try:
                        self._safety.stop()
                    except Exception:
                        pass  # Best effort cleanup
                return False

    def stop(self) -> None:
        """Stop robot and all subsystems.

        Triggers E-stop and cleans up resources. Safe to call
        from any state.
        """
        with self._state_lock:
            _logger.info("Robot stopping...")

            # Stop safety systems (handles shutdown order)
            if self._safety is not None:
                self._safety.stop()

            # Don't change state - leave it as E_STOPPED or current
            if self._state == RobotState.READY:
                self._state = RobotState.E_STOPPED

            _logger.info("Robot stopped")

    def emergency_stop(self, source: str = "manual") -> float:
        """Trigger emergency stop.

        Immediately disables all servos and transitions to E_STOPPED state.

        Args:
            source: Human-readable source identifier for logging.

        Returns:
            Latency in milliseconds for servo disable, -1.0 on error.
        """
        with self._state_lock:
            _logger.warning("Emergency stop triggered: %s", source)

            latency = -1.0
            if self._safety is not None:
                latency = self._safety.trigger_estop(source)

            # Transition to E_STOPPED (from INIT or READY)
            if self._state in (RobotState.INIT, RobotState.READY):
                self._state = RobotState.E_STOPPED

            return latency

    def reset(self) -> bool:
        """Reset from E_STOPPED state.

        Attempts to reset safety systems and return to READY state.
        Only succeeds if all safety conditions are clear.

        Returns:
            True if reset successful, False otherwise.

        Raises:
            RobotStateError: If not in E_STOPPED state.
        """
        with self._state_lock:
            if self._state != RobotState.E_STOPPED:
                raise RobotStateError(
                    f"Cannot reset from state {self._state.name}",
                    from_state=self._state,
                )

            if self._safety is None:
                _logger.error("Cannot reset: no safety coordinator")
                return False

            # Attempt safety reset
            if not self._safety.reset_estop():
                _logger.warning("Safety reset failed")
                return False

            # Transition to READY
            self._state = RobotState.READY
            self._iteration_count = 0
            _logger.info("Robot reset successful")
            return True

    # =========================================================================
    # Control Loop Methods
    # =========================================================================

    def run_control_loop(
        self,
        iteration_callback: Optional[Callable[["Robot"], None]] = None,
        max_iterations: Optional[int] = None,
    ) -> None:
        """Run main control loop.

        Executes the control loop at the configured frequency (default 50Hz).
        Each iteration:
        1. Check state is READY
        2. Feed watchdog (with safety checks)
        3. Read IMU (if available, non-fatal on failure)
        4. Call iteration callback (if provided)
        5. Sleep to maintain target frequency

        Args:
            iteration_callback: Optional function called each iteration.
                Receives this Robot instance as argument.
            max_iterations: Optional maximum number of iterations.
                If None, runs until E-stop or error.

        Raises:
            RobotStateError: If not in READY state when called.
        """
        if self.state != RobotState.READY:
            raise RobotStateError(
                f"Cannot run control loop from state {self.state.name}",
                from_state=self.state,
            )

        _logger.info(
            "Starting control loop: %dHz, max_iterations=%s",
            self._control_loop_hz,
            max_iterations,
        )

        iterations = 0
        while True:
            # Check iteration limit
            if max_iterations is not None and iterations >= max_iterations:
                _logger.info("Control loop: max iterations reached (%d)", iterations)
                break

            # Execute one step
            if not self.step():
                _logger.info("Control loop: step returned False, exiting")
                break

            # Call callback
            if iteration_callback is not None:
                try:
                    iteration_callback(self)
                except Exception as e:
                    _logger.error("Control loop callback error: %s", e)
                    self.emergency_stop(source=f"callback_error:{type(e).__name__}")
                    break

            iterations += 1
            self._iteration_count = iterations

    def step(self) -> bool:
        """Execute single control loop iteration.

        Useful for manual control or testing. Performs all safety
        checks and timing management.

        Returns:
            True if step succeeded, False if loop should exit.
        """
        try:
            step_start = time.perf_counter()

            # Check state
            if self.state != RobotState.READY:
                return False

            # Feed watchdog (includes safety checks)
            if self._safety is not None:
                if not self._safety.feed_watchdog():
                    _logger.warning("step: watchdog feed failed - transitioning to E_STOPPED")
                    with self._state_lock:
                        if self._state == RobotState.READY:
                            self._state = RobotState.E_STOPPED
                    return False

            # Read IMU (non-fatal)
            if self._imu is not None:
                try:
                    self._last_imu_data = self._imu.read_orientation()
                except Exception as e:
                    _logger.warning("IMU read failed (continuing): %s", e)
                    # Don't trigger E-stop for IMU failure

            # Calculate sleep time to maintain frequency
            elapsed = time.perf_counter() - step_start
            sleep_time = self._control_loop_period_s - elapsed

            if sleep_time > 0:
                time.sleep(sleep_time)
            elif elapsed > self._control_loop_period_s * 1.5:
                # Log warning if significantly over period
                _logger.warning(
                    "Control loop iteration took %.1fms (target: %.1fms)",
                    elapsed * 1000,
                    self._control_loop_period_s * 1000,
                )

            self._last_step_time = time.perf_counter() - step_start
            return True

        except Exception as e:
            _logger.error("step error: %s", e)
            self.emergency_stop(source=f"step_error:{type(e).__name__}")
            return False

    # =========================================================================
    # Servo Command Methods
    # =========================================================================

    def set_servo_angle(self, channel: int, angle: float) -> bool:
        """Set servo to specific angle.

        Args:
            channel: Servo channel number (0-15).
            angle: Target angle in degrees (0-180).

        Returns:
            True if command succeeded, False if blocked by safety.

        Raises:
            RobotStateError: If not in READY state.
            SafetyViolationError: If movement blocked by safety system.
            HardwareError: If servo communication fails.
        """
        # Check state
        if self.state != RobotState.READY:
            raise RobotStateError(
                f"Cannot set servo in state {self.state.name}",
                from_state=self.state,
            )

        # Check safety
        if self._safety is not None:
            allowed, reason = self._safety.check_movement_allowed(channel)
            if not allowed:
                raise SafetyViolationError(
                    f"Movement blocked on channel {channel}",
                    reason=reason,
                    context={"channel": channel, "angle": angle},
                )

        # Execute command
        try:
            if self._safety is not None:
                self._safety.register_movement(channel, angle)

            if self._servo_driver is not None:
                self._servo_driver.set_servo_angle(channel, angle)

            if self._safety is not None:
                self._safety.complete_movement(channel)

            return True

        except Exception as e:
            _logger.error("Servo command failed: %s", e)
            # SAFETY CRITICAL: Servo failure IS fatal - trigger E-stop
            self.emergency_stop(source=f"servo_failure:ch{channel}")
            raise HardwareError(
                f"Failed to set servo angle on channel {channel}",
                device="PCA9685",
                context={"channel": channel, "angle": angle, "error": str(e)},
            ) from e

    def set_arm_position(
        self,
        x: float,
        y: float,
        elbow_up: bool = True,
        shoulder_channel: int = 0,
        elbow_channel: int = 1,
    ) -> bool:
        """Set arm end-effector position using inverse kinematics.

        Args:
            x: Target X position in millimeters.
            y: Target Y position in millimeters.
            elbow_up: If True, prefer elbow-up configuration.
            shoulder_channel: Servo channel for shoulder joint.
            elbow_channel: Servo channel for elbow joint.

        Returns:
            True if position was reachable and set, False if unreachable.

        Raises:
            RobotStateError: If not in READY state.
            SafetyViolationError: If movement blocked by safety system.
            HardwareError: If servo communication fails.
        """
        # Solve IK
        result = self._arm.solve_ik(x, y, elbow_up=elbow_up)
        if result is None:
            _logger.warning(
                "IK solution not found for position (%.1f, %.1f)",
                x, y,
            )
            return False

        shoulder_rad, elbow_rad = result

        # Convert to degrees
        shoulder_deg = math.degrees(shoulder_rad)
        elbow_deg = math.degrees(elbow_rad)

        # Clamp to servo range (0-180)
        shoulder_deg = max(0.0, min(180.0, shoulder_deg))
        elbow_deg = max(0.0, min(180.0, elbow_deg))

        # Set both servos
        self.set_servo_angle(shoulder_channel, shoulder_deg)
        self.set_servo_angle(elbow_channel, elbow_deg)

        return True

    # =========================================================================
    # Diagnostics
    # =========================================================================

    def get_diagnostics(self) -> Dict[str, Any]:
        """Get comprehensive diagnostic information.

        Returns:
            Dictionary with all robot state and subsystem diagnostics.
        """
        with self._state_lock:
            diag: Dict[str, Any] = {
                "state": self._state.name,
                "is_operational": self.is_operational,
                "iteration_count": self._iteration_count,
                "last_step_time_ms": self._last_step_time * 1000,
                "control_loop_hz": self._control_loop_hz,
                "arm": {
                    "l1_mm": self._arm.l1,
                    "l2_mm": self._arm.l2,
                    "max_reach_mm": self._arm.max_reach,
                },
            }

            # Safety diagnostics
            if self._safety is not None:
                diag["safety"] = self._safety.get_diagnostics()

            # IMU data
            if self._last_imu_data is not None:
                diag["imu"] = {"last_reading": str(self._last_imu_data)}

            return diag

    # =========================================================================
    # Context Manager
    # =========================================================================

    def __enter__(self) -> "Robot":
        """Context manager entry.

        Note: Does NOT auto-start. Call start() explicitly after entering.
        This allows configuration between __enter__ and start().

        Returns:
            Self for use in with statement.
        """
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - stops robot."""
        self.stop()

    def __repr__(self) -> str:
        with self._state_lock:
            return (
                f"Robot(state={self._state.name}, "
                f"operational={self.is_operational}, "
                f"iterations={self._iteration_count})"
            )
