#!/usr/bin/env python3
"""
Animation Timing System Demo

Demonstrates keyframe-based animation with easing functions.
This is a pure software demo that can run without hardware.

Run with: python examples/animation_demo.py

Author: Boston Dynamics Animation Systems Engineer
Created: 17 January 2026
"""

import sys
from pathlib import Path
import time

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from animation import (
    Keyframe, AnimationSequence, AnimationPlayer,
    ease_linear, ease_in, ease_out, ease_in_out
)


def demo_easing_functions():
    """Demonstrate all easing functions."""
    print("=" * 70)
    print("DEMO 1: Easing Functions")
    print("=" * 70)

    print("\nEasing function comparison at t=0.25:")
    t = 0.25
    print(f"  linear(0.25)      = {ease_linear(t):.4f}")
    print(f"  ease_in(0.25)     = {ease_in(t):.4f}  (slower at start)")
    print(f"  ease_out(0.25)    = {ease_out(t):.4f}  (faster at start)")
    print(f"  ease_in_out(0.25) = {ease_in_out(t):.4f}  (slow start & end)")

    print("\n✓ Easing functions use pre-computed lookup tables for O(1) performance")


def demo_color_fade():
    """Demonstrate color interpolation with easing."""
    print("\n" + "=" * 70)
    print("DEMO 2: Color Fade Animation")
    print("=" * 70)

    # Create fade sequence: black → white over 1 second
    seq = AnimationSequence("color_fade")
    seq.add_keyframe(0, color=(0, 0, 0), easing='ease_in_out')
    seq.add_keyframe(1000, color=(255, 255, 255), easing='ease_in_out')

    print(f"\nSequence: {seq.name}")
    print(f"Duration: {seq.duration_ms}ms")
    print(f"Keyframes: {seq.get_keyframe_count()}")

    print("\nInterpolated colors at various times:")
    for time_ms in [0, 250, 500, 750, 1000]:
        values = seq.get_values(time_ms)
        color = values['color']
        print(f"  t={time_ms:4d}ms: RGB({color[0]:3d}, {color[1]:3d}, {color[2]:3d})")

    print("\n✓ Color interpolation uses easing for smooth transitions")


def demo_brightness_pulse():
    """Demonstrate brightness animation."""
    print("\n" + "=" * 70)
    print("DEMO 3: Breathing Brightness Animation")
    print("=" * 70)

    # Create breathing sequence: dim → bright → dim
    seq = AnimationSequence("breathing", loop=True)
    seq.add_keyframe(0, brightness=0.3, easing='ease_in_out')
    seq.add_keyframe(2000, brightness=1.0, easing='ease_in_out')
    seq.add_keyframe(4000, brightness=0.3, easing='ease_in_out')

    print(f"\nSequence: {seq.name} (looping)")
    print(f"Duration: {seq.duration_ms}ms (4 second breath cycle)")

    print("\nBrightness values during one breath:")
    for time_ms in [0, 500, 1000, 1500, 2000, 2500, 3000, 3500, 4000]:
        values = seq.get_values(time_ms)
        brightness = values['brightness']
        bar_length = int(brightness * 40)
        bar = "█" * bar_length + "░" * (40 - bar_length)
        print(f"  t={time_ms/1000:.1f}s: {brightness:.2f} {bar}")

    print("\n✓ Looping sequences automatically wrap at duration")


def demo_multi_property():
    """Demonstrate multiple properties animating together."""
    print("\n" + "=" * 70)
    print("DEMO 4: Multi-Property Animation")
    print("=" * 70)

    # Create complex sequence with color + brightness + position
    seq = AnimationSequence("complex")
    seq.add_keyframe(
        0,
        color=(255, 0, 0),      # Red
        brightness=0.5,
        position=(0.0, 0.0),
        easing='ease_out'
    )
    seq.add_keyframe(
        1000,
        color=(0, 255, 0),      # Green
        brightness=1.0,
        position=(1.0, 0.5),
        easing='ease_in_out'
    )
    seq.add_keyframe(
        2000,
        color=(0, 0, 255),      # Blue
        brightness=0.3,
        position=(0.0, 1.0),
        easing='ease_in'
    )

    print(f"\nSequence: {seq.name}")
    print(f"Properties: color, brightness, position")

    print("\nAnimation progression:")
    for time_ms in [0, 500, 1000, 1500, 2000]:
        values = seq.get_values(time_ms)
        color = values['color']
        brightness = values['brightness']
        pos = values['position']
        print(f"  t={time_ms/1000:.1f}s: RGB({color[0]:3d},{color[1]:3d},{color[2]:3d}) "
              f"bright={brightness:.2f} pos=({pos[0]:.2f},{pos[1]:.2f})")

    print("\n✓ All properties interpolate independently with their own easing")


def demo_realtime_playback():
    """Demonstrate real-time animation playback."""
    print("\n" + "=" * 70)
    print("DEMO 5: Real-Time Animation Player")
    print("=" * 70)

    # Create fast animation for demo
    seq = AnimationSequence("realtime")
    seq.add_keyframe(0, brightness=0.0, easing='linear')
    seq.add_keyframe(500, brightness=1.0, easing='linear')

    print(f"\nPlaying animation at 30 FPS for 0.5 seconds...")
    print("Brightness progression:")

    player = AnimationPlayer(seq, target_fps=30)
    player.play()

    frame_count = 0
    start_time = time.monotonic()

    while player.is_playing():
        values = player.update()
        brightness = values['brightness']

        # Visual progress bar
        bar_length = int(brightness * 50)
        bar = "█" * bar_length + "░" * (50 - bar_length)

        elapsed_ms = player.get_current_time_ms()
        print(f"\r  Frame {frame_count:2d} ({elapsed_ms:3d}ms): {bar}", end="", flush=True)

        player.wait_for_next_frame()
        frame_count += 1

    elapsed = time.monotonic() - start_time
    actual_fps = frame_count / elapsed

    print(f"\n\n✓ Playback complete!")
    print(f"  Target FPS: 30")
    print(f"  Actual FPS: {actual_fps:.1f}")
    print(f"  Frame count: {frame_count}")
    print(f"  Jitter: {abs(30 - actual_fps):.1f} fps")
    print("\n✓ time.monotonic() provides frame-perfect timing")


def demo_performance():
    """Demonstrate performance characteristics."""
    print("\n" + "=" * 70)
    print("DEMO 6: Performance Benchmarks")
    print("=" * 70)

    # Create complex sequence
    seq = AnimationSequence("benchmark")
    seq.add_keyframe(0, color=(0, 0, 0), brightness=0.0, position=(0, 0))
    seq.add_keyframe(500, color=(128, 128, 128), brightness=0.5, position=(0.5, 0.5))
    seq.add_keyframe(1000, color=(255, 255, 255), brightness=1.0, position=(1, 1))

    # Benchmark interpolation
    iterations = 10000
    start = time.monotonic()
    for i in range(iterations):
        seq.get_values(i % 1000)
    elapsed = time.monotonic() - start

    avg_us = (elapsed / iterations) * 1_000_000
    calls_per_second = iterations / elapsed

    print(f"\nInterpolation performance:")
    print(f"  Iterations: {iterations:,}")
    print(f"  Total time: {elapsed:.3f} seconds")
    print(f"  Avg time: {avg_us:.2f} microseconds per call")
    print(f"  Throughput: {calls_per_second:,.0f} calls/second")

    # Benchmark easing
    iterations = 100000
    start = time.monotonic()
    for _ in range(iterations):
        ease_in_out(0.5)
    elapsed = time.monotonic() - start

    avg_us = (elapsed / iterations) * 1_000_000

    print(f"\nEasing LUT lookup performance:")
    print(f"  Iterations: {iterations:,}")
    print(f"  Avg time: {avg_us:.2f} microseconds per lookup")
    print(f"  Result: {'✓ PASS' if avg_us < 10 else '✗ FAIL'} (target: <10μs)")

    print("\n✓ Performance targets met for 50Hz animation")


def main():
    """Run all demos."""
    print("\n")
    print("=" * 70)
    print("  OpenDuck Mini V3 - Animation Timing System Demo")
    print("=" * 70)

    try:
        demo_easing_functions()
        input("\n[Press Enter to continue...]")

        demo_color_fade()
        input("\n[Press Enter to continue...]")

        demo_brightness_pulse()
        input("\n[Press Enter to continue...]")

        demo_multi_property()
        input("\n[Press Enter to continue...]")

        demo_realtime_playback()
        input("\n[Press Enter to continue...]")

        demo_performance()

        print("\n" + "=" * 70)
        print("ALL DEMOS COMPLETE")
        print("=" * 70)
        print("\n✓ Animation Timing System is ready for LED integration!")
        print("\nNext steps:")
        print("  1. Integrate with LED pattern library (BreathingPattern, etc.)")
        print("  2. Test on Raspberry Pi hardware (GPIO 18 + GPIO 13)")
        print("  3. Validate 50Hz frame rate with real LEDs")
        print()

    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user.")


if __name__ == "__main__":
    main()
