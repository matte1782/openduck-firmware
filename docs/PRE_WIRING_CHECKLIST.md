# Pre-Wiring Checklist (MANDATORY)
## DO NOT SKIP - Prevents 90% of Connection Failures

**Purpose:** This checklist prevents the #1 failure mode: SDA/SCL cable swap

**Time Required:** 5-10 minutes (saves 60-90 minutes of troubleshooting!)

**Created:** 20 January 2026 (after Day 6 hostile review)

---

## Why This Checklist Exists

**Day 6 Lesson Learned:**
- 90 minutes of troubleshooting traced to SDA/SCL cables swapped
- Correct physical pin positions but wrong signal mapping
- Photos would have identified the issue in 2 minutes
- This checklist prevents repeating that mistake

---

## ⚠️ CRITICAL RULE

```
═══════════════════════════════════════════════════════════════
Signal names MUST match - NOT just pin positions!

Pi SDA (GPIO2, Pin 3) → MUST GO TO → Device SDA pin
Pi SCL (GPIO3, Pin 5) → MUST GO TO → Device SCL pin

VERIFY LABELS - Don't assume "Pin 3 to Pin 3" is correct!
═══════════════════════════════════════════════════════════════
```

---

## STEP 1: Identify Components (Take Photos FIRST!) 📸

**MANDATORY: Take photos BEFORE connecting anything!**

```
[ ] Photo 1: Device board top-down view
    - Show all pin labels clearly
    - Verify you can read "SDA", "SCL", "VCC", "GND"

[ ] Photo 2: Close-up of I2C pins on device
    - Zoomed in to show individual pin labels
    - Must be able to read text on PCB

[ ] Photo 3: Raspberry Pi GPIO header
    - Top-down view, pins 1-40 visible
    - Show orientation (Pin 1 in top-left corner)

[ ] Photo 4: All cables laid out with labels
    - Write cable purpose on paper: "SDA - GREEN", "SCL - YELLOW", etc.
    - Take photo showing cables with labels
```

**Why photos are mandatory:**
- If connection fails, photos help diagnose cable swaps instantly
- Visual verification catches errors before powering on
- Reference for future connections or troubleshooting
- Can share with others for remote debugging

---

## STEP 2: Plan Connections (Write It Down!)

**Before touching ANY cables, complete this table:**

| Cable Color | From Pi Side          | Signal | To Device Side       | Device Pin # |
|-------------|-----------------------|--------|----------------------|--------------|
| 🔴 RED      | Pin 1 (3.3V)          | Power  | VCC pin (verify!)    | _____        |
| ⚫ BLACK    | Pin 6 (GND)           | Ground | GND pin (verify!)    | _____        |
| 🟢 GREEN    | Pin 3 (GPIO2/**SDA**) | Data   | **SDA** pin (verify!)| _____        |
| 🟡 YELLOW   | Pin 5 (GPIO3/**SCL**) | Clock  | **SCL** pin (verify!)| _____        |

**Verification steps:**
1. Look at your device PCB - find the pin labeled "SDA"
2. Write down its physical position (e.g., "Pin 4 from bottom")
3. That's where the GREEN (SDA) cable MUST go
4. Repeat for SCL - find "SCL" label on device
5. That's where the YELLOW (SCL) cable MUST go

---

## STEP 3: Verify Signal Matching (CRITICAL!)

**Complete ALL checks before connecting:**

```
Physical Pin Matching:
[ ] I found Pin 1 on Raspberry Pi (top-left, labeled "3.3V")
[ ] I found Pin 3 on Raspberry Pi (labeled "GPIO2" or "SDA")
[ ] I found Pin 5 on Raspberry Pi (labeled "GPIO3" or "SCL")
[ ] I found Pin 6 on Raspberry Pi (labeled "GND")

Device Pin Identification:
[ ] I found the pin labeled "VCC" or "V" or "3.3V" on device
[ ] I found the pin labeled "GND" or "G" on device
[ ] I found the pin labeled "SDA" or "D" on device
[ ] I found the pin labeled "SCL" or "C" or "CL" on device

Signal Matching (MOST IMPORTANT!):
[ ] Pi SDA (Pin 3) will connect to device pin labeled "SDA" ✓
[ ] Pi SCL (Pin 5) will connect to device pin labeled "SCL" ✓
[ ] NOT just "Pin 3 to Pin 3" - I verified SIGNAL NAMES!
[ ] I wrote down the mapping in the table above
```

---

## STEP 4: Connect ONE Cable at a Time

**Follow this exact order:**

**Cable 1: Ground (BLACK) ⚫**
```
[ ] Raspberry Pi Pin 6 (GND)
[ ] Device pin labeled "GND" or "G"
[ ] Press gently until "click"
[ ] Verify: Cable is firmly inserted, not loose
[ ] Take photo of this connection
```

**Cable 2: Power (RED) 🔴**
```
[ ] Raspberry Pi Pin 1 (3.3V)
[ ] Device pin labeled "VCC" or "V"
[ ] Press gently until "click"
[ ] Verify: Cable is firmly inserted, not loose
[ ] Take photo of this connection
```

**Cable 3: Data (GREEN) 🟢 - CRITICAL!**
```
⚠️  THIS IS WHERE MOST MISTAKES HAPPEN!

[ ] Raspberry Pi Pin 3 (look for "GPIO2" or "SDA" label on Pi)
[ ] Device pin labeled "SDA" or "D" (NOT "SCL"!)
[ ] Double-check: Device label says "SDA" (S-D-A)
[ ] Press gently until "click"
[ ] Verify: Cable is firmly inserted
[ ] Take photo showing cable connected to "SDA" label
```

**Cable 4: Clock (YELLOW) 🟡 - CRITICAL!**
```
⚠️  THIS IS WHERE MOST MISTAKES HAPPEN!

[ ] Raspberry Pi Pin 5 (look for "GPIO3" or "SCL" label on Pi)
[ ] Device pin labeled "SCL" or "C" (NOT "SDA"!)
[ ] Double-check: Device label says "SCL" (S-C-L)
[ ] Press gently until "click"
[ ] Verify: Cable is firmly inserted
[ ] Take photo showing cable connected to "SCL" label
```

---

## STEP 5: Pre-Power Photo Verification 📸

**MANDATORY: Take "after" photos BEFORE powering on!**

```
[ ] Photo 5: All 4 cables connected to device
    - Must show pin labels and cable colors
    - Zoom in if needed to show labels

[ ] Photo 6: All 4 cables connected to Raspberry Pi
    - Show GPIO header with cables inserted
    - Verify cables in correct rows (odd/even pins)

[ ] Photo 7: Full setup - both boards connected
    - Overview shot showing complete system
    - Verify no cables touching wrong pins

[ ] Photo 8: Close-up of SDA/SCL verification
    - GREEN cable goes to pin labeled "SDA" ✓
    - YELLOW cable goes to pin labeled "SCL" ✓
```

---

## STEP 6: Final Verification (Before Power!)

**Complete ALL checks:**

```
Visual Inspection:
[ ] All 4 cables firmly inserted (no loose connections)
[ ] No cables touching adjacent pins
[ ] Device board is stable (not dangling by cables)
[ ] Raspberry Pi is currently POWERED OFF

Signal Verification (say it out loud!):
[ ] "RED cable connects 3.3V to VCC" ✓
[ ] "BLACK cable connects GND to GND" ✓
[ ] "GREEN cable connects SDA to SDA" ✓
[ ] "YELLOW cable connects SCL to SCL" ✓

Photo Verification:
[ ] I took at least 8 photos (4 before, 4 after)
[ ] Photos clearly show pin labels and cable colors
[ ] I can see in photos that SDA goes to SDA, SCL to SCL

Reference Comparison:
[ ] I compared my setup to reference photos (if available)
[ ] My wiring matches the reference configuration
[ ] No visible differences or cable swaps
```

---

## STEP 7: Power On and Test

**Now you can safely power on:**

```bash
# Power on Raspberry Pi
# Wait 30-60 seconds for boot

# SSH into Pi
ssh pi@openduck.local

# Run I2C detection
sudo i2cdetect -y 1

# Expected: Device appears at its address (e.g., 0x40 for PCA9685)
```

**Expected output:**
```
     0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
00:          -- -- -- -- -- -- -- -- -- -- -- -- --
...
40: 40 -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
    ↑
    Device detected! ✅
```

---

## IF DETECTION FAILS (All "--")

**MOST COMMON CAUSE: SDA/SCL cables swapped!**

### Quick Fix:

```bash
# Power OFF immediately
sudo poweroff

# Wait for complete shutdown (30 seconds)

# Check your photos from STEP 5:
# - Look at Photo 8 (SDA/SCL close-up)
# - Does GREEN cable go to pin labeled "SDA"?
# - Does YELLOW cable go to pin labeled "SCL"?

# If NOT, swap the two middle cables:
# Option A: Swap on Pi side (Pin 3 ↔ Pin 5)
# Option B: Swap on device side (SDA pin ↔ SCL pin)

# Take new photos showing corrected wiring

# Power ON and test again
sudo i2cdetect -y 1
```

---

## Troubleshooting Decision Tree

```
Device NOT detected?
    ↓
Did you take photos BEFORE connecting? ─ NO → Go back and take photos now!
    │                                          Then review them carefully.
    YES
    ↓
Look at Photo 8 (SDA/SCL verification):
    ↓
Does GREEN cable connect to "SDA" label? ─ NO → SDA/SCL SWAPPED!
    │                                              ↓
    YES                                        Power OFF, swap cables,
    ↓                                          verify labels, power ON
Does YELLOW cable connect to "SCL" label? ─ NO → SDA/SCL SWAPPED!
    │                                              ↓
    YES                                        Power OFF, swap cables,
    ↓                                          verify labels, power ON
Check power connections:
    │
    ├─ Is RED cable in Pi Pin 1? ─ NO → Fix power connection
    │                             YES
    │                              ↓
    ├─ Is BLACK cable in Pi Pin 6? ─ NO → Fix ground connection
    │                                YES
    │                                 ↓
    ├─ Does device have power LED lit? ─ NO → Check VCC/GND connections
    │                                    YES
    │                                     ↓
    └─ Run diagnostic script: ./firmware/scripts/i2c_diagnostic.sh
```

---

## Quick Reference Card

**Print this and keep near your workstation:**

```
┌──────────────────────────────────────────────────────┐
│  PRE-WIRING CHECKLIST - QUICK VERSION               │
├──────────────────────────────────────────────────────┤
│  BEFORE connecting:                                  │
│  [ ] Take photos (4 minimum)                         │
│  [ ] Write down signal mapping                       │
│  [ ] Verify SDA label on device                      │
│  [ ] Verify SCL label on device                      │
│                                                      │
│  WHILE connecting:                                   │
│  [ ] Connect one cable at a time                     │
│  [ ] Verify label before inserting                   │
│  [ ] GREEN → "SDA" label (NOT "SCL"!)                │
│  [ ] YELLOW → "SCL" label (NOT "SDA"!)               │
│                                                      │
│  AFTER connecting:                                   │
│  [ ] Take photos (4 minimum)                         │
│  [ ] Verify SDA ↔ SDA, SCL ↔ SCL in photos          │
│  [ ] Compare to reference photos                     │
│  [ ] Say mapping out loud before power on            │
│                                                      │
│  CRITICAL RULE:                                      │
│  Signal names MUST match - NOT just pin positions!   │
└──────────────────────────────────────────────────────┘
```

---

## Success Criteria

**You've completed this checklist correctly if:**

✅ You took at least 8 photos (4 before, 4 after connection)
✅ You verified signal names match (SDA↔SDA, SCL↔SCL)
✅ You wrote down the mapping before connecting
✅ You connected cables one at a time in order
✅ You took close-up photos showing pin labels
✅ You compared your setup to reference photos
✅ Device detected on first try (no troubleshooting needed)

**If device NOT detected on first try:**
- This checklist saved you time! Look at your photos.
- Most likely: SDA/SCL swapped (check Photo 8)
- Fix takes 2 minutes instead of 90 minutes without photos

---

## For Future Hardware

**Use this checklist for ANY I2C device:**
- BNO085 IMU (coming Day 7)
- TCA9548A I2C multiplexer
- OLED displays
- Additional sensors

**Adapt the table in STEP 2 for each device.**

---

**Document Created:** 20 January 2026
**Reason:** Prevent Day 6 SDA/SCL swap incident from repeating
**Based On:** 90-minute troubleshooting session analysis
**Status:** ✅ MANDATORY for all future I2C connections

**Estimated Time Savings:** 60-90 minutes per connection failure prevented
