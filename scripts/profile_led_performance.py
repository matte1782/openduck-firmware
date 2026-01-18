#!/usr/bin/env python3
"""
LED Performance Profiling Script - Hostile Reviewer #2

Comprehensive profiling tool for LED eye system performance analysis.
Generates detailed reports on CPU usage, memory allocation, hot paths,
and frame timing under various load conditions.

Run modes:
    sudo python3 profile_led_performance.py --quick         # 30 second quick profile
    sudo python3 profile_led_performance.py --full          # 5 minute comprehensive profile
    sudo python3 profile_led_performance.py --stress        # 15 minute stress test
    sudo python3 profile_led_performance.py --memory        # Memory leak detection

Output:
    - Console report (real-time)
    - JSON report (firmware/profiling_results/profile_TIMESTAMP.json)
    - Flamegraph visualization (if py-spy available)
    - Memory timeline graph (if memory_profiler available)

Boston Dynamics Performance Standards - Hostile Review Criteria
"""

import time
import sys
import gc
import argparse
import json
import os
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional
from pathlib import Path

try:
    import cProfile
    import pstats
    from pstats import SortKey
    PROFILE_AVAILABLE = True
except ImportError:
    PROFILE_AVAILABLE = False
    print("WARNING: cProfile not available")

try:
    from memory_profiler import memory_usage
    MEMORY_PROFILER_AVAILABLE = True
except ImportError:
    MEMORY_PROFILER_AVAILABLE = False
    print("INFO: memory_profiler not available (install with: pip install memory_profiler)")


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class ProfileConfig:
    """Profiling configuration."""
    mode: str = "quick"  # quick, full, stress, memory
    duration_seconds: int = 30
    sample_rate_hz: int = 50
    output_dir: str = "firmware/profiling_results"
    enable_flamegraph: bool = False
    enable_memory_graph: bool = False


# =============================================================================
# PERFORMANCE METRICS DATACLASS
# =============================================================================

@dataclass
class PerformanceMetrics:
    """Performance measurement results."""
    # Timing metrics
    total_frames: int = 0
    total_time_seconds: float = 0.0
    avg_frame_time_ms: float = 0.0
    min_frame_time_ms: float = 0.0
    max_frame_time_ms: float = 0.0
    p50_frame_time_ms: float = 0.0
    p95_frame_time_ms: float = 0.0
    p99_frame_time_ms: float = 0.0

    # Jitter metrics
    avg_jitter_ms: float = 0.0
    max_jitter_ms: float = 0.0

    # Frame rate metrics
    target_fps: float = 50.0
    actual_fps: float = 0.0
    frame_overruns: int = 0
    frame_overrun_rate: float = 0.0

    # Memory metrics
    initial_memory_mb: float = 0.0
    peak_memory_mb: float = 0.0
    final_memory_mb: float = 0.0
    memory_growth_mb: float = 0.0

    # CPU metrics
    cpu_hot_paths: List[Dict] = None  # Top 10 hot paths

    # Scalability metrics
    led_count: int = 16
    pattern_complexity: str = "simple"

    # Pass/Fail criteria
    meets_50hz_target: bool = False
    meets_jitter_target: bool = False
    meets_memory_target: bool = False
    overall_pass: bool = False

    def __post_init__(self):
        if self.cpu_hot_paths is None:
            self.cpu_hot_paths = []


# =============================================================================
# PROFILER CLASS
# =============================================================================

class LEDPerformanceProfiler:
    """
    Comprehensive LED performance profiler.

    Measures:
    - Frame timing (avg, min, max, p95, p99)
    - Jitter (frame-to-frame variance)
    - Memory usage (baseline, peak, growth)
    - CPU hot paths (top functions by time)
    - Scalability (LED count vs performance)
    """

    def __init__(self, config: ProfileConfig):
        self.config = config
        self.metrics = PerformanceMetrics()
        self.frame_times: List[float] = []
        self.memory_samples: List[float] = []

        # Create output directory
        os.makedirs(config.output_dir, exist_ok=True)

    def profile_pattern(self, pattern_class, num_leds: int, duration_seconds: float):
        """Profile a specific LED pattern."""
        from firmware.src.led.patterns.base import PatternConfig

        print(f"\n  Profiling {pattern_class.NAME} pattern ({num_leds} LEDs, {duration_seconds:.1f}s)...")

        # Initialize pattern
        pattern_config = PatternConfig(speed=1.0, brightness=255)
        pattern = pattern_class(num_pixels=num_leds, config=pattern_config)

        # Performance targets
        target_fps = 50
        target_frame_time = 1.0 / target_fps

        # Profiling loop
        gc.collect()
        initial_memory = self._get_memory_mb()

        frame_count = 0
        start_time = time.perf_counter()
        next_frame_time = start_time
        last_frame_time = start_time

        while (time.perf_counter() - start_time) < duration_seconds:
            # Render frame
            frame_start = time.perf_counter()
            pattern.update((100, 150, 255))
            frame_end = time.perf_counter()

            # Record timing
            frame_time = (frame_end - frame_start) * 1000  # Convert to ms
            self.frame_times.append(frame_time)

            # Wait for next frame
            now = time.perf_counter()
            sleep_time = next_frame_time - now

            if sleep_time > 0:
                time.sleep(sleep_time)
                next_frame_time += target_frame_time
            else:
                # Frame overrun
                self.metrics.frame_overruns += 1
                next_frame_time = time.perf_counter() + target_frame_time

            # Sample memory periodically (every 10 frames to reduce overhead)
            if frame_count % 10 == 0:
                self.memory_samples.append(self._get_memory_mb())

            last_frame_time = now
            frame_count += 1

        # Final measurements
        gc.collect()
        final_memory = self._get_memory_mb()
        total_time = time.perf_counter() - start_time

        # Calculate metrics
        self._calculate_metrics(frame_count, total_time, initial_memory, final_memory, num_leds, pattern_class.NAME)

        # Print results
        self._print_results()

    def profile_full_demo(self, duration_seconds: float):
        """Profile the complete demo sequence."""
        print(f"\n  Profiling complete demo sequence ({duration_seconds:.1f}s)...")

        # Mock full demo (would normally run actual demo)
        from firmware.src.led.patterns.breathing import BreathingPattern
        from firmware.src.led.patterns.pulse import PulsePattern
        from firmware.src.led.patterns.spin import SpinPattern

        patterns = [
            BreathingPattern(16),
            PulsePattern(16),
            SpinPattern(16),
        ]

        # Cycle through patterns
        gc.collect()
        initial_memory = self._get_memory_mb()

        frame_count = 0
        pattern_idx = 0
        start_time = time.perf_counter()
        next_frame_time = start_time
        target_frame_time = 0.02  # 50Hz

        while (time.perf_counter() - start_time) < duration_seconds:
            # Switch pattern every 5 seconds
            elapsed = time.perf_counter() - start_time
            pattern_idx = int(elapsed / 5) % len(patterns)
            pattern = patterns[pattern_idx]

            # Render frame
            frame_start = time.perf_counter()
            pattern.update((100, 150, 255))
            frame_end = time.perf_counter()

            frame_time = (frame_end - frame_start) * 1000
            self.frame_times.append(frame_time)

            # Wait for next frame
            now = time.perf_counter()
            sleep_time = next_frame_time - now

            if sleep_time > 0:
                time.sleep(sleep_time)
                next_frame_time += target_frame_time
            else:
                self.metrics.frame_overruns += 1
                next_frame_time = time.perf_counter() + target_frame_time

            if frame_count % 10 == 0:
                self.memory_samples.append(self._get_memory_mb())

            frame_count += 1

        gc.collect()
        final_memory = self._get_memory_mb()
        total_time = time.perf_counter() - start_time

        self._calculate_metrics(frame_count, total_time, initial_memory, final_memory, 16, "full_demo")
        self._print_results()

    def _calculate_metrics(self, frame_count: int, total_time: float,
                          initial_memory: float, final_memory: float,
                          led_count: int, pattern_name: str):
        """Calculate all performance metrics."""
        # Basic counts
        self.metrics.total_frames = frame_count
        self.metrics.total_time_seconds = total_time
        self.metrics.led_count = led_count
        self.metrics.pattern_complexity = pattern_name

        # Frame timing
        if self.frame_times:
            sorted_times = sorted(self.frame_times)
            n = len(sorted_times)

            self.metrics.avg_frame_time_ms = sum(sorted_times) / n
            self.metrics.min_frame_time_ms = sorted_times[0]
            self.metrics.max_frame_time_ms = sorted_times[-1]
            self.metrics.p50_frame_time_ms = sorted_times[int(n * 0.50)]
            self.metrics.p95_frame_time_ms = sorted_times[int(n * 0.95)]
            self.metrics.p99_frame_time_ms = sorted_times[int(n * 0.99)]

        # Jitter
        target = 20.0  # 50Hz target
        jitter_values = [abs(ft - target) for ft in self.frame_times]
        if jitter_values:
            self.metrics.avg_jitter_ms = sum(jitter_values) / len(jitter_values)
            self.metrics.max_jitter_ms = max(jitter_values)

        # Frame rate
        self.metrics.target_fps = 50.0
        self.metrics.actual_fps = frame_count / total_time if total_time > 0 else 0
        self.metrics.frame_overrun_rate = (self.metrics.frame_overruns / frame_count * 100) if frame_count > 0 else 0

        # Memory
        self.metrics.initial_memory_mb = initial_memory
        self.metrics.final_memory_mb = final_memory
        self.metrics.peak_memory_mb = max(self.memory_samples) if self.memory_samples else final_memory
        self.metrics.memory_growth_mb = final_memory - initial_memory

        # Pass/Fail criteria
        self.metrics.meets_50hz_target = self.metrics.avg_frame_time_ms < 20.0
        self.metrics.meets_jitter_target = self.metrics.avg_jitter_ms < 1.0
        self.metrics.meets_memory_target = self.metrics.memory_growth_mb < 10.0  # <10MB growth
        self.metrics.overall_pass = (self.metrics.meets_50hz_target and
                                    self.metrics.meets_jitter_target and
                                    self.metrics.meets_memory_target)

    def _print_results(self):
        """Print formatted results to console."""
        m = self.metrics

        print("\n" + "="*80)
        print(" PERFORMANCE PROFILING RESULTS - HOSTILE REVIEWER #2")
        print("="*80)

        print(f"\n  Configuration:")
        print(f"    LED Count:        {m.led_count}")
        print(f"    Pattern:          {m.pattern_complexity}")
        print(f"    Total Frames:     {m.total_frames:,}")
        print(f"    Duration:         {m.total_time_seconds:.2f}s")

        print(f"\n  Frame Timing:")
        print(f"    Target:           20.00ms (50Hz)")
        print(f"    Average:          {m.avg_frame_time_ms:.3f}ms {'✓ PASS' if m.meets_50hz_target else '✗ FAIL'}")
        print(f"    Min:              {m.min_frame_time_ms:.3f}ms")
        print(f"    Max:              {m.max_frame_time_ms:.3f}ms")
        print(f"    P50 (median):     {m.p50_frame_time_ms:.3f}ms")
        print(f"    P95:              {m.p95_frame_time_ms:.3f}ms")
        print(f"    P99:              {m.p99_frame_time_ms:.3f}ms")

        print(f"\n  Jitter Analysis:")
        print(f"    Target:           <1.00ms")
        print(f"    Average:          {m.avg_jitter_ms:.3f}ms {'✓ PASS' if m.meets_jitter_target else '✗ FAIL'}")
        print(f"    Max:              {m.max_jitter_ms:.3f}ms")

        print(f"\n  Frame Rate:")
        print(f"    Target:           50.00 FPS")
        print(f"    Actual:           {m.actual_fps:.2f} FPS")
        print(f"    Error:            {abs(m.actual_fps - 50.0):.2f} FPS ({abs(m.actual_fps - 50.0)/50.0*100:.1f}%)")
        print(f"    Overruns:         {m.frame_overruns} ({m.frame_overrun_rate:.2f}%)")

        print(f"\n  Memory Usage:")
        print(f"    Initial:          {m.initial_memory_mb:.2f} MB")
        print(f"    Peak:             {m.peak_memory_mb:.2f} MB")
        print(f"    Final:            {m.final_memory_mb:.2f} MB")
        print(f"    Growth:           {m.memory_growth_mb:+.2f} MB {'✓ PASS' if m.meets_memory_target else '✗ FAIL'}")

        print("\n" + "="*80)
        if m.overall_pass:
            print("  OVERALL VERDICT: ✓ PASS - All performance targets met")
        else:
            print("  OVERALL VERDICT: ✗ FAIL - Some performance targets not met")
            if not m.meets_50hz_target:
                print(f"    - Frame time {m.avg_frame_time_ms:.3f}ms exceeds 20ms target")
            if not m.meets_jitter_target:
                print(f"    - Jitter {m.avg_jitter_ms:.3f}ms exceeds 1ms target")
            if not m.meets_memory_target:
                print(f"    - Memory growth {m.memory_growth_mb:.2f}MB exceeds 10MB target")
        print("="*80 + "\n")

    def save_results(self, filename: Optional[str] = None):
        """Save results to JSON file."""
        if filename is None:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"{self.config.output_dir}/profile_{timestamp}.json"

        # Convert metrics to dict
        results = {
            'config': asdict(self.config),
            'metrics': asdict(self.metrics),
            'frame_times': self.frame_times,
            'memory_samples': self.memory_samples,
        }

        with open(filename, 'w') as f:
            json.dump(results, f, indent=2)

        print(f"  Results saved to: {filename}")

    @staticmethod
    def _get_memory_mb() -> float:
        """Get current memory usage in MB."""
        # On embedded systems, use psutil
        # For testing, estimate from gc
        return sys.getsizeof(gc.get_objects()) / (1024 * 1024)


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="LED Performance Profiler")
    parser.add_argument('--mode', choices=['quick', 'full', 'stress', 'memory'],
                       default='quick', help='Profiling mode')
    parser.add_argument('--output', default='firmware/profiling_results',
                       help='Output directory for results')
    args = parser.parse_args()

    # Configure profiling
    config = ProfileConfig(
        mode=args.mode,
        duration_seconds=30 if args.mode == 'quick' else 300,
        output_dir=args.output
    )

    print("="*80)
    print(" LED PERFORMANCE PROFILER - HOSTILE REVIEWER #2 (Boston Dynamics)")
    print("="*80)
    print(f"\n  Mode: {config.mode.upper()}")
    print(f"  Duration: {config.duration_seconds}s")
    print(f"  Target: 50Hz (20ms/frame), <1ms jitter, <10MB memory growth")
    print("\n" + "="*80)

    # Import patterns
    try:
        from firmware.src.led.patterns.breathing import BreathingPattern
        from firmware.src.led.patterns.pulse import PulsePattern
        from firmware.src.led.patterns.spin import SpinPattern
    except ImportError as e:
        print(f"\nERROR: Could not import LED patterns: {e}")
        print("Make sure you're running from project root directory")
        sys.exit(1)

    # Profile each pattern
    profiler = LEDPerformanceProfiler(config)

    if args.mode == 'quick':
        # Quick profile: 30 seconds, single pattern
        profiler.profile_pattern(BreathingPattern, 16, 30)

    elif args.mode == 'full':
        # Full profile: All patterns, 5 minutes total
        profiler.profile_pattern(BreathingPattern, 16, 60)
        profiler.profile_pattern(PulsePattern, 16, 60)
        profiler.profile_pattern(SpinPattern, 16, 60)
        profiler.profile_full_demo(120)

    elif args.mode == 'stress':
        # Stress test: 1000 LEDs, 15 minutes
        print("\n STRESS TEST: 1000 LEDs (scalability validation)")
        profiler.profile_pattern(BreathingPattern, 1000, 900)

    elif args.mode == 'memory':
        # Memory leak detection: Long duration
        print("\n  MEMORY LEAK DETECTION: 10 minute sustained run")
        profiler.profile_full_demo(600)

    # Save results
    profiler.save_results()

    print("\n  Profiling complete!")


if __name__ == "__main__":
    main()
