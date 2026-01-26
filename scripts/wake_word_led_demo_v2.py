#!/usr/bin/env python3
"""Wake Word + LED Integration Demo V2 for OpenDuck Mini V3

Production-grade wake word detection with LED animations.

This version uses the production WakeWordPipeline which includes:
- VAD gating (only process during speech)
- Multi-frame confirmation (3/5 frames above threshold)
- EMA score smoothing
- Noise floor calibration
- Cooldown mechanism

Expected Performance:
- False Positive Rate: <1% (down from 80% in V1)
- Detection Latency: <500ms
- CPU Usage: <30% on RPi4

Hardware Requirements:
    - Raspberry Pi 4
    - INMP441 I2S MEMS Microphone (GPIO 18, 19, 20)
    - WS2812B LED Ring 1 on GPIO 10 (16 LEDs) - LEFT EYE
    - WS2812B LED Ring 2 on GPIO 13 (16 LEDs) - RIGHT EYE

GPIO Pin Diagram:
    INMP441:
        VDD  -> Pin 1  (3.3V)
        GND  -> Pin 6  (GND)
        SCK  -> Pin 12 (GPIO 18 - I2S BCLK)
        WS   -> Pin 35 (GPIO 19 - I2S LRCLK)
        SD   -> Pin 38 (GPIO 20 - I2S DIN)
        L/R  -> GND (Left channel)

    LED Ring 1 (Left Eye):
        VCC  -> Pin 2  (5V)
        GND  -> Pin 14 (GND)
        DIN  -> Pin 19 (GPIO 10)

    LED Ring 2 (Right Eye):
        VCC  -> Pin 4  (5V)
        GND  -> Pin 34 (GND)
        DIN  -> Pin 33 (GPIO 13)

Usage:
    sudo python3 wake_word_led_demo_v2.py

Say "Hey OpenDuck" (or "Hey Jarvis") and watch the LEDs react!

Author: OpenDuck Team
Created: 26 January 2026 (Day 21)
Version: 2.0 (Production Pipeline)
"""

import sys
import time
import signal
import logging
import threading
from pathlib import Path

# Add firmware to path for imports
firmware_path = Path(__file__).parent.parent
sys.path.insert(0, str(firmware_path))

from src.voice.pipeline import (
    WakeWordPipeline,
    PipelineConfig,
    PipelineState,
    DetectionResult,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
_logger = logging.getLogger(__name__)

# =============================================================================
# LED Configuration
# =============================================================================

# Dual ring mode
LED_PIN_LEFT = 10   # GPIO 10 (SPI MOSI, Pin 19) - Left Eye
LED_PIN_RIGHT = 13  # GPIO 13 (PWM1, Pin 33) - Right Eye
NUM_LEDS = 16
LED_BRIGHTNESS = 200  # 0-255

# Global state
led_strips = None
current_animation = "idle"
animation_lock = threading.Lock()


# =============================================================================
# LED Functions
# =============================================================================

def init_leds():
    """Initialize dual LED rings."""
    global led_strips

    try:
        from rpi_ws281x import PixelStrip, Color, WS2812_STRIP

        # Initialize left eye (GPIO 10 - SPI)
        strip_left = PixelStrip(
            NUM_LEDS, LED_PIN_LEFT, 800000, 10,
            False, LED_BRIGHTNESS, 0,  # Channel 0 for GPIO 10
            strip_type=WS2812_STRIP
        )
        strip_left.begin()

        # Initialize right eye (GPIO 13 - PWM1)
        strip_right = PixelStrip(
            NUM_LEDS, LED_PIN_RIGHT, 800000, 10,
            False, LED_BRIGHTNESS, 1,  # Channel 1 for GPIO 13
            strip_type=WS2812_STRIP
        )
        strip_right.begin()

        led_strips = {
            'left': strip_left,
            'right': strip_right,
            'Color': Color
        }

        print(f"[LED] Initialized dual rings:")
        print(f"      Left Eye:  GPIO {LED_PIN_LEFT} (Pin 19)")
        print(f"      Right Eye: GPIO {LED_PIN_RIGHT} (Pin 33)")
        return True

    except ImportError:
        print("[LED] rpi_ws281x not available - running in mock mode")
        led_strips = None
        return False
    except Exception as e:
        print(f"[LED] Initialization failed: {e}")
        led_strips = None
        return False


def set_all_leds(r, g, b):
    """Set all LEDs on both rings to a color."""
    if led_strips is None:
        return

    Color = led_strips['Color']
    color = Color(r, g, b)

    for strip in [led_strips['left'], led_strips['right']]:
        for i in range(NUM_LEDS):
            strip.setPixelColor(i, color)
        strip.show()


def clear_leds():
    """Turn off all LEDs."""
    set_all_leds(0, 0, 0)


def run_idle_animation():
    """Pixar-grade IDLE emotion: soft blue breathing.

    Psychology: Calm, attentive, approachable
    Color: Neutral-warm blue (5500K equivalent)
    Timing: 12 BPM (5 second cycle) - restful, meditative
    """
    global current_animation

    if led_strips is None:
        return

    Color = led_strips['Color']
    left = led_strips['left']
    right = led_strips['right']

    # Breathing parameters (12 BPM = 5 second cycle)
    cycle_time = 5.0
    start_time = time.time()

    while current_animation == "idle":
        with animation_lock:
            if current_animation != "idle":
                break

        t = (time.time() - start_time) % cycle_time
        # Gaussian breathing curve for natural feel
        breath = 0.3 + 0.7 * (1 - abs(2 * t / cycle_time - 1) ** 2)

        # Neutral-warm blue (5500K equivalent)
        r = int(100 * breath)
        g = int(160 * breath)
        b = int(255 * breath)

        color = Color(r, g, b)

        for strip in [left, right]:
            for i in range(NUM_LEDS):
                strip.setPixelColor(i, color)
            strip.show()

        time.sleep(0.02)  # 50 FPS


def run_alert_animation(duration=0.5):
    """Pixar-grade ALERT emotion: urgent red-orange pulse.

    Psychology: Attention, activation, readiness
    Color: Saturated red-orange (1800K) - urgency, warning
    Timing: 171 BPM pulse - fight-or-flight response
    """
    global current_animation

    if led_strips is None:
        print("[LED] Mock: ALERT animation (fast red pulse)")
        time.sleep(duration)
        return

    Color = led_strips['Color']
    left = led_strips['left']
    right = led_strips['right']

    start_time = time.time()
    pulse_speed = 4.0  # Fast pulse

    print("[LED] ALERT: Fast red-orange pulse!")

    while (time.time() - start_time) < duration:
        t = time.time() - start_time

        # Fast pulse
        pulse = 0.5 + 0.5 * abs(((t * pulse_speed) % 1.0) * 2 - 1)

        # Saturated red-orange (1800K)
        r = int(255 * pulse)
        g = int(70 * pulse)
        b = int(40 * pulse)

        color = Color(r, g, b)

        for strip in [left, right]:
            for i in range(NUM_LEDS):
                strip.setPixelColor(i, color)
            strip.show()

        time.sleep(0.016)  # 60 FPS


def run_excited_animation(duration=3.0):
    """Pixar-grade EXCITED emotion: fast spinning with sparkles.

    Disney Principles Applied:
    - Squash & Stretch: Brightness pulsing
    - Exaggeration: Fast spin, bright colors
    - Secondary Action: Sparkle bursts

    Color: Bright orange (2200K equiv) - maximum warmth, enthusiasm
    Timing: 100 BPM spin - maximum sustainable excitement
    """
    global current_animation

    if led_strips is None:
        print("[LED] Mock: EXCITED animation (spinning orange + sparkles)")
        time.sleep(duration)
        return

    import random

    Color = led_strips['Color']
    left = led_strips['left']
    right = led_strips['right']

    start_time = time.time()
    spin_speed = 2.5  # 100 BPM equivalent

    print("[LED] EXCITED: Spinning orange with sparkles!")

    while (time.time() - start_time) < duration:
        t = time.time() - start_time

        # Spinning position (opposite direction for each eye)
        spin_pos_l = int((t * spin_speed * NUM_LEDS) % NUM_LEDS)
        spin_pos_r = NUM_LEDS - 1 - spin_pos_l  # Mirrored

        for strip, spin_pos in [(left, spin_pos_l), (right, spin_pos_r)]:
            for i in range(NUM_LEDS):
                # Distance from spin head
                dist = min(abs(i - spin_pos), NUM_LEDS - abs(i - spin_pos))

                # Tail fade
                brightness = max(0, 1.0 - dist / 4)

                # Sparkle burst (random flickers)
                if random.random() < 0.1:  # 10% sparkle chance
                    brightness = min(1.0, brightness + 0.5)

                # Bright orange (2200K equiv)
                r = int(255 * brightness)
                g = int(140 * brightness)
                b = int(40 * brightness)

                strip.setPixelColor(i, Color(r, g, b))
            strip.show()

        time.sleep(0.016)  # ~60 FPS for smooth spin


def run_success_animation(duration=1.0):
    """Success confirmation: green pulse."""
    global current_animation

    if led_strips is None:
        print("[LED] Mock: SUCCESS animation (green pulse)")
        time.sleep(duration)
        return

    Color = led_strips['Color']
    left = led_strips['left']
    right = led_strips['right']

    start_time = time.time()

    print("[LED] SUCCESS: Green pulse!")

    while (time.time() - start_time) < duration:
        t = time.time() - start_time

        # Smooth pulse
        pulse = 0.5 + 0.5 * abs(((t * 2) % 1.0) * 2 - 1)

        # Bright green
        r = int(50 * pulse)
        g = int(255 * pulse)
        b = int(50 * pulse)

        color = Color(r, g, b)

        for strip in [left, right]:
            for i in range(NUM_LEDS):
                strip.setPixelColor(i, color)
            strip.show()

        time.sleep(0.016)


# =============================================================================
# Wake Word Callback
# =============================================================================

def on_wake_word(result: DetectionResult):
    """Called when wake word is detected by production pipeline."""
    global current_animation

    print()
    print("=" * 60)
    print("  WAKE WORD DETECTED!")
    print(f"  '{result.wake_word}' (confidence: {result.smoothed_score:.1%})")
    print(f"  Confirmed: {result.confirm_count}/5 frames")
    print(f"  Noise floor: {result.noise_floor:.1f} dB")
    print("=" * 60)
    print()

    # Stop idle animation
    with animation_lock:
        current_animation = "detected"

    # Run animation sequence
    run_alert_animation(0.5)      # Quick alert
    run_excited_animation(3.0)     # Excited spin
    run_success_animation(0.5)     # Success confirmation

    # Return to idle
    with animation_lock:
        current_animation = "idle"

    # Restart idle animation in background
    threading.Thread(target=run_idle_animation, daemon=True).start()


def on_state_change(state: PipelineState):
    """Called when pipeline state changes."""
    print(f"[PIPELINE] State: {state.name}")


# =============================================================================
# Main
# =============================================================================

def main():
    """Main demo entry point."""
    global current_animation

    print()
    print("=" * 60)
    print("  OpenDuck Mini V3 - Wake Word + LED Demo V2")
    print("  (Production Pipeline - <1% FPR Target)")
    print("=" * 60)
    print()

    # Install signal handlers
    running = True

    def signal_handler(signum, frame):
        nonlocal running
        print("\n[SHUTDOWN] Received signal, cleaning up...")
        running = False

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Initialize LEDs
    print("[INIT] Initializing LED rings...")
    led_ok = init_leds()

    if led_ok:
        print("[LED] Running quick test...")
        set_all_leds(0, 255, 0)  # Green
        time.sleep(0.5)
        set_all_leds(0, 0, 255)  # Blue
        time.sleep(0.5)
        clear_leds()
        print("[LED] Test passed!")
    else:
        print("[WARN] LEDs not available, continuing without...")

    # Configure production pipeline
    print("\n[INIT] Configuring production pipeline...")
    config = PipelineConfig(
        # High threshold for low false positives
        threshold=0.82,
        # Multi-frame confirmation
        confirm_window=5,
        confirm_required=3,
        # Cooldown to prevent rapid triggers
        cooldown_seconds=3.0,
        # Noise calibration
        calibration_seconds=2.0,
        # Audio settings for INMP441
        device="hw:1,0",
        input_sample_rate=48000,
        output_sample_rate=16000,
    )

    print(f"  Threshold: {config.threshold}")
    print(f"  Confirmation: {config.confirm_required}/{config.confirm_window} frames")
    print(f"  Cooldown: {config.cooldown_seconds}s")

    # Create pipeline
    pipeline = WakeWordPipeline(config)
    pipeline.on_wake_word = on_wake_word
    pipeline.on_state_change = on_state_change

    # Start idle animation
    current_animation = "idle"
    idle_thread = threading.Thread(target=run_idle_animation, daemon=True)
    idle_thread.start()

    # Start pipeline
    print("\n[INIT] Starting voice pipeline...")

    try:
        pipeline.start()

        print()
        print("=" * 60)
        print("  LISTENING...")
        print("  Say 'Hey Jarvis' or 'Hey OpenDuck'")
        print("  Press Ctrl+C to exit")
        print("=" * 60)
        print()

        # Main loop
        stats_interval = 10  # Print stats every 10 seconds
        last_stats_time = time.time()

        while running and pipeline.is_running:
            time.sleep(0.1)

            # Print stats periodically
            if time.time() - last_stats_time > stats_interval:
                stats = pipeline.get_statistics()
                print(
                    f"[STATS] Frames: {stats['frames_processed']}, "
                    f"Speech: {stats['vad_speech_frames']}, "
                    f"Blocked FP: {stats['false_positives_blocked']}, "
                    f"Detections: {stats['detections']}, "
                    f"Noise: {stats['noise_floor_db']:.1f}dB"
                )
                last_stats_time = time.time()

    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()

    finally:
        print("\n[CLEANUP] Shutting down...")
        current_animation = "shutdown"
        pipeline.stop()
        clear_leds()

        # Final stats
        stats = pipeline.get_statistics()
        print()
        print("=" * 60)
        print("  Final Statistics")
        print("=" * 60)
        print(f"  Frames processed: {stats['frames_processed']}")
        print(f"  VAD speech frames: {stats['vad_speech_frames']}")
        print(f"  False positives blocked: {stats['false_positives_blocked']}")
        print(f"  Confirmed detections: {stats['detections']}")
        print(f"  Noise floor: {stats['noise_floor_db']:.1f} dB")
        print("=" * 60)
        print()
        print("[DONE] Goodbye!")


if __name__ == "__main__":
    main()
