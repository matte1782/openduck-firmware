# Day 6 - PCA9685 Hardware Verification Commands
## Date: 16 January 2026

---

## ⚠️ BEFORE YOU START: Signal Matching is Critical!

```
═══════════════════════════════════════════════════════════════
⚠️  Pi GPIO2 (SDA) → MUST CONNECT TO → PCA9685 SDA pin
⚠️  Pi GPIO3 (SCL) → MUST CONNECT TO → PCA9685 SCL pin

Swapping SDA/SCL is the #1 cause of "device not detected"!
ALWAYS verify signal names, not just pin positions!
═══════════════════════════════════════════════════════════════
```

**Reference Photos (Day 6 Working Configuration):**
- `hardware_photos/raspberry_pi_gpio.jpeg` - Correct Pi GPIO connections
- `hardware_photos/pca9685_connections.jpeg` - Correct PCA9685 connections

Compare your setup to these photos BEFORE running tests!

---

## Quick Reference - Commands to Run

### Step 1: SSH into Raspberry Pi

```bash
ssh pi@openduck.local
# Password: openduck2026v3xyz
```

### Step 2: I2C Detection Test

```bash
sudo i2cdetect -y 1
```

**Expected Output:**
```
     0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
00:                         -- -- -- -- -- -- -- --
10: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
20: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
30: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
40: 40 -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
50: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
60: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
70: -- -- -- -- -- -- -- --
```

**Success Criteria:** You should see `40` at address 0x40.

---

### Step 3: Hardware Validation Script (I2C Tests)

```bash
cd ~/firmware
python3 scripts/hardware_validation.py --i2c
```

**Expected Output:**
```
==================================================================
  OpenDuck Mini V3 - Hardware Validation (No Batteries Required)
==================================================================
Platform: Linux-6.12.47+rpt-rpi-v8-aarch64-with-glibc2.41
Python: 3.13.x
Date: 2026-01-16 HH:MM:SS

─── I2C Bus Tests ───────────────────────────────────────────────
[PASS] I2C bus initialized                          (X.Xms)
[PASS] I2C scan: found 1 device(s)                  (X.Xms)
       └── 0x40: PCA9685 PWM Controller
[PASS] PCA9685 MODE1 register readable              (X.Xms)
[PASS] PCA9685 frequency set to 50Hz                (X.Xms)

==================================================================
RESULT: 4/4 tests passed
==================================================================

✓ Hardware validation PASSED
✓ I2C communication verified
✓ GPIO configuration verified
✓ PWM registers verified

NOTE: Servo MOVEMENT requires battery power.
      This script only validates communication/configuration.
```

---

### Step 4: PWM Signal Test (Optional)

```bash
python3 scripts/hardware_validation.py --pwm
```

**Note:** This tests PWM signal generation but servos won't move without battery power connected to V+.

---

## Troubleshooting

### Issue: "No devices found" in i2cdetect

⚠️ **MOST COMMON CAUSE: SDA/SCL cables swapped!**

This is the #1 failure mode. Before checking anything else:

**Quick Fix - Try Cable Swap:**
```bash
# Power OFF Raspberry Pi
sudo poweroff

# Swap GREEN and YELLOW/ORANGE cables on EITHER side:
# Option A: Swap on Pi side (Pin 3 ↔ Pin 5)
# Option B: Swap on PCA9685 side (SDA pin ↔ SCL pin)

# Verify after swap:
# - GREEN cable goes to pin labeled "SDA" (NOT "SCL")
# - YELLOW/ORANGE cable goes to pin labeled "SCL" (NOT "SDA")

# Power ON and test again
sudo i2cdetect -y 1
```

**If still not detected, check:**

1. **Signal matching (CRITICAL!):**
   - ⚠️ Pi SDA (GPIO2, Pin 3) → PCA9685 pin labeled "SDA" or "D"
   - ⚠️ Pi SCL (GPIO3, Pin 5) → PCA9685 pin labeled "SCL" or "C"
   - NOT just "Pin 3 to Pin 3" - verify SIGNAL NAMES match!

2. All 4 cables properly connected:
   - 🔴 RED: PCA9685 VCC → Pi Pin 1 (3.3V)
   - ⚫ BLACK: PCA9685 GND → Pi Pin 6 (GND)
   - 🟢 GREEN: PCA9685 **SDA** → Pi Pin 3 (GPIO2/**SDA**)
   - 🟡 YELLOW: PCA9685 **SCL** → Pi Pin 5 (GPIO3/**SCL**)

3. Compare your setup to reference photos:
   - `hardware_photos/raspberry_pi_gpio.jpeg`
   - `hardware_photos/pca9685_connections.jpeg`

4. I2C enabled:
   ```bash
   sudo raspi-config
   # Interface Options → I2C → Yes
   sudo reboot
   ```

5. I2C module loaded:
   ```bash
   lsmod | grep i2c
   # Should show: i2c_dev, i2c_bcm2835
   ```

### Issue: "Module not found" errors

**Install missing packages:**
```bash
python3 -m pip install --break-system-packages adafruit-blinka adafruit-circuitpython-pca9685 RPi.GPIO
```

### Issue: "Permission denied" for I2C

**Add user to i2c group:**
```bash
sudo usermod -aG i2c pi
# Then logout and login again
```

---

## What to Report Back

After running the tests, report:

1. **i2cdetect output:** Did you see `40` at address 0x40?
2. **Hardware validation results:** How many tests passed?
3. **Any error messages:** Copy the full error if tests failed

---

## Connection Reference

### Your Wiring (Confirmed):
```
PCA9685 Side (Left pins, 6 total):
Pin 1 (BOTTOM): GND → ⚫ BLACK → Pi Pin 6
Pin 2:          OE → EMPTY (not connected)
Pin 3:          SCL → 🟠 ORANGE → Pi Pin 5
Pin 4:          SDA → 🟢 GREEN → Pi Pin 3
Pin 5:          VCC → 🔴 RED → Pi Pin 1
Pin 6 (TOP):    V+ → EMPTY (not connected)
```

### Raspberry Pi GPIO (Top 6 pins):
```
Pin 1: 3.3V  ← 🔴 RED
Pin 2: 5V    (empty)
Pin 3: GPIO2 ← 🟢 GREEN
Pin 4: 5V    (empty)
Pin 5: GPIO3 ← 🟠 ORANGE
Pin 6: GND   ← ⚫ BLACK
```

---

**Document Created:** 16 January 2026
**Purpose:** Quick reference for Day 6 PCA9685 hardware verification
**Status:** Ready for testing
