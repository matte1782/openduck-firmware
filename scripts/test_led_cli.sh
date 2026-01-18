#!/bin/bash
# Test script for LED CLI tool
# Tests all commands in mock mode (no hardware required)

echo "======================================================================"
echo "  OpenDuck V3 - LED CLI Test Suite"
echo "======================================================================"
echo ""

# Change to script directory
cd "$(dirname "$0")"

# Test 1: Help
echo "[TEST 1] Help command"
python3 led_cli.py --help
echo ""

# Test 2: Preview breathing pattern
echo "[TEST 2] Preview breathing pattern (mock mode)"
python3 led_cli.py preview breathing --emotion happy --duration 2 --no-hardware
echo ""

# Test 3: Preview rainbow pattern
echo "[TEST 3] Preview rainbow pattern (mock mode)"
python3 led_cli.py preview rainbow --duration 2 --no-hardware
echo ""

# Test 4: Profile breathing
echo "[TEST 4] Profile breathing pattern (50 frames)"
python3 led_cli.py profile breathing --emotion idle --frames 50 --no-hardware
echo ""

# Test 5: Profile rainbow
echo "[TEST 5] Profile rainbow pattern (50 frames)"
python3 led_cli.py profile rainbow --frames 50 --no-hardware
echo ""

# Test 6: Validate config (if exists)
echo "[TEST 6] Validate configuration"
if [ -f "../config/hardware_config.yaml" ]; then
    python3 led_cli.py validate ../config/hardware_config.yaml
else
    echo "SKIPPED: Config file not found"
fi
echo ""

# Test 7: Emotions diagram
echo "[TEST 7] Emotion state machine"
python3 led_cli.py emotions --graph
echo ""

# Test 8: Record pattern
echo "[TEST 8] Record breathing pattern to JSON"
mkdir -p /tmp/led_cli_test
python3 led_cli.py record breathing --emotion curious --duration 2 --output /tmp/led_cli_test/test_profile.json --no-hardware

if [ -f "/tmp/led_cli_test/test_profile.json" ]; then
    echo "SUCCESS: Profile JSON created"
    echo "Preview:"
    head -n 20 /tmp/led_cli_test/test_profile.json
else
    echo "FAILED: Profile JSON not created"
fi
echo ""

# Test 9: Export profiling data
echo "[TEST 9] Profile with JSON export"
python3 led_cli.py profile rainbow --frames 50 --output /tmp/led_cli_test/rainbow_profile.json --no-hardware

if [ -f "/tmp/led_cli_test/rainbow_profile.json" ]; then
    echo "SUCCESS: Profiling export created"
else
    echo "FAILED: Profiling export not created"
fi
echo ""

echo "======================================================================"
echo "  Test suite complete!"
echo "======================================================================"
echo ""
echo "Files created:"
ls -lh /tmp/led_cli_test/ 2>/dev/null || echo "  None"
echo ""
