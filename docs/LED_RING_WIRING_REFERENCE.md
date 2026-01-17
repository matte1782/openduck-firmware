# LED Ring Wiring Reference - OpenDuck Mini V3

**Created:** 17 January 2026
**Status:** VALIDATED - Both rings working

---

## Wire Colors (ACTUAL)

| Function | Wire Color | Description |
|----------|------------|-------------|
| **VCC (5V Power)** | RED | Power supply |
| **DIN (Data)** | BROWN | Signal from GPIO |
| **GND (Ground)** | ORANGE | Common ground |

**NOTE:** These are the actual wire colors used on the OpenDuck LED rings. Do NOT assume standard black/red convention!

---

## Pinout Reference

```
┌─────────────────────────────────────────────────────────────┐
│              DUAL LED RING WIRING - VALIDATED               │
├─────────────┬─────────────────┬─────────────────────────────┤
│    Wire     │     Ring 1      │     Ring 2                  │
├─────────────┼─────────────────┼─────────────────────────────┤
│ VCC (RED)   │ Pin 2 (5V)      │ Pin 4 (5V)                  │
├─────────────┼─────────────────┼─────────────────────────────┤
│ GND (ORANGE)│ Pin 6 (GND)     │ Pin 34 (GND)                │
├─────────────┼─────────────────┼─────────────────────────────┤
│ DIN (BROWN) │ Pin 12 (GPIO18) │ Pin 33 (GPIO13)             │
└─────────────┴─────────────────┴─────────────────────────────┘
```

---

## GPIO and PWM Channel Mapping

| Ring | GPIO | Physical Pin | PWM Channel | Notes |
|------|------|--------------|-------------|-------|
| Ring 1 | GPIO 18 | Pin 12 | Channel 0 | Primary eye |
| Ring 2 | GPIO 13 | Pin 33 | Channel 1 | Secondary eye |

**IMPORTANT:**
- GPIO 12 (Pin 32) does NOT work for second ring - same PWM channel as GPIO 18
- GPIO 13 (Pin 33) MUST be used for Ring 2 (different PWM channel)

---

## Raspberry Pi Header Diagram

```
                    Raspberry Pi 4 GPIO Header
                    (Looking down at the Pi)

        3.3V  (1) ●  ● (2)  5V      ◄── Ring 1 VCC (RED)
       GPIO2  (3) ●  ● (4)  5V      ◄── Ring 2 VCC (RED)
       GPIO3  (5) ●  ● (6)  GND     ◄── Ring 1 GND (ORANGE)
       GPIO4  (7) ●  ● (8)  GPIO14
         GND  (9) ●  ● (10) GPIO15
      GPIO17 (11) ●  ● (12) GPIO18  ◄── Ring 1 DIN (BROWN)
      GPIO27 (13) ●  ● (14) GND
      GPIO22 (15) ●  ● (16) GPIO23
        3.3V (17) ●  ● (18) GPIO24
      GPIO10 (19) ●  ● (20) GND
       GPIO9 (21) ●  ● (22) GPIO25
      GPIO11 (23) ●  ● (24) GPIO8
         GND (25) ●  ● (26) GPIO7
       GPIO0 (27) ●  ● (28) GPIO1
       GPIO5 (29) ●  ● (30) GND
       GPIO6 (31) ●  ● (32) GPIO12  ✗ DON'T USE (PWM conflict)
      GPIO13 (33) ●  ● (34) GND     ◄── Ring 2 GND (ORANGE)
         ↑                              Ring 2 DIN (BROWN)
         └── Pin 33 = GPIO13 = Ring 2 Data
```

---

## Troubleshooting

### Common Issues

1. **"Selected GPIO not possible" error**
   - Using GPIO 12 for Ring 2 (conflicts with Ring 1's PWM channel)
   - Fix: Use GPIO 13 (Pin 33) for Ring 2

2. **Ring 1 stops working when Ring 2 connected**
   - Wrong pin for Ring 2 data (was using Pin 10 instead of Pin 12)
   - Power overload (check 5V connections)
   - Reboot Pi to reset GPIO state

3. **LEDs stuck on after crash**
   - Script crashed before cleanup
   - Fix: Reboot Pi or run cleanup script

### Quick GPIO Reset
```bash
sudo reboot
```

---

## Validated Test Command

```bash
sudo python3 ~/led_test.py           # Ring 1 only
sudo python3 ~/test_dual_leds.py     # Both rings
```

---

**Document Version:** 1.0
**Last Validated:** 17 January 2026
