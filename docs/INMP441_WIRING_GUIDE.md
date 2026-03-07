# INMP441 Microphone Wiring Guide

**Date:** 22 January 2026 (Day 17)
**Component:** INMP441 I2S MEMS Microphone
**Target:** Raspberry Pi 4

---

## Quick Reference

```
INMP441 Pin -> Raspberry Pi Pin
================================
VCC         -> Pin 1  (3.3V)
GND         -> Pin 6  (GND)
SD          -> Pin 38 (GPIO 20 - I2S DIN)
WS          -> Pin 35 (GPIO 19 - I2S LRCLK)
SCK         -> Pin 12 (GPIO 18 - I2S BCLK)
L/R         -> GND    (Left channel - mono)
```

---

## Visual Wiring Diagram

```
    INMP441 Module              Raspberry Pi 4
    ┌─────────────┐             ┌─────────────────────────┐
    │   INMP441   │             │    40-pin GPIO Header   │
    │             │             │                         │
    │  VCC ●──────┼─────────────┼──● Pin 1  (3.3V)       │
    │  GND ●──────┼─────────────┼──● Pin 6  (GND)        │
    │   SD ●──────┼─────────────┼──● Pin 38 (GPIO 20)    │
    │   WS ●──────┼─────────────┼──● Pin 35 (GPIO 19)    │
    │  SCK ●──────┼─────────────┼──● Pin 12 (GPIO 18)    │
    │  L/R ●──┬───┤             │                         │
    │         │   │             └─────────────────────────┘
    │         ▼   │
    │        GND  │  (Connect L/R to GND for Left channel)
    └─────────────┘
```

---

## Raspberry Pi 4 Pin Header Reference

```
                    ┌─────────────────────┐
        3.3V    (1) │ ● ○ │ (2)  5V       │
  I2C SDA GPIO2 (3) │ ○ ○ │ (4)  5V       │
  I2C SCL GPIO3 (5) │ ○ ○ │ (6)  GND ◄────┼── INMP441 GND
        GPIO4   (7) │ ○ ○ │ (8)  GPIO14   │
          GND   (9) │ ○ ○ │ (10) GPIO15   │
       GPIO17  (11) │ ○ ○ │ (12) GPIO18 ◄─┼── INMP441 SCK (BCLK)
       GPIO27  (13) │ ○ ○ │ (14) GND      │
       GPIO22  (15) │ ○ ○ │ (16) GPIO23   │
         3.3V  (17) │ ● ○ │ (18) GPIO24   │   ● = 3.3V for VCC
       GPIO10  (19) │ ○ ○ │ (20) GND      │
        GPIO9  (21) │ ○ ○ │ (22) GPIO25   │
       GPIO11  (23) │ ○ ○ │ (24) GPIO8    │
          GND  (25) │ ○ ○ │ (26) GPIO7    │
        GPIO0  (27) │ ○ ○ │ (28) GPIO1    │
        GPIO5  (29) │ ○ ○ │ (30) GND      │
        GPIO6  (31) │ ○ ○ │ (32) GPIO12   │
       GPIO13  (33) │ ○ ○ │ (34) GND      │
       GPIO19  (35) │ ○ ○ │ (36) GPIO16   │◄── INMP441 WS (LRCLK)
       GPIO26  (37) │ ○ ○ │ (38) GPIO20 ◄─┼── INMP441 SD (DIN)
          GND  (39) │ ○ ○ │ (40) GPIO21   │
                    └─────────────────────┘
```

---

## Step-by-Step Wiring Instructions

### Step 1: Gather Materials
- [ ] INMP441 module
- [ ] 5× jumper wires (female-to-female recommended)
- [ ] Breadboard (optional, for cleaner connections)

### Step 2: Power Connections
1. Connect INMP441 **VCC** to Pi **Pin 1** (3.3V) - RED wire
2. Connect INMP441 **GND** to Pi **Pin 6** (GND) - BLACK wire

### Step 3: I2S Data Connections
3. Connect INMP441 **SD** to Pi **Pin 38** (GPIO 20) - GREEN wire
4. Connect INMP441 **WS** to Pi **Pin 35** (GPIO 19) - YELLOW wire
5. Connect INMP441 **SCK** to Pi **Pin 12** (GPIO 18) - BLUE wire

### Step 4: Channel Selection
6. Connect INMP441 **L/R** to **GND** (for Left channel / mono)
   - Can use the same GND rail as step 2

---

## Raspberry Pi Configuration

### Enable I2S Overlay

Edit `/boot/config.txt`:
```bash
sudo nano /boot/config.txt
```

Add these lines:
```ini
# Enable I2S audio
dtparam=i2s=on
```

### Install ALSA I2S Driver

```bash
# Load the I2S module
sudo modprobe snd-bcm2835

# Make it persistent
echo "snd-bcm2835" | sudo tee -a /etc/modules
```

### Reboot
```bash
sudo reboot
```

---

## Verify I2S is Enabled

After reboot, check that I2S is loaded:
```bash
# Check loaded modules
lsmod | grep snd

# Should show:
# snd_bcm2835
# snd_soc_core
# snd_pcm
```

Check audio devices:
```bash
arecord -l
```

---

## Test the Microphone

### Quick Test with arecord
```bash
# Record 5 seconds of audio
arecord -D plughw:0 -c1 -r 16000 -f S16_LE -t wav -d 5 test.wav

# Play it back
aplay test.wav
```

### Run Validation Script
```bash
cd /path/to/robot_jarvis/firmware
python scripts/validate_inmp441_hardware.py
```

---

## Troubleshooting

### No Audio Device Found
- Check `/boot/config.txt` has `dtparam=i2s=on`
- Reboot after making changes
- Run `arecord -l` to list capture devices

### Very Quiet Audio
- Check VCC is connected to 3.3V (not 5V)
- Verify L/R pin is connected to GND
- Try increasing gain in software

### Static/Noise Only
- Check all I2S connections (SD, WS, SCK)
- Verify GND is properly connected
- Check for loose connections

### GPIO 18 Conflict Warning
- GPIO 18 is shared with LED Ring 1
- Disable LEDs during audio testing if needed
- Long-term: Move LED to GPIO 10

---

## Wire Color Reference (Suggested)

| Wire Color | Connection |
|------------|------------|
| RED | VCC (3.3V) |
| BLACK | GND |
| GREEN | SD (Data) |
| YELLOW | WS (Word Select) |
| BLUE | SCK (Clock) |

---

**Document Status:** Ready for Day 17 hardware validation
