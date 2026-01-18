# Deployment Package - 17-Emotion System
## Week 02 Day 10 | Pi Deployment Instructions

---

## Files to Transfer

### Core Emotion Files (Required)

```bash
# Primary emotions and state machine
firmware/src/animation/emotions.py
firmware/src/animation/emotion_axes.py

# Social emotion patterns (Agent 2)
firmware/src/led/patterns/social_emotions.py

# Compound emotion patterns (Agent 3)
firmware/src/animation/emotion_patterns/__init__.py
firmware/src/animation/emotion_patterns/compound_emotions.py

# Micro-expression system (Agent 4)
firmware/src/animation/micro_expressions_enhanced.py
```

### Demo Scripts

```bash
# Full 17-emotion demo
firmware/scripts/emotion_demo_full.py

# Original 8-emotion demo (legacy)
firmware/scripts/emotion_demo.py
```

### Base Pattern Classes (Dependencies)

```bash
firmware/src/led/patterns/__init__.py
firmware/src/led/patterns/base.py
```

### Test Files (Optional - for validation)

```bash
firmware/tests/test_led/test_social_emotions.py
firmware/tests/test_animation/test_compound_emotions.py
firmware/tests/test_micro_expressions_enhanced.py
firmware/tests/test_integration/test_all_emotions_integration.py
```

---

## SCP Transfer Commands

### From Windows to Pi

Replace `PI_IP` with your Raspberry Pi IP address (e.g., 192.168.1.100):

```bash
# Set variables
PI_IP=YOUR_PI_IP
PI_USER=pi
FIRMWARE_PATH="C:\Users\matte\Desktop\Desktop OLD\AI\Università AI\courses\personal_project\robot_jarvis\firmware"

# Create directory structure on Pi
ssh ${PI_USER}@${PI_IP} "mkdir -p ~/openduck/src/animation/emotion_patterns ~/openduck/src/led/patterns ~/openduck/scripts ~/openduck/tests"

# Transfer core files
scp "${FIRMWARE_PATH}\src\animation\emotions.py" ${PI_USER}@${PI_IP}:~/openduck/src/animation/
scp "${FIRMWARE_PATH}\src\animation\emotion_axes.py" ${PI_USER}@${PI_IP}:~/openduck/src/animation/
scp "${FIRMWARE_PATH}\src\animation\micro_expressions_enhanced.py" ${PI_USER}@${PI_IP}:~/openduck/src/animation/
scp "${FIRMWARE_PATH}\src\animation\emotion_patterns\*.py" ${PI_USER}@${PI_IP}:~/openduck/src/animation/emotion_patterns/

# Transfer LED patterns
scp "${FIRMWARE_PATH}\src\led\patterns\*.py" ${PI_USER}@${PI_IP}:~/openduck/src/led/patterns/

# Transfer scripts
scp "${FIRMWARE_PATH}\scripts\emotion_demo_full.py" ${PI_USER}@${PI_IP}:~/openduck/scripts/
scp "${FIRMWARE_PATH}\scripts\emotion_demo.py" ${PI_USER}@${PI_IP}:~/openduck/scripts/
```

### Alternative: rsync (if available)

```bash
rsync -avz --progress \
    "${FIRMWARE_PATH}/src/" \
    ${PI_USER}@${PI_IP}:~/openduck/src/

rsync -avz --progress \
    "${FIRMWARE_PATH}/scripts/" \
    ${PI_USER}@${PI_IP}:~/openduck/scripts/
```

---

## Pi Setup Commands

### Prerequisites

```bash
# SSH into Pi
ssh pi@${PI_IP}

# Update system
sudo apt update && sudo apt upgrade -y

# Install Python requirements
pip3 install rpi_ws281x adafruit-blinka

# Enable hardware PWM
# Add to /boot/config.txt:
echo "dtparam=audio=off" | sudo tee -a /boot/config.txt
sudo reboot
```

### Directory Setup

```bash
# Create Python path configuration
cd ~/openduck
echo "export PYTHONPATH=\$PYTHONPATH:~/openduck/src" >> ~/.bashrc
source ~/.bashrc
```

---

## Test Commands on Pi

### Syntax Validation

```bash
cd ~/openduck
python3 -m py_compile src/animation/emotions.py
python3 -m py_compile src/animation/emotion_axes.py
python3 -m py_compile src/led/patterns/social_emotions.py
python3 -m py_compile src/animation/emotion_patterns/compound_emotions.py
python3 -m py_compile src/animation/micro_expressions_enhanced.py
echo "All syntax checks passed!"
```

### List Emotions

```bash
sudo python3 scripts/emotion_demo_full.py --list
```

Expected output:
```
PRIMARY EMOTIONS:
  idle, happy, curious, alert, sad, sleepy, excited, thinking

SOCIAL EMOTIONS:
  playful, affectionate, empathetic, grateful

COMPOUND EMOTIONS:
  confused, surprised, anxious, frustrated, proud
```

### Run Benchmark

```bash
sudo python3 scripts/emotion_demo_full.py --benchmark
```

Expected: All 17 emotions PASS with avg < 2.5ms

### Run Full Demo

```bash
# Full 17-emotion showcase (approximately 72 seconds)
sudo python3 scripts/emotion_demo_full.py

# Primary emotions only
sudo python3 scripts/emotion_demo_full.py --primary

# Social emotions only
sudo python3 scripts/emotion_demo_full.py --social

# Compound emotions only
sudo python3 scripts/emotion_demo_full.py --compound
```

### Run Tests (if pytest installed)

```bash
pip3 install pytest
cd ~/openduck
python3 -m pytest tests/test_integration/test_all_emotions_integration.py -v
```

---

## Hardware Verification

### GPIO Pin Check

```bash
# Verify PWM channels are available
sudo gpio readall | grep -E "18|13"
```

Expected: GPIO 18 and GPIO 13 available

### LED Test

```bash
# Quick LED test (should show breathing pattern)
sudo python3 -c "
import sys
sys.path.insert(0, 'src')
from scripts.emotion_demo_full import FullEmotionDemo
demo = FullEmotionDemo()
demo.initialize()
demo.display_emotion('idle', 3.0)
demo.cleanup()
"
```

---

## Troubleshooting

### Common Issues

1. **"ModuleNotFoundError: No module named 'animation'"**
   - Fix: Set PYTHONPATH correctly
   ```bash
   export PYTHONPATH=$PYTHONPATH:~/openduck/src
   ```

2. **"RuntimeError: ws2811_init failed"**
   - Fix: Disable audio (conflicts with PWM)
   ```bash
   echo "dtparam=audio=off" | sudo tee -a /boot/config.txt
   sudo reboot
   ```

3. **"Permission denied on GPIO"**
   - Fix: Run with sudo
   ```bash
   sudo python3 scripts/emotion_demo_full.py
   ```

4. **LEDs not lighting up**
   - Check wire connections (RED=5V, BROWN=Data, ORANGE=GND)
   - Verify GPIO pins (Left=18, Right=13)
   - Check brightness setting (MAX_BRIGHTNESS=60)

---

## Success Criteria

The deployment is successful when:

1. `--list` shows all 17 emotions
2. `--benchmark` shows all PASS
3. `--primary` cycles through 8 emotions with visible LED patterns
4. `--social` shows 4 distinct patterns
5. `--compound` shows 5 distinct patterns
6. No errors or warnings during full demo

---

*Package prepared by: Integration Engineer (Agent 5)*
*Date: 18 January 2026*
