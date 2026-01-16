# Your PCA9685 Board - Exact Wiring Guide
## Pin Identification for TECNOIOT PCA9685 Board

**Reference Photos:**
- Product image: `61TYNrkeNPL._SX522_.jpg`
- Actual hardware: `hardware_photos/raspberry_pi_gpio.jpeg`
- Actual hardware: `hardware_photos/pca9685_connections.jpeg`

**Date:** 16 January 2026
**Status:** ✅ VERIFIED - Working configuration (tested Day 6)

---

## ⚠️ CRITICAL: SIGNAL MATCHING, NOT JUST PIN POSITIONS!

```
═══════════════════════════════════════════════════════════════
⚠️  Pi GPIO2 (SDA) → MUST CONNECT TO → PCA9685 SDA pin
⚠️  Pi GPIO3 (SCL) → MUST CONNECT TO → PCA9685 SCL pin

DO NOT just connect "Pin 3 to Pin 3" - VERIFY SIGNAL NAMES!
═══════════════════════════════════════════════════════════════
```

**Why This Matters:**
- Pin position ≠ Pin function
- Swapping SDA and SCL is the #1 cause of "device not detected"
- Correct physical positions but wrong signals = 90 minutes troubleshooting
- **Always verify:** SDA connects to SDA, SCL connects to SCL

---

## 📸 YOUR BOARD - PHOTO ANALYSIS

### What You See on Your Board:

```
Top-down view of TECNOIOT PCA9685:

    Green Terminal Block
           ↓
    ┌─────────────────────────────────────┐
    │  I2C Pins                   [Green] │
    │  (LEFT SIDE)                        │
    │  ████ ← 6 METALLIC pins             │
    │  (4 used,                Capacitor  │
    │   2 empty)                (black)   │
    │  NO colored                         │
    │  caps                               │
    │                                     │
    │        [PCA9685 Chip]               │
    │        (black, center)              │
    │                                     │
    │  ████████████████████████████████   │
    │  ↑                                  │
    │  SERVO Pins with COLORED CAPS       │
    │  Yellow-Red-Black (repeated)        │
    │  Channels 0-15                      │
    └─────────────────────────────────────┘
```

---

## ✅ I2C PINS IDENTIFIED!

### LEFT SIDE - 6 Metallic Pins (NO Colored Caps)

**Physical Layout (BOTTOM to TOP):**

```
         I2C Pins
         (Left Side)
            ↓
    ┌──────────────┐
    │              │
    │  ████  ← 6 metallic pins
    │  ││││     (silver/black, NO colored plastic)
    │  ││││
    │  ││││  ← These are the I2C pins!
    │  ││││
    │  ││││
    │  ││││
    │              │
    └──────────────┘

Pin Numbering (BOTTOM to TOP):
Pin 1 (BOTTOM): GND  → ⚫ BLACK   → Connect to Pi Pin 6
Pin 2:          OE   → (empty - not connected)
Pin 3:          SCL  → 🟡 YELLOW  → Connect to Pi Pin 5
Pin 4:          SDA  → 🟢 GREEN   → Connect to Pi Pin 3
Pin 5:          VCC  → 🔴 RED     → Connect to Pi Pin 1
Pin 6 (TOP):    V+   → (empty - not connected)
```

**PCB Labels (look for these near the pins):**
- "GND" or "G" (bottom)
- "OE" (leave empty)
- "SCL" or "C"
- "SDA" or "D"
- "VCC" or "V"
- "V+" (top, leave empty)

---

## ❌ DO NOT USE THESE PINS!

### SERVO Pins - With Colored Caps

```
        Servo Pins
        (Center/Right)
            ↓
    ┌──────────────────┐
    │                  │
    │  ████████████    │ ← Many pins with COLORED
    │  ↓↓↓↓↓↓↓↓↓↓↓↓    │    CAPS (Yellow/Red/Black)
    │  YRB YRB YRB     │
    │  012 345 678     │
    │                  │
    └──────────────────┘

❌ These are NOT the I2C pins!
❌ They have colored plastic caps
❌ They are for servo motors (not needed today)
```

---

## 🎯 PHYSICAL IDENTIFICATION

### How to Recognize I2C Pins on YOUR Board:

**Visual Characteristics:**

1. **Position:** LEFT SIDE of the board
2. **Count:** 6 pins total (only 4 will be used)
3. **Appearance:** METALLIC silver/black pins
4. **NO Caps:** NO colored plastic caps on top
5. **Separate:** FAR AWAY from the servo pins with colored caps

**vs Servo Pins:**
- Servo pins have COLORED CAPS (yellow/red/black)
- Located in CENTER/RIGHT of board
- MANY pins (16 groups of 3)

---

## 📋 EXACT WIRING PROCEDURE

### STEP 1: Take Reference Photos FIRST! 📸

```
⚠️  MANDATORY: Take photos BEFORE connecting anything!
════════════════════════════════════════════════════════

[ ] Photo 1: Top-down view of PCA9685 board (show pin labels)
[ ] Photo 2: Close-up of LEFT SIDE I2C pins
[ ] Photo 3: Raspberry Pi GPIO header (pins 1-40 visible)
[ ] Photo 4: All 4 cables laid out with labels

WHY: If connection fails, photos help diagnose cable swaps!
```

---

### STEP 2: Orient the Board

**Place board in front of you like this:**

```
    Green terminal block (top right)
              ↓
    ┌─────────────────────────┐
    │ I2C Pins                │
    │ (left)        [Green]   │
    │ ████                    │
    │ ↑ Pin 6 (TOP)           │
    │ │ Pin 5 (VCC)           │
    │ │ Pin 4 (SDA)           │
    │ │ Pin 3 (SCL)    [Chip] │
    │ │ Pin 2 (OE)            │
    │ ↓ Pin 1 (GND)           │
    │                         │
    │      Servo Pins         │
    │      (colored)          │
    └─────────────────────────┘
          YOU ARE HERE ↑
```

---

### STEP 3: Verify Signal Matching (CRITICAL!)

**Before connecting, write down the mapping:**

| Cable Color | From Pi Side          | Signal | To PCA9685 Side      | Pin # |
|-------------|-----------------------|--------|----------------------|-------|
| 🔴 RED      | Pin 1 (3.3V/VCC)      | Power  | VCC pin (labeled)    | 5     |
| ⚫ BLACK    | Pin 6 (GND)           | Ground | GND pin (labeled)    | 1     |
| 🟢 GREEN    | Pin 3 (GPIO2/**SDA**) | Data   | **SDA** pin (labeled)| 4     |
| 🟡 YELLOW   | Pin 5 (GPIO3/**SCL**) | Clock  | **SCL** pin (labeled)| 3     |

```
✅ VERIFICATION CHECKLIST:
[ ] Pi SDA (Pin 3) connects to PCA9685 pin labeled "SDA" or "D"
[ ] Pi SCL (Pin 5) connects to PCA9685 pin labeled "SCL" or "C"
[ ] NOT just "Pin 3 to Pin 3" - I verified SIGNAL NAMES!
[ ] Power (RED) and Ground (BLACK) are correct
```

---

### STEP 4: Physical Connection

**Connect ONE cable at a time, bottom to top:**

**On PCA9685 (LEFT side pins, BOTTOM to TOP):**

1. **⚫ BLACK** → Pin 1 (BOTTOM - GND)
   - Verify PCB label says "GND" or "G"
   - Press gently until you feel a "click"

2. **Skip Pin 2 (OE)** - leave empty

3. **🟡 YELLOW** → Pin 3 (SCL)
   - ⚠️ Verify PCB label says "SCL" or "C"
   - This is the **CLOCK** signal

4. **🟢 GREEN** → Pin 4 (SDA)
   - ⚠️ Verify PCB label says "SDA" or "D"
   - This is the **DATA** signal

5. **🔴 RED** → Pin 5 (VCC)
   - Verify PCB label says "VCC" or "V"
   - This is **3.3V power**

6. **Skip Pin 6 (V+)** - leave empty

---

### STEP 5: Take "After" Photos 📸

```
[ ] Photo 5: All 4 cables connected to PCA9685
[ ] Photo 6: All 4 cables connected to Raspberry Pi
[ ] Photo 7: Full setup showing both boards connected
[ ] Photo 8: Close-up verifying SDA/SCL labels match connections
```

---

## 🎨 FINAL DIAGRAM - YOUR BOARD

```
        YOUR PCA9685 (top-down view)

    Green Terminal Block
         ↓
┌───────────────────────────────────────┐
│                              [Green]  │
│  I2C Pins                   Terminal  │
│  ████ ←─────────┐          Block      │
│  ││││           │                     │
│  ││││           │                     │
│  ││││           │  [Capacitor]        │
│  ││││           │    (Black)          │
│  ││││           │                     │
│  ││││           │                     │
│  ↓              │                     │
│  Pin 6 (V+)     │  [PCA9685 CHIP]    │
│  Pin 5 🔴 VCC   │  (Black, Center)   │
│  Pin 4 🟢 SDA ←─┼─ ⚠️ DATA SIGNAL    │
│  Pin 3 🟡 SCL ←─┼─ ⚠️ CLOCK SIGNAL   │
│  Pin 2 (OE)     │                     │
│  Pin 1 ⚫ GND   │                     │
│                 │  ████████████████   │
│                 │  ↑ Servo Pins       │
│                 │  (Colored: YRB)     │
│                 │  Channels 0-15      │
│                 │                     │
│                 └─→ NOT these!        │
│                                       │
└───────────────────────────────────────┘
```

---

## ⚠️ COMMON MISTAKE: SDA/SCL SWAP

### Most Common Failure Mode:

```
❌ WRONG (causes "device not detected"):
   Pi Pin 3 (SDA) → PCA9685 Pin 3 (SCL)  ← CROSSED!
   Pi Pin 5 (SCL) → PCA9685 Pin 4 (SDA)  ← CROSSED!

✅ CORRECT:
   Pi Pin 3 (SDA) → PCA9685 SDA pin (Pin 4)  ← Matched by SIGNAL
   Pi Pin 5 (SCL) → PCA9685 SCL pin (Pin 3)  ← Matched by SIGNAL
```

**How to Verify:**
1. Look at Raspberry Pi: Find Pin 3 (should say "GPIO2" or "SDA1")
2. Follow the GREEN cable to PCA9685
3. Verify it connects to pin labeled "SDA" or "D" (NOT "SCL"!)
4. Repeat for YELLOW cable → should go to "SCL" or "C"

---

## ✅ FINAL CHECKLIST - YOUR BOARD

**Before powering on:**

```
[ ] I took reference photos BEFORE connecting
[ ] I verified Pi SDA (Pin 3) connects to PCA "SDA" label
[ ] I verified Pi SCL (Pin 5) connects to PCA "SCL" label
[ ] I verified Power (RED) connects to PCA "VCC" label
[ ] I verified Ground (BLACK) connects to PCA "GND" label
[ ] I took "after" photos showing all connections
[ ] Raspberry Pi is currently POWERED OFF
[ ] No cables are touching wrong pins
[ ] I compared my setup to reference photos
```

---

## 🚀 VERIFICATION TEST

**After connecting, run this test:**

```bash
# Power on Raspberry Pi, wait for boot
# SSH in, then run:
sudo i2cdetect -y 1

# Expected output:
#      0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
# 00:          -- -- -- -- -- -- -- -- -- -- -- -- --
# ...
# 40: 40 -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
#     ↑
#     PCA9685 detected at address 0x40! ✅
```

**If you see all "--" (no device detected):**

```
MOST COMMON CAUSE: SDA/SCL cables swapped!

FIX:
1. Power OFF Raspberry Pi
2. Take photo of current wiring
3. Swap GREEN and YELLOW cables on Pi side (or PCA side)
4. Verify: GREEN now goes to "SDA" label, YELLOW to "SCL" label
5. Power ON and test again
```

---

## 📸 REFERENCE PHOTOS

**Working Configuration (Day 6 Verified):**

- `hardware_photos/raspberry_pi_gpio.jpeg` - Shows correct Pi GPIO connections
- `hardware_photos/pca9685_connections.jpeg` - Shows correct PCA9685 connections

Compare your setup to these photos before powering on!

---

## 🎯 ULTRA-SIMPLE SUMMARY

### On YOUR Board:

**✅ USE THESE (Left Side):**
- 6 METALLIC pins (silver/black)
- NO colored caps
- Labels: GND, OE, SCL, SDA, VCC, V+
- Connect 4 cables (skip OE and V+)

**❌ DO NOT USE (Center/Right):**
- Pins with COLORED CAPS (yellow/red/black)
- These are for servos
- Channels 0-15

**⚠️ CRITICAL RULE:**
- **SDA on Pi → SDA on PCA9685** (verify label!)
- **SCL on Pi → SCL on PCA9685** (verify label!)
- Pin positions don't matter - SIGNAL NAMES matter!

---

**Document Created:** 16 January 2026
**Last Updated:** 20 January 2026 (hostile review fixes)
**Based On:** Actual TECNOIOT PCA9685 board photos and verified Day 6 working configuration
**Photos:** `61TYNrkeNPL._SX522_.jpg`, `hardware_photos/*.jpeg`
**Status:** ✅ TESTED & VERIFIED - All tests passed (6/6)
