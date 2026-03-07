#!/usr/bin/env python3
"""Wake Word + LED Integration Demo for OpenDuck Mini V3

Demonstrates the full voice-to-LED pipeline:
1. Listens for "Hey OpenDuck" wake word via INMP441 microphone
2. When detected, triggers Pixar-grade EXCITED LED animation
3. Smooth emotion transitions using the emotion system

NOTE: This version uses ONLY LED Ring 2 (GPIO 13) to avoid conflict with
      INMP441 microphone which uses GPIO 18 for I2S BCLK.

      For dual-ring operation, move LED Ring 1 from GPIO 18 to GPIO 10.

Hardware Requirements:
    - Raspberry Pi 4
    - INMP441 I2S MEMS Microphone (GPIO 18, 19, 20)
    - WS2812B LED Ring 2 on GPIO 13 (16 LEDs) - RIGHT EYE ONLY

GPIO Pin Diagram:
    INMP441:
        VDD  -> Pin 1  (3.3V)
        GND  -> Pin 6  (GND)
        SCK  -> Pin 12 (GPIO 18 - I2S BCLK)
        WS   -> Pin 35 (GPIO 19 - I2S LRCLK)
        SD   -> Pin 38 (GPIO 20 - I2S DIN)
        L/R  -> GND (Left channel)

    LED Ring 2 (Right Eye) - ACTIVE:
        VCC  -> Pin 4  (5V)
        GND  -> Pin 34 (GND)
        DIN  -> Pin 33 (GPIO 13)

Usage:
    sudo python3 wake_word_led_demo.py

Say "Hey OpenDuck" (or "Hey Jarvis") and watch the LED react!

Author: OpenDuck Team
Created: 21 January 2026 (Day 21)
"""

import sys
import time
import signal
import logging
import threading

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
_logger = logging.getLogger(__name__)

# LED Constants - SINGLE RING MODE (Right Eye only, no I2S conflict)
LED_PIN = 13        # GPIO 13 (PWM1, Pin 33) - NO CONFLICT with I2S
NUM_LEDS = 16
LED_BRIGHTNESS = 200  # 0-255

# Audio Constants
SAMPLE_RATE = 16000
CHUNK_SIZE = 1280  # 80ms at 16kHz (OpenWakeWord optimal)

# Global state
running = True
led_strip = None
current_emotion = "idle"


def signal_handler(signum, frame):
    """Handle shutdown signals."""
    global running
    print("\n[SHUTDOWN] Received signal, cleaning up...")
    running = False


def init_leds():
    """Initialize LED strip (single ring mode)."""
    global led_strip

    try:
        from rpi_ws281x import PixelStrip, Color

        # Initialize single LED strip (Right Eye - GPIO 13)
        strip = PixelStrip(
            NUM_LEDS, LED_PIN, 800000, 10,
            False, LED_BRIGHTNESS, 1  # Channel 1 for GPIO 13
        )
        strip.begin()

        led_strip = {
            'strip': strip,
            'Color': Color
        }

        print(f"[LED] Initialized: Right Eye on GPIO {LED_PIN} (Pin 33)")
        print("[LED] Note: Single-ring mode (Left Eye disabled to avoid I2S conflict)")
        return True

    except ImportError:
        print("[LED] rpi_ws281x not available - running in mock mode")
        led_strip = None
        return False
    except Exception as e:
        print(f"[LED] Initialization failed: {e}")
        led_strip = None
        return False


def set_all_leds(r, g, b):
    """Set all LEDs to a color."""
    if led_strip is None:
        return

    Color = led_strip['Color']
    strip = led_strip['strip']
    color = Color(r, g, b)

    for i in range(NUM_LEDS):
        strip.setPixelColor(i, color)
    strip.show()


def clear_leds():
    """Turn off all LEDs."""
    set_all_leds(0, 0, 0)


def run_idle_animation():
    """Pixar-grade IDLE emotion: soft blue breathing."""
    global current_emotion

    if led_strip is None:
        return

    Color = led_strip['Color']
    strip = led_strip['strip']

    # Breathing parameters (12 BPM = 5 second cycle)
    cycle_time = 5.0
    start_time = time.time()

    while running and current_emotion == "idle":
        t = (time.time() - start_time) % cycle_time
        # Gaussian breathing curve
        breath = 0.3 + 0.7 * (1 - abs(2 * t / cycle_time - 1) ** 2)

        # Neutral-warm blue (5500K equiv)
        r = int(100 * breath)
        g = int(160 * breath)
        b = int(255 * breath)

        color = Color(r, g, b)
        for i in range(NUM_LEDS):
            strip.setPixelColor(i, color)
        strip.show()

        time.sleep(0.02)  # 50 FPS


def run_excited_animation(duration=3.0):
    """Pixar-grade EXCITED emotion: fast spinning with sparkles.

    Disney Principles Applied:
    - Squash & Stretch: Brightness pulsing
    - Exaggeration: Fast spin, bright colors
    - Secondary Action: Sparkle bursts

    Color: Bright orange (2200K equiv) - maximum warmth, enthusiasm
    Timing: 100 BPM spin - maximum sustainable excitement
    """
    global current_emotion

    if led_strip is None:
        print("[LED] Mock: EXCITED animation (spinning orange + sparkles)")
        time.sleep(duration)
        return

    Color = led_strip['Color']
    strip = led_strip['strip']
    current_emotion = "excited"

    start_time = time.time()
    spin_speed = 2.5  # 100 BPM equivalent

    print("[LED] EXCITED: Spinning orange with sparkles!")

    while running and (time.time() - start_time) < duration:
        t = time.time() - start_time

        # Spinning position
        spin_pos = int((t * spin_speed * NUM_LEDS) % NUM_LEDS)

        for i in range(NUM_LEDS):
            # Distance from spin head
            dist = min(abs(i - spin_pos), NUM_LEDS - abs(i - spin_pos))

            # Tail fade
            brightness = max(0, 1.0 - dist / 4)

            # Sparkle burst (random flickers)
            import random
            if random.random() < 0.1:  # 10% sparkle chance
                brightness = min(1.0, brightness + 0.5)

            # Bright orange (2200K equiv)
            r = int(255 * brightness)
            g = int(140 * brightness)
            b = int(40 * brightness)

            strip.setPixelColor(i, Color(r, g, b))
        strip.show()

        time.sleep(0.016)  # ~60 FPS for smooth spin

    # Transition back to idle
    print("[LED] Transitioning back to IDLE...")
    current_emotion = "idle"


def run_alert_animation(duration=0.5):
    """Pixar-grade ALERT emotion: urgent red-orange pulse.

    Color: Saturated red-orange (1800K) - urgency, warning
    Timing: 171 BPM pulse - fight-or-flight response
    """
    global current_emotion

    if led_strip is None:
        print("[LED] Mock: ALERT animation (fast red pulse)")
        time.sleep(duration)
        return

    Color = led_strip['Color']
    strip = led_strip['strip']
    current_emotion = "alert"

    start_time = time.time()
    pulse_speed = 4.0  # Fast pulse

    print("[LED] ALERT: Fast red-orange pulse!")

    while running and (time.time() - start_time) < duration:
        t = time.time() - start_time

        # Fast pulse
        pulse = 0.5 + 0.5 * abs(((t * pulse_speed) % 1.0) * 2 - 1)

        # Saturated red-orange (1800K)
        r = int(255 * pulse)
        g = int(70 * pulse)
        b = int(40 * pulse)

        color = Color(r, g, b)
        for i in range(NUM_LEDS):
            strip.setPixelColor(i, color)
        strip.show()

        time.sleep(0.016)  # 60 FPS


def init_audio():
    """Initialize audio capture."""
    try:
        import sounddevice as sd

        # Find INMP441 device
        devices = sd.query_devices()
        input_device = None

        for i, dev in enumerate(devices):
            name = dev['name'].lower()
            if 'i2s' in name or 'inmp' in name or 'googlevoicehat' in name or 'adau' in name:
                input_device = i
                print(f"[AUDIO] Found I2S device: {dev['name']}")
                break

        if input_device is None:
            # Use default input
            input_device = sd.default.device[0]
            if input_device is not None:
                print(f"[AUDIO] Using default: {devices[input_device]['name']}")
            else:
                print("[AUDIO] No input device found!")
                return None

        return input_device

    except Exception as e:
        print(f"[AUDIO] Init failed: {e}")
        return None


def init_wake_word():
    """Initialize OpenWakeWord detector."""
    try:
        import openwakeword
        from openwakeword.model import Model

        # Get the hey_jarvis model path
        model_paths = openwakeword.get_pretrained_model_paths()
        hey_jarvis_path = None

        for path in model_paths:
            if 'hey_jarvis' in path.lower():
                hey_jarvis_path = path
                break

        if hey_jarvis_path is None:
            print("[WAKE] hey_jarvis model not found in cache")
            print("[WAKE] Available models:", model_paths)
            return None

        # Create model
        model = Model(
            wakeword_model_paths=[hey_jarvis_path],
            inference_framework="onnx"
        )

        print(f"[WAKE] OpenWakeWord initialized!")
        print("[WAKE] Say: 'Hey OpenDuck', 'Hey Jarvis', 'Hey Ducky', or 'Hey Paperella'")
        return model

    except ImportError:
        print("[WAKE] OpenWakeWord not installed")
        print("[WAKE] Install with: pip install openwakeword")
        return None
    except Exception as e:
        print(f"[WAKE] Init failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def wake_word_callback(wake_word, score):
    """Called when wake word is detected."""
    global current_emotion

    print(f"\n{'='*50}")
    print(f"  WAKE WORD DETECTED!")
    print(f"  '{wake_word}' (confidence: {score:.1%})")
    print(f"{'='*50}\n")

    # Trigger LED animation sequence
    current_emotion = "alert"

    # Run animation sequence
    run_alert_animation(0.5)   # Quick alert first
    run_excited_animation(3.0)  # Then excited spin

    # Return to idle
    current_emotion = "idle"


def main():
    """Main demo entry point."""
    global running, current_emotion

    print()
    print("="*50)
    print("  OpenDuck Mini V3 - Wake Word + LED Demo")
    print("  (Single Ring Mode - Right Eye Only)")
    print("="*50)
    print()

    # Install signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Initialize LEDs
    print("[INIT] Initializing LED Ring 2 (GPIO 13)...")
    led_ok = init_leds()

    if led_ok:
        # Quick LED test
        print("[LED] Running quick test...")
        set_all_leds(0, 255, 0)  # Green
        time.sleep(0.5)
        set_all_leds(0, 0, 255)  # Blue
        time.sleep(0.5)
        clear_leds()
        print("[LED] Test passed!")

    # Initialize wake word
    print("\n[INIT] Initializing wake word detector...")
    wake_model = init_wake_word()

    if wake_model is None:
        print("[WARN] Wake word detector not available")
        print("[WARN] Running in LED demo mode only\n")

        # Demo mode: simulate detection every 5 seconds
        try:
            current_emotion = "idle"
            idle_thread = threading.Thread(target=run_idle_animation, daemon=True)
            idle_thread.start()

            while running:
                print("\n[DEMO] Simulating wake word detection in 5 seconds...")
                time.sleep(5)
                if running:
                    wake_word_callback("Hey OpenDuck", 0.95)
                    # Restart idle animation
                    idle_thread = threading.Thread(target=run_idle_animation, daemon=True)
                    idle_thread.start()
        except KeyboardInterrupt:
            pass
        finally:
            clear_leds()
            print("\n[DONE] Goodbye!")
        return

    # Initialize audio
    print("\n[INIT] Initializing audio capture...")
    audio_device = init_audio()

    if audio_device is None:
        print("[ERROR] Could not initialize audio")
        clear_leds()
        return

    # Start idle animation in background
    current_emotion = "idle"
    idle_thread = threading.Thread(target=run_idle_animation, daemon=True)
    idle_thread.start()

    # Main audio loop
    print("\n" + "="*50)
    print("  LISTENING...")
    print("  Say 'Hey Jarvis' or 'Hey OpenDuck'")
    print("  Press Ctrl+C to exit")
    print("="*50 + "\n")

    try:
        import sounddevice as sd
        import numpy as np

        detection_threshold = 0.5

        def audio_callback(indata, frames, time_info, status):
            global current_emotion

            if status:
                _logger.debug(f"Audio status: {status}")

            if current_emotion != "idle":
                return  # Don't process during animations

            # Convert to int16 for OpenWakeWord
            audio_int16 = (indata[:, 0] * 32767).astype(np.int16)

            # Run wake word detection
            prediction = wake_model.predict(audio_int16)

            # Check for detection
            for model_name, score in prediction.items():
                if score > detection_threshold:
                    # Run callback in separate thread to not block audio
                    threading.Thread(
                        target=wake_word_callback,
                        args=("Hey OpenDuck", score)
                    ).start()
                    wake_model.reset()  # Reset to prevent re-trigger
                    break

        # Start audio stream
        with sd.InputStream(
            device=audio_device,
            channels=1,
            samplerate=SAMPLE_RATE,
            blocksize=CHUNK_SIZE,
            dtype=np.float32,
            callback=audio_callback
        ):
            while running:
                time.sleep(0.1)

    except Exception as e:
        print(f"\n[ERROR] Audio loop failed: {e}")
        import traceback
        traceback.print_exc()

    finally:
        print("\n[CLEANUP] Shutting down...")
        running = False
        time.sleep(0.1)
        clear_leds()
        print("[DONE] Goodbye!")


if __name__ == "__main__":
    main()
