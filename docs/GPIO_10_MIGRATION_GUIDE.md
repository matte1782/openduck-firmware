# GPIO 10 Migration Guide - LED Ring 1 Permanent Fix
## OpenDuck Mini V3 - Week 02 Hardware Reconfiguration

**Date Created:** 18 January 2026
**Target Date:** Week 02 Day 8 (22 January 2026)
**Priority:** HIGH - Required before audio system work
**Status:** Planning Complete - Awaiting Execution

---

## Executive Summary

**Problem:** LED Ring 1 (Left Eye) and I2S Audio both require GPIO 18, causing a hardware conflict.

**Current Workaround (Option A):** I2S audio disabled via boot configuration, allowing LED Ring 1 to operate on GPIO 18.

**Permanent Solution (Option B):** Move LED Ring 1 from GPIO 18 → GPIO 10, enabling both LED and audio to coexist.

**Migration Window:** Week 02 Day 8 (22 Jan 2026), estimated 45 minutes.

---

## Pre-Migration Checklist

Before starting the migration, verify:

- [ ] All Weekend LED work is complete and tested
- [ ] Current LED Ring 1 on GPIO 18 is working perfectly
- [ ] No active LED-dependent code is running
- [ ] Raspberry Pi can be powered off safely
- [ ] Git repository is clean (all changes committed)
- [ ] Backup of current hardware_config.yaml exists

---

## Migration Overview

### What Changes

| Component | Current (Option A) | After Migration (Option B) |
|-----------|-------------------|---------------------------|
| LED Ring 1 (Left Eye) | GPIO 18 (Pin 12) | GPIO 10 (Pin 19) |
| LED Ring 2 (Right Eye) | GPIO 13 (Pin 33) | GPIO 13 (Pin 33) - NO CHANGE |
| I2S Audio | DISABLED | ENABLED |
| Boot Config | `dtparam=audio=off` | `dtparam=audio=on` or commented out |

### Why GPIO 10?

GPIO 10 was selected because:

1. **SPI MOSI Pin** - Currently unused (no SPI devices in BOM)
2. **Software PWM Compatible** - rpi_ws281x library supports it
3. **Physically Adjacent** - Pin 19 is near Pin 12 (easy wire routing)
4. **No Conflicts** - No other assigned functions
5. **Future Safe** - SPI can be disabled if needed, just like I2S

---

## Step-by-Step Migration Procedure

### Phase 1: Pre-Migration Testing (5 minutes)

**Purpose:** Verify current configuration works before changes.

```bash
# 1. Test current LED Ring 1 (GPIO 18)
sudo python3 firmware/scripts/test_dual_leds.py

# Expected: Both rings light up, no flickering

# 2. Verify I2S is disabled
aplay -l

# Expected: "no soundcards found" or only HDMI

# 3. Check boot config
grep "dtparam=audio" /boot/firmware/config.txt

# Expected: dtparam=audio=off

# 4. Commit any uncommitted work
cd firmware
git status
git add .
git commit -m "chore: Pre-migration checkpoint - LED Ring 1 on GPIO 18 working"
```

---

### Phase 2: Hardware Disconnection (10 minutes)

**Purpose:** Safely disconnect LED Ring 1 from GPIO 18.

**CRITICAL: Ensure Raspberry Pi is powered OFF before touching wires!**

```bash
# 1. Shutdown Raspberry Pi
sudo shutdown now

# Wait 30 seconds for complete shutdown
```

**Hardware Steps:**

1. **Verify Power is OFF**
   - No LEDs on Raspberry Pi
   - No power to LED rings

2. **Identify LED Ring 1 Wiring**
   - VCC (RED wire) → Pin 2 (5V)
   - GND (ORANGE wire) → Pin 6 (GND)
   - DIN (BROWN wire) → Pin 12 (GPIO 18) ← THIS ONE CHANGES

3. **Disconnect DIN Wire**
   - Gently remove BROWN wire from Pin 12
   - DO NOT disconnect VCC or GND wires

4. **Label for Safety** (optional but recommended)
   - Use masking tape to mark BROWN wire as "Ring 1 DIN"

---

### Phase 3: Hardware Reconnection (10 minutes)

**Purpose:** Connect LED Ring 1 to GPIO 10.

**GPIO 10 Pin Location:**

```
Physical Pin Layout (Raspberry Pi 4):

   Pin 1  (3.3V)  ●────────● Pin 2  (5V) ← LED Ring 1 VCC (no change)
   Pin 3  (GPIO2) ●────────● Pin 4  (5V)
   Pin 5  (GPIO3) ●────────● Pin 6  (GND) ← LED Ring 1 GND (no change)
   Pin 7  (GPIO4) ●────────● Pin 8  (GPIO14)
   Pin 9  (GND)   ●────────● Pin 10 (GPIO15)
   Pin 11 (GPIO17)●────────● Pin 12 (GPIO18) ← OLD LED Ring 1 DIN
   Pin 13 (GPIO27)●────────● Pin 14 (GND)
   Pin 15 (GPIO22)●────────● Pin 16 (GPIO23)
   Pin 17 (3.3V)  ●────────● Pin 18 (GPIO24)
   Pin 19 (GPIO10)●────────● Pin 20 (GND)   ← NEW LED Ring 1 DIN (target!)
        ↑
   THIS IS IT!
```

**Hardware Steps:**

1. **Connect BROWN wire to Pin 19 (GPIO 10)**
   - Firmly insert wire into Pin 19
   - Ensure good connection (gentle tug test)

2. **Verify All Connections**
   - VCC (RED) → Pin 2 (5V) ✓
   - GND (ORANGE) → Pin 6 (GND) ✓
   - DIN (BROWN) → Pin 19 (GPIO 10) ✓

3. **Visual Inspection**
   - No loose wires
   - No shorts between pins
   - Wire routing is clean

---

### Phase 4: Software Configuration (10 minutes)

**Purpose:** Update firmware configs to use GPIO 10.

**DO NOT POWER ON YET - Update configs first!**

```bash
# 1. Boot your development machine (not the Pi yet)
# 2. Update hardware_config.yaml

cd firmware/config
nano hardware_config.yaml
```

**Change this section:**

```yaml
# BEFORE (GPIO 18):
neopixel:
  ring_1:
    data_pin: 18  # GPIO 18 (PWM0, Physical pin 12)
    num_leds: 16
    brightness: 0.5
```

**To this:**

```yaml
# AFTER (GPIO 10):
neopixel:
  ring_1:
    data_pin: 10  # GPIO 10 (SPI0 MOSI, Physical pin 19) - Migrated from GPIO 18
    num_leds: 16
    brightness: 0.5
```

**Update all LED test scripts:**

```bash
# 3. Update test_dual_leds.py (if it hardcodes GPIO 18)
nano firmware/scripts/test_dual_leds.py

# Find:
RING1_PIN = 18

# Change to:
RING1_PIN = 10

# 4. Update openduck_eyes_demo.py
nano firmware/scripts/openduck_eyes_demo.py

# Find:
LEFT_EYE_PIN = 18

# Change to:
LEFT_EYE_PIN = 10

# 5. Commit configuration changes
git add firmware/config/hardware_config.yaml
git add firmware/scripts/test_dual_leds.py
git add firmware/scripts/openduck_eyes_demo.py
git commit -m "config: Migrate LED Ring 1 from GPIO 18 to GPIO 10 (Option B)"
```

**Re-enable I2S Audio:**

```bash
# 6. SSH to Raspberry Pi or edit SD card on dev machine
sudo nano /boot/firmware/config.txt

# Find:
dtparam=audio=off

# Change to:
dtparam=audio=on
# OR simply comment out:
# dtparam=audio=off

# Save and exit (Ctrl+X, Y, Enter)
```

---

### Phase 5: Post-Migration Testing (10 minutes)

**Purpose:** Verify LED Ring 1 works on GPIO 10 and I2S is available.

**Now you can power on the Raspberry Pi:**

```bash
# 1. Power on Raspberry Pi
# (physical power connection)

# 2. SSH into Pi
ssh pi@openduck.local

# 3. TEST 1: Verify I2S audio is now available
aplay -l

# Expected: I2S audio devices listed (or at least NOT "no soundcards")

# 4. TEST 2: Test LED Ring 1 on new GPIO 10
sudo python3 firmware/scripts/test_dual_leds.py

# Expected: Both rings light up perfectly (no flickering)

# 5. TEST 3: Run full eyes demo
sudo python3 firmware/scripts/openduck_eyes_demo.py

# Expected: Smooth animations on both rings

# 6. TEST 4: Long-duration stability test
# Let demo run for 5 minutes, watch for any glitches
# Ctrl+C to stop when satisfied

# 7. TEST 5: Run GPIO validation script
sudo python3 firmware/scripts/validate_gpio_config.py

# Expected: All checks pass, no conflicts detected
```

---

### Phase 6: Audio System Validation (Optional, 5 minutes)

**Purpose:** Confirm I2S audio works alongside LEDs.

```bash
# 1. Test audio output while LEDs run
sudo python3 firmware/scripts/openduck_eyes_demo.py &
speaker-test -t wav -c 2

# Expected:
#   - LEDs continue animating smoothly
#   - Audio plays without interference
#   - No flickering on either LED ring

# 2. Stop both tests
# Press Ctrl+C for speaker-test
# Then:
sudo pkill -f openduck_eyes_demo.py
```

---

## Rollback Procedure

**If migration fails or causes issues:**

### Quick Rollback (Hardware Only)

1. **Power off Raspberry Pi**
   ```bash
   sudo shutdown now
   ```

2. **Move BROWN wire back**
   - From Pin 19 (GPIO 10)
   - To Pin 12 (GPIO 18)

3. **Revert boot config**
   ```bash
   sudo nano /boot/firmware/config.txt
   # Change back to: dtparam=audio=off
   sudo reboot
   ```

4. **Revert git changes**
   ```bash
   git checkout firmware/config/hardware_config.yaml
   git checkout firmware/scripts/test_dual_leds.py
   git checkout firmware/scripts/openduck_eyes_demo.py
   ```

5. **Test rollback**
   ```bash
   sudo python3 firmware/scripts/test_dual_leds.py
   # Should work exactly as before migration
   ```

---

## Known Risks & Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| GPIO 10 doesn't support WS2812B timing | Low | High | Pre-test with simple script before full migration |
| Loose wire connection on Pin 19 | Medium | Medium | Visual inspection + gentle tug test |
| Software PWM jitter on GPIO 10 | Low | Medium | Use same PWM library settings as GPIO 18 |
| SPI peripheral conflict later | Low | Low | SPI can be disabled if needed (like I2S was) |
| Incorrect pin (moved to wrong GPIO) | Low | High | Triple-check pin 19 location before powering on |

---

## Pre-Migration Testing Script

**Create this test before migration to verify GPIO 10 works:**

```python
#!/usr/bin/env python3
# test_gpio10_compatibility.py
# Quick test to verify GPIO 10 can drive WS2812B LEDs

from rpi_ws281x import PixelStrip, Color
import time

# Configuration
LED_COUNT = 16
LED_PIN = 10  # GPIO 10 (Pin 19)
LED_FREQ_HZ = 800000
LED_DMA = 10
LED_BRIGHTNESS = 50
LED_INVERT = False
LED_CHANNEL = 0

def test_gpio10():
    """Test if GPIO 10 can control WS2812B"""
    print("Testing GPIO 10 for WS2812B compatibility...")

    try:
        strip = PixelStrip(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA,
                          LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL)
        strip.begin()

        # Test 1: All RED
        print("Test 1: All RED (3 seconds)")
        for i in range(LED_COUNT):
            strip.setPixelColor(i, Color(255, 0, 0))
        strip.show()
        time.sleep(3)

        # Test 2: All GREEN
        print("Test 2: All GREEN (3 seconds)")
        for i in range(LED_COUNT):
            strip.setPixelColor(i, Color(0, 255, 0))
        strip.show()
        time.sleep(3)

        # Test 3: All BLUE
        print("Test 3: All BLUE (3 seconds)")
        for i in range(LED_COUNT):
            strip.setPixelColor(i, Color(0, 0, 255))
        strip.show()
        time.sleep(3)

        # Turn off
        for i in range(LED_COUNT):
            strip.setPixelColor(i, Color(0, 0, 0))
        strip.show()

        print("SUCCESS: GPIO 10 is compatible with WS2812B!")
        return True

    except Exception as e:
        print(f"FAILED: GPIO 10 cannot drive WS2812B: {e}")
        return False

if __name__ == '__main__':
    import sys
    success = test_gpio10()
    sys.exit(0 if success else 1)
```

**Run this AFTER hardware is moved but BEFORE updating configs:**

```bash
# After moving wire from Pin 12 → Pin 19:
sudo python3 test_gpio10_compatibility.py

# If this fails, rollback immediately!
```

---

## Migration Checklist Summary

Print this and check off during migration:

**Pre-Migration:**
- [ ] LED Ring 1 on GPIO 18 works perfectly
- [ ] I2S audio is disabled (aplay -l shows no soundcards)
- [ ] Git repository is clean
- [ ] Backup of hardware_config.yaml created

**Hardware Migration:**
- [ ] Raspberry Pi powered OFF
- [ ] BROWN wire disconnected from Pin 12 (GPIO 18)
- [ ] BROWN wire connected to Pin 19 (GPIO 10)
- [ ] Visual inspection: all wires secure, no shorts

**Software Migration:**
- [ ] hardware_config.yaml updated (data_pin: 18 → 10)
- [ ] test_dual_leds.py updated (RING1_PIN = 10)
- [ ] openduck_eyes_demo.py updated (LEFT_EYE_PIN = 10)
- [ ] /boot/firmware/config.txt updated (audio=off → audio=on)
- [ ] All changes committed to git

**Post-Migration Testing:**
- [ ] Raspberry Pi powered ON
- [ ] I2S audio available (aplay -l shows devices)
- [ ] LED Ring 1 works on GPIO 10 (no flickering)
- [ ] LED Ring 2 still works on GPIO 13
- [ ] Full eyes demo runs smoothly
- [ ] 5-minute stability test passed
- [ ] GPIO validation script passes (all checks)
- [ ] Audio + LED simultaneous test passed

---

## Success Criteria

Migration is considered successful when:

1. ✅ LED Ring 1 operates on GPIO 10 without flickering
2. ✅ LED Ring 2 continues to work on GPIO 13 (unchanged)
3. ✅ I2S audio devices are detected (`aplay -l`)
4. ✅ Audio can play while LEDs animate (no interference)
5. ✅ All GPIO validation tests pass
6. ✅ 5-minute continuous operation without glitches
7. ✅ No warnings in `dmesg | grep -i gpio`

---

## Post-Migration Documentation Updates

After successful migration, update these files:

1. **CHANGELOG.md**
   - Log migration completion
   - Note any issues encountered
   - Record test results

2. **COMPLETE_PIN_DIAGRAM_V3.md**
   - Update LED Ring 1 from GPIO 18 → GPIO 10
   - Remove GPIO 18 conflict warning

3. **GPIO_CONFLICT_RESOLUTION.md**
   - Mark Option B as COMPLETED
   - Add migration date and results

4. **This file (GPIO_10_MIGRATION_GUIDE.md)**
   - Add "Migration Completed" banner at top
   - Record actual vs. estimated time
   - Note any deviations from plan

---

## Timeline Estimate

| Phase | Duration | Cumulative |
|-------|----------|------------|
| Pre-Migration Testing | 5 min | 5 min |
| Hardware Disconnection | 10 min | 15 min |
| Hardware Reconnection | 10 min | 25 min |
| Software Configuration | 10 min | 35 min |
| Post-Migration Testing | 10 min | 45 min |
| Audio Validation (Optional) | 5 min | 50 min |

**Total Estimated Time:** 45-50 minutes

---

## References

- Original Conflict Analysis: `electronics/diagrams/GPIO_CONFLICT_RESOLUTION.md`
- Complete Pin Diagram: `electronics/diagrams/COMPLETE_PIN_DIAGRAM_V3.md`
- Hardware Config File: `firmware/config/hardware_config.yaml`
- rpi_ws281x Library Docs: https://github.com/jgarff/rpi_ws281x
- Raspberry Pi GPIO Pinout: https://pinout.xyz/

---

## Document Control

| Field | Value |
|-------|-------|
| Version | 1.0 |
| Created | 18 January 2026 |
| Author | Hardware Integration Team |
| Status | Planning Complete - Ready for Execution |
| Target Date | 22 January 2026 (Week 02 Day 8) |
| Last Updated | 18 January 2026 |
| Migration Status | NOT YET STARTED |

---

**Note:** This is the PERMANENT solution. After this migration, both LED and audio systems can operate simultaneously without conflicts.
