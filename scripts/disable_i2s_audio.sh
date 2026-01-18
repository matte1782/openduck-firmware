#!/bin/bash
# OpenDuck Mini V3 - I2S Audio Disable Script
# Purpose: Resolve GPIO 18 conflict between LED Ring 1 and I2S Audio
# Author: Hardware Integration Team
# Date: 18 January 2026
# Status: Weekend Workaround (Option A)

set -e  # Exit on any error

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script metadata
SCRIPT_NAME="I2S Audio Disable"
VERSION="1.0.0"
CONFIG_FILE="/boot/firmware/config.txt"
BACKUP_FILE="/boot/firmware/config.txt.backup.$(date +%Y%m%d_%H%M%S)"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}OpenDuck Mini V3 - ${SCRIPT_NAME}${NC}"
echo -e "${BLUE}Version: ${VERSION}${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}ERROR: This script must be run as root${NC}"
    echo "Usage: sudo bash $0"
    exit 1
fi

# Check if config file exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo -e "${YELLOW}WARNING: Config file not found at $CONFIG_FILE${NC}"
    echo -e "${YELLOW}Trying alternative location: /boot/config.txt${NC}"
    CONFIG_FILE="/boot/config.txt"
    BACKUP_FILE="/boot/config.txt.backup.$(date +%Y%m%d_%H%M%S)"

    if [ ! -f "$CONFIG_FILE" ]; then
        echo -e "${RED}ERROR: Cannot find /boot/config.txt or /boot/firmware/config.txt${NC}"
        exit 1
    fi
fi

echo -e "${GREEN}Found config file: $CONFIG_FILE${NC}"
echo ""

# Display current audio status
echo -e "${BLUE}Current Audio Configuration:${NC}"
if aplay -l &>/dev/null; then
    echo -e "${YELLOW}I2S audio devices detected:${NC}"
    aplay -l | grep -i "card" || echo "  None"
else
    echo -e "${GREEN}No audio devices found (I2S may already be disabled)${NC}"
fi
echo ""

# Display GPIO 18 conflict explanation
echo -e "${YELLOW}=== GPIO 18 CONFLICT EXPLANATION ===${NC}"
echo "GPIO 18 is currently assigned to TWO functions:"
echo "  1. LED Ring 1 (Left Eye) - PWM Channel 0 for WS2812B"
echo "  2. I2S Audio BCLK - Hardware I2S peripheral"
echo ""
echo "When I2S is enabled, GPIO 18 switches to I2S mode,"
echo "causing LED Ring 1 to flicker or fail completely."
echo ""
echo -e "${BLUE}This script will DISABLE I2S audio to allow LED Ring 1 to work.${NC}"
echo ""

# Ask for confirmation
read -p "Do you want to proceed? (y/n): " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Operation cancelled by user${NC}"
    exit 0
fi

echo ""
echo -e "${BLUE}Step 1: Creating backup of config.txt${NC}"
cp "$CONFIG_FILE" "$BACKUP_FILE"
echo -e "${GREEN}Backup created: $BACKUP_FILE${NC}"
echo ""

# Check if audio is already disabled
if grep -q "^dtparam=audio=off" "$CONFIG_FILE"; then
    echo -e "${GREEN}I2S audio is already disabled in config.txt${NC}"
    echo "No changes needed."
    echo ""
    exit 0
fi

echo -e "${BLUE}Step 2: Modifying $CONFIG_FILE${NC}"

# Comment out any existing audio=on lines
if grep -q "^dtparam=audio=on" "$CONFIG_FILE"; then
    echo "  - Commenting out existing 'dtparam=audio=on'"
    sed -i 's/^dtparam=audio=on/# dtparam=audio=on  # Disabled for GPIO 18 LED conflict/' "$CONFIG_FILE"
fi

# Add audio=off if not already present
if ! grep -q "dtparam=audio=off" "$CONFIG_FILE"; then
    echo "  - Adding 'dtparam=audio=off'"
    echo "" >> "$CONFIG_FILE"
    echo "# GPIO 18 Conflict Resolution - Disable I2S Audio (Option A)" >> "$CONFIG_FILE"
    echo "# This allows LED Ring 1 to use GPIO 18 without interference" >> "$CONFIG_FILE"
    echo "# Added: $(date '+%Y-%m-%d %H:%M:%S')" >> "$CONFIG_FILE"
    echo "dtparam=audio=off" >> "$CONFIG_FILE"
fi

echo -e "${GREEN}Configuration updated successfully${NC}"
echo ""

# Display what changed
echo -e "${BLUE}Step 3: Verification${NC}"
echo "Current audio parameter in config.txt:"
grep "dtparam=audio" "$CONFIG_FILE" | sed 's/^/  /'
echo ""

# Instructions for next steps
echo -e "${YELLOW}=== NEXT STEPS ===${NC}"
echo "1. Reboot the Raspberry Pi for changes to take effect:"
echo "   ${BLUE}sudo reboot${NC}"
echo ""
echo "2. After reboot, verify I2S is disabled:"
echo "   ${BLUE}aplay -l${NC}"
echo "   Expected: 'No soundcards found' or only HDMI audio"
echo ""
echo "3. Test LED Ring 1 on GPIO 18:"
echo "   ${BLUE}sudo python3 firmware/scripts/test_dual_leds.py${NC}"
echo "   Expected: Both LED rings work without flickering"
echo ""
echo "4. Run full validation:"
echo "   ${BLUE}sudo python3 firmware/scripts/validate_gpio_config.py${NC}"
echo ""
echo -e "${YELLOW}=== ROLLBACK INSTRUCTIONS ===${NC}"
echo "If you need to re-enable I2S audio later:"
echo "  1. Edit $CONFIG_FILE"
echo "  2. Change 'dtparam=audio=off' to 'dtparam=audio=on'"
echo "  3. Reboot"
echo ""
echo "Or restore from backup:"
echo "  ${BLUE}sudo cp $BACKUP_FILE $CONFIG_FILE${NC}"
echo "  ${BLUE}sudo reboot${NC}"
echo ""
echo -e "${GREEN}=== MIGRATION TO GPIO 10 (Week 02) ===${NC}"
echo "This is a temporary solution for weekend LED work."
echo "In Week 02, LED Ring 1 will be moved to GPIO 10,"
echo "allowing both LED and audio to coexist."
echo ""
echo "See: firmware/docs/GPIO_10_MIGRATION_GUIDE.md"
echo ""
echo -e "${GREEN}Script completed successfully!${NC}"
echo -e "${BLUE}========================================${NC}"
