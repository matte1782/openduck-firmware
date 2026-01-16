# PCA9685 Wiring Map - Official Project Standard
## Date: 16 January 2026 | Updated: 20 January 2026

**IMPORTANT:** This is the OFFICIAL color mapping for all PCA9685 connections.
Always use these colors for consistency and easy debugging.

---

## ⚠️ CRITICAL: Signal Matching Required!

```
═══════════════════════════════════════════════════════════════
Before connecting, verify SIGNAL NAMES match:

Pi GPIO2 (SDA, Pin 3) → PCA9685 pin labeled "SDA" or "D"
Pi GPIO3 (SCL, Pin 5) → PCA9685 pin labeled "SCL" or "C"

Pin positions don't matter - SIGNAL NAMES must match!
═══════════════════════════════════════════════════════════════
```

---

## 🎨 OFFICIAL COLOR MAPPING

### PCA9685 → Raspberry Pi I2C

| Cable | Function | From (PCA9685) | To (Raspberry Pi) | Voltage/Signal |
|-------|----------|----------------|-------------------|----------------|
| 🔴 RED      | Power     | VCC (Pin 5) | Pin 1 (3.3V)   | 3.3V Power |
| ⚫ BLACK    | Ground    | GND (Pin 1) | Pin 6 (GND)    | 0V Ground  |
| 🟢 GREEN    | I2C Data  | **SDA** (Pin 4) | Pin 3 (GPIO2/**SDA**) | I2C Data |
| 🟡 YELLOW   | I2C Clock | **SCL** (Pin 3) | Pin 5 (GPIO3/**SCL**) | I2C Clock |

**Note:** Pin numbers refer to the 6-pin I2C header (bottom to top). Pins 2 (OE) and 6 (V+) are left empty.

---

## 📊 VISUAL DIAGRAM WITH SIGNAL EMPHASIS

```
    PCA9685 Board                         Raspberry Pi 4
    (Left I2C pins)                       (GPIO Header)

    ┌─────────────┐                       ┌──────────────┐
    │             │                       │              │
    │             │   NOT just positions  │              │
    │             │   ↓                   │              │
    │ Pin 6 (V+)  ○   Must verify         │              │
    │             │   SIGNAL NAMES! ─────→│              │
    │ Pin 5 VCC ●─┼────🔴 RED ────────────┼──● Pin 1     │ 3.3V
    │             │                       │              │
    │ Pin 4 SDA ●─┼────🟢 GREEN ──────────┼──● Pin 3     │ GPIO2/SDA
    │         ↑   │    ↑                  │      ↑       │
    │       LABEL │  VERIFY!              │    LABEL     │
    │             │                       │              │
    │ Pin 3 SCL ●─┼────🟡 YELLOW ─────────┼──● Pin 5     │ GPIO3/SCL
    │         ↑   │    ↑                  │      ↑       │
    │       LABEL │  VERIFY!              │    LABEL     │
    │             │                       │              │
    │ Pin 2 (OE)  ○   (empty)             │              │
    │ Pin 1 GND ●─┼────⚫ BLACK ──────────┼──● Pin 6     │ GND
    │             │                       │              │
    └─────────────┘                       │ [USB-C]──────┼─── Power
                                          └──────────────┘

    ⚠️  GREEN connects to "SDA" label (NOT just "Pin 4")!
    ⚠️  YELLOW connects to "SCL" label (NOT just "Pin 3")!
```

---

## 🔍 DETAILED PIN VIEW

### PCA9685 Pins (6-pin I2C header, BOTTOM to TOP):

```
┌─────────────────────────────────────────┐
│  PCA9685 I2C Connection (Left Side)     │
│  Pin numbering: BOTTOM to TOP           │
│                                         │
│  Pin 6 (TOP):    V+   ○ (empty)         │
│  Pin 5:          VCC  ●──🔴 RED         │
│  Pin 4:          SDA  ●──🟢 GREEN ← DATA SIGNAL   │
│  Pin 3:          SCL  ●──🟡 YELLOW ← CLOCK SIGNAL │
│  Pin 2:          OE   ○ (empty)         │
│  Pin 1 (BOTTOM): GND  ●──⚫ BLACK        │
│                                         │
│  ⚠️  Verify PCB labels match cables!    │
│      GREEN → "SDA" label                │
│      YELLOW → "SCL" label               │
└─────────────────────────────────────────┘
```

### Raspberry Pi GPIO:

```
┌─────────────────────────────────────────┐
│  Raspberry Pi 4 GPIO (Top View)         │
│  Pin 1 is top-left corner               │
│                                         │
│  Pin 1 (3.3V)    [●]──🔴 RED            │
│  Pin 2 (5V)      [●]     (empty)        │
│  Pin 3 (GPIO2)   [●]──🟢 GREEN ← SDA    │
│  Pin 4 (5V)      [●]     (empty)        │
│  Pin 5 (GPIO3)   [●]──🟡 YELLOW ← SCL   │
│  Pin 6 (GND)     [●]──⚫ BLACK           │
│  Pin 7 (GPIO4)   [●]     (empty)        │
│  ...                                    │
│                                         │
│  ⚠️  GREEN cable MUST go to Pin 3 (SDA) │
│  ⚠️  YELLOW cable MUST go to Pin 5 (SCL)│
└─────────────────────────────────────────┘
```

---

## 📋 WIRING CHECKLIST WITH SIGNAL VERIFICATION

### Before Connecting (Raspberry Pi OFF):

```
[ ] I have 4 F-F cables: Red, Black, Green, Yellow
[ ] Raspberry Pi is OFF (USB-C disconnected)
[ ] Safe workspace prepared
[ ] I read PRE_WIRING_CHECKLIST.md
[ ] I will take photos BEFORE and AFTER connecting
```

### Connection Order (ONE cable at a time):

#### STEP 1: BLACK Cable ⚫ (Ground First!)
```
From: PCA9685 Pin 1 (BOTTOM) - labeled "GND" or "G"
To:   Raspberry Pi Pin 6 - labeled "GND"
[ ] Connected and fully inserted
[ ] Verified: Firm connection, not loose
```

#### STEP 2: RED Cable 🔴 (Power Second!)
```
From: PCA9685 Pin 5 - labeled "VCC" or "V"
To:   Raspberry Pi Pin 1 (top-left corner) - labeled "3V3" or "3.3V"
[ ] Connected and fully inserted
[ ] Verified: Firm connection, not loose
```

#### STEP 3: GREEN Cable 🟢 (Data Line - CRITICAL!)
```
⚠️  VERIFY SIGNAL NAME BEFORE CONNECTING!

From: PCA9685 Pin 4 - labeled "SDA" or "D" (CHECK LABEL!)
To:   Raspberry Pi Pin 3 - labeled "GPIO2" or "SDA"
[ ] Verified: PCA9685 label says "SDA" (NOT "SCL")
[ ] Connected and fully inserted
[ ] Double-checked: GREEN goes to "SDA" label
```

#### STEP 4: YELLOW Cable 🟡 (Clock Line - CRITICAL!)
```
⚠️  VERIFY SIGNAL NAME BEFORE CONNECTING!

From: PCA9685 Pin 3 - labeled "SCL" or "C" (CHECK LABEL!)
To:   Raspberry Pi Pin 5 - labeled "GPIO3" or "SCL"
[ ] Verified: PCA9685 label says "SCL" (NOT "SDA")
[ ] Connected and fully inserted
[ ] Double-checked: YELLOW goes to "SCL" label
```

---

## ✅ FINAL VERIFICATION (Before Power On!)

### Signal Matching Checklist (CRITICAL):

```
⚠️  Say this out loud before powering on:

[ ] "GREEN cable connects Pi SDA to PCA9685 SDA label"
[ ] "YELLOW cable connects Pi SCL to PCA9685 SCL label"
[ ] "Not just Pin 3 to Pin 3 - I verified SIGNAL NAMES"

Color Checklist:
[ ] PCA9685 VCC (Pin 5) → 🔴 RED → Pi Pin 1 (3.3V)
[ ] PCA9685 GND (Pin 1) → ⚫ BLACK → Pi Pin 6 (GND)
[ ] PCA9685 **SDA label** (Pin 4) → 🟢 GREEN → Pi Pin 3 (GPIO2/SDA)
[ ] PCA9685 **SCL label** (Pin 3) → 🟡 YELLOW → Pi Pin 5 (GPIO3/SCL)

Safety Checklist:
[ ] All 4 cables fully inserted
[ ] No exposed wires touching other pins
[ ] Pins 2 (OE) and 6 (V+) are EMPTY on PCA9685
[ ] Raspberry Pi still OFF
[ ] No loose connections
```

### Photo Verification:

```
[ ] Took photos showing PCA9685 pin labels with cables
[ ] Took photos showing Pi GPIO connections
[ ] Can verify in photos: GREEN → "SDA", YELLOW → "SCL"
[ ] Compared my setup to reference photos:
    - hardware_photos/raspberry_pi_gpio.jpeg
    - hardware_photos/pca9685_connections.jpeg
```

---

## 🎯 PROJECT STANDARD

**This mapping is OFFICIAL for:**
- ✅ Day 6 testing
- ✅ Week 02 hardware integration
- ✅ All future PCA9685 setups
- ✅ Documentation and troubleshooting

**Benefits:**
1. **Consistency:** Same colors = fewer errors
2. **Quick debugging:** If SDA fails, check GREEN cable
3. **Maintenance:** Anyone can follow the standard
4. **Photo documentation:** Colors easily recognizable

---

## 🔧 TROUBLESHOOTING BY COLOR

| Problem | Cable to Check | What to Verify |
|---------|---------------|----------------|
| I2C doesn't detect 0x40 | 🟢 GREEN, 🟡 YELLOW | **SDA/SCL SWAPPED?** Most common! |
| Board doesn't power on | 🔴 RED, ⚫ BLACK | Power connections |
| "No such device" error | 🟢 GREEN | SDA connection |
| Clock error | 🟡 YELLOW | SCL connection |
| Unstable data reads | All cables | Loose connections |

### If Device Not Detected:

**Most Common Cause (90%):** SDA/SCL cables swapped!

**Quick Fix:**
1. Power OFF: `sudo poweroff`
2. Check photos: Does GREEN go to "SDA" label?
3. If NO: Swap GREEN and YELLOW cables
4. Verify: GREEN → "SDA", YELLOW → "SCL"
5. Power ON and test: `sudo i2cdetect -y 1`

---

## 📸 PHOTO DOCUMENTATION NOTES

When taking photos of your setup:
- Ensure cable colors are clearly visible
- Take photos from multiple angles (top view, side view, close-ups)
- Show PCB labels with connected cables
- Save in: `firmware/docs/hardware_photos/`
- Compare to reference photos before powering on

---

## 📝 REVISION HISTORY

| Date | Version | Changes |
|------|---------|---------|
| 16 Jan 2026 | 1.0 | Initial mapping for Day 6 |
| 20 Jan 2026 | 2.0 | Added SDA/SCL warnings, 6-pin layout, signal emphasis (hostile review fixes) |

---

**Document Created:** 16 January 2026
**Last Updated:** 20 January 2026
**Status:** ✅ APPROVED - Official Project Standard
**File:** `firmware/docs/WIRING_MAP_PCA9685.md`
