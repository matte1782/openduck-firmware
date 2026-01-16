"""Servo Watchdog Timer for OpenDuck Mini V3 Safety System.

This module provides a watchdog timer that monitors the servo control loop
and triggers an emergency stop if the loop stops responding. This prevents
runaway servo behavior if the control software crashes or hangs.

Use Case:
    The servo command loop calls feed() after each successful command cycle.
    If the loop crashes, hangs, or is blocked, the watchdog will timeout and
    trigger the emergency stop, immediately halting all servo motion.

Safety Philosophy:
    - Fail-safe design: if watchdog thread itself fails, it cannot prevent E-stop
    - Conservative timeouts: better to false-trigger than miss a real hang
    - Non-blocking: watchdog runs in daemon thread, won't block program exit
"""

import threading
import time
from typing import Optional

from .emergency_stop import EmergencyStop


class ServoWatchdog:
    """Watchdog timer for servo control loop safety monitoring.

    Monitors the servo control loop by requiring periodic feed() calls.
    If no feed() is received within the configured timeout, triggers
    an emergency stop to prevent uncontrolled servo behavior.

    Thread Safety:
        All public methods are thread-safe. The watchdog runs in a separate
        daemon thread and can be fed from any thread.

    Example:
        >>> e_stop = EmergencyStop()
        >>> watchdog = ServoWatchdog(e_stop, timeout_ms=500)
        >>> watchdog.start()
        >>> # In your servo control loop:
        >>> while running:
        ...     send_servo_commands()
        ...     watchdog.feed()  # Reset watchdog timer
        >>> watchdog.stop()

    Attributes:
        timeout_ms: Configured timeout in milliseconds
        is_expired: True if watchdog has timed out
        is_running: True if watchdog monitoring is active
    """

    # Check interval in seconds (how often the thread checks for timeout)
    _CHECK_INTERVAL_SEC = 0.1  # 100ms

    def __init__(
        self,
        emergency_stop: EmergencyStop,
        timeout_ms: int = 1000
    ) -> None:
        """Initialize servo watchdog timer.

        Args:
            emergency_stop: EmergencyStop instance to trigger on timeout
            timeout_ms: Timeout in milliseconds (default: 1000ms)

        Raises:
            ValueError: If timeout_ms is not positive
        """
        if timeout_ms <= 0:
            raise ValueError(f"timeout_ms must be positive, got {timeout_ms}")

        self._emergency_stop = emergency_stop
        self._timeout_ms = timeout_ms
        self._timeout_sec = timeout_ms / 1000.0

        self._lock = threading.Lock()
        self._last_feed_time: Optional[float] = None
        self._expired = False
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    @property
    def timeout_ms(self) -> int:
        """Get configured timeout in milliseconds.

        Returns:
            Timeout value in milliseconds
        """
        return self._timeout_ms

    @property
    def is_expired(self) -> bool:
        """Check if watchdog has timed out.

        Returns:
            True if timeout exceeded without feed(), False otherwise
        """
        with self._lock:
            return self._expired

    @property
    def is_running(self) -> bool:
        """Check if watchdog monitoring is active.

        Returns:
            True if watchdog thread is running, False otherwise
        """
        with self._lock:
            return self._running

    def start(self) -> None:
        """Start watchdog timer monitoring.

        Creates a daemon background thread that monitors for timeout.
        The thread checks every 100ms if timeout has been exceeded.

        Note:
            Call feed() immediately after start() to initialize the timer,
            otherwise the watchdog will expire after timeout_ms.

        Raises:
            RuntimeError: If watchdog is already running
        """
        with self._lock:
            if self._running:
                raise RuntimeError("Watchdog is already running")

            self._expired = False
            self._last_feed_time = time.monotonic()
            self._stop_event.clear()
            self._running = True

        # Create and start monitoring thread
        self._thread = threading.Thread(
            target=self._monitor_loop,
            name="ServoWatchdog",
            daemon=True  # Won't block program exit
        )
        self._thread.start()

    def stop(self) -> None:
        """Stop watchdog timer monitoring.

        Signals the monitoring thread to exit and waits for it to complete.
        Safe to call even if watchdog is not running.
        """
        with self._lock:
            if not self._running:
                return
            self._running = False

        # Signal thread to stop
        self._stop_event.set()

        # Wait for thread to exit (with timeout to prevent deadlock)
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=1.0)

        self._thread = None

    def feed(self) -> None:
        """Reset watchdog timer (heartbeat).

        Must be called periodically by the servo control loop to prevent
        timeout. Each call resets the timer to zero.

        This method is very fast (just updates a timestamp) and safe to
        call from any thread.
        """
        with self._lock:
            self._last_feed_time = time.monotonic()

    def _monitor_loop(self) -> None:
        """Background monitoring loop (runs in separate thread).

        Checks every 100ms if the last feed() was within the timeout window.
        If timeout is exceeded, triggers emergency stop and sets expired flag.

        Note: E-stop trigger is called inside the lock to prevent race condition
        where feed() could be called between timeout check and trigger. This is
        safe because EmergencyStop.trigger() has its own internal lock and is
        designed to be called from any context.
        """
        while not self._stop_event.is_set():
            # Check for timeout and trigger E-stop atomically inside lock
            # to prevent race condition with feed() calls
            with self._lock:
                if not self._running:
                    break

                if self._last_feed_time is not None:
                    # Use time.monotonic() for consistent, NTP-immune timing
                    elapsed = time.monotonic() - self._last_feed_time
                    if elapsed >= self._timeout_sec:
                        self._expired = True
                        self._running = False
                        # Trigger inside lock to prevent race with feed()
                        # EmergencyStop.trigger() is safe to call here as it
                        # has its own internal lock and won't cause deadlock
                        self._emergency_stop.trigger(
                            f"Servo watchdog timeout ({self._timeout_ms}ms)"
                        )
                        break

            # Sleep until next check (or until stop is requested)
            self._stop_event.wait(timeout=self._CHECK_INTERVAL_SEC)

    def __enter__(self) -> "ServoWatchdog":
        """Context manager entry - starts watchdog.

        Returns:
            Self for use in with statement
        """
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - stops watchdog.

        Always stops the watchdog, regardless of whether an exception occurred.
        """
        self.stop()
