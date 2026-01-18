# LED Error Handling Guide
## OpenDuck Mini V3 - Comprehensive Failure Mode Documentation

**Document Type:** Error Handling Specification
**Author:** Boston Dynamics Systems Integration Engineer
**Created:** 18 January 2026
**Status:** COMPLETE

---

## 1. Overview

This document describes all error conditions, failure modes, and recovery strategies for the LED integration subsystem. Every error condition has a defined handling strategy.

### Error Handling Principles

1. **Fail Safe** - Never leave LEDs in undefined state
2. **Fail Loud** - Log all errors with context
3. **Graceful Degradation** - Continue operation when possible
4. **Clear Messages** - Error messages guide users to solutions
5. **No Silent Failures** - All errors are logged or raised

---

## 2. Initialization Errors

### 2.1 Hardware Import Failure

**Condition:** `rpi_ws281x` library not installed or not available

```python
# Error Code: LED-INIT-001
try:
    from rpi_ws281x import PixelStrip, Color
except ImportError:
    _logger.warning("rpi_ws281x not available - using mock mode")
    return False
```

**Impact:** Hardware LEDs will not work, but system continues

**Recovery:**
- Log warning (not error - expected on dev machines)
- Return False from `initialize_hardware()`
- System continues in mock mode
- Tests still pass

**User Action:**
- Install library: `sudo pip3 install rpi_ws281x --break-system-packages`
- OR continue in mock mode for testing

**Prevention:** Check platform before hardware initialization

---

### 2.2 GPIO Permission Error

**Condition:** Not running with sufficient permissions (not root/sudo)

```python
# Error Code: LED-INIT-002
except PermissionError:
    _logger.error("LED hardware initialization failed: Permission denied")
    _logger.error("Run with: sudo python3 <script>")
    return False
```

**Impact:** LEDs cannot be initialized

**Recovery:**
- Log clear error with solution
- Return False from `initialize_hardware()`
- LEDManager continues but LEDs won't update

**User Action:**
- Run script with `sudo` or as root
- Check udev rules for GPIO access

**Prevention:** Document sudo requirement in README

---

### 2.3 GPIO Conflict Error

**Condition:** GPIO pins already in use (e.g., I2S audio enabled)

```python
# Error Code: LED-INIT-003
except RuntimeError as e:
    _logger.error(f"LED initialization failed: {e}")
    _logger.error("Check GPIO 18 not used by I2S audio")
    _logger.error("Try different GPIO or disable conflicting service")
    return False
```

**Impact:** LEDs cannot be initialized

**Recovery:**
- Log error with troubleshooting steps
- Return False from `initialize_hardware()`
- System continues without LEDs

**User Action:**
- Check `/boot/config.txt` for conflicting overlays
- Move LED to different GPIO (update config)
- Disable I2S audio if not needed

**Prevention:**
- GPIO conflict checking in safety system
- Document known conflicts in pin diagram

---

### 2.4 DMA Channel Conflict

**Condition:** DMA channel already in use

```python
# Error Code: LED-INIT-004
# Same handler as GPIO conflict
except RuntimeError as e:
    _logger.error(f"LED initialization failed: {e}")
    _logger.error("Try different DMA channel (edit LED_DMA)")
    return False
```

**Impact:** LEDs cannot be initialized

**Recovery:**
- Log error with solution
- Suggest alternative DMA channels (10, 11, 12, 13, 14)
- Return False

**User Action:**
- Change `LED_DMA` constant to different channel
- Check system DMA usage: `sudo cat /sys/kernel/debug/dma_pl330`

**Prevention:** Document valid DMA channels

---

## 3. Configuration Errors

### 3.1 Invalid Pattern Name

**Condition:** Unknown pattern requested

```python
# Error Code: LED-CFG-001
if pattern_name not in PATTERN_REGISTRY:
    raise ValueError(
        f"Unknown pattern: {pattern_name}. "
        f"Available: {list(PATTERN_REGISTRY.keys())}"
    )
```

**Impact:** Pattern not set, exception raised

**Recovery:**
- Raise ValueError immediately (fail fast)
- Error message lists valid patterns
- Previous pattern remains active

**User Action:**
- Check pattern name spelling
- Use one of: 'breathing', 'pulse', 'spin'

**Prevention:**
- Type hints in IDE
- Enum for pattern names (future)
- Unit tests for all valid patterns

---

### 3.2 Invalid Color Format

**Condition:** Color is not RGB tuple or values out of range

```python
# Error Code: LED-CFG-002
if not isinstance(color, tuple) or len(color) != 3:
    raise ValueError(f"Color must be RGB tuple, got {color}")

# Error Code: LED-CFG-003
if not all(0 <= c <= 255 for c in color):
    raise ValueError(f"RGB values must be 0-255, got {color}")
```

**Impact:** Color not set, exception raised

**Recovery:**
- Raise ValueError immediately
- Clear error message with format requirements
- Previous color remains active

**User Action:**
- Use tuple: `(255, 128, 64)` not list `[255, 128, 64]`
- Ensure values 0-255

**Prevention:**
- Type hints: `color: RGB` (Tuple[int, int, int])
- Validation in constructor
- Example code in docs

---

### 3.3 Invalid Brightness

**Condition:** Brightness outside 0-255 range

```python
# Error Code: LED-CFG-004
if not 0 <= brightness <= 255:
    raise ValueError(f"Brightness must be 0-255, got {brightness}")
```

**Impact:** Brightness not set, exception raised

**Recovery:**
- Raise ValueError immediately
- Previous brightness remains active

**User Action:**
- Use 0-255 range (not 0.0-1.0)

**Prevention:**
- Clear documentation
- Type hints
- Unit tests for boundary values

---

### 3.4 Invalid Speed

**Condition:** Speed is zero or negative (in pattern config)

```python
# Error Code: LED-CFG-005
# In PatternConfig.__post_init__()
if self.pattern_speed <= 0:
    raise ValueError("pattern_speed must be positive")
```

**Impact:** Pattern config creation fails

**Recovery:**
- Raise ValueError at config creation time
- Fail fast before pattern instantiation

**User Action:**
- Use positive speed (e.g., 0.5, 1.0, 2.0)

**Prevention:**
- Documentation of valid range
- Example configs
- Unit tests

---

## 4. Emotion System Errors

### 4.1 Invalid Emotion Type

**Condition:** Non-EmotionState passed to `set_emotion()`

```python
# Error Code: LED-EMO-001
if not isinstance(emotion, EmotionState):
    raise TypeError(
        f"Expected EmotionState, got {type(emotion).__name__}"
    )
```

**Impact:** Emotion not set, exception raised

**Recovery:**
- Raise TypeError immediately
- Clear message shows expected type
- Previous emotion remains active

**User Action:**
- Use `EmotionState.HAPPY` not string `"happy"`
- Import EmotionState enum

**Prevention:**
- Type hints
- IDE autocomplete
- Examples in docs

---

### 4.2 Invalid Emotion Transition

**Condition:** Attempted transition not in VALID_TRANSITIONS

```python
# Error Code: LED-EMO-002
if not force and not self.can_transition(emotion):
    raise InvalidTransitionError(self._current_emotion, emotion)

# Exception includes:
# - Current state
# - Attempted state
# - List of valid target states
```

**Impact:** Emotion not changed, exception raised

**Recovery:**
- Raise custom exception with guidance
- Previous emotion remains active
- User can force with `force=True` parameter

**User Action:**
- Check valid transitions: `VALID_TRANSITIONS[current_state]`
- OR use `force=True` for emergency override
- OR chain through intermediate states

**Example:**
```python
# Invalid: SLEEPY -> EXCITED
led_mgr.set_emotion(EmotionState.EXCITED)  # Raises InvalidTransitionError

# Solution 1: Force
led_mgr.set_emotion(EmotionState.EXCITED, force=True)

# Solution 2: Valid path
led_mgr.set_emotion(EmotionState.ALERT)    # SLEEPY -> ALERT is valid
led_mgr.set_emotion(EmotionState.EXCITED)  # ALERT -> EXCITED is valid
```

**Prevention:**
- Document transition matrix
- Provide `can_transition()` method for pre-checking
- State diagram in docs

---

## 5. Runtime Errors

### 5.1 Pattern Render Exception

**Condition:** Exception during pattern frame computation

```python
# Error Code: LED-RUN-001
# In LEDController.update()
try:
    pixels = self._current_pattern.render(self._current_color)
except Exception as e:
    _logger.error(f"Pattern render error: {e}", exc_info=True)
    # Continue without updating hardware this frame
    return
```

**Impact:** Single frame skipped, system continues

**Recovery:**
- Log error with full traceback
- Skip hardware update for this frame
- Continue with next frame
- Previous frame remains visible

**User Action:**
- Check logs for pattern-specific issue
- Report bug if reproducible

**Prevention:**
- Unit tests for all patterns
- Boundary value testing
- Hostile code review

---

### 5.2 Hardware Update Exception

**Condition:** Exception during `strip.show()` or GPIO write

```python
# Error Code: LED-RUN-002
# In LEDController.update()
try:
    self._left_strip.show()
    self._right_strip.show()
except Exception as e:
    _logger.error(f"LED hardware update error: {e}", exc_info=True)
    # Continue - try again next frame
```

**Impact:** Frame not displayed, system continues

**Recovery:**
- Log error
- Next frame will retry
- Pattern continues advancing

**User Action:**
- Check hardware connections
- Check GPIO permissions still valid
- Check system logs for GPIO issues

**Prevention:**
- Validate hardware on startup
- Monitor GPIO state
- Graceful shutdown on termination

---

### 5.3 Frame Overrun

**Condition:** Frame computation takes longer than frame budget (20ms)

```python
# Error Code: LED-RUN-003
# In LEDManager._update_loop()
if sleep_time > 0:
    time.sleep(sleep_time)
    next_frame_time += self.frame_time
else:
    # Frame overrun - reset to prevent death spiral
    _logger.warning(f"Frame overrun: {-sleep_time*1000:.1f}ms late")
    next_frame_time = time.monotonic() + self.frame_time
```

**Impact:** Single frame late, timing reset to prevent accumulation

**Recovery:**
- Log warning (not error - may be transient)
- Reset next frame time (no death spiral)
- System continues at target FPS

**User Action:**
- Check CPU load (`top`)
- Check pattern render time (should be <10ms)
- Reduce system load

**Prevention:**
- Optimize pattern rendering
- Pre-compute lookup tables
- Zero-allocation rendering
- Performance testing

---

### 5.4 Thread Exception

**Condition:** Unhandled exception in update thread

```python
# Error Code: LED-RUN-004
# In LEDManager._update_loop()
while self._running:
    try:
        self.led_controller.update()
        self._frame_count += 1
    except Exception as e:
        _logger.error(f"LED update error: {e}", exc_info=True)
        # Continue running - don't crash thread
```

**Impact:** Single frame skipped, system continues

**Recovery:**
- Log full traceback
- Continue update loop
- System remains operational

**User Action:**
- Check logs for root cause
- Report bug if reproducible

**Prevention:**
- Comprehensive exception handling
- Unit tests for edge cases
- Integration testing

---

## 6. Lifecycle Errors

### 6.1 Double Start

**Condition:** `start()` called when already running

```python
# Error Code: LED-LIFE-001
if self._running:
    _logger.warning("LED update loop already running")
    return
```

**Impact:** No-op, warning logged

**Recovery:**
- Log warning (not error - may be application logic)
- Return immediately
- Existing thread continues

**User Action:**
- Check application logic
- Ignore if intentional

**Prevention:**
- Check `_running` flag before start
- Document start/stop lifecycle

---

### 6.2 Stop Without Start

**Condition:** `stop()` called when not running

```python
# Error Code: LED-LIFE-002
if not self._running:
    return  # No-op
```

**Impact:** No-op, no warning (expected case)

**Recovery:**
- Return immediately
- No logging (not an error)

**User Action:**
- None required

**Prevention:**
- Idempotent stop() method
- Safe to call multiple times

---

### 6.3 Thread Join Timeout

**Condition:** Update thread doesn't stop within timeout

```python
# Error Code: LED-LIFE-003
if self._update_thread:
    self._update_thread.join(timeout=1.0)
    if self._update_thread.is_alive():
        _logger.error("LED update thread did not stop within timeout")
```

**Impact:** Thread may continue running (zombie)

**Recovery:**
- Log error
- Continue with shutdown
- Thread is daemon so won't block exit

**User Action:**
- Check for deadlocks in pattern code
- Report bug if reproducible

**Prevention:**
- Daemon threads
- No blocking calls in update loop
- Timeout guards

---

## 7. Edge Cases

### 7.1 Zero Brightness

**Condition:** Brightness set to 0

```python
# Not an error - valid edge case
led_controller.set_brightness(0)  # LEDs off, but pattern still updates
```

**Impact:** LEDs appear off (but pattern continues)

**Recovery:** N/A - valid configuration

**User Action:**
- Use `clear()` if intent is to turn off
- OR increase brightness

**Prevention:**
- Documentation of behavior
- Unit test for edge case

---

### 7.2 Maximum Brightness on Pi Power

**Condition:** Brightness > 127 when powered from Pi 5V

```python
# Error Code: LED-SAFE-001
# Future: LEDSafetyManager integration
if power_source == "PI_5V" and brightness > 127:
    _logger.warning(f"Brightness {brightness} exceeds safe limit for Pi power (127)")
    _logger.warning("Recommend external 5V supply or reduce brightness")
    # Future: Auto-clamp to 127
```

**Impact:** Risk of Pi brownout, SD corruption

**Recovery:**
- Log warning
- Future: Auto-clamp to safe value
- Continue with user-set brightness

**User Action:**
- Reduce brightness to ≤127
- OR use external 5V power supply

**Prevention:**
- Safety manager integration
- Auto-detection of power source
- Current limiting

---

### 7.3 Pattern Change During Update

**Condition:** Pattern changed while render in progress

```python
# Handled by RLock in LEDController
with self._lock:
    # All pattern operations locked
    # No race conditions possible
```

**Impact:** None - thread-safe

**Recovery:** N/A - prevented by locking

**User Action:** None required

**Prevention:**
- RLock for all critical sections
- Thread-safe design
- Race condition testing

---

### 7.4 Emotion Change During Transition

**Condition:** New emotion set before previous transition completes

```python
# Not an error - expected behavior
led_mgr.set_emotion(EmotionState.HAPPY)
# Immediate change, no transition animation
led_mgr.set_emotion(EmotionState.SAD)
# Overrides previous, starts new config immediately
```

**Impact:** Previous transition cancelled, new one starts

**Recovery:** N/A - expected behavior

**User Action:** None required (or debounce emotion changes)

**Prevention:**
- Document behavior
- Consider transition queuing (future)

---

## 8. Error Recovery Strategies

### Strategy 1: Retry with Exponential Backoff

**Use Case:** Transient hardware errors

```python
def retry_hardware_init(max_attempts=3):
    for attempt in range(max_attempts):
        try:
            return initialize_hardware()
        except RuntimeError as e:
            if attempt < max_attempts - 1:
                delay = 2 ** attempt  # 1s, 2s, 4s
                _logger.warning(f"Init failed, retry in {delay}s: {e}")
                time.sleep(delay)
            else:
                raise
```

---

### Strategy 2: Fallback to Safe State

**Use Case:** Pattern render error

```python
def safe_fallback():
    """Return to IDLE emotion on error."""
    try:
        led_mgr.set_emotion(EmotionState.IDLE, force=True)
    except Exception as e:
        _logger.error(f"Even fallback failed: {e}")
        led_controller.clear()  # Last resort - turn off LEDs
```

---

### Strategy 3: Graceful Degradation

**Use Case:** Missing hardware

```python
def create_controller_with_fallback():
    """Create hardware controller, fall back to mock if unavailable."""
    controller = LEDController()
    if not controller.initialize_hardware():
        _logger.info("Using mock LED controller (no hardware)")
        from tests.test_led.conftest import MockPixelStrip
        # Use mock for testing
    return controller
```

---

### Strategy 4: Circuit Breaker

**Use Case:** Repeated hardware errors

```python
class CircuitBreaker:
    def __init__(self, threshold=5, timeout=30):
        self.threshold = threshold
        self.timeout = timeout
        self.failures = 0
        self.last_failure = 0
        self.open = False

    def call(self, func):
        if self.open:
            if time.time() - self.last_failure > self.timeout:
                self.open = False  # Try again
                self.failures = 0
            else:
                raise CircuitOpenError("Too many failures")

        try:
            result = func()
            self.failures = 0
            return result
        except Exception as e:
            self.failures += 1
            self.last_failure = time.time()
            if self.failures >= self.threshold:
                self.open = True
            raise
```

---

## 9. Debugging Guide

### Enable Debug Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)
_logger = logging.getLogger('core.led_manager')
_logger.setLevel(logging.DEBUG)
```

### Get System State

```python
stats = led_mgr.get_stats()
print(f"Running: {stats['running']}")
print(f"FPS: {stats['fps']:.1f}")
print(f"Frames: {stats['frame_count']}")
print(f"Emotion: {stats['emotion']}")
print(f"Pattern: {stats['pattern']}")
print(f"Color: RGB{stats['color']}")
print(f"Brightness: {stats['brightness']}")
```

### Check Pattern Metrics

```python
pattern = led_controller._current_pattern
metrics = pattern.get_metrics()
if metrics:
    print(f"Frame: {metrics.frame_number}")
    print(f"Render: {metrics.render_time_us/1000:.2f}ms")
```

### Validate Transitions

```python
from animation.emotions import VALID_TRANSITIONS, EmotionState

current = led_mgr.get_current_emotion()
valid = VALID_TRANSITIONS[current]
print(f"Current: {current.name}")
print(f"Valid transitions: {[e.name for e in valid]}")

# Check specific transition
can_go = led_mgr.emotion_manager.can_transition(EmotionState.HAPPY)
print(f"Can go to HAPPY: {can_go}")
```

---

## 10. Error Code Reference

| Code | Category | Severity | Description |
|------|----------|----------|-------------|
| LED-INIT-001 | Init | WARNING | rpi_ws281x not available |
| LED-INIT-002 | Init | ERROR | Permission denied (need sudo) |
| LED-INIT-003 | Init | ERROR | GPIO conflict |
| LED-INIT-004 | Init | ERROR | DMA channel conflict |
| LED-CFG-001 | Config | ERROR | Invalid pattern name |
| LED-CFG-002 | Config | ERROR | Invalid color format |
| LED-CFG-003 | Config | ERROR | Color values out of range |
| LED-CFG-004 | Config | ERROR | Brightness out of range |
| LED-CFG-005 | Config | ERROR | Invalid speed |
| LED-EMO-001 | Emotion | ERROR | Invalid emotion type |
| LED-EMO-002 | Emotion | ERROR | Invalid transition |
| LED-RUN-001 | Runtime | ERROR | Pattern render exception |
| LED-RUN-002 | Runtime | ERROR | Hardware update exception |
| LED-RUN-003 | Runtime | WARNING | Frame overrun |
| LED-RUN-004 | Runtime | ERROR | Thread exception |
| LED-LIFE-001 | Lifecycle | WARNING | Double start |
| LED-LIFE-002 | Lifecycle | INFO | Stop without start |
| LED-LIFE-003 | Lifecycle | ERROR | Thread join timeout |
| LED-SAFE-001 | Safety | WARNING | Brightness exceeds Pi limit |

---

## 11. Testing Error Conditions

### Unit Test Examples

```python
def test_invalid_pattern_name():
    """Test error on unknown pattern."""
    with pytest.raises(ValueError, match="Unknown pattern"):
        controller.set_pattern('nonexistent')

def test_invalid_transition():
    """Test error on invalid emotion change."""
    mgr.set_emotion(EmotionState.SLEEPY)
    with pytest.raises(InvalidTransitionError):
        mgr.set_emotion(EmotionState.EXCITED)

def test_recovery_from_render_error():
    """Test system continues after pattern error."""
    # Mock pattern to raise exception
    with patch.object(pattern, 'render', side_effect=RuntimeError):
        controller.update()  # Should not crash
        controller.update()  # Should work again
```

---

**End of Document**

For questions or issues not covered here, consult:
- `LED_INTEGRATION_ARCHITECTURE.md` - System design
- `firmware/tests/test_core/test_led_integration.py` - Test examples
- `firmware/src/core/led_manager.py` - Implementation
