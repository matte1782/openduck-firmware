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

# Summary
echo "=========================================="
echo "DIAGNOSTIC SUMMARY"
echo "=========================================="
echo ""
echo "If NO devices were detected in Test 3 & 4:"
echo "  → Check physical connections (SDA, SCL, VCC, GND)"
echo "  → Verify cables are firmly inserted"
echo "  → Try swapping to the second PCA9685 board"
echo "  → Check if PCA9685 LED is lit (power indicator)"
echo ""
echo "If address 0x40 shows UU instead of 40:"
echo "  → Device is detected but in use by kernel driver"
echo "  → This is actually GOOD - means it's detected"
echo ""
echo "Next steps:"
echo "  1. If still not detected, slow down I2C bus:"
echo "     sudo nano /boot/firmware/config.txt"
echo "     Add: dtparam=i2c_baudrate=10000"
echo "     sudo reboot"
echo ""
echo "  2. Try the second PCA9685 board"
echo ""
echo "  3. Check cable integrity with multimeter"
echo "=========================================="
