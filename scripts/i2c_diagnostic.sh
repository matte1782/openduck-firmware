#!/bin/bash
# I2C Diagnostic Script for PCA9685 Troubleshooting
# Date: 16 January 2026

echo "=========================================="
echo "I2C Diagnostic Test - PCA9685"
echo "=========================================="
echo ""

# Test 1: Check if I2C is enabled
echo "Test 1: I2C Configuration"
echo "--------------------------"
if grep -q "^dtparam=i2c_arm=on" /boot/firmware/config.txt; then
    echo "✓ I2C enabled in config.txt"
else
    echo "✗ I2C NOT enabled in config.txt"
fi

if lsmod | grep -q i2c_dev; then
    echo "✓ i2c_dev module loaded"
else
    echo "✗ i2c_dev module NOT loaded"
fi

if [ -e /dev/i2c-1 ]; then
    echo "✓ /dev/i2c-1 device exists"
else
    echo "✗ /dev/i2c-1 device NOT found"
fi
echo ""

# Test 2: Check GPIO pin configuration
echo "Test 2: GPIO Pin Configuration"
echo "-------------------------------"
if command -v gpio &> /dev/null; then
    echo "GPIO 2 (SDA1) and GPIO 3 (SCL1) status:"
    gpio -g mode 2
    gpio -g mode 3
else
    echo "gpio command not available (installing wiringpi...)"
    sudo apt-get install -y wiringpi > /dev/null 2>&1
    if command -v gpio &> /dev/null; then
        gpio -g mode 2
        gpio -g mode 3
    else
        echo "Could not install gpio utility"
    fi
fi
echo ""

# Test 3: Standard I2C detection
echo "Test 3: Standard I2C Device Scan"
echo "---------------------------------"
sudo i2cdetect -y 1
echo ""

# Test 4: SMBus Quick Write detection
echo "Test 4: SMBus Quick Write Scan"
echo "-------------------------------"
echo "Trying with SMBus protocol (-r flag):"
sudo i2cdetect -y -r 1
echo ""

# Test 5: Check I2C bus speed
echo "Test 5: I2C Bus Speed"
echo "---------------------"
if grep -q "dtparam=i2c_baudrate" /boot/firmware/config.txt; then
    speed=$(grep "dtparam=i2c_baudrate" /boot/firmware/config.txt | cut -d= -f2)
    echo "I2C baudrate configured: $speed Hz"
else
    echo "I2C baudrate: default (100000 Hz)"
fi
echo ""

# Test 6: Try to read from address 0x40
echo "Test 6: Direct Read from 0x40"
echo "------------------------------"
if sudo i2cget -y 1 0x40 0x00 2>&1 | grep -q "Error"; then
    echo "✗ Cannot read from address 0x40"
    echo "   Device not responding"
else
    value=$(sudo i2cget -y 1 0x40 0x00 2>&1)
    echo "✓ Successfully read from 0x40: $value"
fi
echo ""

# Test 7: Check for I2C errors in kernel log
echo "Test 7: Recent I2C Errors in Kernel Log"
echo "----------------------------------------"
if sudo dmesg | grep -i "i2c" | tail -5 | grep -q "error\|fail"; then
    echo "Recent I2C errors found:"
    sudo dmesg | grep -i "i2c" | grep -i "error\|fail" | tail -5
else
    echo "No recent I2C errors in kernel log"
fi
echo ""

# Test 8: Check for Most Common Issue - SDA/SCL Swap
echo "Test 8: Cable Swap Detection (Most Common Issue!)"
echo "--------------------------------------------------"
echo "⚠️  SDA/SCL swap is the #1 cause of 'no devices detected'"
echo ""
echo "Verification checklist:"
echo "  [ ] Pi Pin 3 (GPIO2/SDA) connects to PCA9685 pin labeled 'SDA' or 'D'"
echo "  [ ] Pi Pin 5 (GPIO3/SCL) connects to PCA9685 pin labeled 'SCL' or 'C'"
echo "  [ ] NOT just 'Pin 3 to Pin 3' - SIGNAL NAMES must match!"
echo ""
echo "Quick visual check:"
echo "  1. Look at Raspberry Pi Pin 3 - follow the cable"
echo "  2. Where does it connect on PCA9685?"
echo "  3. Does that pin's label say 'SDA' or 'SCL'?"
echo "  4. It MUST say 'SDA' (not 'SCL')!"
echo ""
echo "If labels don't match:"
echo "  → Power OFF: sudo poweroff"
echo "  → Swap the two middle cables (GREEN ↔ YELLOW/ORANGE)"
echo "  → Can swap on either Pi side or PCA9685 side"
echo "  → Power ON and re-run: sudo i2cdetect -y 1"
echo ""

# Summary
echo "=========================================="
echo "DIAGNOSTIC SUMMARY"
echo "=========================================="
echo ""
echo "If NO devices were detected in Test 3 & 4:"
echo ""
echo "  MOST LIKELY CAUSE (90% of cases):"
echo "  ⚠️  SDA and SCL cables are SWAPPED!"
echo "     → Try swapping GREEN and YELLOW cables"
echo "     → Verify: GREEN goes to 'SDA' label, YELLOW to 'SCL' label"
echo ""
echo "  Other possible causes:"
echo "  → Check physical connections (VCC, GND firmly inserted)"
echo "  → Verify cables are not damaged"
echo "  → Try swapping to the second PCA9685 board"
echo "  → Check if PCA9685 LED is lit (power indicator)"
echo "  → Use multimeter for continuity test"
echo ""
echo "If address 0x40 shows UU instead of 40:"
echo "  → Device is detected but in use by kernel driver"
echo "  → This is actually GOOD - means it's detected"
echo ""
echo "Advanced troubleshooting (if swap doesn't fix):"
echo "  1. Slow down I2C bus:"
echo "     sudo nano /boot/firmware/config.txt"
echo "     Add: dtparam=i2c_baudrate=10000"
echo "     sudo reboot"
echo ""
echo "  2. Try the second PCA9685 board"
echo ""
echo "  3. Take photos and compare to reference:"
echo "     hardware_photos/raspberry_pi_gpio.jpeg"
echo "     hardware_photos/pca9685_connections.jpeg"
echo "=========================================="
