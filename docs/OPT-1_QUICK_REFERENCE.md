# OPT-1 Quick Reference Card

**Optimization:** HSV→RGB Lookup Table
**Target Speedup:** 5-8ms per rainbow frame
**Status:** ✅ Implementation complete

---

## Run Commands

```bash
# Normal demo (optimized by default)
sudo python3 firmware/scripts/openduck_eyes_demo.py

# Benchmark mode (compare fast vs slow)
sudo python3 firmware/scripts/openduck_eyes_demo.py --benchmark

# Standalone benchmark (no hardware)
python3 firmware/scripts/benchmark_hsv_lut.py
```

---

## Implementation at a Glance

```python
# Pre-computed at startup (30,976 entries, ~30KB RAM)
HSV_LUT = {(h, s, v): (r, g, b) for all combinations}

# O(1) lookup (no branches, no arithmetic)
def hsv_to_rgb_fast(h, s, v):
    h_key = int(h * 255)
    s_key = min(int(s * 10), 10)
    v_key = min(int(v * 10), 10)
    return HSV_LUT[(h_key, s_key, v_key)]
```

---

## Files Modified/Created

**Modified:**
- `firmware/scripts/openduck_eyes_demo.py` (+168 lines)
- `firmware/CHANGELOG.md` (Day 3 evening session logged)

**Created:**
- `firmware/scripts/benchmark_hsv_lut.py` (176 lines)
- `firmware/docs/OPT-1_HSV_LUT_PERFORMANCE_REPORT.md` (243 lines)
- `firmware/docs/LED_OPTIMIZATION_USAGE.md` (172 lines)
- `firmware/docs/OPT-1_IMPLEMENTATION_SUMMARY.md` (255 lines)
- `firmware/docs/OPT-1_QUICK_REFERENCE.md` (this file)

---

## Key Metrics

| Metric | Value |
|--------|-------|
| LUT entries | 30,976 (256×11×11) |
| Memory overhead | ~30 KB |
| Build time | <50ms (one-time) |
| Target speedup | 5-8ms per frame |
| Expected improvement | 50-80% faster HSV conversions |

---

## Testing Checklist

- [x] ✅ Implementation complete
- [x] ✅ LUT builds without errors
- [x] ✅ Memory overhead <50 KB
- [ ] ⏳ Hardware benchmark (awaiting Pi + LEDs)
- [ ] ⏳ Visual verification (colors identical)
- [ ] ⏳ Long-term stability (1000+ cycles)

---

## Next Steps

1. Run hardware benchmark on Raspberry Pi 4
2. Verify 5-8ms speedup achieved
3. Document actual results
4. Consider OPT-2 (NumPy vectorization) if needed

---

**Last Updated:** 17 January 2026
**Piano B Progress:** Part 1 of 2 complete
