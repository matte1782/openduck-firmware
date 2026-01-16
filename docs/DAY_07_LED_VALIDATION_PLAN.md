# Day 7 - LED Ring Validation Plan (REVISED)
## Date: 21 January 2026 | Status: APPROVED with CRITICAL fixes

**Context:**
- Team ahead of schedule (60-65% vs 55-60% target)
- No critical hardware arriving until next week
- WS2812B LED rings physically available
- This is a "light day" (60 min max) before Week 02 intensity

---

## ⚠️ CRITICAL FIXES FROM HOSTILE REVIEW

### Issue C1: Power Supply
- **WRONG:** Original plan used 3.3V (WS2812B requires 5V)
- **FIXED:** Use external 5V supply with shared ground OR Pi 5V with current monitoring

### Issue C2: Voltage Level Shifting
- **WRONG:** Pi GPIO outputs 3.3V logic; WS2812B expects 5V logic
- **FIXED:** Test without shifter first (may work), but document risk and be prepared to add 74AHCT125 if needed

### Issue C3: Current Measurement
- **WRONG:** No current monitoring → brownout risk → SD card corruption
- **FIXED:** Mandatory multimeter measurement before connecting to Pi

### Issue H1: GPIO Pin Choice
- **WRONG:** GPIO 10 is non-standard for WS2812B
- **FIXED:** Use GPIO 18 (PWM0, Physical Pin 12) - standard for rpi_ws281x library

---

## REVISED SCOPE (60 minutes maximum)

### Pre-Flight Checks (10 min)

```
[ ] Verify GPIO 18 available in hardware_config.yaml
[ ] Check rpi_ws281x library installed: pip3 show rpi-ws281x
[ ] Review PRE_WIRING_CHECKLIST.md workflow
[ ] Multimeter ready for current measurement
[ ] External 5V power supply OR Pi 5V rail decision made
[ ] Hard timer set for 60 minutes
```

---

### Hardware Setup (15 min)

**Wiring Configuration:**

| Connection | LED Ring Side | Raspberry Pi Side | Notes |
|------------|---------------|-------------------|-------|
| Data       | DIN pin       | GPIO 18 (Pin 12)  | PWM0 - standard for WS2812B |
| Power      | 5V / VCC      | **Option A:** External 5V supply<br>**Option B:** Pi Pin 2 (5V) with current meter | Measure first! |
| Ground     | GND           | Pi Pin 6 (GND) + external supply GND if used | Common ground required |

**Power Supply Options:**

**Option A: External 5V Supply (RECOMMENDED)**
- Use USB power adapter (5V 2A)
- Connect GND to both LED ring AND Pi Pin 6 (shared ground)
- No risk to Pi power supply
- Required if testing >6 LEDs at full brightness

**Option B: Pi 5V Rail (with current monitoring)**
- Measure current draw BEFORE connecting to Pi:
  - Power LED ring from bench supply or USB adapter
  - Set LEDs to (128, 128, 128) — 50% white
  - Measure current with multimeter
  - If >400mA → Use Option A instead
  - If <400mA → Safe to use Pi 5V rail

**CRITICAL: Current Budget Check**
```
12 LEDs at 50% brightness (128,128,128):
- Per LED: ~30mA (50% of 60mA max)
- Total: 12 × 30mA = 360mA
- Pi 5V rail budget: ~1.2A (USB-C supply)
- Pi base load: 400-600mA
- Safety margin: 1200 - 600 - 360 = 240mA ✅ ACCEPTABLE

If using 16-LED ring: 16 × 30mA = 480mA
Safety margin: 1200 - 600 - 480 = 120mA ⚠️ MARGINAL (use external supply)
```

**Voltage Level Shifting:**
- Test WITHOUT level shifter first (GPIO 18 → DIN direct)
- WS2812B threshold: ~0.7×VDD = 3.5V (Pi outputs 3.3V)
- May work due to short wire lengths (<15cm recommended)
- If LEDs flicker/fail: Add 74AHCT125 level shifter OR 330Ω resistor trick

**Photo Checklist:**
```
[ ] Photo 1: LED ring with pin labels visible
[ ] Photo 2: Wiring connections (data, power, ground)
[ ] Photo 3: Multimeter showing current measurement
[ ] Photo 4: Complete setup before power on
```

---

### Software Test (20 min)

**Install Library (if needed):**
```bash
# Check if installed
pip3 show rpi-ws281x

# If not installed
sudo pip3 install rpi-ws281x
```

**Minimal Test Script:**

Create `test_led_ring.py`:
```python
#!/usr/bin/env python3
"""
Day 7 LED Ring Validation - Minimal Test
GPIO 18 (PWM0), 50% white brightness only
"""

from rpi_ws281x import PixelStrip, Color
import time

# LED strip configuration
LED_COUNT = 12        # Number of LED pixels (adjust to your ring)
LED_PIN = 18          # GPIO pin connected to pixels (PWM0)
LED_FREQ_HZ = 800000  # LED signal frequency (800kHz)
LED_DMA = 10          # DMA channel (10 is safe default)
LED_BRIGHTNESS = 128  # Brightness (0-255), using 50% for safety
LED_INVERT = False    # Don't invert signal
LED_CHANNEL = 0       # PWM channel (0 or 1)

def main():
    # Create PixelStrip object
    strip = PixelStrip(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA,
                       LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL)

    # Initialize library (must run as root)
    strip.begin()

    print("Setting all LEDs to 50% white...")
    print("Current draw should be ~30mA per LED")
    print(f"Expected total: {LED_COUNT * 30}mA\n")

    # Set all LEDs to 50% white (128, 128, 128)
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, Color(128, 128, 128))
    strip.show()

    print("✅ LEDs should now be lit (dim white)")
    print("If you see light, test PASSED")
    print("\nWaiting 5 seconds...")
    time.sleep(5)

    # Turn off
    print("Turning off...")
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, Color(0, 0, 0))
    strip.show()

    print("✅ Test complete")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\nTest interrupted")
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\nCommon issues:")
        print("- Must run with sudo (GPIO access)")
        print("- Check wiring (data to GPIO 18, not GPIO 10)")
        print("- Verify 5V power connected")
        print("- Try adding level shifter if LEDs don't respond")
```

**Run Test:**
```bash
cd ~/openduck_v3/firmware
sudo python3 test_led_ring.py
```

**Success Criteria:**
- ✅ LEDs light up (any visible light = PASS)
- ✅ No error messages from library
- ✅ No brownout (Pi stays responsive)
- ✅ Current draw within predicted range

**Failure Modes:**
- No light after 30 min debugging → STOP, document issue, defer to Week 02
- Brownout/reboot → Power supply insufficient, use external supply
- Flickering → Voltage level issue, add 74AHCT125 shifter
- Library errors → GPIO conflict, check pin assignments

---

### Documentation (15 min)

**Update CHANGELOG:**
```markdown
### Day 7 - LED Ring Validation (21 Jan 2026)

**Hardware Test:**
- Component: WS2812B LED Ring ([12 or 16] LEDs)
- GPIO: 18 (PWM0, Physical Pin 12)
- Power: [External 5V / Pi 5V rail]
- Current Draw: [XXX mA measured at 50% brightness]

**Test Results:**
- Library: rpi-ws281x v[X.X.X]
- Test: All LEDs set to (128,128,128) - 50% white
- Result: [PASS / FAIL]
- Issues: [None / List any issues found]

**Notes:**
- Level shifter: [Used / Not needed / Required for reliability]
- Timing: [XX minutes actual vs 60 min budgeted]
- Photos: [List photo filenames]
```

**Take Photos:**
```
[ ] Photo 5: LEDs lit (proof of working test)
[ ] Photo 6: Terminal output showing test results
[ ] Save photos to: firmware/docs/hardware_photos/day_07_led_test_*.jpeg
```

**Update hardware_config.yaml (if needed):**
- Confirm GPIO 18 assignment
- Note actual LED count (12 vs 16)
- Document current draw for future reference

---

## SCOPE LIMITATIONS (DO NOT EXCEED)

### ✅ ALLOWED (Day 7):
- Basic power-on test (one color, one brightness)
- Current measurement
- GPIO pin validation
- Library installation verification
- Documentation of results

### ❌ FORBIDDEN (Defer to Week 02):
- Multiple color tests (red, green, blue, etc.)
- Individual LED addressing tests
- Animation patterns (chase, rainbow, fade, pulse)
- Brightness ramping tests
- Second LED ring testing
- Integration with robot state machine
- Pattern library creation
- Multi-threading considerations
- Performance optimization

---

## HARD STOP CONDITIONS

**Time-Based:**
- ⏰ **60-minute timer beeps → STOP IMMEDIATELY**
- No "just one more test" extensions allowed

**Failure-Based:**
- 30 minutes debugging with no light → STOP, document failure
- Any smoke/heat from LEDs → POWER OFF immediately
- Pi brownout/reboot → STOP, switch to external power or defer
- SD card corruption detected → STOP, reinstall OS if needed

**Scope Creep Detection:**
- If you catch yourself saying "let me just try..." → STOP
- If you open GitHub to find animation code → STOP
- If you start designing patterns → STOP

---

## RISK ASSESSMENT

| Risk | Severity | Mitigation |
|------|----------|------------|
| Pi brownout from LED current draw | HIGH | Measure current first, use external supply if >400mA |
| SD card corruption from brownout | HIGH | Current measurement mandatory before Pi connection |
| Voltage level incompatibility | MEDIUM | Accept risk, add shifter if needed |
| Scope creep (2 hours → 4 hours) | MEDIUM | Hard timer set, explicit forbidden list |
| GPIO conflict with other devices | LOW | Verified GPIO 18 available in config |
| Hardware damage to LEDs | LOW | 50% brightness keeps current safe |

---

## SUCCESS METRICS

**Minimum Viable Success:**
- ✅ LED ring powered without Pi damage
- ✅ At least 1 LED lights up
- ✅ Results documented in CHANGELOG
- ✅ Completed in <60 minutes
- ✅ Photos taken for reference

**Stretch Success (if time permits):**
- ✅ All LEDs light up uniformly
- ✅ Current draw measured and logged
- ✅ Level shifter need documented

**NOT REQUIRED for Day 7:**
- ❌ Perfect brightness uniformity
- ❌ Color accuracy testing
- ❌ Animation capabilities
- ❌ Second ring validation

---

## ALTERNATIVE: SKIP DAY 7 ENTIRELY

**Boston Dynamics Recommendation:**

You're ahead of schedule. Week 02 is intense. A full rest day would:
- Prevent burnout before hard push
- Let you start Week 02 fresh and focused
- Avoid "partial progress" cleanup later

**Counter-Argument:**
LEDs are fun, morale matters, quick wins feel good.

**Verdict:**
Your call. LED test is low-risk validation IF you follow the 60-min limit. Rest is valid too.

---

## APPROVAL STATUS

**Hostile Review Rating:** 7.5/10 (after revisions)

**Approved By:** Boston Dynamics Standards (with mandatory fixes applied)

**Conditions:**
- ✅ Power supply plan fixed (external 5V or current-limited)
- ✅ GPIO 18 used (standard WS2812B pin)
- ✅ Current measurement required before Pi connection
- ✅ Scope reduced to 60 min, single color test only
- ✅ Hard timer set with stop discipline

**Risk Level:** LOW (if current limited), MEDIUM (if scope creep occurs)

**Value Level:** 3/10 (cosmetic feature, not critical path)

**Final Verdict:** APPROVED for execution OR skip entirely (both valid choices)

---

**Document Created:** 21 January 2026
**Hostile Review:** af3fb93 (Complete)
**Status:** ✅ READY FOR EXECUTION (optional)
