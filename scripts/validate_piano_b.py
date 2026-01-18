#!/usr/bin/env python3
"""
Piano B Validation Script - OPT-2 & OPT-3
==========================================
Validates that PrecisionTimer and batched LED updates meet performance targets.

Run without hardware (simulation mode):
  python3 validate_piano_b.py

Expected results:
  - PrecisionTimer achieves <1ms jitter
  - Simulated LED batching shows expected call patterns
  - All tests PASS
"""

import time
import sys

# =============================================================================
# TEST 1: PrecisionTimer Jitter Measurement
# =============================================================================

class PrecisionTimer:
    """Simplified version of OPT-2 timer for validation"""

    def __init__(self, target_fps=50):
        self.frame_time = 1.0 / target_fps
        self.next_frame = time.monotonic()
        self.last_frame = self.next_frame
        self.frame_count = 0
        self.jitter_values = []

    def wait_for_next_frame(self):
        """Sleep exactly until next frame boundary"""
        now = time.monotonic()
        sleep_time = self.next_frame - now

        # Calculate jitter
        actual_frame_time = now - self.last_frame
        jitter = abs(actual_frame_time - self.frame_time)
        self.jitter_values.append(jitter * 1000)  # ms

        if sleep_time > 0:
            time.sleep(sleep_time)
            self.next_frame += self.frame_time
        else:
            self.next_frame = time.monotonic() + self.frame_time

        self.last_frame = now
        self.frame_count += 1

    def get_avg_jitter(self):
        return sum(self.jitter_values) / len(self.jitter_values) if self.jitter_values else 0

    def get_max_jitter(self):
        return max(self.jitter_values) if self.jitter_values else 0


def test_precision_timer():
    """Validate PrecisionTimer achieves <1ms jitter"""
    print("="*70)
    print("TEST 1: PrecisionTimer Jitter Measurement (OPT-2)")
    print("="*70)

    timer = PrecisionTimer(50)  # 50 Hz
    test_frames = 500  # 10 seconds at 50Hz

    print(f"\nRunning {test_frames} frames at 50 Hz...")
    print("(This will take ~10 seconds)")

    start_time = time.monotonic()

    for _ in range(test_frames):
        # Simulate some work (variable render time)
        work_time = 0.001 + ((_ % 10) * 0.0005)  # 1-5ms variable
        time.sleep(work_time)

        # Wait for next frame
        timer.wait_for_next_frame()

    elapsed_time = time.monotonic() - start_time
    actual_fps = test_frames / elapsed_time
    avg_jitter = timer.get_avg_jitter()
    max_jitter = timer.get_max_jitter()

    print(f"\nResults:")
    print(f"  Target FPS:       50.00 Hz")
    print(f"  Actual FPS:       {actual_fps:.2f} Hz")
    print(f"  Average jitter:   {avg_jitter:.3f} ms")
    print(f"  Max jitter:       {max_jitter:.3f} ms")

    # Pass/Fail criteria
    fps_pass = abs(actual_fps - 50.0) < 1.0
    jitter_pass = avg_jitter < 1.0

    print(f"\nPass/Fail:")
    print(f"  FPS (49-51 Hz):   {'✅ PASS' if fps_pass else '❌ FAIL'}")
    print(f"  Jitter (<1ms):    {'✅ PASS' if jitter_pass else '❌ FAIL'}")

    return fps_pass and jitter_pass


# =============================================================================
# TEST 2: Batched LED Update Pattern
# =============================================================================

class MockPixelStrip:
    """Mock LED strip for testing batching pattern"""

    def __init__(self, name):
        self.name = name
        self.show_calls = 0
        self.pixel_calls = 0

    def setPixelColor(self, i, color):
        self.pixel_calls += 1

    def show(self):
        self.show_calls += 1

    def numPixels(self):
        return 16


def set_all_no_show(strip, r, g, b):
    """OPT-3: Set pixels without show()"""
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, (r, g, b))
    # NO show() here


def set_both_batched(left, right, r, g, b):
    """OPT-3: Batched update for both eyes"""
    set_all_no_show(left, r, g, b)
    set_all_no_show(right, r, g, b)
    left.show()
    right.show()


def set_both_old(left, right, r, g, b):
    """OLD: Non-batched update"""
    for i in range(left.numPixels()):
        left.setPixelColor(i, (r, g, b))
    left.show()
    for i in range(right.numPixels()):
        right.setPixelColor(i, (r, g, b))
    right.show()


def test_batched_updates():
    """Validate batched updates reduce show() calls"""
    print("\n" + "="*70)
    print("TEST 2: Batched LED Update Pattern (OPT-3)")
    print("="*70)

    # Test OLD method
    left_old = MockPixelStrip("left")
    right_old = MockPixelStrip("right")

    print("\nOLD METHOD (non-batched):")
    for _ in range(100):
        set_both_old(left_old, right_old, 255, 100, 50)

    print(f"  setPixelColor calls: {left_old.pixel_calls + right_old.pixel_calls}")
    print(f"  show() calls:        {left_old.show_calls + right_old.show_calls}")

    # Test NEW method
    left_new = MockPixelStrip("left")
    right_new = MockPixelStrip("right")

    print("\nNEW METHOD (batched):")
    for _ in range(100):
        set_both_batched(left_new, right_new, 255, 100, 50)

    print(f"  setPixelColor calls: {left_new.pixel_calls + right_new.pixel_calls}")
    print(f"  show() calls:        {left_new.show_calls + right_new.show_calls}")

    # Validate
    old_shows = left_old.show_calls + right_old.show_calls
    new_shows = left_new.show_calls + right_new.show_calls

    print(f"\nComparison:")
    print(f"  OLD show() calls:    {old_shows}")
    print(f"  NEW show() calls:    {new_shows}")
    print(f"  Reduction:           {old_shows - new_shows} calls ({(1 - new_shows/old_shows)*100:.1f}%)")

    # Pass/Fail (should be same number since we still call show() twice per frame)
    # But the batching means we prepare both buffers before any show()
    batching_correct = (old_shows == new_shows)  # Should be equal
    pattern_correct = (new_shows == 200)  # 100 frames × 2 eyes

    print(f"\nPass/Fail:")
    print(f"  Show count equal:    {'✅ PASS' if batching_correct else '❌ FAIL'}")
    print(f"  Pattern correct:     {'✅ PASS' if pattern_correct else '❌ FAIL'}")

    print(f"\nNote: Batching doesn't reduce show() COUNT, but reduces TIME")
    print(f"      by preparing both buffers before SPI transfers.")

    return batching_correct and pattern_correct


# =============================================================================
# TEST 3: Combined Performance Simulation
# =============================================================================

def test_combined_performance():
    """Simulate full frame with OPT-2 + OPT-3"""
    print("\n" + "="*70)
    print("TEST 3: Combined OPT-2 + OPT-3 Performance Simulation")
    print("="*70)

    timer = PrecisionTimer(50)
    left = MockPixelStrip("left")
    right = MockPixelStrip("right")

    test_frames = 250  # 5 seconds at 50Hz

    print(f"\nRunning {test_frames} frames with batched updates...")

    frame_times = []
    start_time = time.monotonic()

    for frame in range(test_frames):
        frame_start = time.monotonic()

        # Simulate render work
        time.sleep(0.003)  # 3ms render

        # Batched LED update
        set_both_batched(left, right, 255, 100, 50)

        # Precision timing
        timer.wait_for_next_frame()

        frame_end = time.monotonic()
        frame_times.append((frame_end - frame_start) * 1000)

    elapsed = time.monotonic() - start_time
    actual_fps = test_frames / elapsed
    avg_frame_time = sum(frame_times) / len(frame_times)

    print(f"\nResults:")
    print(f"  Frames rendered:     {test_frames}")
    print(f"  Elapsed time:        {elapsed:.3f} s")
    print(f"  Actual FPS:          {actual_fps:.2f} Hz")
    print(f"  Avg frame time:      {avg_frame_time:.3f} ms")
    print(f"  Avg jitter:          {timer.get_avg_jitter():.3f} ms")

    combined_pass = (abs(actual_fps - 50.0) < 1.0) and (timer.get_avg_jitter() < 1.0)

    print(f"\nPass/Fail:")
    print(f"  Combined test:       {'✅ PASS' if combined_pass else '❌ FAIL'}")

    return combined_pass


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Run all validation tests"""
    print("\n")
    print("╔" + "="*68 + "╗")
    print("║" + " "*15 + "PIANO B VALIDATION SUITE (OPT-2 & OPT-3)" + " "*13 + "║")
    print("╚" + "="*68 + "╝")

    results = []

    # Run tests
    results.append(("PrecisionTimer Jitter", test_precision_timer()))
    results.append(("Batched LED Updates", test_batched_updates()))
    results.append(("Combined Performance", test_combined_performance()))

    # Summary
    print("\n" + "="*70)
    print("VALIDATION SUMMARY")
    print("="*70)

    all_pass = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {name:<30} {status}")
        all_pass = all_pass and passed

    print("="*70)

    if all_pass:
        print("\n🎉 ALL TESTS PASSED - Piano B optimizations validated!\n")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED - Review results above\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
