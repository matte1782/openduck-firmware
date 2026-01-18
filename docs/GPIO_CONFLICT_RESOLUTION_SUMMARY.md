# GPIO 18 Conflict Resolution - Quick Reference
## OpenDuck Mini V3 - Implementation Summary

**Date:** 18 January 2026
**Status:** ✅ READY FOR RASPBERRY PI EXECUTION
**Estimated Time:** 10 minutes

---

## What Was Done

The GPIO 18 conflict between LED Ring 1 and I2S audio has been resolved with **Option A (Weekend Workaround)**.

### Files Created

1. **`firmware/scripts/disable_i2s_audio.sh`** (230 lines)
   - Automated I2S audio disable script
   - Safe with automatic backups
   - One command execution

2. **`firmware/scripts/validate_gpio_config.py`** (580 lines)
   - 9 comprehensive hardware validation checks
   - Verifies conflict resolution status
   - Color-coded pass/fail reports

3. **`firmware/docs/GPIO_10_MIGRATION_GUIDE.md`** (730 lines)
   - Complete Week 02 migration procedure
   - Step-by-step hardware reconfiguration
   - Rollback instructions included

4. **`firmware/config/hardware_config.yaml`** (UPDATED)
   - Added GPIO 18 conflict documentation
   - Marked I2S as disabled
   - Referenced migration guide

---

## How to Use (Raspberry Pi)

### Step 1: Disable I2S Audio (5 minutes)

```bash
# SSH to Raspberry Pi
ssh pi@openduck.local

# Navigate to project
cd robot_jarvis

# Run disable script
sudo bash firmware/scripts/disable_i2s_audio.sh

# Follow prompts and reboot when done
sudo reboot
```

### Step 2: Validate Configuration (3 minutes)

```bash
# After reboot, SSH back in
ssh pi@openduck.local
cd robot_jarvis

# Run validation script
sudo python3 firmware/scripts/validate_gpio_config.py
```

**Expected Output:**
```
========================================
OpenDuck Mini V3 - GPIO Validation
Version: 1.0.0
========================================

[1/9] Checking root access...
  ✓ PASS: Running as root

[2/9] Checking I2S audio status...
  ✓ PASS: I2S audio is disabled (no soundcards found)

[3/9] Checking boot configuration...
  ✓ PASS: dtparam=audio=off found in config

... (7 more checks)

[9/9] Verifying GPIO 18 conflict resolution...
  ✓ PASS: GPIO 18 conflict resolved
    - I2S audio disabled: ✓
    - GPIO 18 accessible: ✓
    - LED Ring 1 can operate on GPIO 18

========================================
STATUS: ALL CHECKS PASSED ✓
========================================

LED Ring 1 (GPIO 18) and LED Ring 2 (GPIO 13) are ready!

Next steps:
  1. Test dual LEDs: sudo python3 firmware/scripts/test_dual_leds.py
  2. Run full demo: sudo python3 firmware/scripts/openduck_eyes_demo.py
```

### Step 3: Test LED Rings (2 minutes)

```bash
# Test both LED rings
sudo python3 firmware/scripts/test_dual_leds.py

# Expected: Both rings light up, no flickering

# Run full demo
sudo python3 firmware/scripts/openduck_eyes_demo.py

# Expected: Smooth eye animations, 8 different emotions
```

---

## What Happens Behind the Scenes

### Before (Conflict State)
```
GPIO 18 (Pin 12):
  ├─ LED Ring 1 (wants to use PWM)
  └─ I2S Audio BCLK (wants to use I2S peripheral)
     └─ CONFLICT! Cannot both operate simultaneously
```

### After Option A (Weekend Workaround)
```
GPIO 18 (Pin 12):
  ├─ LED Ring 1 ✅ (PWM works perfectly)
  └─ I2S Audio ❌ (DISABLED via boot config)

/boot/firmware/config.txt:
  dtparam=audio=off  ← Added by disable_i2s_audio.sh
```

### After Option B (Week 02 Permanent Fix)
```
GPIO 10 (Pin 19):
  └─ LED Ring 1 ✅ (PWM works perfectly)

GPIO 18 (Pin 12):
  └─ I2S Audio BCLK ✅ (Re-enabled)

Both systems coexist! 🎉
```

---

## Current Hardware Configuration

```
LED Ring 1 (Left Eye):
  VCC (RED)    → Pin 2  (5V)
  GND (ORANGE) → Pin 6  (GND)
  DIN (BROWN)  → Pin 12 (GPIO 18) ✅ Works with I2S disabled

LED Ring 2 (Right Eye):
  VCC (RED)    → Pin 4  (5V)
  GND (ORANGE) → Pin 34 (GND)
  DIN (BROWN)  → Pin 33 (GPIO 13) ✅ No conflicts
```

---

## Week 02 Migration (Preview)

In Week 02 Day 8 (22 Jan 2026), LED Ring 1 will be permanently moved:

```
LED Ring 1 (Left Eye):
  VCC (RED)    → Pin 2  (5V)      ← No change
  GND (ORANGE) → Pin 6  (GND)     ← No change
  DIN (BROWN)  → Pin 19 (GPIO 10) ← Changed from Pin 12
```

**Benefits:**
- Both LED Ring 1 AND I2S audio work simultaneously
- No more workarounds needed
- Permanent solution

**Guide:** See `firmware/docs/GPIO_10_MIGRATION_GUIDE.md` for complete procedure.

---

## Troubleshooting

### Issue: "I2S audio still detected after running script"

**Diagnosis:**
```bash
aplay -l
# If shows I2S devices, I2S not disabled
```

**Fix:**
```bash
# Check boot config
cat /boot/firmware/config.txt | grep audio

# Should see: dtparam=audio=off
# If not, manually edit:
sudo nano /boot/firmware/config.txt
# Add: dtparam=audio=off
sudo reboot
```

---

### Issue: "GPIO 18 not accessible for LED Ring 1"

**Diagnosis:**
```bash
# Check if I2S is claiming GPIO 18
dmesg | grep -i i2s
dmesg | grep -i gpio
```

**Fix:**
```bash
# Verify I2S truly disabled
sudo modprobe -r snd_soc_core
sudo reboot

# Then run validation script again
sudo python3 firmware/scripts/validate_gpio_config.py
```

---

### Issue: "LED Ring 1 flickers"

**Possible Causes:**
1. I2S audio not fully disabled
2. Loose wire connection
3. Power supply issues

**Fix:**
```bash
# 1. Verify I2S disabled
aplay -l  # Should show "no soundcards"

# 2. Check power
vcgencmd measure_volts
# Should be ~1.35V for core voltage

# 3. Check for GPIO conflicts
sudo python3 firmware/scripts/validate_gpio_config.py
```

---

### Issue: "Validation script exits with code 2 (warnings)"

**Meaning:** Non-critical issues detected, but system should work.

**Common Warnings:**
- PyYAML not installed (can't validate config file)
- rpi_ws281x not installed (can't test LED hardware)

**Fix:**
```bash
# Install missing dependencies
pip3 install PyYAML rpi_ws281x RPi.GPIO

# Run validation again
sudo python3 firmware/scripts/validate_gpio_config.py
```

---

## Rollback Instructions

If you need to **undo** the changes:

```bash
# Method 1: Re-enable I2S audio
sudo nano /boot/firmware/config.txt
# Change: dtparam=audio=off → dtparam=audio=on
sudo reboot

# Method 2: Restore from backup
sudo cp /boot/firmware/config.txt.backup.YYYYMMDD_HHMMSS /boot/firmware/config.txt
sudo reboot
```

**After rollback:**
- I2S audio will work again
- LED Ring 1 will flicker or fail
- Back to original conflict state

---

## Reference Documentation

| Document | Purpose |
|----------|---------|
| `electronics/diagrams/GPIO_CONFLICT_RESOLUTION.md` | Technical analysis of conflict |
| `electronics/diagrams/COMPLETE_PIN_DIAGRAM_V3.md` | Full GPIO pin assignments |
| `firmware/docs/GPIO_10_MIGRATION_GUIDE.md` | Week 02 permanent fix procedure |
| `firmware/config/hardware_config.yaml` | Current software configuration |
| `firmware/CHANGELOG.md` | Implementation history |

---

## Quick Command Reference

```bash
# Disable I2S audio
sudo bash firmware/scripts/disable_i2s_audio.sh

# Validate GPIO configuration
sudo python3 firmware/scripts/validate_gpio_config.py

# Test LED rings
sudo python3 firmware/scripts/test_dual_leds.py

# Run eye demo
sudo python3 firmware/scripts/openduck_eyes_demo.py

# Check I2S status
aplay -l

# Check boot config
cat /boot/firmware/config.txt | grep audio
```

---

## Success Criteria Checklist

- [ ] `disable_i2s_audio.sh` executed successfully
- [ ] Raspberry Pi rebooted
- [ ] `validate_gpio_config.py` shows "ALL CHECKS PASSED"
- [ ] `aplay -l` shows "no soundcards found"
- [ ] `test_dual_leds.py` shows both rings working
- [ ] `openduck_eyes_demo.py` runs smoothly (no flickering)
- [ ] Ready to proceed with weekend LED optimization

---

## Timeline

| Phase | Time | Status |
|-------|------|--------|
| Planning (Option A selected) | Completed | ✅ |
| Script development | Completed | ✅ |
| Documentation | Completed | ✅ |
| **Raspberry Pi execution** | **10 minutes** | **⏳ PENDING** |
| Weekend LED work | 16-20 hours | 📅 After validation |
| Week 02 GPIO 10 migration | 45 minutes | 📅 Day 8 (22 Jan) |

---

## Contact / Support

**If validation fails or issues occur:**

1. Check `firmware/CHANGELOG.md` for known issues
2. Review `electronics/diagrams/GPIO_CONFLICT_RESOLUTION.md` for technical details
3. Consult `firmware/docs/GPIO_10_MIGRATION_GUIDE.md` for alternative approaches

**Common support scenarios:**
- Scripts won't run → Check file permissions (`chmod +x`)
- I2S won't disable → Manual config edit (instructions above)
- LED still flickers → Verify I2S fully disabled, check power supply
- Validation fails → Review error messages, check dependencies

---

**Status:** ✅ All implementation complete, ready for Raspberry Pi execution
**Next Action:** Run `disable_i2s_audio.sh` on Raspberry Pi
**Estimated Time to Complete:** 10 minutes
