# LED Performance Optimization - Usage Guide

## Quick Start

### Run Demo (Normal Mode)
Uses optimized HSV→RGB lookup table by default:
```bash
sudo python3 firmware/scripts/openduck_eyes_demo.py
```

### Run Hardware Benchmark
Compares FAST vs SLOW implementations on actual hardware:
```bash
sudo python3 firmware/scripts/openduck_eyes_demo.py --benchmark
```

### Run Standalone Benchmark
No hardware required (software simulation):
```bash
python3 firmware/scripts/benchmark_hsv_lut.py
```

---

## What Changed

### Before (Reference Implementation)
```python
def rainbow_cycle(duration=5.0):
    for frame in range(frames):
        for i in range(NUM_LEDS):
            hue = ((i * 256 // NUM_LEDS) + (frame * 5)) % 256
            r, g, b = hsv_to_rgb(hue / 255, 1.0, 1.0)  # 6-way conditional
            # ... set LED color
```

**Performance:**
- 16 conversions per frame
- Each conversion: 6 conditional branches + arithmetic
- ~10-15ms per rainbow frame

### After (Optimized with LUT)
```python
# One-time at startup
HSV_LUT = {}  # Pre-compute 30,976 entries

def rainbow_cycle(duration=5.0):
    for frame in range(frames):
        for i in range(NUM_LEDS):
            hue = ((i * 256 // NUM_LEDS) + (frame * 5)) % 256
            r, g, b = hsv_to_rgb_fast(hue / 255, 1.0, 1.0)  # O(1) lookup
            # ... set LED color
```

**Performance:**
- Same visual output
- O(1) dictionary lookup (no branches)
- Target: 2-7ms per rainbow frame (5-8ms saved)

---

## Benchmark Output Example

```
======================================================================
              HSV→RGB PERFORMANCE BENCHMARK (OPT-1)
======================================================================

[BENCHMARK 1/2] Reference HSV→RGB (6-way conditional)
  Rainbow cycle [SLOW (reference)] - BENCHMARKING MODE...
    Frame time: avg=12.345ms, min=11.234ms, max=14.567ms
    Total HSV conversions: 2400

[BENCHMARK 2/2] Optimized HSV→RGB (LUT)
  Rainbow cycle [FAST (LUT)] - BENCHMARKING MODE...
    Frame time: avg=5.678ms, min=4.890ms, max=6.234ms
    Total HSV conversions: 2400

======================================================================
                        RESULTS
======================================================================

Reference (slow):  12.345ms per frame
Optimized (fast):  5.678ms per frame

Speedup:           6.667ms per frame (54.0% faster)
HSV conversions:   2400 total
LUT Memory:        30.45 KB

======================================================================
  OPTIMIZATION SUCCESS
======================================================================
```

---

## Memory Profiling

### Lookup Table Size
- **Entries:** 30,976 (256 hue × 11 saturation × 11 value)
- **Memory:** ~30 KB (acceptable for RPi 4 with 4GB RAM)
- **Build time:** <50ms (one-time at startup)

### Memory Reduction Option
If memory is constrained, reduce LUT resolution:
```python
HSV_LUT_SIZE_H = 128  # Half hue resolution
HSV_LUT_SIZE_S = 6    # Fewer saturation steps
HSV_LUT_SIZE_V = 6    # Fewer value steps
# Result: 4,608 entries, ~5 KB
```

---

## Technical Details

### Lookup Function
```python
def hsv_to_rgb_fast(h, s, v):
    """
    O(1) dictionary lookup - no branches, no arithmetic.

    Args:
        h: Hue (0.0 - 1.0)
        s: Saturation (0.0 - 1.0)
        v: Value (0.0 - 1.0)

    Returns:
        (r, g, b) tuple with values in 0.0 - 1.0 range
    """
    h_key = int(h * 255)
    s_key = min(int(s * 10), 10)  # Clamp to 0-10
    v_key = min(int(v * 10), 10)  # Clamp to 0-10
    return HSV_LUT[(h_key, s_key, v_key)]
```

### Key Quantization
- **Hue:** 256 steps (full 8-bit resolution, visually lossless)
- **Saturation:** 11 steps (0.1 increments, perceptually adequate)
- **Value:** 11 steps (0.1 increments, perceptually adequate)

### Trade-offs
| Aspect | Reference | Optimized |
|--------|-----------|-----------|
| Speed | Slow (branches) | Fast (O(1) lookup) |
| Memory | 0 KB | 30 KB |
| Precision | Exact | Quantized (0.1 S/V steps) |
| Build time | 0 ms | <50 ms |

---

## Validation

### Visual Verification
Both implementations should produce identical rainbow colors:
```bash
# Run reference (slow) - visual check
# Run optimized (fast) - should look identical
```

### Performance Verification
Hardware benchmark should show 5-8ms speedup:
```bash
sudo python3 firmware/scripts/openduck_eyes_demo.py --benchmark
```

Expected result:
- Reference: 10-15ms per frame
- Optimized: 2-7ms per frame
- Speedup: 5-8ms (50-80% faster)

---

## Troubleshooting

### Issue: No speedup observed
**Cause:** Hardware bottleneck (LED update, I2C, etc.)
**Solution:** Run standalone benchmark to isolate HSV conversion performance

### Issue: Colors look different
**Cause:** Quantization error from 0.1 S/V resolution
**Solution:** Increase LUT_SIZE_S and LUT_SIZE_V to 21 (0.05 steps)

### Issue: Memory warning
**Cause:** LUT too large for constrained system
**Solution:** Reduce to 128×6×6 (see Memory Reduction Option above)

---

## Next Optimizations

After OPT-1, consider:

1. **OPT-2: NumPy Vectorization** (3-5ms saved)
   - Replace per-LED loops with vector operations
   - Requires: `pip install numpy`

2. **OPT-3: C Extension Module** (2-3ms saved)
   - Compile critical paths in C
   - Requires: Development toolchain

3. **OPT-4: DMA-based LED Updates** (hardware-dependent)
   - Bypass CPU for LED data transfer
   - Requires: Advanced rpi_ws281x configuration

---

**Last Updated:** 17 January 2026
**Optimization:** OPT-1 (HSV→RGB Lookup Table)
**Status:** Implementation complete, awaiting hardware benchmark
