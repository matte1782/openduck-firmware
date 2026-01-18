#!/usr/bin/env python3
"""
HSV→RGB Lookup Table Benchmark (OPT-1)
======================================
Standalone benchmark to measure performance improvement from LUT optimization.

Run with: sudo python3 benchmark_hsv_lut.py

This script:
1. Builds the HSV→RGB lookup table
2. Runs rainbow cycle with SLOW (reference) implementation
3. Runs rainbow cycle with FAST (LUT) implementation
4. Reports speedup, memory usage, and efficiency gains
"""

import time
import sys

# =============================================================================
# HSV→RGB IMPLEMENTATIONS
# =============================================================================

def hsv_to_rgb_reference(h, s, v):
    """Original HSV→RGB conversion (reference implementation with branches)"""
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
# BUILD LOOKUP TABLE
# =============================================================================

print("="*70)
print("         HSV→RGB LOOKUP TABLE BENCHMARK (OPT-1)")
print("="*70)
print("\n[PHASE 1/3] Building lookup table...")

t_start = time.monotonic()

HSV_LUT = {}
HSV_LUT_SIZE_H = 256  # Full hue resolution (0-255)
HSV_LUT_SIZE_S = 11   # Saturation steps (0.0 - 1.0 in 0.1 increments)
HSV_LUT_SIZE_V = 11   # Value steps (0.0 - 1.0 in 0.1 increments)

for h_idx in range(HSV_LUT_SIZE_H):
    for s_idx in range(HSV_LUT_SIZE_S):
        for v_idx in range(HSV_LUT_SIZE_V):
            h = h_idx / 255.0
            s = s_idx / 10.0
            v = v_idx / 10.0
            HSV_LUT[(h_idx, s_idx, v_idx)] = hsv_to_rgb_reference(h, s, v)

t_elapsed = (time.monotonic() - t_start) * 1000
lut_entries = HSV_LUT_SIZE_H * HSV_LUT_SIZE_S * HSV_LUT_SIZE_V
lut_memory_kb = sys.getsizeof(HSV_LUT) / 1024

print(f"  Build time: {t_elapsed:.2f}ms")
print(f"  Entries:    {lut_entries:,} ({HSV_LUT_SIZE_H}×{HSV_LUT_SIZE_S}×{HSV_LUT_SIZE_V})")
print(f"  Memory:     {lut_memory_kb:.2f} KB")

def hsv_to_rgb_fast(h, s, v):
    """Fast HSV→RGB conversion using pre-computed lookup table"""
    h_key = int(h * 255)
    s_key = min(int(s * 10), 10)
    v_key = min(int(v * 10), 10)
    return HSV_LUT[(h_key, s_key, v_key)]

# =============================================================================
# BENCHMARK PARAMETERS
# =============================================================================

NUM_LEDS = 16
ITERATIONS = 10000  # Number of rainbow cycles to simulate

print(f"\n[PHASE 2/3] Benchmarking reference implementation...")
print(f"  Simulating {ITERATIONS:,} rainbow cycles ({NUM_LEDS} LEDs each)")

# Benchmark reference implementation
t_start = time.monotonic()
for iteration in range(ITERATIONS):
    for led in range(NUM_LEDS):
        hue = ((led * 256 // NUM_LEDS) + (iteration * 5)) % 256
        r, g, b = hsv_to_rgb_reference(hue / 255, 1.0, 1.0)
        # Simulate LED color application (no actual hardware)
t_ref_ms = (time.monotonic() - t_start) * 1000

total_conversions = ITERATIONS * NUM_LEDS
time_per_conversion_ref = t_ref_ms / total_conversions

print(f"  Total time:  {t_ref_ms:.2f}ms")
print(f"  Per cycle:   {t_ref_ms / ITERATIONS:.3f}ms")
print(f"  Per conv:    {time_per_conversion_ref:.6f}ms")

print(f"\n[PHASE 3/3] Benchmarking optimized implementation...")

# Benchmark optimized implementation
t_start = time.monotonic()
for iteration in range(ITERATIONS):
    for led in range(NUM_LEDS):
        hue = ((led * 256 // NUM_LEDS) + (iteration * 5)) % 256
        r, g, b = hsv_to_rgb_fast(hue / 255, 1.0, 1.0)
        # Simulate LED color application (no actual hardware)
t_fast_ms = (time.monotonic() - t_start) * 1000

time_per_conversion_fast = t_fast_ms / total_conversions

print(f"  Total time:  {t_fast_ms:.2f}ms")
print(f"  Per cycle:   {t_fast_ms / ITERATIONS:.3f}ms")
print(f"  Per conv:    {time_per_conversion_fast:.6f}ms")

# =============================================================================
# RESULTS
# =============================================================================

speedup_total_ms = t_ref_ms - t_fast_ms
speedup_per_cycle_ms = (t_ref_ms - t_fast_ms) / ITERATIONS
speedup_pct = (speedup_total_ms / t_ref_ms) * 100 if t_ref_ms > 0 else 0

print("\n" + "="*70)
print("                           RESULTS")
print("="*70)

print(f"\nTotal conversions:     {total_conversions:,}")
print(f"LUT memory overhead:   {lut_memory_kb:.2f} KB")

print(f"\n--- Per Conversion ---")
print(f"Reference (slow):      {time_per_conversion_ref:.6f}ms")
print(f"Optimized (fast):      {time_per_conversion_fast:.6f}ms")
print(f"Speedup:               {(time_per_conversion_ref - time_per_conversion_fast):.6f}ms ({speedup_pct:.1f}% faster)")

print(f"\n--- Per Rainbow Cycle ({NUM_LEDS} LEDs) ---")
print(f"Reference (slow):      {t_ref_ms / ITERATIONS:.3f}ms")
print(f"Optimized (fast):      {t_fast_ms / ITERATIONS:.3f}ms")
print(f"Speedup:               {speedup_per_cycle_ms:.3f}ms")

print(f"\n--- At 50Hz Frame Rate ---")
frame_time_target_ms = 20.0  # 50Hz = 20ms per frame
cycles_per_frame = 1
hsv_overhead_ref = (t_ref_ms / ITERATIONS) * cycles_per_frame
hsv_overhead_fast = (t_fast_ms / ITERATIONS) * cycles_per_frame
hsv_savings = hsv_overhead_ref - hsv_overhead_fast

print(f"Target frame time:     {frame_time_target_ms:.1f}ms")
print(f"HSV overhead (ref):    {hsv_overhead_ref:.3f}ms ({(hsv_overhead_ref/frame_time_target_ms)*100:.1f}% of budget)")
print(f"HSV overhead (opt):    {hsv_overhead_fast:.3f}ms ({(hsv_overhead_fast/frame_time_target_ms)*100:.1f}% of budget)")
print(f"Savings per frame:     {hsv_savings:.3f}ms")

print("\n" + "="*70)
if speedup_pct > 50:
    print("  OPTIMIZATION SUCCESS - MAJOR PERFORMANCE GAIN")
elif speedup_pct > 20:
    print("  OPTIMIZATION SUCCESS - MODERATE PERFORMANCE GAIN")
elif speedup_pct > 0:
    print("  OPTIMIZATION SUCCESS - MINOR PERFORMANCE GAIN")
else:
    print("  UNEXPECTED RESULT - INVESTIGATE")
print("="*70)

# Expected results on Raspberry Pi 4:
# - Reference: ~0.002-0.005ms per conversion
# - Optimized: ~0.0005-0.001ms per conversion
# - Speedup: 50-80% faster
# - Per rainbow cycle: 5-8ms saved (target from engineer notes)
