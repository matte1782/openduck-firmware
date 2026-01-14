# OpenDuck Mini V3 Firmware
**Version:** 0.1.0-dev
**Status:** Week 01 Development - Foundation Phase
**Target:** Raspberry Pi 4 Model B (4GB RAM)
**Date:** 15 January 2026

## Architecture

### Hardware Abstraction Layer (HAL)
`src/drivers/` - Low-level hardware interfaces
- **`servo/`** - PCA9685 PWM driver, servo control and coordination
- **`led/`** - WS2812B NeoPixel rings (16 LEDs × 2)
- **`audio/`** - MAX98357A I2S amplifier, INMP441 microphone
- **`sensor/`** - HC-SR04 ultrasonic distance, BNO085 9-DOF IMU

### Control Layer
`src/control/` - Kinematics and motion planning
- Inverse kinematics (2-DOF arm, 3-DOF leg)
- Multi-servo coordination and sequencing
- Trajectory generation and interpolation
- Gait patterns (trot, crawl, walk)

### Application Layer
`src/core/` - Robot state machine and safety systems
- Main robot class with state management
- Power management with current limiting (3A UBEC)
- Emergency stop system (<100ms latency)
- Fault detection and recovery

### Utilities
`src/utils/` - Cross-cutting concerns
- Logging and diagnostics
- Configuration management (YAML)
- Mathematical utilities

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run main robot
python src/core/robot.py

# Run tests
pytest tests/ -v --cov=src

# Run tests with coverage report
pytest tests/ --cov=src --cov-report=html
```

## Development Workflow

```bash
# Format code
black src/ tests/

# Lint code
pylint src/

# Type checking
mypy src/
```

## Week 01 Goals (15-21 Jan 2026)

**Day 1 (15 Jan):**
- [x] Repository structure initialized
- [x] Documentation foundation

**Day 2 (16 Jan):**
- [ ] Raspberry Pi setup and configuration
- [ ] PCA9685 driver implementation
- [ ] First servo control test

**Day 3 (17 Jan):**
- [ ] LED ring driver (WS2812B)
- [ ] Multi-servo coordination
- [ ] Power consumption measurements

**Days 4-5 (18-19 Jan):**
- [ ] 2-DOF arm inverse kinematics
- [ ] Power manager with current limiting
- [ ] Emergency stop GPIO implementation

**Days 6-7 (20-21 Jan):**
- [ ] Test suite >40% coverage
- [ ] Integration testing
- [ ] Week 01 completion review

## Hardware Platform

**Compute:**
- Raspberry Pi 4 Model B (4GB RAM)
- Raspbian OS Lite (64-bit)

**Servos:**
- 5× MG90S servos (testing, low torque)
- 16× Feetech STS3215 servos (main, 20kg·cm @ 7.4V) - *arriving later*

**Sensors:**
- 3× HC-SR04 ultrasonic (distance sensing)
- 1× BNO085 9-DOF IMU (orientation, balance) - *arriving next week*

**Actuators:**
- 2× WS2812B LED rings (16 LEDs each, 5V)
- 1× MAX98357A I2S audio amplifier

**Power System:**
- 2S Li-ion battery pack (7.4V nominal, 6000mAh in 2S2P config)
- BMS 2S 20A (charge protection, balancing)
- Dual UBEC: 5V 3A (logic) + 6V 3A (servos)
- XT30 connectors for battery interface

## Configuration

Configuration files in `config/`:
- `hardware_config.yaml` - GPIO pins, I2C addresses, PWM frequencies
- `robot_config.yaml` - Servo limits, kinematics parameters, safety thresholds
- `safety_config.yaml` - Current limits, emergency stop settings

## Testing

```bash
# Run all tests
pytest tests/

# Run specific test module
pytest tests/test_drivers/test_pca9685.py

# Run with coverage
pytest --cov=src --cov-report=term-missing

# Run integration tests only
pytest tests/ -m integration
```

## Documentation

Detailed API documentation in `docs/`:
- Architecture diagrams
- Hardware wiring guides
- API reference
- Troubleshooting guides

## Contributing

This is a personal robotics project (OpenDuck Mini V3 quadruped robot). Code follows:
- PEP 8 style guidelines
- Type hints for all public APIs
- Docstrings in Google format
- Test coverage >40% (target 70% by end of Week 01)

## License

Personal project - not for commercial use.

## References

- OpenDuck Community: https://discord.gg/UtJZsgfQGe
- Feetech Servos: http://www.feetechrc.com/
- Raspberry Pi Documentation: https://www.raspberrypi.com/documentation/

---

**Created:** 15 January 2026
**Status:** Week 01 Day 1 Complete - Foundation Ready
**Next:** Day 2 - Raspberry Pi setup + PCA9685 driver implementation
