#!/usr/bin/env python3
"""
OpenDuck Mini V3 - LED Developer CLI Tool
==========================================
Boston Dynamics Quality Developer Tools for LED Pattern Development

Commands:
  preview    - Test LED patterns without hardware (mock mode)
  profile    - Performance profiling (FPS, jitter, frame time)
  validate   - Configuration validation
  emotions   - Display emotion state machine diagram
  record     - Record pattern timing data to file

Usage Examples:
  led_cli.py preview happy --duration 5 --no-hardware
  led_cli.py profile rainbow --timing --frames 250
  led_cli.py validate config/hardware_config.yaml
  led_cli.py emotions --graph
  led_cli.py record breathing --output data/breathing_profile.json

Author: OpenDuck V3 Team
Date: 17 January 2026
"""

import sys
import time
import argparse
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
from dataclasses import dataclass, asdict
import statistics

# Try to import hardware library, fallback to mock
try:
    from rpi_ws281x import PixelStrip, Color as HardwareColor
    HARDWARE_AVAILABLE = True
except ImportError:
    HARDWARE_AVAILABLE = False
    print("[INFO] rpi_ws281x not available - using mock mode")


# =============================================================================
# MOCK HARDWARE (For Development Without Raspberry Pi)
# =============================================================================

class MockPixelStrip:
    """Mock LED strip for development without hardware"""

    def __init__(self, num_leds, pin, freq, dma, invert, brightness, channel):
        self.num_leds = num_leds
        self.pin = pin
        self.brightness = brightness
        self.channel = channel
        self.pixels = [(0, 0, 0)] * num_leds
        self._show_count = 0

    def begin(self):
        """Initialize (no-op for mock)"""
        pass

    def numPixels(self):
        """Return number of pixels"""
        return self.num_leds

    def setPixelColor(self, n, color):
        """Set pixel color"""
        if 0 <= n < self.num_leds:
            # Extract RGB from packed color
            r = (color >> 16) & 0xFF
            g = (color >> 8) & 0xFF
            b = color & 0xFF
            self.pixels[n] = (r, g, b)

    def show(self):
        """Update display (no-op for mock, just count calls)"""
        self._show_count += 1

    def get_show_count(self):
        """Get number of show() calls (for profiling)"""
        return self._show_count

    def get_pixels(self):
        """Get current pixel state"""
        return self.pixels.copy()


def MockColor(r, g, b):
    """Mock Color function - packs RGB into 24-bit integer"""
    return (int(r) << 16) | (int(g) << 8) | int(b)


# =============================================================================
# PROFILER
# =============================================================================

@dataclass
class FrameStats:
    """Frame timing statistics"""
    frame_number: int
    compute_time_ms: float
    spi_time_ms: float
    total_time_ms: float
    target_time_ms: float
    overrun: bool

    def to_dict(self):
        """Convert to dictionary"""
        return asdict(self)


class FrameProfiler:
    """
    Professional frame profiler for LED animations.
    Tracks compute time, SPI transfer time, jitter, and FPS.
    """

    def __init__(self, target_fps: int = 50):
        self.target_fps = target_fps
        self.target_frame_time = 1.0 / target_fps

        # Timing data
        self.frame_stats: List[FrameStats] = []
        self.frame_start_time = 0.0
        self.compute_end_time = 0.0

        # Metrics
        self.current_frame = 0

    def start_frame(self):
        """Mark start of frame"""
        self.frame_start_time = time.perf_counter()
        self.current_frame += 1

    def mark_compute_done(self):
        """Mark end of computation phase"""
        self.compute_end_time = time.perf_counter()

    def mark_spi_done(self):
        """Mark end of SPI transfer phase"""
        spi_end_time = time.perf_counter()

        # Calculate timings
        compute_time = (self.compute_end_time - self.frame_start_time) * 1000
        spi_time = (spi_end_time - self.compute_end_time) * 1000
        total_time = (spi_end_time - self.frame_start_time) * 1000

        # Check for overrun
        overrun = total_time > (self.target_frame_time * 1000)

        # Record stats
        stats = FrameStats(
            frame_number=self.current_frame,
            compute_time_ms=compute_time,
            spi_time_ms=spi_time,
            total_time_ms=total_time,
            target_time_ms=self.target_frame_time * 1000,
            overrun=overrun
        )
        self.frame_stats.append(stats)

    def get_summary(self) -> Dict:
        """Get summary statistics"""
        if not self.frame_stats:
            return {}

        compute_times = [s.compute_time_ms for s in self.frame_stats]
        spi_times = [s.spi_time_ms for s in self.frame_stats]
        total_times = [s.total_time_ms for s in self.frame_stats]

        overruns = sum(1 for s in self.frame_stats if s.overrun)

        return {
            'target_fps': self.target_fps,
            'target_frame_time_ms': self.target_frame_time * 1000,
            'frames_recorded': len(self.frame_stats),
            'overruns': overruns,
            'overrun_rate': overruns / len(self.frame_stats) * 100,

            # Compute stats
            'compute_avg_ms': statistics.mean(compute_times),
            'compute_min_ms': min(compute_times),
            'compute_max_ms': max(compute_times),
            'compute_stdev_ms': statistics.stdev(compute_times) if len(compute_times) > 1 else 0,

            # SPI stats
            'spi_avg_ms': statistics.mean(spi_times),
            'spi_min_ms': min(spi_times),
            'spi_max_ms': max(spi_times),
            'spi_stdev_ms': statistics.stdev(spi_times) if len(spi_times) > 1 else 0,

            # Total frame stats
            'frame_avg_ms': statistics.mean(total_times),
            'frame_min_ms': min(total_times),
            'frame_max_ms': max(total_times),
            'frame_stdev_ms': statistics.stdev(total_times) if len(total_times) > 1 else 0,

            # Jitter
            'jitter_ms': statistics.stdev(total_times) if len(total_times) > 1 else 0,

            # Actual FPS
            'actual_fps': 1000.0 / statistics.mean(total_times) if total_times else 0,
        }

    def print_report(self):
        """Print formatted profiling report"""
        summary = self.get_summary()

        if not summary:
            print("No profiling data recorded")
            return

        print("\n" + "="*70)
        print("                    FRAME PROFILING REPORT")
        print("="*70)
        print(f"\n  Target Performance:")
        print(f"    FPS: {summary['target_fps']} Hz")
        print(f"    Frame Time: {summary['target_frame_time_ms']:.2f} ms")

        print(f"\n  Actual Performance:")
        print(f"    FPS: {summary['actual_fps']:.2f} Hz")
        print(f"    Frame Time: {summary['frame_avg_ms']:.2f} ms (avg)")
        print(f"    Jitter: ±{summary['jitter_ms']:.2f} ms")

        print(f"\n  Frame Breakdown (avg):")
        print(f"    Compute:  {summary['compute_avg_ms']:6.2f} ms  ({summary['compute_avg_ms']/summary['frame_avg_ms']*100:.1f}%)")
        print(f"    SPI:      {summary['spi_avg_ms']:6.2f} ms  ({summary['spi_avg_ms']/summary['frame_avg_ms']*100:.1f}%)")
        print(f"    Total:    {summary['frame_avg_ms']:6.2f} ms")

        print(f"\n  Timing Range:")
        print(f"    Compute:  {summary['compute_min_ms']:.2f} - {summary['compute_max_ms']:.2f} ms  (σ={summary['compute_stdev_ms']:.2f})")
        print(f"    SPI:      {summary['spi_min_ms']:.2f} - {summary['spi_max_ms']:.2f} ms  (σ={summary['spi_stdev_ms']:.2f})")
        print(f"    Total:    {summary['frame_min_ms']:.2f} - {summary['frame_max_ms']:.2f} ms  (σ={summary['frame_stdev_ms']:.2f})")

        print(f"\n  Frame Overruns:")
        print(f"    Count: {summary['overruns']} / {summary['frames_recorded']} frames")
        print(f"    Rate:  {summary['overrun_rate']:.1f}%")

        if summary['overrun_rate'] > 0:
            print(f"\n  ⚠️  WARNING: {summary['overrun_rate']:.1f}% of frames exceeded target time!")

        if summary['jitter_ms'] > 1.0:
            print(f"  ⚠️  WARNING: High jitter detected ({summary['jitter_ms']:.2f} ms)")

        if summary['actual_fps'] < summary['target_fps'] * 0.95:
            print(f"  ⚠️  WARNING: Actual FPS below target ({summary['actual_fps']:.1f} vs {summary['target_fps']})")

        print("\n" + "="*70)

    def export_json(self, filename: str):
        """Export profiling data to JSON file"""
        data = {
            'summary': self.get_summary(),
            'frames': [s.to_dict() for s in self.frame_stats]
        }

        Path(filename).parent.mkdir(parents=True, exist_ok=True)
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)

        print(f"\n[SAVED] Profiling data exported to: {filename}")


# =============================================================================
# PRECISION TIMER
# =============================================================================

class PrecisionTimer:
    """
    Precision frame timer using monotonic clock.
    Prevents drift and eliminates jitter.
    """

    def __init__(self, target_fps: int = 50):
        self.frame_time = 1.0 / target_fps
        self.next_frame = time.monotonic()
        self.overruns = 0

    def wait_for_next_frame(self) -> bool:
        """
        Sleep until next frame boundary.
        Returns True if on time, False if frame overrun occurred.
        """
        now = time.monotonic()
        sleep_time = self.next_frame - now

        if sleep_time > 0:
            time.sleep(sleep_time)
            self.next_frame += self.frame_time
            return True
        else:
            # Frame overrun - reset to prevent death spiral
            self.overruns += 1
            self.next_frame = time.monotonic() + self.frame_time
            return False


# =============================================================================
# ANIMATION ENGINE (with Profiling)
# =============================================================================

class LEDAnimationEngine:
    """
    LED animation engine with profiling support.
    Works with both real and mock hardware.
    """

    def __init__(self, use_hardware: bool = True, num_leds: int = 16,
                 left_pin: int = 18, right_pin: int = 13, brightness: int = 60):
        self.num_leds = num_leds
        self.use_hardware = use_hardware and HARDWARE_AVAILABLE

        if self.use_hardware:
            print(f"[HARDWARE] Initializing real LED strips...")
            self.left_eye = PixelStrip(num_leds, left_pin, 800000, 10, False, brightness, 0)
            self.right_eye = PixelStrip(num_leds, right_pin, 800000, 10, False, brightness, 1)
            self.Color = HardwareColor

            self.left_eye.begin()
            self.right_eye.begin()
        else:
            print(f"[MOCK] Using mock LED strips (no hardware)")
            self.left_eye = MockPixelStrip(num_leds, left_pin, 800000, 10, False, brightness, 0)
            self.right_eye = MockPixelStrip(num_leds, right_pin, 800000, 10, False, brightness, 1)
            self.Color = MockColor

    def set_all(self, strip, r, g, b):
        """Set all LEDs on a strip"""
        for i in range(strip.numPixels()):
            strip.setPixelColor(i, self.Color(int(r), int(g), int(b)))

    def set_both(self, r, g, b):
        """Set both eyes to same color"""
        self.set_all(self.left_eye, r, g, b)
        self.set_all(self.right_eye, r, g, b)
        self.left_eye.show()
        self.right_eye.show()

    def clear_both(self):
        """Turn off both eyes"""
        self.set_both(0, 0, 0)

    @staticmethod
    def ease_in_out(t):
        """Smooth easing function"""
        if t < 0.5:
            return 2 * t * t
        return 1 - pow(-2 * t + 2, 2) / 2

    @staticmethod
    def lerp(a, b, t):
        """Linear interpolation"""
        return a + (b - a) * t

    def breathing_pattern(self, color: Tuple[int, int, int], frames: int, profiler: Optional[FrameProfiler] = None):
        """Breathing animation with optional profiling"""
        r, g, b = color
        timer = PrecisionTimer(50)

        for i in range(frames):
            if profiler:
                profiler.start_frame()

            # Compute phase
            t = self.ease_in_out((i % 100) / 100)
            brightness = 0.3 + 0.7 * t

            if profiler:
                profiler.mark_compute_done()

            # SPI transfer phase
            self.set_both(r * brightness, g * brightness, b * brightness)

            if profiler:
                profiler.mark_spi_done()

            # Wait for next frame
            timer.wait_for_next_frame()

    def rainbow_pattern(self, frames: int, profiler: Optional[FrameProfiler] = None):
        """Rainbow animation with optional profiling"""
        timer = PrecisionTimer(50)

        for frame in range(frames):
            if profiler:
                profiler.start_frame()

            # Compute phase
            for i in range(self.num_leds):
                hue = ((i * 256 // self.num_leds) + (frame * 5)) % 256
                r, g, b = self.hsv_to_rgb(hue / 255, 1.0, 1.0)
                self.left_eye.setPixelColor(i, self.Color(int(r*255), int(g*255), int(b*255)))
                self.right_eye.setPixelColor(self.num_leds - 1 - i, self.Color(int(r*255), int(g*255), int(b*255)))

            if profiler:
                profiler.mark_compute_done()

            # SPI transfer phase
            self.left_eye.show()
            self.right_eye.show()

            if profiler:
                profiler.mark_spi_done()

            # Wait for next frame
            timer.wait_for_next_frame()

    @staticmethod
    def hsv_to_rgb(h, s, v):
        """Convert HSV to RGB"""
        if s == 0:
            return v, v, v

        i = int(h * 6)
        f = (h * 6) - i
        p = v * (1 - s)
        q = v * (1 - s * f)
        t = v * (1 - s * (1 - f))
        i = i % 6

        if i == 0: return v, t, p
        if i == 1: return q, v, p
        if i == 2: return p, v, t
        if i == 3: return p, q, v
        if i == 4: return t, p, v
        if i == 5: return v, p, q


# =============================================================================
# CLI COMMANDS
# =============================================================================

EMOTION_COLORS = {
    'idle': (100, 150, 255),
    'happy': (255, 220, 50),
    'curious': (50, 255, 150),
    'alert': (255, 100, 50),
    'sleepy': (150, 100, 200),
    'excited': (255, 50, 150),
    'thinking': (200, 200, 255),
}


def cmd_preview(args):
    """Preview LED patterns"""
    print(f"\n[PREVIEW MODE] Pattern: {args.pattern}")
    print(f"  Duration: {args.duration}s")
    print(f"  Hardware: {'DISABLED (mock mode)' if args.no_hardware else 'ENABLED'}")

    engine = LEDAnimationEngine(use_hardware=not args.no_hardware)

    if args.pattern == 'breathing':
        color = EMOTION_COLORS.get(args.emotion, EMOTION_COLORS['idle'])
        frames = int(args.duration * 50)
        print(f"  Emotion: {args.emotion} {color}")
        engine.breathing_pattern(color, frames)

    elif args.pattern == 'rainbow':
        frames = int(args.duration * 50)
        engine.rainbow_pattern(frames)

    else:
        print(f"ERROR: Unknown pattern '{args.pattern}'")
        return 1

    engine.clear_both()
    print("\n[COMPLETE] Preview finished")
    return 0


def cmd_profile(args):
    """Profile LED pattern performance"""
    print(f"\n[PROFILING MODE] Pattern: {args.pattern}")
    print(f"  Frames: {args.frames}")
    print(f"  Target FPS: 50 Hz")
    print(f"  Hardware: {'DISABLED (mock mode)' if args.no_hardware else 'ENABLED'}")

    engine = LEDAnimationEngine(use_hardware=not args.no_hardware)
    profiler = FrameProfiler(target_fps=50)

    print(f"\n[RUNNING] Capturing {args.frames} frames...")

    if args.pattern == 'breathing':
        color = EMOTION_COLORS.get(args.emotion, EMOTION_COLORS['idle'])
        engine.breathing_pattern(color, args.frames, profiler)

    elif args.pattern == 'rainbow':
        engine.rainbow_pattern(args.frames, profiler)

    else:
        print(f"ERROR: Unknown pattern '{args.pattern}'")
        return 1

    engine.clear_both()

    # Show report
    profiler.print_report()

    # Export if requested
    if args.output:
        profiler.export_json(args.output)

    return 0


def cmd_validate(args):
    """Validate configuration files"""
    print(f"\n[VALIDATION] Config file: {args.config}")

    config_path = Path(args.config)

    if not config_path.exists():
        print(f"ERROR: Config file not found: {args.config}")
        return 1

    # Try to load and validate
    try:
        import yaml
        with open(config_path) as f:
            config = yaml.safe_load(f)

        print(f"[OK] YAML syntax valid")

        # Validate structure (basic checks)
        if 'led' in config:
            led_config = config['led']
            print(f"\n  LED Configuration:")
            print(f"    Left Eye GPIO:  {led_config.get('left_eye_gpio', 'MISSING')}")
            print(f"    Right Eye GPIO: {led_config.get('right_eye_gpio', 'MISSING')}")
            print(f"    LEDs per ring:  {led_config.get('num_leds', 'MISSING')}")
            print(f"    Brightness:     {led_config.get('brightness', 'MISSING')}")

            # Check for conflicts
            left_gpio = led_config.get('left_eye_gpio')
            right_gpio = led_config.get('right_eye_gpio')

            if left_gpio == right_gpio:
                print(f"\n  ⚠️  WARNING: Both eyes on same GPIO pin ({left_gpio})!")

            # Check for I2S conflict
            if 'audio' in config and config['audio'].get('enabled'):
                if left_gpio == 18 or right_gpio == 18:
                    print(f"\n  ⚠️  WARNING: GPIO 18 conflict with I2S audio!")
                    print(f"      Disable audio or move LED to different GPIO")

        print(f"\n[COMPLETE] Validation finished")
        return 0

    except yaml.YAMLError as e:
        print(f"ERROR: Invalid YAML syntax: {e}")
        return 1
    except Exception as e:
        print(f"ERROR: Validation failed: {e}")
        return 1


def cmd_emotions(args):
    """Display emotion state machine"""
    print("\n" + "="*70)
    print("                    EMOTION STATE MACHINE")
    print("="*70)

    print("\n  Available Emotions:")
    for emotion, color in EMOTION_COLORS.items():
        print(f"    {emotion:12s}  RGB{color}")

    print("\n  State Transitions:")
    print("    idle → alert       (loud noise detected)")
    print("    idle → curious     (movement detected)")
    print("    curious → happy    (face recognized)")
    print("    happy → excited    (positive interaction)")
    print("    * → sleepy         (low battery, idle timeout)")
    print("    * → alert          (emergency event)")

    if args.graph:
        print("\n  ASCII State Diagram:")
        print("""
        ┌─────────┐
        │  IDLE   │◄──────────┐
        └────┬────┘           │
             │                │
        ┌────┴─────┐    ┌─────┴──────┐
        │  ALERT   │    │  CURIOUS   │
        └──────────┘    └─────┬──────┘
                              │
                        ┌─────┴──────┐
                        │   HAPPY    │
                        └─────┬──────┘
                              │
                        ┌─────┴──────┐
                        │  EXCITED   │
                        └────────────┘

        SLEEPY ◄── (low battery, timeout from any state)
        """)

    print("="*70 + "\n")
    return 0


def cmd_record(args):
    """Record pattern timing to file"""
    print(f"\n[RECORD MODE] Pattern: {args.pattern}")
    print(f"  Duration: {args.duration}s")
    print(f"  Output: {args.output}")

    engine = LEDAnimationEngine(use_hardware=not args.no_hardware)
    profiler = FrameProfiler(target_fps=50)
    frames = int(args.duration * 50)

    print(f"\n[RECORDING] Capturing {frames} frames...")

    if args.pattern == 'breathing':
        color = EMOTION_COLORS.get(args.emotion, EMOTION_COLORS['idle'])
        engine.breathing_pattern(color, frames, profiler)
    elif args.pattern == 'rainbow':
        engine.rainbow_pattern(frames, profiler)

    engine.clear_both()

    # Export data
    profiler.export_json(args.output)

    print(f"\n[COMPLETE] Recording saved to {args.output}")
    return 0


# =============================================================================
# CLI PARSER
# =============================================================================

def create_parser():
    """Create argument parser"""
    parser = argparse.ArgumentParser(
        description='OpenDuck V3 LED Developer CLI - Professional LED Pattern Tools',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s preview breathing --emotion happy --duration 5 --no-hardware
  %(prog)s profile rainbow --frames 250 --output profile.json
  %(prog)s validate ../config/hardware_config.yaml
  %(prog)s emotions --graph
  %(prog)s record breathing --emotion idle --duration 10 --output data/idle.json
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Preview command
    preview_parser = subparsers.add_parser('preview', help='Preview LED patterns')
    preview_parser.add_argument('pattern', choices=['breathing', 'rainbow'], help='Pattern type')
    preview_parser.add_argument('--emotion', default='idle', choices=EMOTION_COLORS.keys(), help='Emotion (for breathing)')
    preview_parser.add_argument('--duration', type=float, default=5.0, help='Duration in seconds')
    preview_parser.add_argument('--no-hardware', action='store_true', help='Use mock mode (no hardware)')

    # Profile command
    profile_parser = subparsers.add_parser('profile', help='Profile performance')
    profile_parser.add_argument('pattern', choices=['breathing', 'rainbow'], help='Pattern type')
    profile_parser.add_argument('--emotion', default='idle', choices=EMOTION_COLORS.keys(), help='Emotion (for breathing)')
    profile_parser.add_argument('--frames', type=int, default=250, help='Number of frames to profile')
    profile_parser.add_argument('--timing', action='store_true', help='Enable detailed timing (always enabled)')
    profile_parser.add_argument('--output', type=str, help='Export profiling data to JSON')
    profile_parser.add_argument('--no-hardware', action='store_true', help='Use mock mode (no hardware)')

    # Validate command
    validate_parser = subparsers.add_parser('validate', help='Validate configuration')
    validate_parser.add_argument('config', help='Path to config file (YAML)')

    # Emotions command
    emotions_parser = subparsers.add_parser('emotions', help='Show emotion state machine')
    emotions_parser.add_argument('--graph', action='store_true', help='Show ASCII state diagram')

    # Record command
    record_parser = subparsers.add_parser('record', help='Record pattern timing data')
    record_parser.add_argument('pattern', choices=['breathing', 'rainbow'], help='Pattern type')
    record_parser.add_argument('--emotion', default='idle', choices=EMOTION_COLORS.keys(), help='Emotion (for breathing)')
    record_parser.add_argument('--duration', type=float, default=10.0, help='Recording duration in seconds')
    record_parser.add_argument('--output', type=str, required=True, help='Output JSON file')
    record_parser.add_argument('--no-hardware', action='store_true', help='Use mock mode (no hardware)')

    return parser


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Main entry point"""
    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Banner
    print("\n" + "="*70)
    print("         OpenDuck V3 - LED Developer CLI")
    print("="*70)

    # Route to command
    if args.command == 'preview':
        return cmd_preview(args)
    elif args.command == 'profile':
        return cmd_profile(args)
    elif args.command == 'validate':
        return cmd_validate(args)
    elif args.command == 'emotions':
        return cmd_emotions(args)
    elif args.command == 'record':
        return cmd_record(args)
    else:
        print(f"ERROR: Unknown command '{args.command}'")
        parser.print_help()
        return 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
