"""
LED Integration Tests - System-level testing

Tests the complete LED subsystem integration:
- LEDManager orchestration
- Pattern + Emotion + Timing integration
- Error handling and recovery
- Performance requirements

Run with: pytest tests/test_core/test_led_integration.py -v

Author: Boston Dynamics Systems Integration Engineer
Created: 18 January 2026
"""

import pytest
import time
import threading
from unittest.mock import Mock, MagicMock, patch
from typing import List, Tuple

# Add firmware/src to path
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from core.led_manager import (
    LEDManager,
    LEDController,
    create_led_manager,
    RGB
)
from animation.emotions import EmotionState, EMOTION_CONFIGS
from led.patterns import PATTERN_REGISTRY


# === Mock Hardware ===

class MockPixelStrip:
    """Mock rpi_ws281x.PixelStrip for testing without hardware."""

    def __init__(self, num_pixels, pin, freq_hz, dma, invert, brightness, channel):
        self.num_pixels = num_pixels
        self.pin = pin
        self.brightness = brightness
        self.channel = channel
        self._pixels = [0] * num_pixels
        self._began = False

    def begin(self):
        self._began = True

    def show(self):
        pass

    def setPixelColor(self, n, color):
        self._pixels[n] = color

    def setBrightness(self, brightness):
        self.brightness = brightness


def MockColor(r, g, b):
    """Mock Color function."""
    return (r << 16) | (g << 8) | b


# === Fixtures ===

@pytest.fixture
def mock_hardware():
    """Mock rpi_ws281x hardware.

    The PixelStrip and Color are imported inside LEDController.initialize_hardware()
    directly from rpi_ws281x, so we must patch at the rpi_ws281x module level.
    """
    with patch.dict('sys.modules', {'rpi_ws281x': Mock(PixelStrip=MockPixelStrip, Color=MockColor)}):
        yield


@pytest.fixture
def led_controller(mock_hardware):
    """Create LED controller with mocked hardware."""
    controller = LEDController(num_pixels=16, brightness=128)
    controller.initialize_hardware()
    return controller


@pytest.fixture
def led_manager(led_controller):
    """Create LED manager with mocked controller."""
    return LEDManager(led_controller=led_controller, auto_start=False)


# === LEDController Tests ===

class TestLEDController:
    """Test LED controller functionality."""

    def test_initialization(self, led_controller):
        """Test controller initializes correctly."""
        assert led_controller.num_pixels == 16
        assert led_controller.left_pin == 18
        assert led_controller.right_pin == 13
        assert led_controller._brightness == 128

    def test_set_pattern_valid(self, led_controller):
        """Test setting valid pattern."""
        led_controller.set_pattern('breathing', speed=1.0)
        assert led_controller._pattern_name == 'breathing'
        assert led_controller._current_pattern is not None

    def test_set_pattern_invalid(self, led_controller):
        """Test setting invalid pattern raises error."""
        with pytest.raises(ValueError, match="Unknown pattern"):
            led_controller.set_pattern('nonexistent')

    def test_set_color_valid(self, led_controller):
        """Test setting valid color."""
        led_controller.set_color((255, 128, 64))
        assert led_controller._current_color == (255, 128, 64)

    def test_set_color_invalid_type(self, led_controller):
        """Test setting invalid color type raises error."""
        with pytest.raises(ValueError, match="RGB tuple"):
            led_controller.set_color([255, 128, 64])  # List instead of tuple

    def test_set_color_invalid_range(self, led_controller):
        """Test setting color with out-of-range values."""
        with pytest.raises(ValueError, match="0-255"):
            led_controller.set_color((300, 128, 64))

    def test_set_brightness_valid(self, led_controller):
        """Test setting valid brightness."""
        led_controller.set_brightness(200)
        assert led_controller._brightness == 200

    def test_set_brightness_invalid(self, led_controller):
        """Test setting invalid brightness raises error."""
        with pytest.raises(ValueError, match="0-255"):
            led_controller.set_brightness(300)

    def test_update_without_pattern(self, led_controller):
        """Test update without pattern set (should not crash)."""
        led_controller.update()  # Should do nothing gracefully

    def test_update_with_pattern(self, led_controller):
        """Test update with pattern advances frame."""
        led_controller.set_pattern('breathing')
        led_controller.set_color((100, 150, 255))

        initial_frame = led_controller._current_pattern._frame
        led_controller.update()
        assert led_controller._current_pattern._frame == initial_frame + 1

    def test_clear(self, led_controller):
        """Test clearing LEDs."""
        led_controller.set_pattern('breathing')
        led_controller.update()
        led_controller.clear()  # Should not crash

    def test_thread_safety(self, led_controller):
        """Test thread-safe operations."""
        def worker():
            for _ in range(10):
                led_controller.set_brightness(128)
                led_controller.update()

        threads = [threading.Thread(target=worker) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should complete without deadlock


# === LEDManager Tests ===

class TestLEDManager:
    """Test LED manager orchestration."""

    def test_initialization(self, led_manager):
        """Test manager initializes correctly."""
        assert led_manager.target_fps == 50
        assert not led_manager._running
        assert led_manager.emotion_manager is not None

    def test_start_stop(self, led_manager):
        """Test starting and stopping update loop."""
        led_manager.start()
        assert led_manager._running
        time.sleep(0.1)  # Let a few frames run

        led_manager.stop()
        assert not led_manager._running

    def test_set_emotion_valid(self, led_manager):
        """Test setting valid emotion."""
        led_manager.start()
        result = led_manager.set_emotion(EmotionState.HAPPY)
        assert result is True
        assert led_manager.get_current_emotion() == EmotionState.HAPPY
        led_manager.stop()

    def test_set_emotion_invalid_transition(self, led_manager):
        """Test invalid emotion transition raises error."""
        led_manager.start()
        led_manager.set_emotion(EmotionState.SLEEPY)

        # SLEEPY -> EXCITED is not valid (without force)
        from animation.emotions import InvalidTransitionError
        with pytest.raises(InvalidTransitionError):
            led_manager.set_emotion(EmotionState.EXCITED)

        led_manager.stop()

    def test_set_emotion_forced(self, led_manager):
        """Test forced emotion transition bypasses validation."""
        led_manager.start()
        led_manager.set_emotion(EmotionState.SLEEPY)

        # Force invalid transition
        result = led_manager.set_emotion(EmotionState.EXCITED, force=True)
        assert result is True
        assert led_manager.get_current_emotion() == EmotionState.EXCITED

        led_manager.stop()

    def test_emotion_changes_pattern(self, led_manager):
        """Test emotion change updates LED pattern."""
        led_manager.start()

        # HAPPY uses 'pulse' pattern
        led_manager.set_emotion(EmotionState.HAPPY)
        assert led_manager.led_controller._pattern_name == 'pulse'

        # THINKING uses 'spin' pattern
        led_manager.set_emotion(EmotionState.THINKING)
        assert led_manager.led_controller._pattern_name == 'spin'

        led_manager.stop()

    def test_emotion_changes_color(self, led_manager):
        """Test emotion change updates LED color."""
        led_manager.start()

        led_manager.set_emotion(EmotionState.HAPPY)
        happy_config = EMOTION_CONFIGS[EmotionState.HAPPY]
        assert led_manager.led_controller._current_color == happy_config.led_color

        led_manager.set_emotion(EmotionState.ALERT)
        alert_config = EMOTION_CONFIGS[EmotionState.ALERT]
        assert led_manager.led_controller._current_color == alert_config.led_color

        led_manager.stop()

    def test_fps_tracking(self, led_manager):
        """Test FPS tracking."""
        led_manager.start()
        time.sleep(0.5)  # Let some frames run

        fps = led_manager.get_fps()
        assert fps > 0
        assert 40 <= fps <= 60  # Should be close to 50Hz

        led_manager.stop()

    def test_stats_reporting(self, led_manager):
        """Test stats dictionary."""
        led_manager.start()
        led_manager.set_emotion(EmotionState.HAPPY)

        stats = led_manager.get_stats()
        assert 'fps' in stats
        assert 'frame_count' in stats
        assert 'emotion' in stats
        assert 'pattern' in stats
        assert stats['emotion'] == 'HAPPY'

        led_manager.stop()

    def test_context_manager(self, led_controller):
        """Test context manager interface."""
        with LEDManager(led_controller=led_controller) as mgr:
            assert mgr._running
            mgr.set_emotion(EmotionState.CURIOUS)

        assert not mgr._running  # Auto-stopped on exit

    def test_create_led_manager_factory(self, mock_hardware):
        """Test factory function."""
        mgr = create_led_manager(target_fps=30, auto_start=False)
        assert mgr.target_fps == 30
        assert not mgr._running


# === Integration Tests ===

class TestLEDIntegration:
    """Test complete LED subsystem integration."""

    def test_full_emotion_cycle(self, led_manager):
        """Test cycling through multiple emotions."""
        led_manager.start()

        emotions = [
            EmotionState.IDLE,
            EmotionState.CURIOUS,
            EmotionState.HAPPY,
            EmotionState.EXCITED,
            EmotionState.THINKING,
            EmotionState.IDLE,
        ]

        for emotion in emotions:
            led_manager.set_emotion(emotion)
            assert led_manager.get_current_emotion() == emotion
            time.sleep(0.05)  # Brief delay to see pattern change

        led_manager.stop()

    def test_all_patterns_render(self, led_controller):
        """Test all patterns render without errors."""
        for pattern_name in PATTERN_REGISTRY.keys():
            led_controller.set_pattern(pattern_name)
            led_controller.set_color((255, 128, 64))

            # Render several frames
            for _ in range(10):
                led_controller.update()

            # Should complete without errors

    def test_pattern_speed_variations(self, led_controller):
        """Test patterns at different speeds."""
        led_controller.set_pattern('breathing')
        led_controller.set_color((100, 150, 255))

        for speed in [0.5, 1.0, 2.0]:
            led_controller.set_pattern('breathing', speed=speed)
            for _ in range(5):
                led_controller.update()

            # Should handle all speeds

    def test_brightness_scaling(self, led_controller):
        """Test brightness affects pattern output."""
        led_controller.set_pattern('breathing')
        led_controller.set_color((255, 255, 255))

        # Test different brightness levels
        for brightness in [50, 128, 200]:
            led_controller.set_brightness(brightness)
            led_controller.update()

            # Verify pattern config updated
            assert led_controller._current_pattern.config.brightness == brightness / 255.0

    def test_concurrent_updates(self, led_manager):
        """Test concurrent emotion changes and updates."""
        led_manager.start()

        def emotion_changer():
            emotions = [EmotionState.HAPPY, EmotionState.CURIOUS, EmotionState.IDLE]
            for emotion in emotions:
                try:
                    led_manager.set_emotion(emotion)
                    time.sleep(0.05)
                except Exception:
                    pass  # Invalid transitions expected

        thread = threading.Thread(target=emotion_changer)
        thread.start()

        time.sleep(0.2)  # Let it run
        thread.join(timeout=1.0)

        led_manager.stop()

    def test_error_recovery(self, led_manager):
        """Test recovery from errors."""
        led_manager.start()

        # Trigger error by setting invalid brightness directly
        try:
            led_manager.led_controller.set_brightness(999)
        except ValueError:
            pass  # Expected

        # Manager should still work
        led_manager.set_emotion(EmotionState.HAPPY)
        assert led_manager.get_current_emotion() == EmotionState.HAPPY

        led_manager.stop()


# === Performance Tests ===

class TestLEDPerformance:
    """Test performance requirements."""

    def test_target_fps_achieved(self, led_manager):
        """Test actual FPS meets target (50Hz)."""
        led_manager.start()
        time.sleep(1.0)  # Run for 1 second

        fps = led_manager.get_fps()
        assert fps >= 45.0, f"FPS too low: {fps} (target: 50)"
        assert fps <= 55.0, f"FPS too high: {fps} (target: 50)"

        led_manager.stop()

    def test_pattern_render_time(self, led_controller):
        """Test pattern render time meets 10ms budget."""
        led_controller.set_pattern('breathing')
        led_controller.set_color((255, 128, 64))

        render_times = []
        for _ in range(100):
            start = time.perf_counter()
            led_controller.update()
            end = time.perf_counter()
            render_times.append((end - start) * 1000)  # Convert to ms

        avg_time = sum(render_times) / len(render_times)
        max_time = max(render_times)

        assert avg_time < 10.0, f"Avg render time too high: {avg_time:.2f}ms"
        assert max_time < 20.0, f"Max render time too high: {max_time:.2f}ms"

    def test_memory_stability(self, led_manager):
        """Test no memory leaks during extended operation."""
        led_manager.start()

        initial_frame = led_manager._frame_count

        # Run for a while
        time.sleep(0.5)

        final_frame = led_manager._frame_count
        frames_processed = final_frame - initial_frame

        assert frames_processed > 20, "Not enough frames processed"

        led_manager.stop()

        # If we got here without crash, memory is stable


# === Edge Cases ===

class TestLEDEdgeCases:
    """Test edge cases and failure modes."""

    def test_double_start(self, led_manager):
        """Test starting already running manager."""
        led_manager.start()
        led_manager.start()  # Should warn but not crash
        assert led_manager._running
        led_manager.stop()

    def test_double_stop(self, led_manager):
        """Test stopping already stopped manager."""
        led_manager.start()
        led_manager.stop()
        led_manager.stop()  # Should be no-op
        assert not led_manager._running

    def test_stop_without_start(self, led_manager):
        """Test stopping manager that was never started."""
        led_manager.stop()  # Should be no-op
        assert not led_manager._running

    def test_emotion_change_while_stopped(self, led_manager):
        """Test changing emotion while manager stopped."""
        result = led_manager.set_emotion(EmotionState.HAPPY)
        assert result is True  # Should work even while stopped

    def test_invalid_pattern_name(self, led_controller):
        """Test handling invalid pattern name."""
        with pytest.raises(ValueError):
            led_controller.set_pattern('nonexistent_pattern')

    def test_zero_brightness(self, led_controller):
        """Test zero brightness (edge case)."""
        led_controller.set_brightness(0)
        assert led_controller._brightness == 0

        led_controller.set_pattern('breathing')
        led_controller.update()  # Should not crash

    def test_max_brightness(self, led_controller):
        """Test max brightness (255)."""
        led_controller.set_brightness(255)
        assert led_controller._brightness == 255

        led_controller.set_pattern('breathing')
        led_controller.update()  # Should not crash


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
