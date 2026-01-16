# OpenDuck Mini V3 Firmware

<p align="center">
  <strong>Quadruped Robot Firmware for Raspberry Pi</strong>
</p>

<p align="center">
  <a href="#about">About</a> •
  <a href="#disclaimer">Disclaimer</a> •
  <a href="#architecture">Architecture</a> •
  <a href="#status">Status</a>
</p>

---

## Author

**Matteo Panzeri**
BSc Student, University of Pavia, Italy
Personal Robotics Project - January 2026

---

## Disclaimer

> **This repository is EXPERIMENTAL and under active development.**
>
> **I do NOT recommend using this code in your own projects at this time.**
>
> - The codebase is incomplete and rapidly changing
> - APIs may change without notice
> - Hardware configurations are specific to my setup
> - Safety systems are still being validated
> - No guarantees of functionality or safety
>
> **If you're interested in the OpenDuck Mini project, please visit the official [OpenDuck Community Discord](https://discord.gg/UtJZsgfQGe) for stable resources.**

---

## Safety Warning

> **This firmware controls a robot powered by Li-ion batteries.**
>
> Li-ion batteries can explode, cause fires, and result in serious injury or death if mishandled.
>
> - 18+ only
> - Electrical safety training required
> - Class D fire extinguisher required nearby
> - Never charge unattended
> - Use proper BMS (Battery Management System)
>
> **Read [Battery Safety Warnings](docs/SAFETY_WARNINGS.md) before proceeding.**

---

## About

This firmware is part of my personal project to build an **OpenDuck Mini V3** - a 12-DOF quadruped robot based on the open-source [OpenDuck](https://github.com/apirrone/Open_Duck_Mini) design.

### Project Goals

1. **Learn embedded robotics** - Gain hands-on experience with real-time control systems, sensor fusion, and motion planning

2. **Implement safety-first design** - Build robust safety systems (E-stop, watchdog, current limiting) as a foundation before adding features

3. **Develop walking gaits** - Implement inverse kinematics and gait algorithms to achieve stable quadruped locomotion

4. **Integrate AI capabilities** - Eventually add computer vision (Pi AI Camera) and voice interaction for an autonomous companion robot

### Why This Project?

As a BSc student at University of Pavia, I wanted to combine my interests in:
- Embedded systems programming
- Control theory and kinematics
- Machine learning and AI
- Practical hardware engineering

This project serves as a learning platform where theory meets practice.

---

## Architecture

```
firmware/
├── src/
│   ├── core/               # Robot orchestrator, state machine, safety
│   │   ├── robot.py        # Main Robot class
│   │   ├── robot_state.py  # State machine (INIT → READY ↔ E_STOPPED)
│   │   └── safety_coordinator.py
│   │
│   ├── drivers/            # Hardware Abstraction Layer (HAL)
│   │   ├── servo/          # PCA9685 PWM controller
│   │   ├── sensor/         # BNO085 IMU, HC-SR04 ultrasonic
│   │   ├── led/            # WS2812B NeoPixel
│   │   └── power/          # Voltage monitoring
│   │
│   ├── safety/             # Safety subsystems
│   │   ├── emergency_stop.py
│   │   ├── watchdog.py
│   │   └── current_limiter.py
│   │
│   └── kinematics/         # Motion planning
│       └── arm_kinematics.py  # 2-DOF inverse kinematics
│
├── tests/                  # Unit and integration tests (136+ tests)
├── scripts/                # Hardware validation utilities
├── config/                 # YAML configuration files
└── docs/                   # Documentation
```

### Key Design Principles

- **Safety First**: E-stop system with <100ms latency, watchdog timers, current limiting
- **Thread Safety**: I2C bus manager prevents collisions between devices
- **Testability**: Comprehensive mocks allow testing without hardware
- **Modularity**: Clean separation between HAL, control, and application layers

---

## Hardware Platform

| Component | Model | Purpose |
|-----------|-------|---------|
| **Compute** | Raspberry Pi 4 (4GB) | Main controller |
| **PWM** | PCA9685 | 16-channel servo control |
| **IMU** | BNO085 9-DOF | Orientation sensing |
| **Servos** | MG90S (testing) | Initial development |
| **Servos** | Feetech STS3215 (future) | Production servos |
| **Power** | 2S Li-ion + UBEC | 5V/6V regulated power |

---

## Status

**Current Phase:** Week 01 - Foundation
**Version:** 0.1.0-dev
**Tests:** 136+ passing

### Completed
- [x] PCA9685 servo driver with I2C bus management
- [x] Robot orchestrator with state machine
- [x] Safety systems (E-stop, Watchdog, CurrentLimiter)
- [x] SafetyCoordinator (unified safety)
- [x] 2-DOF arm inverse kinematics
- [x] BNO085 IMU driver
- [x] Comprehensive test suite

### In Progress
- [ ] Hardware validation on Raspberry Pi
- [ ] Servo movement testing (waiting for batteries)
- [ ] Multi-servo coordination

### Planned (Week 02+)
- [ ] 3-DOF leg kinematics
- [ ] Basic gait patterns (crawl, trot)
- [ ] Sensor fusion (IMU + foot contact)
- [ ] PyBullet simulation integration

---

## Quick Start

> **Note:** This is for reference only. The code is experimental.

```bash
# Clone repository
git clone https://github.com/matte1782/openduck-firmware.git
cd openduck-firmware

# Install dependencies
pip install -r requirements.txt

# Run tests (works without hardware)
pytest tests/ -v

# Hardware validation (requires Raspberry Pi + PCA9685)
python scripts/hardware_validation.py --i2c
```

---

## Contributing

This is a personal learning project. While I'm not accepting contributions at this time, feel free to:

- Open issues for questions or suggestions
- Fork for your own experiments
- Star if you find it interesting!

For stable OpenDuck resources, visit the [OpenDuck Community](https://discord.gg/UtJZsgfQGe).

---

## License

This project is for educational purposes. See [LICENSE](../LICENSE) for details.

---

## Acknowledgments

- **OpenDuck Community** - For the amazing open-source quadruped robot design
- **University of Pavia** - For the educational foundation
- **Adafruit** - For excellent hardware libraries and documentation

---

<p align="center">
  <em>Built with curiosity and coffee</em> ☕
</p>

<p align="center">
  <strong>Matteo Panzeri</strong><br>
  University of Pavia, Italy<br>
  January 2026
</p>
