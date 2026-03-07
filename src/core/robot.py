"""Robot Orchestrator for OpenDuck Mini V3.

This module provides the main Robot class that ties together all subsystems:
- Head servo control via PCA9685Driver + HeadController
- Arm/leg bus servo control via STS3215Driver
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
    - HeadController runs animation threads (daemon, generation-guarded)
    - IMU failure is non-fatal (logged, continues)
    - Servo failure IS fatal (triggers E-stop)

Subsystem Routing:
    - PCA9685 (PWM, ch 0-15): Head servos only (via HeadController)
    - STS3215 (UART, servo IDs): Arm/leg bus servos

Example:
    >>> from src.core.robot import Robot
    >>> from unittest.mock import MagicMock
    >>> mock_driver = MagicMock()
    >>> with Robot(servo_driver=mock_driver) as robot:
    ...     robot.start()
    ...     robot.move_head(head_yaw=30)
"""

import logging
import math
import time
import threading
from typing import Any, Callable, Dict, List, Optional

from .robot_state import (
    RobotState,
    validate_transition,
    RobotError,
    RobotStateError,
    SafetyViolationError,
    HardwareError,
)
from .safety_coordinator import SafetyCoordinator
from src.kinematics.arm_kinematics import ArmKinematics

_logger = logging.getLogger(__name__)


class Robot:
    """Main robot orchestrator class.

    Coordinates all robot subsystems and provides a unified interface
    for controlling the OpenDuck Mini V3.

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
        bus_servo_driver: Optional[Any] = None,
        head_controller: Optional[Any] = None,
        imu: Optional[Any] = None,
        gpio_provider: Optional[Any] = None,
        control_loop_hz: int = DEFAULT_CONTROL_LOOP_HZ,
        watchdog_timeout_ms: int = DEFAULT_WATCHDOG_TIMEOUT_MS,
        arm_l1_mm: float = DEFAULT_ARM_L1_MM,
        arm_l2_mm: float = DEFAULT_ARM_L2_MM,
        enable_hardware: bool = True,
        bus_servo_ids: Optional[List[int]] = None,
    ) -> None:
        """Initialize robot orchestrator.

        Args:
            servo_driver: PCA9685Driver instance for head PWM servos.
                If None and enable_hardware is True, creates default driver.
            bus_servo_driver: STS3215Driver instance for arm/leg bus servos.
                Optional — arm commands will log warnings if not provided.
            head_controller: HeadController instance. If None and servo_driver
                is available, one can be created via create_head_controller().
            imu: Optional BNO085Driver instance for orientation sensing.
            gpio_provider: GPIO provider for E-stop button. None uses default.
            control_loop_hz: Target control loop frequency (default: 50Hz).
            watchdog_timeout_ms: Watchdog timeout in milliseconds.
            arm_l1_mm: First arm link length in millimeters.
            arm_l2_mm: Second arm link length in millimeters.
            enable_hardware: If False, skips hardware initialization (testing).
            bus_servo_ids: List of STS3215 servo IDs on the bus (for e-stop).

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

        # Create or store PCA9685 servo driver (head PWM servos)
        self._servo_driver: Optional[Any] = None
        if enable_hardware and servo_driver is None:
            try:
                from src.drivers.servo.pca9685 import PCA9685Driver
                self._servo_driver = PCA9685Driver()
            except Exception as e:
                _logger.warning("Failed to create default servo driver: %s", e)
        else:
            self._servo_driver = servo_driver

        # Store STS3215 bus servo driver (arm/leg servos)
        self._bus_servo_driver: Optional[Any] = None
        if bus_servo_driver is not None:
            self._bus_servo_driver = bus_servo_driver
        self._bus_servo_ids: List[int] = bus_servo_ids or []

        # Store HeadController (optional — created via create_head_controller)
        self._head_controller: Optional[Any] = head_controller

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
            "Robot initialized: hz=%d, watchdog=%dms, arm=%.1fx%.1fmm, "
            "head_controller=%s, bus_servos=%s",
            control_loop_hz,
            watchdog_timeout_ms,
            arm_l1_mm,
            arm_l2_mm,
            "yes" if self._head_controller else "no",
            self._bus_servo_ids or "none",
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
        """Get PCA9685 servo driver instance."""
        return self._servo_driver

    @property
    def bus_servo_driver(self) -> Optional[Any]:
        """Get STS3215 bus servo driver instance."""
        return self._bus_servo_driver

    @property
    def head_controller(self) -> Optional[Any]:
        """Get HeadController instance."""
        return self._head_controller

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

                # Register callback so GPIO/watchdog e-stops propagate
                # to bus servos and HeadController (C1 safety fix)
                self._safety.register_estop_callback(
                    self._on_external_estop,
                )

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

        Shutdown order matches emergency_stop(): bus servos (physical danger)
        first, PCA9685 second, HeadController last.
        Safe to call from any state.
        """
        with self._state_lock:
            _logger.info("Robot stopping...")

            # 1. Disable bus servos FIRST (physical danger — arms/legs)
            if self._bus_servo_driver is not None:
                try:
                    self._bus_servo_driver.torque_disable_all(self._bus_servo_ids)
                except Exception as e:
                    _logger.warning("Bus servo disable error: %s", e)

            # 2. Stop safety systems / PCA9685
            if self._safety is not None:
                self._safety.stop()

            # 3. Stop head controller animations LAST (least critical)
            if self._head_controller is not None:
                try:
                    self._head_controller.emergency_stop()
                except Exception as e:
                    _logger.warning("HeadController stop error: %s", e)

            # Don't change state - leave it as E_STOPPED or current
            if self._state == RobotState.READY:
                self._state = RobotState.E_STOPPED

            _logger.info("Robot stopped")

    def emergency_stop(self, source: str = "manual") -> float:
        """Trigger emergency stop.

        Immediately disables all servos (PWM + bus) and transitions
        to E_STOPPED state.

        Args:
            source: Human-readable source identifier for logging.

        Returns:
            Latency in milliseconds for servo disable, -1.0 on error.
        """
        with self._state_lock:
            _logger.warning("Emergency stop triggered: %s", source)

            latency = -1.0

            # Disable bus servos FIRST (broadcast for <1ms latency)
            # This is the most critical — must happen even if other steps fail
            if self._bus_servo_driver is not None:
                try:
                    self._bus_servo_driver.torque_disable_all(self._bus_servo_ids)
                except Exception as e:
                    _logger.error("Bus servo e-stop error: %s", e)

            # Disable PCA9685 PWM servos via safety coordinator
            if self._safety is not None:
                latency = self._safety.trigger_estop(source)

            # Stop head animations (least critical — can't cause physical harm)
            if self._head_controller is not None:
                try:
                    self._head_controller.emergency_stop()
                except Exception as e:
                    _logger.error("HeadController e-stop error: %s", e)

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

            # Reset head controller emergency state
            if self._head_controller is not None:
                try:
                    self._head_controller.reset_emergency()
                except Exception as e:
                    _logger.error("HeadController reset failed: %s — staying E_STOPPED", e)
                    return False

            # Transition to READY
            self._state = RobotState.READY
            self._iteration_count = 0
            _logger.info("Robot reset successful")
            return True

    def _on_external_estop(self, source: str) -> None:
        """Callback for GPIO/watchdog-triggered e-stops.

        Called by SafetyCoordinator when EmergencyStop transitions to E_STOP.
        Disables bus servos and HeadController that the EmergencyStop system
        doesn't know about (it only disables PCA9685).

        IMPORTANT: This may be called from within EmergencyStop._lock context
        (GPIO interrupt thread). To avoid AB-BA deadlock with
        Robot.emergency_stop() (which holds _state_lock then acquires
        EmergencyStop._lock), we must NOT acquire _state_lock here.
        Instead, we use a non-blocking atomic state write.
        """
        _logger.warning("External e-stop callback: %s", source)

        # Disable bus servos FIRST (critical — physical danger)
        if self._bus_servo_driver is not None:
            try:
                self._bus_servo_driver.torque_disable_all(self._bus_servo_ids)
            except Exception as e:
                _logger.error("Bus servo disable in external e-stop: %s", e)

        # Stop head animations
        if self._head_controller is not None:
            try:
                self._head_controller.emergency_stop()
            except Exception as e:
                _logger.error("HeadController stop in external e-stop: %s", e)

        # Transition state — lock-free write to avoid deadlock.
        # RobotState assignment is atomic in CPython (GIL) and the only
        # valid transitions here (INIT/READY -> E_STOPPED) are safe to
        # race with: worst case emergency_stop() also sets E_STOPPED.
        if self._state in (RobotState.INIT, RobotState.READY):
            self._state = RobotState.E_STOPPED

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
    # Head Commands (via HeadController)
    # =========================================================================

    def move_head(
        self,
        neck_pitch: Optional[float] = None,
        head_pitch: Optional[float] = None,
        head_yaw: Optional[float] = None,
        head_roll: Optional[float] = None,
        duration_ms: Optional[int] = None,
    ) -> bool:
        """Move head to target position via HeadController.

        Args:
            neck_pitch: Target neck pitch angle (degrees), or None to keep current.
            head_pitch: Target head pitch angle (degrees), or None to keep current.
            head_yaw: Target head yaw angle (degrees), or None to keep current.
            head_roll: Target head roll angle (degrees), or None to keep current.
            duration_ms: Movement duration in milliseconds. None uses default.

        Returns:
            True if command accepted, False if no HeadController or not operational.

        Raises:
            RobotStateError: If not in READY state.
        """
        if self.state != RobotState.READY:
            raise RobotStateError(
                f"Cannot move head in state {self.state.name}",
                from_state=self.state,
            )

        if self._head_controller is None:
            _logger.warning("move_head: no HeadController configured")
            return False

        kwargs: Dict[str, Any] = {}
        if neck_pitch is not None:
            kwargs["neck_pitch"] = neck_pitch
        if head_pitch is not None:
            kwargs["head_pitch"] = head_pitch
        if head_yaw is not None:
            kwargs["head_yaw"] = head_yaw
        if head_roll is not None:
            kwargs["head_roll"] = head_roll
        if duration_ms is not None:
            kwargs["duration_ms"] = duration_ms

        try:
            self._head_controller.move_to(**kwargs)
            return True
        except Exception as e:
            _logger.error("Head move failed: %s", e)
            self.emergency_stop(source="head_move_failure")
            return False

    def nod(self, count: int = 2, amplitude: Optional[float] = None,
            speed_ms: Optional[int] = None) -> bool:
        """Perform head nod gesture via HeadController.

        Args:
            count: Number of nods (default 2).
            amplitude: Nod amplitude in degrees. None uses config default.
            speed_ms: Speed per nod cycle. None uses config default.

        Returns:
            True if command accepted, False if no HeadController.
        """
        if self.state != RobotState.READY:
            raise RobotStateError(
                f"Cannot nod in state {self.state.name}",
                from_state=self.state,
            )
        if self._head_controller is None:
            _logger.warning("nod: no HeadController configured")
            return False

        kwargs: Dict[str, Any] = {"count": count}
        if amplitude is not None:
            kwargs["amplitude"] = amplitude
        if speed_ms is not None:
            kwargs["speed_ms"] = speed_ms

        try:
            self._head_controller.nod(**kwargs)
            return True
        except Exception as e:
            _logger.error("Head nod failed: %s", e)
            self.emergency_stop(source="head_nod_failure")
            return False

    def shake(self, count: int = 2, amplitude: Optional[float] = None,
              speed_ms: Optional[int] = None) -> bool:
        """Perform head shake gesture via HeadController.

        Args:
            count: Number of shakes (default 2).
            amplitude: Shake amplitude in degrees. None uses config default.
            speed_ms: Speed per shake cycle. None uses config default.

        Returns:
            True if command accepted, False if no HeadController.
        """
        if self.state != RobotState.READY:
            raise RobotStateError(
                f"Cannot shake in state {self.state.name}",
                from_state=self.state,
            )
        if self._head_controller is None:
            _logger.warning("shake: no HeadController configured")
            return False

        kwargs: Dict[str, Any] = {"count": count}
        if amplitude is not None:
            kwargs["amplitude"] = amplitude
        if speed_ms is not None:
            kwargs["speed_ms"] = speed_ms

        try:
            self._head_controller.shake(**kwargs)
            return True
        except Exception as e:
            _logger.error("Head shake failed: %s", e)
            self.emergency_stop(source="head_shake_failure")
            return False

    # =========================================================================
    # PCA9685 Raw Servo Commands (low-level)
    # =========================================================================

    def set_servo_angle(self, channel: int, angle: float) -> bool:
        """Set PCA9685 servo to specific angle (low-level).

        For head control, prefer move_head() / nod() / shake() which use
        HeadController with animation and safety. This method is for
        direct PCA9685 channel control.

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

    # =========================================================================
    # Bus Servo Commands (STS3215 arm/leg servos)
    # =========================================================================

    def set_bus_servo_position(self, servo_id: int, degrees: float) -> bool:
        """Set STS3215 bus servo to target position.

        Routes to STS3215Driver for arm/leg servos. Does NOT use PCA9685.

        Args:
            servo_id: STS3215 servo ID (0-253).
            degrees: Target angle in degrees (0-360 for STS3215).

        Returns:
            True if command sent, False if no bus servo driver.

        Raises:
            RobotStateError: If not in READY state.
            HardwareError: If bus servo communication fails.
        """
        if self.state != RobotState.READY:
            raise RobotStateError(
                f"Cannot set bus servo in state {self.state.name}",
                from_state=self.state,
            )

        if self._bus_servo_driver is None:
            _logger.warning(
                "set_bus_servo_position: no STS3215Driver configured (id=%d)",
                servo_id,
            )
            return False

        try:
            result = self._bus_servo_driver.set_position(servo_id, degrees)
            if not result:
                _logger.warning("Bus servo %d: set_position returned False", servo_id)
            return result
        except Exception as e:
            _logger.error("Bus servo %d command failed: %s", servo_id, e)
            self.emergency_stop(source=f"bus_servo_failure:id{servo_id}")
            raise HardwareError(
                f"Failed to set bus servo position (ID {servo_id})",
                device="STS3215",
                context={"servo_id": servo_id, "degrees": degrees, "error": str(e)},
            ) from e

    def set_arm_position(
        self,
        x: float,
        y: float,
        elbow_up: bool = True,
        shoulder_id: Optional[int] = None,
        elbow_id: Optional[int] = None,
    ) -> bool:
        """Set arm end-effector position using inverse kinematics.

        Routes to STS3215 bus servos if available, otherwise falls back
        to PCA9685 channels (legacy behavior for testing).

        Args:
            x: Target X position in millimeters.
            y: Target Y position in millimeters.
            elbow_up: If True, prefer elbow-up configuration.
            shoulder_id: STS3215 servo ID for shoulder. None uses legacy PCA9685 ch 0.
            elbow_id: STS3215 servo ID for elbow. None uses legacy PCA9685 ch 1.

        Returns:
            True if position was reachable and set, False if unreachable.

        Raises:
            RobotStateError: If not in READY state.
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

        # Route to bus servos if IDs provided and driver available
        if shoulder_id is not None and elbow_id is not None and self._bus_servo_driver is not None:
            # Clamp to STS3215 range (0-360)
            shoulder_deg = max(0.0, min(360.0, shoulder_deg))
            elbow_deg = max(0.0, min(360.0, elbow_deg))

            self.set_bus_servo_position(shoulder_id, shoulder_deg)
            self.set_bus_servo_position(elbow_id, elbow_deg)
        else:
            # Legacy fallback: PCA9685 channels (for testing)
            shoulder_deg = max(0.0, min(180.0, shoulder_deg))
            elbow_deg = max(0.0, min(180.0, elbow_deg))

            self.set_servo_angle(0, shoulder_deg)
            self.set_servo_angle(1, elbow_deg)

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
                "subsystems": {
                    "head_controller": self._head_controller is not None,
                    "bus_servo_driver": self._bus_servo_driver is not None,
                    "bus_servo_ids": self._bus_servo_ids,
                    "imu": self._imu is not None,
                },
            }

            # Safety diagnostics
            if self._safety is not None:
                diag["safety"] = self._safety.get_diagnostics()

            # IMU data
            if self._last_imu_data is not None:
                diag["imu"] = {"last_reading": str(self._last_imu_data)}

            # Head state
            if self._head_controller is not None:
                try:
                    head_state = self._head_controller.get_state()
                    diag["head"] = {
                        "neck_pitch": head_state.neck_pitch,
                        "head_pitch": head_state.head_pitch,
                        "head_yaw": head_state.head_yaw,
                        "head_roll": head_state.head_roll,
                        "is_moving": head_state.is_moving,
                    }
                except Exception:
                    diag["head"] = {"error": "failed to read state"}

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
                f"iterations={self._iteration_count}, "
                f"head={'yes' if self._head_controller else 'no'}, "
                f"bus_servos={len(self._bus_servo_ids)})"
            )
