"""Comprehensive test suite for ServoWatchdog class.

Tests cover:
- Timeout detection (expiry behavior, custom timeouts, short timeouts)
- Feed mechanism (timer reset, multiple feeds, feed count tracking)
- Emergency stop integration (trigger on expire, source tracking, single trigger)
- Thread safety (concurrent start/stop, concurrent feed)

Test Strategy:
- Use short timeouts (50-100ms) for fast test execution
- Mock EmergencyStop to track trigger() calls
- Use time.sleep() carefully for timing-sensitive tests
"""

import pytest
import threading
import time
from typing import List, Optional
from dataclasses import dataclass, field

from src.safety.watchdog import ServoWatchdog


# =============================================================================
# Mock EmergencyStop
# =============================================================================

@dataclass
class MockEmergencyStop:
    """Mock EmergencyStop that tracks trigger() calls.

    Attributes:
        trigger_calls: List of (source, timestamp) tuples for each trigger call
        trigger_count: Number of times trigger() was called
        trigger_delay_ms: Optional artificial delay to simulate slow trigger
    """
    trigger_calls: List[tuple] = field(default_factory=list)
    trigger_count: int = 0
    trigger_delay_ms: float = 0.0
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def trigger(self, source: str = "unknown") -> float:
        """Record trigger call and return simulated latency."""
        with self._lock:
            self.trigger_count += 1
            self.trigger_calls.append((source, time.time()))

        if self.trigger_delay_ms > 0:
            time.sleep(self.trigger_delay_ms / 1000.0)

        return self.trigger_delay_ms

    def reset(self) -> None:
        """Reset the mock state."""
        with self._lock:
            self.trigger_calls.clear()
            self.trigger_count = 0


@pytest.fixture
def mock_estop():
    """Create a fresh MockEmergencyStop for each test."""
    return MockEmergencyStop()


# =============================================================================
# Timeout Detection Tests (5+)
# =============================================================================

class TestTimeoutDetection:
    """Test cases for watchdog timeout detection behavior."""

    def test_watchdog_expires_after_timeout_when_not_fed(self, mock_estop):
        """Watchdog expires after timeout when not fed.

        Verifies that if feed() is never called after start(), the watchdog
        will expire and trigger emergency stop.
        """
        timeout_ms = 100
        watchdog = ServoWatchdog(mock_estop, timeout_ms=timeout_ms)

        watchdog.start()

        # Wait for timeout + buffer
        time.sleep((timeout_ms + 150) / 1000.0)

        # Should have expired and triggered E-stop
        assert watchdog.is_expired is True
        assert mock_estop.trigger_count == 1

        watchdog.stop()

    def test_watchdog_does_not_expire_when_regularly_fed(self, mock_estop):
        """Watchdog does not expire when regularly fed.

        Verifies that regular feed() calls prevent watchdog expiration.
        """
        timeout_ms = 100
        watchdog = ServoWatchdog(mock_estop, timeout_ms=timeout_ms)

        watchdog.start()
        watchdog.feed()

        # Feed regularly for 400ms (4x timeout period)
        for _ in range(8):
            time.sleep(0.040)  # 40ms between feeds
            watchdog.feed()

        # Should NOT have expired
        assert watchdog.is_expired is False
        assert mock_estop.trigger_count == 0

        watchdog.stop()

    def test_expired_property_returns_correct_state(self, mock_estop):
        """is_expired property returns correct state before and after expiration."""
        timeout_ms = 80
        watchdog = ServoWatchdog(mock_estop, timeout_ms=timeout_ms)

        # Before start: not expired
        assert watchdog.is_expired is False

        watchdog.start()

        # Immediately after start: not expired (timer just started)
        assert watchdog.is_expired is False

        # Wait for expiration
        time.sleep((timeout_ms + 150) / 1000.0)

        # After timeout: expired
        assert watchdog.is_expired is True

        watchdog.stop()

    def test_custom_timeout_values_work(self, mock_estop):
        """Custom timeout values are respected.

        Tests both short and longer custom timeouts to verify the
        timeout_ms parameter is properly used.
        """
        # Test with 200ms timeout
        timeout_ms = 200
        watchdog = ServoWatchdog(mock_estop, timeout_ms=timeout_ms)

        assert watchdog.timeout_ms == timeout_ms

        watchdog.start()

        # Feed once, wait less than timeout
        watchdog.feed()
        time.sleep(0.100)  # 100ms < 200ms timeout

        # Should NOT have expired yet
        assert watchdog.is_expired is False

        # Wait for remaining timeout + buffer
        time.sleep(0.150)  # Total ~250ms > 200ms timeout

        # Should have expired now
        assert watchdog.is_expired is True

        watchdog.stop()

    def test_short_timeout_50ms_for_testing(self, mock_estop):
        """Short timeout (50ms) works for fast testing.

        Verifies that very short timeouts function correctly,
        enabling fast test execution.
        """
        timeout_ms = 50
        watchdog = ServoWatchdog(mock_estop, timeout_ms=timeout_ms)

        watchdog.start()

        # Wait for expiration with short timeout
        time.sleep(0.200)  # 200ms >> 50ms timeout

        assert watchdog.is_expired is True
        assert mock_estop.trigger_count == 1

        watchdog.stop()

    def test_invalid_timeout_raises_value_error(self, mock_estop):
        """Creating watchdog with invalid timeout raises ValueError."""
        with pytest.raises(ValueError, match="must be positive"):
            ServoWatchdog(mock_estop, timeout_ms=0)

        with pytest.raises(ValueError, match="must be positive"):
            ServoWatchdog(mock_estop, timeout_ms=-100)


# =============================================================================
# Feed Mechanism Tests (4+)
# =============================================================================

class TestFeedMechanism:
    """Test cases for watchdog feed() mechanism."""

    def test_feed_resets_the_timer(self, mock_estop):
        """feed() resets the watchdog timer.

        Verifies that calling feed() resets the timeout countdown.
        """
        timeout_ms = 100
        watchdog = ServoWatchdog(mock_estop, timeout_ms=timeout_ms)

        watchdog.start()

        # Wait 80ms (close to timeout)
        time.sleep(0.080)

        # Feed to reset timer
        watchdog.feed()

        # Wait another 80ms (would have expired if feed didn't reset)
        time.sleep(0.080)

        # Should NOT have expired (timer was reset)
        assert watchdog.is_expired is False
        assert mock_estop.trigger_count == 0

        # Now stop feeding and let it expire
        time.sleep(0.150)

        assert watchdog.is_expired is True

        watchdog.stop()

    def test_multiple_feeds_extend_timeout(self, mock_estop):
        """Multiple feeds continuously extend the timeout.

        Verifies that repeatedly calling feed() keeps the watchdog alive
        indefinitely (within the test duration).
        """
        timeout_ms = 60
        watchdog = ServoWatchdog(mock_estop, timeout_ms=timeout_ms)

        watchdog.start()

        # Feed 20 times over ~500ms (8x the timeout period)
        for i in range(20):
            watchdog.feed()
            time.sleep(0.025)  # 25ms between feeds

        # Should still be alive
        assert watchdog.is_expired is False
        assert mock_estop.trigger_count == 0

        watchdog.stop()

    def test_feed_during_expiration_race_condition_safe(self, mock_estop):
        """feed() during expiration check is race-condition safe.

        Tests that calling feed() from another thread while the watchdog
        is checking for expiration doesn't cause issues.
        """
        timeout_ms = 80
        watchdog = ServoWatchdog(mock_estop, timeout_ms=timeout_ms)

        feed_count = [0]
        stop_feeding = threading.Event()

        def rapid_feeder():
            """Feed rapidly in a tight loop."""
            while not stop_feeding.is_set():
                watchdog.feed()
                feed_count[0] += 1
                time.sleep(0.001)  # 1ms between feeds

        watchdog.start()

        # Start rapid feeding thread
        feed_thread = threading.Thread(target=rapid_feeder)
        feed_thread.start()

        # Let it run for 300ms (3x timeout period with rapid feeding)
        time.sleep(0.300)

        # Stop feeding
        stop_feeding.set()
        feed_thread.join(timeout=1.0)

        # Should NOT have expired (was being fed rapidly)
        assert watchdog.is_expired is False
        assert mock_estop.trigger_count == 0
        assert feed_count[0] > 100  # Should have fed many times

        watchdog.stop()

    def test_feed_is_fast_operation(self, mock_estop):
        """feed() is a fast operation (< 1ms typical).

        Verifies that feed() has minimal overhead and can be called
        frequently without performance impact.
        """
        watchdog = ServoWatchdog(mock_estop, timeout_ms=1000)
        watchdog.start()

        # Measure time for 1000 feeds
        start_time = time.perf_counter()
        for _ in range(1000):
            watchdog.feed()
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        # 1000 feeds should take < 100ms (0.1ms per feed average)
        assert elapsed_ms < 100, f"1000 feeds took {elapsed_ms:.2f}ms (expected < 100ms)"

        avg_per_feed = elapsed_ms / 1000
        assert avg_per_feed < 0.1, f"Average feed time {avg_per_feed:.4f}ms (expected < 0.1ms)"

        watchdog.stop()


# =============================================================================
# Emergency Stop Integration Tests (4+)
# =============================================================================

class TestEmergencyStopIntegration:
    """Test cases for watchdog-to-emergency-stop integration."""

    def test_expired_watchdog_triggers_emergency_stop(self, mock_estop):
        """Expired watchdog triggers emergency_stop.trigger().

        Verifies that when the watchdog times out, it calls trigger()
        on the EmergencyStop instance.
        """
        timeout_ms = 80
        watchdog = ServoWatchdog(mock_estop, timeout_ms=timeout_ms)

        watchdog.start()

        # Wait for expiration
        time.sleep((timeout_ms + 150) / 1000.0)

        # Verify trigger was called
        assert mock_estop.trigger_count == 1

        watchdog.stop()

    def test_estop_source_contains_watchdog_timeout(self, mock_estop):
        """E-stop source message indicates watchdog timeout.

        Verifies that the trigger source message identifies the
        watchdog timeout as the cause.
        """
        timeout_ms = 70
        watchdog = ServoWatchdog(mock_estop, timeout_ms=timeout_ms)

        watchdog.start()

        # Wait for expiration
        time.sleep((timeout_ms + 150) / 1000.0)

        # Verify source message
        assert len(mock_estop.trigger_calls) == 1
        source, _ = mock_estop.trigger_calls[0]
        assert "watchdog" in source.lower()
        assert "timeout" in source.lower()
        assert str(timeout_ms) in source  # Should include timeout value

        watchdog.stop()

    def test_estop_not_triggered_if_stopped_before_expiry(self, mock_estop):
        """E-stop not triggered if watchdog stopped before expiry.

        Verifies that stopping the watchdog before it expires prevents
        the emergency stop from being triggered.
        """
        timeout_ms = 200
        watchdog = ServoWatchdog(mock_estop, timeout_ms=timeout_ms)

        watchdog.start()

        # Wait less than timeout
        time.sleep(0.100)  # 100ms < 200ms

        # Stop watchdog before expiry
        watchdog.stop()

        # Wait a bit more to ensure no delayed trigger
        time.sleep(0.200)

        # Should NOT have triggered E-stop
        assert mock_estop.trigger_count == 0

    def test_multiple_expirations_only_trigger_once(self, mock_estop):
        """Multiple expirations only trigger E-stop once.

        Verifies that even if the watchdog would "expire" multiple times,
        the emergency stop is only triggered once.
        """
        timeout_ms = 60
        watchdog = ServoWatchdog(mock_estop, timeout_ms=timeout_ms)

        watchdog.start()

        # Wait for multiple "timeout periods"
        time.sleep(0.400)  # ~6x timeout period

        # Should have triggered exactly once
        assert mock_estop.trigger_count == 1

        watchdog.stop()

    def test_watchdog_stops_running_after_trigger(self, mock_estop):
        """Watchdog stops monitoring after triggering E-stop.

        Verifies that the watchdog thread exits after triggering,
        preventing resource leaks.
        """
        timeout_ms = 60
        watchdog = ServoWatchdog(mock_estop, timeout_ms=timeout_ms)

        watchdog.start()
        assert watchdog.is_running is True

        # Wait for expiration
        time.sleep((timeout_ms + 150) / 1000.0)

        # Should have stopped running after trigger
        assert watchdog.is_running is False
        assert watchdog.is_expired is True

        # Explicit stop should be safe (idempotent)
        watchdog.stop()


# =============================================================================
# Thread Safety Tests (2+)
# =============================================================================

class TestThreadSafety:
    """Test cases for watchdog thread safety."""

    def test_start_stop_from_different_threads_safe(self, mock_estop):
        """start/stop from different threads is safe.

        Verifies that calling start() and stop() from different threads
        doesn't cause race conditions or crashes.
        """
        watchdog = ServoWatchdog(mock_estop, timeout_ms=500)

        errors = []

        def starter():
            try:
                watchdog.start()
            except RuntimeError:
                # Expected if already running
                pass
            except Exception as e:
                errors.append(f"Starter error: {e}")

        def stopper():
            try:
                time.sleep(0.050)  # Small delay
                watchdog.stop()
            except Exception as e:
                errors.append(f"Stopper error: {e}")

        # Run multiple start/stop cycles from different threads
        for _ in range(5):
            t1 = threading.Thread(target=starter)
            t2 = threading.Thread(target=stopper)

            t1.start()
            t2.start()

            t1.join(timeout=2.0)
            t2.join(timeout=2.0)

            # Small delay before next cycle
            time.sleep(0.050)

        # Ensure final cleanup
        watchdog.stop()

        assert len(errors) == 0, f"Thread safety errors: {errors}"

    def test_feed_from_different_threads_safe(self, mock_estop):
        """feed() from different threads is safe.

        Verifies that multiple threads can call feed() concurrently
        without race conditions.
        """
        watchdog = ServoWatchdog(mock_estop, timeout_ms=500)

        feed_counts = [0, 0, 0, 0]
        stop_event = threading.Event()
        errors = []

        def feeder(thread_id):
            while not stop_event.is_set():
                try:
                    watchdog.feed()
                    feed_counts[thread_id] += 1
                except Exception as e:
                    errors.append(f"Thread {thread_id} error: {e}")
                time.sleep(0.001)  # 1ms between feeds

        watchdog.start()

        # Start 4 feeder threads
        threads = []
        for i in range(4):
            t = threading.Thread(target=feeder, args=(i,))
            threads.append(t)
            t.start()

        # Let them run for 300ms
        time.sleep(0.300)

        # Stop feeders
        stop_event.set()
        for t in threads:
            t.join(timeout=2.0)

        watchdog.stop()

        # Verify no errors
        assert len(errors) == 0, f"Thread safety errors: {errors}"

        # Verify all threads fed successfully
        total_feeds = sum(feed_counts)
        assert total_feeds > 100, f"Expected many feeds, got {total_feeds}"

        # Each thread should have fed multiple times
        for i, count in enumerate(feed_counts):
            assert count > 10, f"Thread {i} only fed {count} times"

    def test_concurrent_operations_no_deadlock(self, mock_estop):
        """Concurrent start/stop/feed operations don't deadlock.

        Stress test with many threads doing different operations
        to ensure no deadlocks occur.
        """
        watchdog = ServoWatchdog(mock_estop, timeout_ms=1000)

        stop_event = threading.Event()
        operation_count = [0]
        errors = []
        lock = threading.Lock()

        def random_operations(thread_id):
            ops = ['feed', 'feed', 'feed', 'start', 'stop', 'check_expired', 'check_running']
            import random
            while not stop_event.is_set():
                op = random.choice(ops)
                try:
                    if op == 'feed':
                        watchdog.feed()
                    elif op == 'start':
                        try:
                            watchdog.start()
                        except RuntimeError:
                            pass  # Already running
                    elif op == 'stop':
                        watchdog.stop()
                    elif op == 'check_expired':
                        _ = watchdog.is_expired
                    elif op == 'check_running':
                        _ = watchdog.is_running

                    with lock:
                        operation_count[0] += 1
                except Exception as e:
                    errors.append(f"Thread {thread_id} error during {op}: {e}")

                time.sleep(0.001)

        # Start many threads doing random operations
        threads = []
        for i in range(6):
            t = threading.Thread(target=random_operations, args=(i,))
            threads.append(t)
            t.start()

        # Run for 500ms
        time.sleep(0.500)

        # Stop all threads (with timeout to detect deadlock)
        stop_event.set()
        deadlocked = False
        for t in threads:
            t.join(timeout=3.0)
            if t.is_alive():
                deadlocked = True

        # Final cleanup
        watchdog.stop()

        assert not deadlocked, "Threads deadlocked during concurrent operations"
        assert len(errors) == 0, f"Errors during operations: {errors}"
        assert operation_count[0] > 100, f"Expected many operations, got {operation_count[0]}"


# =============================================================================
# Context Manager Tests
# =============================================================================

class TestContextManager:
    """Test cases for watchdog context manager usage."""

    def test_context_manager_starts_and_stops(self, mock_estop):
        """Context manager properly starts and stops watchdog."""
        with ServoWatchdog(mock_estop, timeout_ms=500) as watchdog:
            assert watchdog.is_running is True
            watchdog.feed()

        # After exiting context, should be stopped
        assert watchdog.is_running is False

    def test_context_manager_stops_on_exception(self, mock_estop):
        """Context manager stops watchdog even if exception occurs."""
        watchdog = None
        try:
            with ServoWatchdog(mock_estop, timeout_ms=500) as wd:
                watchdog = wd
                assert watchdog.is_running is True
                raise ValueError("Test exception")
        except ValueError:
            pass

        # Should be stopped even after exception
        assert watchdog is not None
        assert watchdog.is_running is False


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================

class TestEdgeCases:
    """Test cases for edge cases and error conditions."""

    def test_cannot_start_already_running_watchdog(self, mock_estop):
        """Starting an already running watchdog raises RuntimeError."""
        watchdog = ServoWatchdog(mock_estop, timeout_ms=500)

        watchdog.start()

        with pytest.raises(RuntimeError, match="already running"):
            watchdog.start()

        watchdog.stop()

    def test_stop_when_not_running_is_safe(self, mock_estop):
        """Stopping a non-running watchdog is safe (no error)."""
        watchdog = ServoWatchdog(mock_estop, timeout_ms=500)

        # Stop before start should be safe
        watchdog.stop()

        # Multiple stops should be safe
        watchdog.stop()
        watchdog.stop()

    def test_feed_before_start_updates_timestamp(self, mock_estop):
        """feed() before start() doesn't crash (updates internal state)."""
        watchdog = ServoWatchdog(mock_estop, timeout_ms=100)

        # Feed before start should not crash
        watchdog.feed()
        watchdog.feed()

        # Start should still work
        watchdog.start()
        watchdog.feed()

        # Wait less than timeout
        time.sleep(0.050)

        assert watchdog.is_expired is False

        watchdog.stop()

    def test_is_running_property_accurate(self, mock_estop):
        """is_running property accurately reflects watchdog state."""
        watchdog = ServoWatchdog(mock_estop, timeout_ms=500)

        # Before start
        assert watchdog.is_running is False

        watchdog.start()
        assert watchdog.is_running is True

        watchdog.stop()
        assert watchdog.is_running is False

    def test_timeout_ms_property_returns_configured_value(self, mock_estop):
        """timeout_ms property returns the configured timeout value."""
        for timeout in [50, 100, 500, 1000, 5000]:
            watchdog = ServoWatchdog(mock_estop, timeout_ms=timeout)
            assert watchdog.timeout_ms == timeout

    def test_repr_returns_useful_string(self, mock_estop):
        """__repr__ returns a useful debugging string with key info."""
        watchdog = ServoWatchdog(mock_estop, timeout_ms=500)

        repr_str = repr(watchdog)

        # Should contain class name and key state info
        assert "ServoWatchdog" in repr_str
        assert "timeout_ms=500" in repr_str
        assert "running=" in repr_str
        assert "expired=" in repr_str

        # Test state changes are reflected
        watchdog.start()
        repr_running = repr(watchdog)
        assert "running=True" in repr_running

        watchdog.stop()
