#!/usr/bin/env python3
"""
Perlin Noise Performance Benchmark - Day 9 Pre-Flight Test
OpenDuck Mini V3 - Week 02

This script validates that the Perlin noise library performs adequately
on Raspberry Pi 4 ARM architecture before implementing organic LED patterns.

Performance Target: <10ms average per frame (50Hz = 20ms budget)

Author: Boston Dynamics Performance Engineer
Created: 18 January 2026
"""

from noise import pnoise2
import time
import sys


def benchmark_perlin_noise(iterations=1000, num_leds=16):
    """
    Benchmark Perlin noise generation for LED ring patterns.

    Args:
        iterations: Number of frames to simulate
        num_leds: Number of LEDs in ring (default: 16)

    Returns:
        dict: Performance metrics
    """
    print("=" * 70)
    print("OpenDuck Mini V3 - Perlin Noise Performance Benchmark")
    print("=" * 70)
    print(f"Configuration:")
    print(f"  - Iterations: {iterations}")
    print(f"  - LEDs per frame: {num_leds}")
    print(f"  - Total samples: {iterations * num_leds}")
    print()

    # Warmup (JIT compilation, cache warming)
    print("Warming up...")
    for i in range(100):
        for led in range(num_leds):
            _ = pnoise2(led * 0.1, i * 0.01)

    print("Running benchmark...")

    # Actual benchmark
    start = time.monotonic()
    for frame in range(iterations):
        for led in range(num_leds):
            val = pnoise2(led * 0.1, frame * 0.01)
    end = time.monotonic()

    # Calculate metrics
    total_time_ms = (end - start) * 1000
    avg_frame_time_ms = total_time_ms / iterations
    samples_per_sec = (iterations * num_leds) / (end - start)

    print()
    print("=" * 70)
    print("RESULTS")
    print("=" * 70)
    print(f"Total time: {total_time_ms:.2f}ms")
    print(f"Average frame time: {avg_frame_time_ms:.3f}ms")
    print(f"Samples per second: {samples_per_sec:,.0f}")
    print(f"Target frame time: <10ms (50Hz = 20ms budget)")
    print()

    # Decision
    if avg_frame_time_ms < 10:
        print("✅ PASS: Proceed with procedural Perlin noise")
        print("   → Fire, Cloud, Dream patterns will use real-time generation")
        decision = "PROCEDURAL"
        status = 0
    else:
        print("❌ FAIL: Average frame time exceeds budget")
        print("   → Fallback to 64×64 pre-computed LUT")
        print("   → Patterns will use lookup table instead")
        decision = "LUT_FALLBACK"
        status = 1

    print()
    print("=" * 70)
    print(f"DECISION: {decision}")
    print("=" * 70)

    return {
        "avg_frame_time_ms": avg_frame_time_ms,
        "total_time_ms": total_time_ms,
        "samples_per_sec": samples_per_sec,
        "decision": decision,
        "status": status
    }


if __name__ == "__main__":
    try:
        metrics = benchmark_perlin_noise()
        sys.exit(metrics["status"])
    except ImportError as e:
        print("❌ ERROR: noise library not installed")
        print(f"   {e}")
        print()
        print("Install with: sudo pip3 install noise --break-system-packages")
        sys.exit(2)
    except Exception as e:
        print(f"❌ ERROR: Benchmark failed")
        print(f"   {e}")
        sys.exit(3)
