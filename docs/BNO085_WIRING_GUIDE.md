# BNO085 IMU Wiring Guide

**Date:** 22 January 2026 (Day 17)
**Component:** BNO085 9-DOF Absolute Orientation IMU
**Target:** Raspberry Pi 4

---

## Quick Reference

```
BNO085 Pin -> Raspberry Pi Pin
================================
VIN         -> Pin 1  (3.3V)
GND         -> Pin 6  (GND)
SDA         -> Pin 3  (GPIO 2 - I2C SDA)
SCL         -> Pin 5  (GPIO 3 - I2C SCL)
INT         -> Not connected (optional)
RST         -> Not connected (optional)
```

---

## Visual Wiring Diagram

```
    BNO085 Module               Raspberry Pi 4
    +-------------+             +-------------------------+
    |   BNO085    |             |    40-pin GPIO Header   |
    |             |             |                         |
    | VIN *-------+-------------+--* Pin 1  (3.3V)       |
    | GND *-------+-------------+--* Pin 6  (GND)        |
    | SDA *-------+-------------+--* Pin 3  (GPIO 2)     |
    | SCL *-------+-------------+--* Pin 5  (GPIO 3)     |
    | INT *       |             |                         |
    | RST *       |             |                         |
    +-------------+             +-------------------------+
```

---

## Raspberry Pi 4 Pin Header Reference

```
                    +---------------------+
        3.3V    (1) | * o | (2)  5V       |  <- VIN here (3.3V)
  I2C SDA GPIO2 (3) | * o | (4)  5V       |  <- SDA here
  I2C SCL GPIO3 (5) | * o | (6)  GND      |  <- SCL here, GND here
        GPIO4   (7) | o o | (8)  GPIO14   |
          GND   (9) | o o | (10) GPIO15   |
       GPIO17  (11) | o o | (12) GPIO18   |
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
       GPIO19  (35) | o o | (36) GPIO16   |
       GPIO26  (37) | o o | (38) GPIO20   |
          GND  (39) | o o | (40) GPIO21   |
                    +---------------------+

* = Used by BNO085
```

---

## Step-by-Step Wiring Instructions

### Step 1: Gather Materials
- [ ] BNO085 module (Adafruit or compatible)
- [ ] 4x jumper wires (female-to-female recommended)
- [ ] Soldering iron (if header not pre-soldered)

### Step 2: Solder Header Pins (if needed)
The BNO085 module from Adafruit comes with header pins that need soldering:
1. Insert header pins into the module (short side through holes)
2. Solder from the component side (where BNO085 chip is)
3. Only need to solder: VIN, GND, SDA, SCL (4 pins minimum)

### Step 3: Power Connections
1. Connect BNO085 **VIN** to Pi **Pin 1** (3.3V) - RED wire
2. Connect BNO085 **GND** to Pi **Pin 6** (GND) - BLACK wire

### Step 4: I2C Data Connections
3. Connect BNO085 **SDA** to Pi **Pin 3** (GPIO 2) - BLUE wire
4. Connect BNO085 **SCL** to Pi **Pin 5** (GPIO 3) - YELLOW wire

### Step 5: Optional Connections (Not Required)
- **INT** (Interrupt): Can connect to any free GPIO for interrupt-driven reads
- **RST** (Reset): Can connect to GPIO for hardware reset capability

---

## Raspberry Pi Configuration

### Enable I2C Interface

```bash
sudo raspi-config
```

Navigate to:
1. Interface Options
2. I2C
3. Enable

### Alternative: Edit config.txt

```bash
sudo nano /boot/config.txt
```

Ensure this line exists:
```ini
dtparam=i2c_arm=on
```

### Reboot
```bash
sudo reboot
```

---

## Verify I2C is Enabled

After reboot, check I2C:

```bash
# Check I2C module is loaded
lsmod | grep i2c

# Should show:
# i2c_bcm2835
# i2c_dev

# Install i2c-tools if needed
sudo apt install i2c-tools

# Scan I2C bus
i2cdetect -y 1
```

Expected output:
```
     0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
00:          -- -- -- -- -- -- -- -- -- -- -- -- --
10: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
20: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
30: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
40: -- -- -- -- -- -- -- -- -- -- 4a -- -- -- -- --
50: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
60: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
70: -- -- -- -- -- -- -- --
```

`4a` indicates BNO085 at address 0x4A (default).

---

## Test the IMU

### Quick Test with Python
```bash
# Install dependencies
pip install adafruit-circuitpython-bno08x

# Test script
python3 -c "
import board
import busio
from adafruit_bno08x.i2c import BNO08X_I2C
from adafruit_bno08x import BNO_REPORT_ROTATION_VECTOR
import time

i2c = busio.I2C(board.SCL, board.SDA, frequency=400000)
bno = BNO08X_I2C(i2c)
bno.enable_feature(BNO_REPORT_ROTATION_VECTOR)
time.sleep(0.5)

for _ in range(10):
    quat = bno.quaternion
    print(f'Quaternion: {quat}')
    time.sleep(0.2)
"
```

### Run Validation Script
```bash
cd /path/to/robot_jarvis/firmware
python scripts/validate_bno085_hardware.py
```

---

## Troubleshooting

### BNO085 Not Detected (i2cdetect shows nothing)
1. Check VIN is connected to 3.3V (Pin 1), NOT 5V
2. Check GND is properly connected
3. Check SDA/SCL wires are not swapped
4. Try different jumper wires (common failure point)
5. Check solder joints on the module

### Wrong I2C Address
- Default: 0x4A
- If address jumper is soldered: 0x4B
- Check which address your module uses

### "Remote I/O error"
- Usually indicates loose connection
- Check all wire connections
- Try reducing I2C speed if using long wires

### "Device or resource busy"
- Another program is using I2C
- Stop any running Python scripts using the IMU
- Check for conflicting services

### Noisy/Unstable Readings
- Keep sensor away from motors and magnets
- Ensure stable power supply
- Add decoupling capacitor if needed (0.1uF near VIN)

### I2C Bus Conflict with PCA9685
The BNO085 shares I2C bus with PCA9685 servo controller. The OpenDuck firmware uses I2CBusManager to prevent collisions. When testing manually:
- Only one I2C device should be accessed at a time
- The driver handles bus coordination automatically

---

## Wire Color Reference (Suggested)

| Wire Color | Connection |
|------------|------------|
| RED | VIN (3.3V) |
| BLACK | GND |
| BLUE | SDA (Data) |
| YELLOW | SCL (Clock) |

---

## BNO085 Module Pinout (Adafruit)

```
        +------------------+
        |      BNO085      |
        |                  |
        |  VIN  o          |
        |  3Vo  o          |
        |  GND  o          |
        |  SDA  o          |
        |  SCL  o          |
        |  INT  o          |
        |  RST  o          |
        |  P0   o          |
        |  P1   o          |
        +------------------+
```

**Required pins:** VIN, GND, SDA, SCL (4 pins)
**Optional pins:** INT (interrupt), RST (reset), P0/P1 (protocol selection)

---

## I2C Bus Sharing Note

The BNO085 shares the I2C bus (GPIO 2, 3) with:
- PCA9685 Servo Controller (0x40)

The OpenDuck firmware uses `I2CBusManager` singleton to prevent bus collisions. Both devices work together safely when using the provided drivers.

---

**Document Status:** Ready for Day 17 hardware validation
