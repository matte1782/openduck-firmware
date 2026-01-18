"""Pytest fixtures for LED pattern testing.

Provides mock hardware (LED strips, GPIO) for dev machine testing.
All tests can run without actual hardware.

Author: Boston Dynamics Test Engineer
Created: 17 January 2026
"""

import threading
from typing import List, Tuple
from unittest.mock import Mock, MagicMock

import pytest


# Type alias for RGB colors
RGB = Tuple[int, int, int]


class MockPixelStrip:
    """Mock rpi_ws281x.PixelStrip for hardware-free testing.

    Simulates LED strip behavior without requiring actual hardware.
    Tracks all operations for test verification.
    """

    def __init__(self, num_pixels: int, pin: int, freq_hz: int = 800000,
                 dma: int = 10, invert: bool = False, brightness: int = 255,
                 channel: int = 0):
        """Initialize mock LED strip.

        Args:
            num_pixels: Number of LEDs in strip
            pin: GPIO pin number
            freq_hz: Signal frequency
            dma: DMA channel
            invert: Invert signal
            brightness: Overall brightness (0-255)
            channel: PWM channel
        """
        self.num_pixels = num_pixels
        self.pin = pin
        self.freq_hz = freq_hz
        self.dma = dma
        self.invert = invert
        self.brightness = brightness
        self.channel = channel

        # State tracking
        self._pixels: List[RGB] = [(0, 0, 0)] * num_pixels
        self._began = False
        self._show_count = 0
        self._lock = threading.Lock()

    def begin(self) -> None:
        """Initialize the strip (called once at startup)."""
        with self._lock:
            self._began = True

    def show(self) -> None:
        """Update the strip (send pixels to hardware)."""
        with self._lock:
            if not self._began:
                raise RuntimeError("Must call begin() before show()")
            self._show_count += 1

    def setPixelColor(self, n: int, color: int) -> None:
        """Set pixel color.

        Args:
            n: Pixel index (0 to num_pixels-1)
            color: 24-bit RGB color (0x00RRGGBB)
        """
        with self._lock:
            if not 0 <= n < self.num_pixels:
                raise IndexError(f"Pixel {n} out of range (0-{self.num_pixels-1})")

            # Extract RGB from 24-bit color
            r = (color >> 16) & 0xFF
            g = (color >> 8) & 0xFF
            b = color & 0xFF
            self._pixels[n] = (r, g, b)

    def getPixelColor(self, n: int) -> int:
        """Get pixel color as 24-bit RGB.

        Args:
            n: Pixel index

        Returns:
            24-bit RGB color (0x00RRGGBB)
        """
        with self._lock:
            if not 0 <= n < self.num_pixels:
                raise IndexError(f"Pixel {n} out of range")
            r, g, b = self._pixels[n]
            return (r << 16) | (g << 8) | b

    def getPixelColorRGB(self, n: int) -> RGB:
        """Get pixel color as RGB tuple (for testing).

        Args:
            n: Pixel index

        Returns:
            RGB tuple (r, g, b)
        """
        with self._lock:
            return self._pixels[n]

    def numPixels(self) -> int:
        """Get number of pixels."""
        return self.num_pixels

    def getShowCount(self) -> int:
        """Get number of times show() was called (for testing)."""
        with self._lock:
            return self._show_count

    def getAllPixels(self) -> List[RGB]:
        """Get all pixel colors as RGB tuples (for testing)."""
        with self._lock:
            return self._pixels.copy()


def MockColor(r: int, g: int, b: int) -> int:
    """Mock rpi_ws281x.Color function.

    Converts RGB to 24-bit color value.

    Args:
        r: Red (0-255)
        g: Green (0-255)
        b: Blue (0-255)

    Returns:
        24-bit RGB color
    """
    return (r << 16) | (g << 8) | b


@pytest.fixture
def mock_led_strip():
    """Provide mock LED strip for testing (16 pixels, GPIO 18)."""
    strip = MockPixelStrip(num_pixels=16, pin=18, brightness=255, channel=0)
    strip.begin()
    return strip


@pytest.fixture
def mock_dual_led_strips():
    """Provide dual mock LED strips for testing (left + right eyes).

    Returns:
        Tuple of (left_strip, right_strip, Color_function)
    """
    left = MockPixelStrip(num_pixels=16, pin=18, brightness=255, channel=0)
    right = MockPixelStrip(num_pixels=16, pin=13, brightness=255, channel=1)
    left.begin()
    right.begin()
    return (left, right, MockColor)


@pytest.fixture
def mock_gpio():
    """Provide mock GPIO for testing.

    Minimal GPIO mock for LED testing (most LED patterns don't use GPIO).
    """
    gpio = Mock()
    gpio.BCM = 11
    gpio.setmode = Mock()
    gpio.setup = Mock()
    gpio.cleanup = Mock()
    return gpio


@pytest.fixture
def pattern_test_colors():
    """Standard colors for pattern testing."""
    return {
        'white': (255, 255, 255),
        'red': (255, 0, 0),
        'green': (0, 255, 0),
        'blue': (0, 0, 255),
        'soft_blue': (100, 150, 255),
        'orange': (255, 100, 0),
        'purple': (200, 0, 255),
        'black': (0, 0, 0),
    }


@pytest.fixture
def performance_threshold():
    """Performance thresholds for pattern rendering.

    Returns:
        Dictionary of performance requirements
    """
    return {
        'max_render_time_ms': 10.0,  # Max render time for 50Hz (20ms frame budget)
        'target_fps': 50.0,           # Target frame rate
        'min_fps': 45.0,              # Minimum acceptable FPS
    }
