# Test-Driven Development Strategy - Week 02
## OpenDuck Mini V3 - Hardware Integration Phase

**Version:** 1.0
**Created:** 21 January 2026
**Status:** APPROVED - Ready for Execution

---

## TDD Philosophy for Hardware Integration

> "The best time to write a test is before the code exists.
> The second best time is now."

Week 02 introduces hardware integration (batteries, servos, IMU). TDD becomes MORE critical because:
1. **Hardware bugs are expensive** (damaged servos, burned components)
2. **Debugging hardware is slow** (physical inspection, multimeter)
3. **Mock tests catch 80% of issues** before hardware is involved

---

## Three-Stage Testing Model

### Stage 1: Mock Tests (Dev Machine)
Run WITHOUT hardware. Use mock objects for all I/O.

```python
@pytest.fixture
def mock_servo_driver():
    """Mock PCA9685 for dev machine testing"""
    driver = MagicMock(spec=PCA9685Driver)
    driver.set_angle.return_value = True
    driver.get_angle.return_value = 90
    return driver

def test_servo_calibration_updates_limits(mock_servo_driver):
    calibrator = ServoCalibrator(mock_servo_driver)
    calibrator.set_min_angle(30)
    calibrator.set_max_angle(150)

    assert calibrator.min_angle == 30
    assert calibrator.max_angle == 150
    mock_servo_driver.set_angle.assert_not_called()  # No HW call yet
```

**Run Frequency:** Every commit (CI/CD), every save (IDE)
**Target:** 95%+ pass rate, <30 seconds execution

### Stage 2: Integration Tests (Pi, No Power)
Run ON Raspberry Pi with I2C connected but servo V+ unpowered.

```python
@pytest.mark.integration
@pytest.mark.requires_hardware
def test_pca9685_i2c_detection():
    """Verify PCA9685 responds on I2C bus"""
    driver = PCA9685Driver()
    assert driver.is_connected()
    assert driver.read_register(0x00) is not None

@pytest.mark.integration
@pytest.mark.requires_hardware
def test_bno085_i2c_detection():
    """Verify BNO085 responds on I2C bus"""
    imu = BNO085Driver()
    assert imu.is_connected()
```

**Run Frequency:** Once per hardware change, end of day
**Target:** 90%+ pass rate (some HW-specific failures acceptable)

### Stage 3: Hardware Tests (Full Power)
Run with batteries connected and servos powered.

```python
@pytest.mark.hardware
@pytest.mark.dangerous  # Servo movement
def test_servo_moves_to_center():
    """Verify servo physically moves"""
    driver = PCA9685Driver()
    driver.set_angle(0, 90)
    time.sleep(0.5)

    # Human verification required
    print("VERIFY: Servo at channel 0 should be at center (90°)")
    result = input("Pass? (y/n): ")
    assert result.lower() == 'y'
```

**Run Frequency:** Manual, once per feature completion
**Target:** 100% pass (all hardware must work)

---

## TDD Workflow for Each Feature

### Step-by-Step Process

```
┌─────────────────────────────────────────────────────────────────┐
│                    TDD Feature Workflow                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. WRITE TEST (RED)                                            │
│     └── Test describes expected behavior                        │
│     └── Test FAILS (code doesn't exist yet)                     │
│                                                                 │
│  2. WRITE MINIMUM CODE (GREEN)                                  │
│     └── Just enough to pass the test                            │
│     └── No optimizations, no extras                             │
│                                                                 │
│  3. REFACTOR (STILL GREEN)                                      │
│     └── Clean up code                                           │
│     └── All tests still pass                                    │
│                                                                 │
│  4. HOSTILE REVIEW                                              │
│     └── Agent reviews for security, edge cases                  │
│     └── Add more tests if issues found                          │
│                                                                 │
│  5. INTEGRATION TEST (Pi)                                       │
│     └── Run on hardware                                         │
│     └── Verify real-world behavior                              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Example: BNO085 IMU Driver

**Step 1: Write Test (RED)**
```python
# tests/test_drivers/test_bno085.py

class TestBNO085Driver:
    def test_initialization(self, mock_i2c):
        """Driver should initialize with I2C address 0x4A"""
        driver = BNO085Driver(mock_i2c)
        mock_i2c.scan.assert_called()
        assert driver.address == 0x4A

    def test_read_orientation_returns_euler(self, mock_i2c):
        """read_orientation should return heading, pitch, roll"""
        driver = BNO085Driver(mock_i2c)
        mock_i2c.read.return_value = b'\x00\x00\x00\x00...'  # Mock quaternion

        orientation = driver.read_orientation()

        assert hasattr(orientation, 'heading')
        assert hasattr(orientation, 'pitch')
        assert hasattr(orientation, 'roll')
        assert -180 <= orientation.heading <= 180
        assert -90 <= orientation.pitch <= 90
        assert -180 <= orientation.roll <= 180
```

**Step 2: Run Test (FAILS - No code yet)**
```bash
$ pytest tests/test_drivers/test_bno085.py -v
FAILED test_initialization - ModuleNotFoundError: No module named 'bno085'
```

**Step 3: Write Minimum Code (GREEN)**
```python
# src/drivers/sensor/imu/bno085.py

@dataclass
class OrientationData:
    heading: float
    pitch: float
    roll: float

class BNO085Driver:
    def __init__(self, i2c=None):
        self.address = 0x4A
        self.i2c = i2c or self._default_i2c()

    def read_orientation(self) -> OrientationData:
        raw = self.i2c.read(self.address, 16)
        quat = self._parse_quaternion(raw)
        return self._quaternion_to_euler(quat)
```

**Step 4: Run Test (PASSES)**
```bash
$ pytest tests/test_drivers/test_bno085.py -v
PASSED test_initialization
PASSED test_read_orientation_returns_euler
```

**Step 5: Refactor, then Hostile Review**

---

## Test Categories for Week 02

### Category A: Unit Tests (Mock-based)

| Component | Test Count | Coverage |
|-----------|------------|----------|
| BNO085 Driver | 25 | 90% |
| Servo Calibration | 30 | 85% |
| Animation Timing | 40 | 95% |
| Easing Functions | 15 | 100% |
| LED Patterns | 30 | 85% |
| Emotion State Machine | 35 | 90% |
| Head Controller | 25 | 85% |
| **Total** | **200** | **90%** |

### Category B: Integration Tests (Pi, No Power)

| Component | Test Count | Purpose |
|-----------|------------|---------|
| I2C Bus Scan | 5 | Verify devices detected |
| PCA9685 Registers | 10 | Verify read/write |
| BNO085 Registers | 10 | Verify IMU comms |
| GPIO States | 5 | Verify pin configuration |
| LED Strip Init | 5 | Verify WS2812B responds |
| **Total** | **35** | |

### Category C: Hardware Tests (Full Power)

| Component | Test Count | Purpose |
|-----------|------------|---------|
| Servo Movement | 10 | Verify all channels |
| Servo Calibration | 5 | Verify limits |
| IMU Orientation | 5 | Verify readings |
| LED Colors | 5 | Verify RGB accuracy |
| Full Animation | 5 | Verify end-to-end |
| **Total** | **30** | |

---

## Test Infrastructure

### pytest Configuration

```ini
# pytest.ini

[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*

markers =
    unit: Unit tests (mock-based, fast)
    integration: Integration tests (requires Pi)
    hardware: Hardware tests (requires power)
    slow: Slow tests (>1 second)
    dangerous: Tests that move servos

filterwarnings =
    ignore::DeprecationWarning

addopts =
    --strict-markers
    -v
    --tb=short
```

### Test Fixtures

```python
# tests/conftest.py

import pytest
from unittest.mock import MagicMock

@pytest.fixture
def mock_i2c():
    """Mock I2C bus for unit tests"""
    i2c = MagicMock()
    i2c.scan.return_value = [0x40, 0x4A]  # PCA9685 + BNO085
    i2c.read.return_value = bytes(16)
    i2c.write.return_value = None
    return i2c

@pytest.fixture
def mock_gpio():
    """Mock GPIO for unit tests"""
    gpio = MagicMock()
    gpio.input.return_value = 1  # Default HIGH
    return gpio

@pytest.fixture
def mock_robot(mock_i2c, mock_gpio):
    """Full mock robot for orchestration tests"""
    robot = Robot(i2c=mock_i2c, gpio=mock_gpio)
    robot.start()
    yield robot
    robot.stop()
```

### Running Tests

```bash
# Run all unit tests (fast, no hardware)
pytest -m unit

# Run integration tests (on Pi)
pytest -m integration

# Run all tests with coverage
pytest --cov=src --cov-report=html

# Run specific module
pytest tests/test_animation/test_timing.py -v

# Run with failure stop (stop on first failure)
pytest -x

# Run parallel (faster)
pytest -n auto
```

---

## Continuous Integration

### Pre-Commit Hook

```bash
#!/bin/bash
# .git/hooks/pre-commit

echo "Running unit tests..."
pytest -m unit --tb=short -q

if [ $? -ne 0 ]; then
    echo "Unit tests failed. Commit blocked."
    exit 1
fi

echo "Unit tests passed. Proceeding with commit."
```

### Daily Test Run

```bash
#!/bin/bash
# scripts/daily_test.sh

echo "=== Daily Test Report ==="
date

echo ""
echo "=== Unit Tests ==="
pytest -m unit --tb=short

echo ""
echo "=== Integration Tests ==="
pytest -m integration --tb=short

echo ""
echo "=== Coverage Report ==="
pytest --cov=src --cov-report=term-missing

echo ""
echo "=== Test Complete ==="
```

---

## Test Naming Conventions

### Pattern: test_[unit]_[action]_[expected]

```python
# Good names
def test_servo_set_angle_clamps_to_limits():
def test_imu_read_orientation_returns_valid_euler():
def test_animation_play_starts_from_frame_zero():
def test_emotion_transition_respects_timing():

# Bad names (unclear)
def test_servo():
def test_1():
def test_it_works():
```

### Test Class Organization

```python
class TestServoCalibration:
    """Tests for ServoCalibrator class"""

    class TestInitialization:
        def test_default_limits(self): ...
        def test_custom_limits(self): ...

    class TestAngleClamping:
        def test_below_minimum(self): ...
        def test_above_maximum(self): ...
        def test_within_range(self): ...

    class TestPersistence:
        def test_save_to_yaml(self): ...
        def test_load_from_yaml(self): ...
```

---

## Test Documentation

### Docstrings for Complex Tests

```python
def test_animation_timing_accuracy():
    """
    Verify animation frame timing is accurate within 10ms.

    Setup:
        1. Create 1-second animation with 50 keyframes
        2. Mock time.monotonic() to control timing

    Test:
        1. Start animation
        2. Advance time by 500ms
        3. Verify we're at keyframe 25 (±1)

    Expected:
        - Frame position should be 25 (±1 for timing jitter)
        - No skipped frames
        - No duplicate frames

    Related:
        - Issue #42: Animation jitter on Pi 4
        - PR #56: Timing fix with monotonic clock
    """
    ...
```

---

## Week 02 Test Milestones

| Day | Milestone | Tests Added | Cumulative |
|-----|-----------|-------------|------------|
| Day 8 | BNO085 Driver | +50 | 502 |
| Day 9 | Easing + LED Patterns | +48 | 550 |
| Day 10 | Emotion System | +40 | 590 |
| Day 11 | Head Controller + Color | +35 | 625 |
| Day 12 | Integration Tests | +35 | 660 |
| Day 13 | Polish + Edge Cases | +15 | 675 |
| Day 14 | Final Validation | +5 | 680 |
| [BATTERY] | Hardware Tests | +20 | 700 |

**Week 02 Target:** 700 tests, 95%+ pass rate (standardized across all planning documents)

---

## Hostile Review Integration

After each TDD cycle, run hostile review:

```bash
# Run hostile review on new code
claude review src/drivers/sensor/imu/bno085.py \
    --focus "thread safety, error handling, edge cases"
```

### Hostile Review Test Generation

When hostile review finds issues, add tests BEFORE fixing:

```python
# Hostile review found: "No handling for I2C NAK"
# ADD TEST FIRST:

def test_imu_handles_i2c_nak(mock_i2c):
    """Hostile review: Handle I2C NAK gracefully"""
    mock_i2c.read.side_effect = IOError("I2C NAK")

    driver = BNO085Driver(mock_i2c)
    orientation = driver.read_orientation()

    assert orientation is None  # Graceful failure
    # OR
    with pytest.raises(IMUCommunicationError):
        driver.read_orientation()
```

---

## Summary

### TDD Rules for Week 02

1. **No code without a test** - Every function gets tested
2. **Tests first, code second** - RED → GREEN → REFACTOR
3. **Mock everything in unit tests** - Fast feedback loop
4. **Integration tests on Pi** - Verify real hardware
5. **Hostile review after green** - Catch edge cases
6. **Commit only when green** - Never break main branch

### Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Test Count | 700 | `pytest --collect-only | grep test` |
| Pass Rate | 95%+ | `pytest --tb=no` |
| Coverage | 90%+ | `pytest --cov=src` |
| Execution Time | <60s unit | `time pytest -m unit` |

---

**Document Version:** 1.0
**Last Updated:** 21 January 2026
**Approved By:** Boston Dynamics Standards
