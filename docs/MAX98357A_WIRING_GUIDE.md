# MAX98357A Amplifier Wiring Guide

**Date:** 22 January 2026 (Day 17)
**Component:** MAX98357A I2S Class D Mono Amplifier
**Target:** Raspberry Pi 4

---

## Quick Reference

```
MAX98357A Pin -> Raspberry Pi Pin
================================
VIN          -> Pin 2 or 4 (5V) - IMPORTANT!
GND          -> Pin 6  (GND)
DIN          -> Pin 40 (GPIO 21 - I2S DOUT)
BCLK         -> Pin 12 (GPIO 18 - I2S BCLK)
LRCLK        -> Pin 35 (GPIO 19 - I2S LRCLK)
GAIN         -> GND (15dB) or unconnected (9dB)
SD           -> Unconnected (enabled)
```

**CRITICAL:** VIN must be 5V, NOT 3.3V!

---

## Visual Wiring Diagram

```
    MAX98357A Module            Raspberry Pi 4
    +---------------+           +-------------------------+
    |   MAX98357A   |           |    40-pin GPIO Header   |
    |               |           |                         |
    | VIN *---------+-----------+--* Pin 2 or 4 (5V)     |
    | GND *---------+-----------+--* Pin 6  (GND)        |
    | DIN *---------+-----------+--* Pin 40 (GPIO 21)    |
    | BCLK *--------+-----------+--* Pin 12 (GPIO 18)    |
    | LRCLK *-------+-----------+--* Pin 35 (GPIO 19)    |
    | GAIN *----+   |           |                         |
    |           |   |           |                         |
    |           +-->GND         |   (Connect to GND for   |
    |               |           |    15dB gain)           |
    | SD *          |           |   (Leave unconnected)   |
    |               |           |                         |
    | + *---[SPEAKER]---* -     |                         |
    +---------------+           +-------------------------+
```

---

## Raspberry Pi 4 Pin Header Reference

```
                    +---------------------+
        3.3V    (1) | o o | (2)  5V  <----+-- VIN here (5V!)
  I2C SDA GPIO2 (3) | o o | (4)  5V       |
  I2C SCL GPIO3 (5) | o o | (6)  GND <----+-- GND here
        GPIO4   (7) | o o | (8)  GPIO14   |
          GND   (9) | o o | (10) GPIO15   |
       GPIO17  (11) | o o | (12) GPIO18 <-+-- BCLK here
       GPIO27  (13) | o o | (14) GND      |
       GPIO22  (15) | o o | (16) GPIO23   |
         3.3V  (17) | o o | (18) GPIO24   |
       GPIO10  (19) | o o | (20) GND      |
        GPIO9  (21) | o o | (22) GPIO25   |
       GPIO11  (23) | o o | (24) GPIO8    |
          GND  (25) | o o | (26) GPIO7    |
        GPIO0  (27) | o o | (28) GPIO1    |
        GPIO5  (29) | o o | (30) GND      |
        GPIO6  (31) | o o | (32) GPIO12   |
       GPIO13  (33) | o o | (34) GND      |
       GPIO19  (35) | * o | (36) GPIO16   |<-- LRCLK here
       GPIO26  (37) | o o | (38) GPIO20   |
          GND  (39) | o * | (40) GPIO21 <-+-- DIN here
                    +---------------------+

* = Used by MAX98357A
```

---

## Step-by-Step Wiring Instructions

### Step 1: Gather Materials
- [ ] MAX98357A amplifier module
- [ ] 5x jumper wires (female-to-female)
- [ ] Small speaker (4-8 ohm, 1-3W recommended)
- [ ] Soldering iron (if headers not pre-installed)

### Step 2: Solder Header Pins (if needed)
The MAX98357A module needs header pins soldered:
1. Insert header pins (short side through holes)
2. Solder from the top side
3. Required pins: VIN, GND, DIN, BCLK, LRCLK (5 minimum)
4. Also solder GAIN pin if you want 15dB gain

### Step 3: Power Connection (CRITICAL)
1. Connect MAX98357A **VIN** to Pi **Pin 2 or 4** (5V) - RED wire

   **WARNING:** Do NOT use 3.3V! The amplifier needs 5V for proper operation.

2. Connect MAX98357A **GND** to Pi **Pin 6** (GND) - BLACK wire

### Step 4: I2S Data Connections
3. Connect MAX98357A **DIN** to Pi **Pin 40** (GPIO 21) - GREEN wire
4. Connect MAX98357A **BCLK** to Pi **Pin 12** (GPIO 18) - YELLOW wire
5. Connect MAX98357A **LRCLK** to Pi **Pin 35** (GPIO 19) - BLUE wire

### Step 5: Gain Configuration (Optional)
The GAIN pin controls amplifier gain:
- **Unconnected (floating)**: 9dB gain (default, quieter)
- **Connected to GND**: 15dB gain (louder)
- **Connected to VIN**: 12dB gain (medium)

For louder output, connect GAIN to GND.

### Step 6: Shutdown Pin (Optional)
The SD (shutdown) pin:
- **Unconnected**: Amplifier enabled (normal operation)
- **Connected to GND**: Amplifier disabled (shutdown mode)

Leave unconnected for normal use.

### Step 7: Connect Speaker
Connect a speaker to the output terminals:
- **+** terminal -> Speaker positive (usually marked with +)
- **-** terminal -> Speaker negative

Recommended: 4-8 ohm speaker, 1-3W power rating.

---

## Raspberry Pi Configuration

### Enable I2S Overlay

```bash
sudo nano /boot/config.txt
```

Add these lines:
```ini
# Enable I2S audio
dtparam=i2s=on
```

### Load Audio Module (Optional)

For better audio support:
```bash
# Install ALSA tools
sudo apt install alsa-utils

# Test audio configuration
aplay -l
```

### Reboot
```bash
sudo reboot
```

---

## Test the Amplifier

### Quick Test with Python
```bash
pip install sounddevice numpy

python3 -c "
import numpy as np
import sounddevice as sd

# Generate 440Hz tone
sample_rate = 16000
duration = 1.0
t = np.linspace(0, duration, int(sample_rate * duration))
audio = np.sin(2 * np.pi * 440 * t).astype(np.float32) * 0.5

print('Playing 440Hz tone...')
sd.play(audio, samplerate=sample_rate)
sd.wait()
print('Done!')
"
```

### Run Validation Script
```bash
cd /path/to/robot_jarvis/firmware
python scripts/validate_max98357a_hardware.py
```

---

## Troubleshooting

### No Sound Output
1. **Check VIN voltage**: Must be 5V, not 3.3V
2. **Check speaker connection**: Ensure + and - are connected
3. **Check I2S configuration**: Verify dtparam=i2s=on in config.txt
4. **Reboot**: I2S changes require reboot

### Distorted/Crackling Audio
1. **Power supply issue**: Use official Pi power supply
2. **Ground loop**: Ensure common ground between Pi and amp
3. **Speaker mismatch**: Use 4-8 ohm speaker
4. **Gain too high**: Try GAIN unconnected (9dB) instead of GND (15dB)

### Very Quiet Output
1. **Check GAIN pin**: Connect to GND for 15dB gain
2. **Software volume**: Increase volume in software
3. **Speaker impedance**: 4 ohm speakers are louder than 8 ohm

### GPIO 18/19 Conflict
GPIO 18 (BCLK) and GPIO 19 (LRCLK) are shared with:
- INMP441 microphone (uses same I2S clock lines)
- LED Ring 1 (GPIO 18) - may conflict!

If LEDs conflict with audio:
- Disable LEDs during audio playback
- Or move LED ring to different GPIO (recommended: GPIO 10)

### "Device busy" Error
Another process is using the audio device:
1. Stop any running audio applications
2. Kill any Python scripts using sounddevice
3. Check: `lsof /dev/snd/*`

---

## Wire Color Reference (Suggested)

| Wire Color | Connection |
|------------|------------|
| RED | VIN (5V) |
| BLACK | GND |
| GREEN | DIN (Data) |
| YELLOW | BCLK (Bit Clock) |
| BLUE | LRCLK (Word Select) |

---

## MAX98357A Module Pinout

```
    +-------------------+
    |     MAX98357A     |
    |                   |
    |  VIN   o          |
    |  GND   o          |
    |  SD    o          |   (Shutdown, leave unconnected)
    |  GAIN  o          |   (Ground for 15dB)
    |  DIN   o          |   (I2S data from Pi)
    |  BCLK  o          |   (I2S bit clock)
    |  LRCLK o          |   (I2S word select)
    |                   |
    |  [+] [-]          |   <- Speaker terminals
    +-------------------+
```

---

## I2S Bus Sharing Note

The MAX98357A shares I2S bus signals with INMP441 microphone:
- **BCLK** (GPIO 18): Shared bit clock
- **LRCLK** (GPIO 19): Shared word select
- **DIN** (GPIO 21): Speaker data out (not shared)
- **DOUT** (GPIO 20): Microphone data in (not shared)

The OpenDuck firmware uses `I2SBusManager` to coordinate access. Both devices can work together safely when using the provided drivers.

---

## Speaker Recommendations

| Speaker Type | Impedance | Power | Notes |
|--------------|-----------|-------|-------|
| Small 4 ohm | 4 ohm | 3W | Loudest, small enclosure |
| Small 8 ohm | 8 ohm | 2W | Quieter but clearer |
| Mylar speaker | 8 ohm | 0.5W | Very compact |

For OpenDuck Mini V3, a 28mm or 40mm speaker fits well in the head enclosure.

---

**Document Status:** Ready for Day 17 hardware validation
