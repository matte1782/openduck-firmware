# Firmware - OpenDuck Mini V3

## Overview

This directory contains the firmware for the OpenDuck Mini V3 robot, designed to run on a Raspberry Pi Zero 2W with USB-UART servo control.

## Directory Structure

```
firmware/
├── openduck_firmware/          # Main firmware (to be populated from upstream)
│   ├── src/                    # Source files
│   ├── include/                # Header files
│   ├── platformio.ini          # PlatformIO config (if applicable)
│   └── README.md
├── configs/                    # Configuration files
│   ├── servo_limits.yaml       # Servo angle limits and IDs
│   ├── sensor_calibration.yaml # Sensor calibration data
│   └── network_config.yaml     # WiFi/network settings
├── scripts/                    # Utility scripts
│   ├── flash.sh                # Flashing script
│   ├── calibrate_servos.py     # Servo calibration tool
│   └── test_sensors.py         # Sensor test script
└── README_FIRMWARE.md          # This file
```

## Development Environment

### Required Tools

- Python 3.11+
- PlatformIO (for microcontroller firmware)
- Thonny (optional, for quick Pi debugging)

### Setup

```bash
# Install Python dependencies
pip install pyserial pyyaml

# Clone firmware from upstream (when ready)
# git clone <upstream-firmware-repo> openduck_firmware/
```

## Servo Configuration

The robot uses 16× Feetech STS3215 serial bus servos connected via FE-URT-1 USB-UART controller.

### Servo ID Map

| ID | Location | Joint |
|----|----------|-------|
| 1-4 | Front-Left Leg | Hip, Upper, Lower, Ankle |
| 5-8 | Front-Right Leg | Hip, Upper, Lower, Ankle |
| 9-12 | Rear-Left Leg | Hip, Upper, Lower, Ankle |
| 13-16 | Rear-Right Leg | Hip, Upper, Lower, Ankle |

### Servo Limits

See `configs/servo_limits.yaml` for angle limits.

## Calibration Procedure

1. **Connect servos one at a time** to program unique IDs
2. **Set mechanical neutral** - servo horn aligned with leg link
3. **Define software limits** - prevent mechanical collision
4. **Save calibration** to `configs/servo_limits.yaml`

### Calibration Command

```bash
python scripts/calibrate_servos.py --port /dev/ttyUSB0
```

## First Boot Procedure

1. Flash Raspberry Pi OS Lite to SD card
2. Enable SSH, configure WiFi (headless setup)
3. Boot and verify SSH access
4. Install dependencies
5. Clone/copy firmware
6. Connect USB-UART controller
7. Run servo test: `python scripts/test_sensors.py`

## Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| Servo not responding | Wrong ID or disconnected | Check wiring, verify ID |
| USB device not found | Permission or driver issue | Add user to dialout group |
| Servo overshoots | PID tuning needed | Adjust PID values |
| IMU drift | Calibration needed | Run IMU calibration |
