# LED CLI - Quick Start Guide

**5-Minute Quick Start for Weekend Engineer**

---

## Installation

```bash
cd firmware/scripts
chmod +x led_cli.py test_led_cli.sh
```

## Run Tests (No Hardware Needed!)

```bash
# Test everything in mock mode
bash test_led_cli.sh
```

## Common Commands

### 1. Preview Pattern (No Hardware)
```bash
python3 led_cli.py preview breathing --emotion happy --duration 5 --no-hardware
```

### 2. Profile Performance
```bash
python3 led_cli.py profile rainbow --frames 250 --no-hardware
```

### 3. Check Config
```bash
python3 led_cli.py validate ../config/hardware_config.yaml
```

### 4. Show Emotions
```bash
python3 led_cli.py emotions --graph
```

### 5. Record Data
```bash
python3 led_cli.py record breathing --duration 10 \
  --output /tmp/profile.json --no-hardware
```

---

## Expected Output (Profile Command)

```
======================================================================
                    FRAME PROFILING REPORT
======================================================================

  Target Performance:
    FPS: 50 Hz
    Frame Time: 20.00 ms

  Actual Performance:
    FPS: 49.87 Hz
    Frame Time: 20.05 ms (avg)
    Jitter: ±0.34 ms

  Frame Breakdown (avg):
    Compute:    2.34 ms  (11.7%)
    SPI:        1.56 ms  (7.8%)
    Total:     20.05 ms
```

---

## Hardware Mode (Raspberry Pi)

```bash
# Add sudo for GPIO access
sudo python3 led_cli.py profile rainbow --frames 250
```

---

## Help

```bash
python3 led_cli.py --help
python3 led_cli.py profile --help
```

---

## Full Documentation

See `LED_CLI_README.md` for complete guide.

---

**Created:** 17 January 2026
**Status:** Ready to use ✅
