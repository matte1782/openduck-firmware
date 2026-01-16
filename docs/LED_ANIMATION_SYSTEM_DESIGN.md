# Disney-Level LED Animation System Design
## OpenDuck Mini V3 - Emotion & Expression Framework

**Version:** 1.0
**Created:** 21 January 2026
**Status:** DESIGN COMPLETE - Ready for Implementation

---

## Overview

This document defines the architecture and implementation guidelines for a Disney-quality LED animation system for the OpenDuck Mini V3 robot. The system transforms a simple 16-LED WS2812B ring into expressive "eyes" that communicate emotion and personality.

### Design Philosophy

> "The illusion of life is not about complexity, but about timing and anticipation."
> — Frank Thomas & Ollie Johnston, Disney Animation Legends

Our LED system will:
1. **Feel alive** through subtle constant motion
2. **Communicate emotion** through color and pattern
3. **React with personality** through timing and easing
4. **Never feel robotic** by avoiding linear movements

---

## Disney's 12 Principles Applied to LEDs

### 1. Squash & Stretch
**Traditional:** Object deforms to show weight and flexibility
**LED Application:** Brightness "compression" during emotion transitions

```python
def squash_stretch_brightness(base: int, intensity: float) -> int:
    """Squash = dim quickly, Stretch = brighten slowly"""
    if intensity > 0:  # Stretching (expanding emotion)
        return int(base * (1 + intensity * 0.3))  # 30% overshoot
    else:  # Squashing (contracting)
        return int(base * (1 + intensity * 0.5))  # 50% undershoot
```

### 2. Anticipation
**Traditional:** Prepare audience for action
**LED Application:** Brief dim/color shift before major emotion change

```python
async def anticipate_emotion_change(current_color, target_color):
    """Brief anticipation flash before emotion transition"""
    # Quick dim (100ms)
    await fade_to(brightness=0.3, duration_ms=100)
    # Hold (50ms)
    await asyncio.sleep(0.05)
    # Transition to new emotion
    await transition_to(target_color, duration_ms=400)
```

### 3. Staging
**Traditional:** Present idea clearly
**LED Application:** Single focal point per emotion (one dominant effect)

```python
EMOTION_PRIMARY_EFFECT = {
    'happy': 'warm_glow',      # Primary: brightness
    'sad': 'slow_fade',        # Primary: dimness
    'curious': 'focus_point',  # Primary: directionality
    'alert': 'pulse',          # Primary: movement speed
}
```

### 4. Straight Ahead vs Pose-to-Pose
**Traditional:** Spontaneous vs planned animation
**LED Application:** Idle behaviors (straight ahead) vs scripted emotions (pose-to-pose)

### 5. Follow Through & Overlapping Action
**Traditional:** Parts continue moving after main action
**LED Application:** Color "echo" and brightness settling

```python
def follow_through(color_change):
    """After main transition, subtle follow-through"""
    # Main transition complete, but...
    # Brief overshoot in brightness
    yield brightness_overshoot(1.1, duration=100)
    # Settle back to target
    yield settle(target, duration=200)
```

### 6. Slow In & Slow Out
**Traditional:** More frames at start/end of movement
**LED Application:** Easing functions on ALL transitions

```python
EASING_FUNCTIONS = {
    'ease_in': lambda t: t ** 2,
    'ease_out': lambda t: 1 - (1 - t) ** 2,
    'ease_in_out': lambda t: (
        2 * t ** 2 if t < 0.5
        else 1 - (-2 * t + 2) ** 2 / 2
    ),
    'ease_in_out_back': lambda t: ...,  # Overshoot easing
}
```

### 7. Arc
**Traditional:** Natural movements follow arcs
**LED Application:** Color transitions through color wheel, not directly

```python
def transition_color_arc(start: RGB, end: RGB, progress: float) -> RGB:
    """Transition through HSV color wheel, not linear RGB"""
    start_hsv = rgb_to_hsv(start)
    end_hsv = rgb_to_hsv(end)

    # Interpolate through hue (circular)
    hue = interpolate_circular(start_hsv.h, end_hsv.h, progress)
    sat = lerp(start_hsv.s, end_hsv.s, progress)
    val = lerp(start_hsv.v, end_hsv.v, progress)

    return hsv_to_rgb(HSV(hue, sat, val))
```

### 8. Secondary Action
**Traditional:** Supplementary animation supporting main action
**LED Application:** Subtle patterns underneath primary emotion color

```python
class SecondaryPatterns:
    """Background patterns that add life without distraction"""

    def subtle_sparkle(self, base_color, intensity=0.1):
        """Random pixel brightness variation"""
        for i in range(16):
            variance = random.uniform(1 - intensity, 1 + intensity)
            self.pixels[i] = scale_color(base_color, variance)

    def micro_breathing(self, base_color, rate=0.5):
        """Very subtle sine wave (±5% brightness)"""
        offset = math.sin(time.time() * rate) * 0.05
        return scale_brightness(base_color, 1 + offset)
```

### 9. Timing
**Traditional:** Speed of action gives weight and emotion
**LED Application:** Different durations for different emotions

```python
EMOTION_TIMING_MS = {
    'idle': {'transition': 800, 'pattern_speed': 0.5},
    'happy': {'transition': 400, 'pattern_speed': 1.2},
    'sad': {'transition': 1200, 'pattern_speed': 0.3},
    'curious': {'transition': 300, 'pattern_speed': 1.0},
    'alert': {'transition': 150, 'pattern_speed': 2.0},
    'excited': {'transition': 200, 'pattern_speed': 1.8},
    'sleepy': {'transition': 1500, 'pattern_speed': 0.2},
    'thinking': {'transition': 500, 'pattern_speed': 0.8},
}
```

### 10. Exaggeration
**Traditional:** Push expressions beyond realistic
**LED Application:** Amplify color saturation and brightness for emotions

```python
EXAGGERATION_FACTORS = {
    'happy': 1.3,     # 30% brighter
    'sad': 0.6,       # 40% dimmer
    'excited': 1.5,   # 50% more intense
    'sleepy': 0.4,    # Very dim
}

def apply_exaggeration(color, emotion):
    factor = EXAGGERATION_FACTORS.get(emotion, 1.0)
    return scale_brightness(color, factor)
```

### 11. Solid Drawing
**Traditional:** Consistent 3D form
**LED Application:** Consistent color temperature and saturation per emotion family

### 12. Appeal
**Traditional:** Character that audience connects with
**LED Application:** Colors that feel warm, friendly, and non-threatening

```python
# AVOID: Pure saturated colors (feel artificial)
BAD_COLORS = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]

# PREFER: Warm, desaturated, friendly colors
GOOD_COLORS = {
    'warm_white': (255, 244, 229),
    'soft_blue': (150, 180, 255),
    'gentle_green': (150, 220, 170),
    'friendly_orange': (255, 200, 120),
}
```

---

## Color Psychology for Robot Emotions

### Primary Emotion Palette

| Emotion | Primary Color | RGB | Meaning | Notes |
|---------|---------------|-----|---------|-------|
| Idle | Soft Blue | (100, 150, 255) | Calm, neutral | Default resting state |
| Happy | Warm Yellow | (255, 220, 50) | Joy, warmth | Avoid pure yellow (harsh) |
| Curious | Soft Green | (150, 255, 150) | Interest, growth | Lean toward teal |
| Alert | Warm Red | (255, 100, 100) | Attention | NOT pure red (aggression) |
| Sad | Muted Blue | (100, 100, 200) | Melancholy | Desaturated |
| Sleepy | Lavender | (150, 130, 200) | Drowsy, calm | Very dim |
| Excited | Orange | (255, 150, 50) | Energy, enthusiasm | High brightness |
| Thinking | White-Blue | (200, 200, 255) | Processing | Slight blue tint |

### Color Temperature Rules

```python
# Warm emotions (happy, excited) = High color temperature (yellow/orange)
# Cool emotions (sad, sleepy) = Low color temperature (blue/purple)
# Neutral emotions (idle, thinking) = Balanced white/blue

def adjust_color_temperature(color: RGB, warmth: float) -> RGB:
    """warmth: -1.0 (cool) to +1.0 (warm)"""
    r, g, b = color
    if warmth > 0:
        # Warmer: increase red/yellow, decrease blue
        r = min(255, int(r * (1 + warmth * 0.3)))
        b = max(0, int(b * (1 - warmth * 0.3)))
    else:
        # Cooler: increase blue, decrease red/yellow
        b = min(255, int(b * (1 - warmth * 0.3)))
        r = max(0, int(r * (1 + warmth * 0.3)))
    return (r, g, b)
```

---

## Pattern Library

### Core Patterns

#### 1. Breathing (Idle State)
```python
class BreathingPattern:
    """Slow sine wave brightness - the pulse of life"""

    CYCLE_DURATION_SEC = 4.0  # One full breath
    MIN_BRIGHTNESS = 0.3      # Never fully dim
    MAX_BRIGHTNESS = 1.0

    def render(self, frame: int, base_color: RGB) -> List[RGB]:
        progress = (frame / 50) / self.CYCLE_DURATION_SEC  # 50Hz
        breath = (math.sin(progress * 2 * math.pi) + 1) / 2

        brightness = self.MIN_BRIGHTNESS + breath * (
            self.MAX_BRIGHTNESS - self.MIN_BRIGHTNESS
        )

        return [scale_brightness(base_color, brightness)] * 16
```

#### 2. Pulse (Alert/Excited)
```python
class PulsePattern:
    """Quick heartbeat pulse"""

    def render(self, frame: int, base_color: RGB) -> List[RGB]:
        # Double-pulse heartbeat pattern
        t = (frame / 50) % 1.0  # 1 second cycle

        if t < 0.1:       # First pulse (100ms)
            intensity = math.sin(t / 0.1 * math.pi)
        elif t < 0.2:     # Rest (100ms)
            intensity = 0.3
        elif t < 0.3:     # Second pulse (100ms)
            intensity = math.sin((t - 0.2) / 0.1 * math.pi) * 0.7
        else:             # Long rest (700ms)
            intensity = 0.3

        brightness = 0.3 + intensity * 0.7
        return [scale_brightness(base_color, brightness)] * 16
```

#### 3. Spin (Thinking)
```python
class SpinPattern:
    """Rotating dot for 'thinking' state"""

    TAIL_LENGTH = 4  # Pixels in the comet tail

    def render(self, frame: int, base_color: RGB) -> List[RGB]:
        head_pos = (frame // 2) % 16  # Position updates every 2 frames

        pixels = [(0, 0, 0)] * 16

        for i in range(self.TAIL_LENGTH):
            pos = (head_pos - i) % 16
            fade = 1.0 - (i / self.TAIL_LENGTH)
            pixels[pos] = scale_brightness(base_color, fade)

        return pixels
```

#### 4. Sparkle (Happy/Excited)
```python
class SparklePattern:
    """Random twinkling pixels"""

    SPARKLE_PROBABILITY = 0.1

    def render(self, frame: int, base_color: RGB) -> List[RGB]:
        pixels = [base_color] * 16

        for i in range(16):
            if random.random() < self.SPARKLE_PROBABILITY:
                # Random brightness boost
                boost = random.uniform(1.2, 1.5)
                pixels[i] = scale_brightness(base_color, boost)
            else:
                # Subtle variation
                variation = random.uniform(0.9, 1.1)
                pixels[i] = scale_brightness(base_color, variation)

        return pixels
```

#### 5. Fade (Sad/Sleepy)
```python
class FadePattern:
    """Slow, gentle dimming"""

    FADE_DURATION_SEC = 3.0

    def render(self, frame: int, base_color: RGB, target_brightness: float = 0.2):
        progress = min(1.0, (frame / 50) / self.FADE_DURATION_SEC)
        eased = ease_in_out(progress)

        brightness = 1.0 - eased * (1.0 - target_brightness)
        return [scale_brightness(base_color, brightness)] * 16
```

---

## State Machine Architecture

### Emotion State Transitions

```
                    ┌──────────┐
                    │   IDLE   │
                    └────┬─────┘
                         │
        ┌────────────────┼────────────────┐
        ▼                ▼                ▼
    ┌───────┐       ┌────────┐       ┌────────┐
    │ HAPPY │◄─────►│ CURIOUS│◄─────►│ ALERT  │
    └───┬───┘       └───┬────┘       └────┬───┘
        │               │                  │
        ▼               ▼                  ▼
    ┌────────┐     ┌──────────┐      ┌─────────┐
    │EXCITED │     │ THINKING │      │   SAD   │
    └────────┘     └──────────┘      └─────────┘
                                           │
                                           ▼
                                     ┌─────────┐
                                     │ SLEEPY  │
                                     └─────────┘
```

### Transition Rules

```python
VALID_TRANSITIONS = {
    'idle': ['happy', 'curious', 'alert', 'sleepy'],
    'happy': ['idle', 'excited', 'curious'],
    'curious': ['idle', 'happy', 'alert', 'thinking'],
    'alert': ['idle', 'curious', 'sad'],
    'excited': ['happy', 'idle'],
    'thinking': ['curious', 'idle'],
    'sad': ['idle', 'sleepy'],
    'sleepy': ['idle', 'sad'],
}

def can_transition(current: str, target: str) -> bool:
    return target in VALID_TRANSITIONS.get(current, [])
```

---

## Implementation Architecture

### Class Hierarchy

```
LEDController
├── PatternEngine
│   ├── BreathingPattern
│   ├── PulsePattern
│   ├── SpinPattern
│   ├── SparklePattern
│   └── FadePattern
├── ColorManager
│   ├── color_blend()
│   ├── hsv_transition()
│   └── temperature_adjust()
└── EmotionManager
    ├── set_emotion()
    ├── transition_to()
    └── update()
```

### Thread Model

```
Main Thread          Animation Thread        Hardware Thread
    │                      │                      │
    │ set_emotion()        │                      │
    ├─────────────────────►│                      │
    │                      │ update() @ 50Hz      │
    │                      ├─────────────────────►│
    │                      │                      │ write_pixels()
    │                      │                      │
```

### Timing Constraints

| Operation | Maximum Latency | Target |
|-----------|-----------------|--------|
| Pattern frame render | 10ms | 5ms |
| Color transition calc | 5ms | 2ms |
| Pixel data write | 2ms | 1ms |
| Full frame | 20ms | 10ms |

---

## Test Requirements

### Unit Tests

```python
# tests/test_led/test_patterns.py

class TestBreathingPattern:
    def test_brightness_range(self):
        """Brightness stays within 0.3-1.0"""

    def test_cycle_duration(self):
        """Full cycle takes 4 seconds"""

    def test_continuous_output(self):
        """No sudden jumps between frames"""

class TestColorTransitions:
    def test_hsv_arc(self):
        """Colors transition through HSV, not RGB"""

    def test_no_flicker(self):
        """No single-frame brightness spikes"""

class TestEmotionManager:
    def test_valid_transitions(self):
        """Only valid transitions allowed"""

    def test_transition_duration(self):
        """Transitions respect timing config"""

    def test_rapid_changes(self):
        """Rapid emotion changes don't cause glitches"""
```

### Hardware Tests

```python
# tests/test_led/test_hardware.py

class TestLEDHardware:
    def test_all_pixels_addressable(self):
        """All 16 pixels can be set individually"""

    def test_color_accuracy(self):
        """Set color matches expected (within tolerance)"""

    def test_frame_rate(self):
        """Maintains 50Hz update rate"""

    def test_power_consumption(self):
        """Current draw within budget"""
```

---

## Performance Optimization

### Pre-computed Lookup Tables

```python
# Pre-compute easing curves (avoid math.sin every frame)
EASE_IN_OUT_LUT = [ease_in_out(i / 100) for i in range(101)]

def fast_ease(t: float) -> float:
    """Lookup table easing (O(1) vs O(n) math)"""
    index = int(t * 100)
    return EASE_IN_OUT_LUT[min(index, 100)]
```

### Pixel Buffer Reuse

```python
class LEDController:
    def __init__(self):
        # Pre-allocate pixel buffer (avoid allocations in render loop)
        self._pixel_buffer = [(0, 0, 0)] * 16

    def render(self):
        # Modify in place, don't create new list
        for i in range(16):
            self._pixel_buffer[i] = self._compute_pixel(i)
```

---

## Integration with Robot System

### Emotion Triggers

```python
# Automatic emotion triggers from robot state
EMOTION_TRIGGERS = {
    'low_battery': EmotionState.SLEEPY,
    'obstacle_detected': EmotionState.ALERT,
    'voice_command': EmotionState.CURIOUS,
    'task_complete': EmotionState.HAPPY,
    'error_state': EmotionState.SAD,
    'processing': EmotionState.THINKING,
}
```

### Synchronization with Head Movement

```python
class EmotionCoordinator:
    """Coordinates LED emotions with head servo movements"""

    def set_emotion(self, emotion: EmotionState):
        # LED transition
        self.led_manager.transition_to(emotion)

        # Synchronized head movement
        head_preset = EMOTION_HEAD_PRESETS[emotion]
        self.head_controller.move_to(head_preset)

    EMOTION_HEAD_PRESETS = {
        'happy': {'pan': 90, 'tilt': 80},    # Slight up
        'sad': {'pan': 90, 'tilt': 110},     # Looking down
        'curious': {'pan': 70, 'tilt': 85},  # Head tilt
        'alert': {'pan': 90, 'tilt': 90},    # Straight ahead
    }
```

---

## References

### Disney Animation
- "The Illusion of Life" - Frank Thomas & Ollie Johnston
- Disney's 12 Principles of Animation (1981)

### MIT Media Lab
- Cynthia Breazeal - "Designing Sociable Robots"
- Kismet robot facial expression research

### Color Psychology
- "Color and Human Response" - Faber Birren
- "Interaction of Color" - Josef Albers

---

**Document Version:** 1.0
**Last Updated:** 21 January 2026
**Next Review:** After Week 02 Implementation
