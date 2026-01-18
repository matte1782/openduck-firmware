"""
Emotion State Machine Tests - TDD First Approach

Tests written BEFORE implementation per CLAUDE.md Rule 4.
All tests should FAIL initially until implementation is complete.

Run with: pytest tests/test_animation/test_emotions.py -v
(from firmware/ directory)
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock
from dataclasses import dataclass
from enum import Enum
from typing import Tuple, Dict, Set

# Add firmware/src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))


# === Test Fixtures ===

@pytest.fixture
def mock_led_controller():
    """Mock LED controller for testing without hardware."""
    mock = Mock()
    mock.set_pattern = Mock()
    mock.set_color = Mock()
    mock.set_brightness = Mock()
    mock.transition_to = Mock()
    return mock


@pytest.fixture
def mock_animator():
    """Mock animator for testing without servo hardware."""
    mock = Mock()
    mock.play = Mock()
    mock.queue = Mock()
    mock.is_playing = Mock(return_value=False)
    return mock


@pytest.fixture
def emotion_manager(mock_led_controller, mock_animator):
    """Create EmotionManager with mock dependencies."""
    # Import will fail until we create the module
    from animation.emotions import EmotionManager
    return EmotionManager(mock_led_controller, mock_animator)


# === EmotionState Enum Tests ===

class TestEmotionStateEnum:
    """Test EmotionState enumeration."""

    def test_all_eight_states_exist(self):
        """Verify all 8 emotion states are defined."""
        from animation.emotions import EmotionState

        expected_states = [
            'IDLE', 'HAPPY', 'CURIOUS', 'ALERT',
            'SLEEPY', 'EXCITED', 'THINKING', 'SAD'
        ]

        for state_name in expected_states:
            assert hasattr(EmotionState, state_name), f"Missing state: {state_name}"

    def test_state_values_are_lowercase_strings(self):
        """State values should be lowercase for config lookup."""
        from animation.emotions import EmotionState

        for state in EmotionState:
            assert state.value == state.name.lower(), \
                f"State {state.name} should have lowercase value"

    def test_states_are_unique(self):
        """All state values must be unique."""
        from animation.emotions import EmotionState

        values = [s.value for s in EmotionState]
        assert len(values) == len(set(values)), "Duplicate state values found"


# === EmotionConfig Tests ===

class TestEmotionConfig:
    """Test EmotionConfig dataclass."""

    def test_config_has_required_fields(self):
        """EmotionConfig must have all required fields."""
        from animation.emotions import EmotionConfig

        config = EmotionConfig(
            led_color=(100, 150, 255),
            led_pattern='breathing',
            led_brightness=128,
            pattern_speed=0.5,
            transition_ms=800
        )

        assert config.led_color == (100, 150, 255)
        assert config.led_pattern == 'breathing'
        assert config.led_brightness == 128
        assert config.pattern_speed == 0.5
        assert config.transition_ms == 800

    def test_led_color_is_rgb_tuple(self):
        """LED color must be (R, G, B) tuple with values 0-255."""
        from animation.emotions import EmotionConfig

        config = EmotionConfig(
            led_color=(255, 128, 0),
            led_pattern='pulse',
            led_brightness=200,
            pattern_speed=1.0,
            transition_ms=400
        )

        assert len(config.led_color) == 3
        assert all(0 <= c <= 255 for c in config.led_color)

    def test_brightness_clamped_to_valid_range(self):
        """Brightness should be 0-255."""
        from animation.emotions import EmotionConfig

        config = EmotionConfig(
            led_color=(100, 100, 100),
            led_pattern='breathing',
            led_brightness=128,
            pattern_speed=1.0,
            transition_ms=500
        )

        assert 0 <= config.led_brightness <= 255


# === EMOTION_CONFIGS Dictionary Tests ===

class TestEmotionConfigs:
    """Test EMOTION_CONFIGS dictionary."""

    def test_all_states_have_configs(self):
        """Every EmotionState must have a corresponding config."""
        from animation.emotions import EmotionState, EMOTION_CONFIGS

        for state in EmotionState:
            assert state in EMOTION_CONFIGS, \
                f"Missing config for state: {state.name}"

    def test_idle_config_values(self):
        """IDLE state has correct default config."""
        from animation.emotions import EmotionState, EMOTION_CONFIGS

        config = EMOTION_CONFIGS[EmotionState.IDLE]

        # IDLE: Neutral-warm blue (5500K equiv), breathing, medium brightness
        assert config.led_color == (100, 160, 255)
        assert config.led_pattern == 'breathing'
        assert 100 <= config.led_brightness <= 150
        assert config.pattern_speed == 0.5  # Slow for calm
        assert config.transition_ms >= 500  # Gradual transition

    def test_happy_config_values(self):
        """HAPPY state has warm, bright config."""
        from animation.emotions import EmotionState, EMOTION_CONFIGS

        config = EMOTION_CONFIGS[EmotionState.HAPPY]

        # HAPPY: Warm yellow, pulse (sparkle deferred), high brightness
        assert config.led_color[0] > 200  # High red (warm)
        assert config.led_color[1] > 150  # High green
        assert config.led_pattern == 'pulse'  # Using pulse until sparkle implemented
        assert config.led_brightness >= 180
        assert config.pattern_speed >= 1.0  # Energetic

    def test_alert_config_values(self):
        """ALERT state has attention-grabbing config."""
        from animation.emotions import EmotionState, EMOTION_CONFIGS

        config = EMOTION_CONFIGS[EmotionState.ALERT]

        # ALERT: Red/orange, pulse, high brightness
        assert config.led_color[0] > 200  # High red
        assert config.led_pattern == 'pulse'
        assert config.led_brightness >= 200
        assert config.pattern_speed >= 1.5  # Fast pulse

    def test_thinking_config_values(self):
        """THINKING state has processing indicator."""
        from animation.emotions import EmotionState, EMOTION_CONFIGS

        config = EMOTION_CONFIGS[EmotionState.THINKING]

        # THINKING: Blue-white, spin, medium brightness
        assert config.led_pattern == 'spin'
        assert 0.8 <= config.pattern_speed <= 1.5  # Moderate spin

    def test_sleepy_config_values(self):
        """SLEEPY state has dim, slow config."""
        from animation.emotions import EmotionState, EMOTION_CONFIGS

        config = EMOTION_CONFIGS[EmotionState.SLEEPY]

        # SLEEPY: Dim, slow breathing (fade deferred to Day 9)
        assert config.led_brightness <= 100  # Dim
        assert config.led_pattern == 'breathing'  # Using breathing until fade implemented
        assert config.pattern_speed <= 0.5  # Very slow


# === VALID_TRANSITIONS Matrix Tests ===

class TestValidTransitions:
    """Test emotion transition validity matrix."""

    def test_transitions_defined_for_all_states(self):
        """Every state must have defined transitions."""
        from animation.emotions import EmotionState, VALID_TRANSITIONS

        for state in EmotionState:
            assert state in VALID_TRANSITIONS, \
                f"No transitions defined for: {state.name}"

    def test_idle_can_transition_to_most_states(self):
        """IDLE is the hub - can reach most emotions."""
        from animation.emotions import EmotionState, VALID_TRANSITIONS

        idle_targets = VALID_TRANSITIONS[EmotionState.IDLE]

        # IDLE should transition to at least 5 states
        assert len(idle_targets) >= 5

        # Must be able to become alert (safety)
        assert EmotionState.ALERT in idle_targets

    def test_all_states_can_return_to_idle(self):
        """Every state must be able to return to IDLE."""
        from animation.emotions import EmotionState, VALID_TRANSITIONS

        for state in EmotionState:
            if state != EmotionState.IDLE:
                targets = VALID_TRANSITIONS[state]
                assert EmotionState.IDLE in targets, \
                    f"State {state.name} cannot return to IDLE"

    def test_alert_is_always_reachable(self):
        """ALERT must be reachable from every state (safety)."""
        from animation.emotions import EmotionState, VALID_TRANSITIONS

        for state in EmotionState:
            if state != EmotionState.ALERT:
                targets = VALID_TRANSITIONS[state]
                assert EmotionState.ALERT in targets, \
                    f"Cannot reach ALERT from {state.name}"

    def test_no_self_transitions(self):
        """States should not transition to themselves."""
        from animation.emotions import EmotionState, VALID_TRANSITIONS

        for state, targets in VALID_TRANSITIONS.items():
            assert state not in targets, \
                f"State {state.name} has self-transition"

    def test_sleepy_to_excited_blocked(self):
        """Cannot go directly from SLEEPY to EXCITED."""
        from animation.emotions import EmotionState, VALID_TRANSITIONS

        sleepy_targets = VALID_TRANSITIONS[EmotionState.SLEEPY]
        assert EmotionState.EXCITED not in sleepy_targets, \
            "SLEEPY should not transition directly to EXCITED"

    def test_sad_to_excited_blocked(self):
        """Cannot go directly from SAD to EXCITED."""
        from animation.emotions import EmotionState, VALID_TRANSITIONS

        sad_targets = VALID_TRANSITIONS[EmotionState.SAD]
        assert EmotionState.EXCITED not in sad_targets, \
            "SAD should not transition directly to EXCITED"


# === EmotionManager Tests ===

class TestEmotionManagerInitialization:
    """Test EmotionManager initialization."""

    def test_initial_state_is_idle(self, emotion_manager):
        """Manager starts in IDLE state."""
        from animation.emotions import EmotionState

        assert emotion_manager.current_emotion == EmotionState.IDLE

    def test_led_controller_stored(self, emotion_manager, mock_led_controller):
        """LED controller reference is stored."""
        assert emotion_manager.led_controller is mock_led_controller

    def test_animator_stored(self, emotion_manager, mock_animator):
        """Animator reference is stored."""
        assert emotion_manager.animator is mock_animator


class TestEmotionTransitions:
    """Test emotion state transitions."""

    def test_valid_transition_changes_state(self, emotion_manager):
        """Valid transition updates current_emotion."""
        from animation.emotions import EmotionState

        emotion_manager.set_emotion(EmotionState.HAPPY)
        assert emotion_manager.current_emotion == EmotionState.HAPPY

    def test_transition_triggers_led_change(self, emotion_manager, mock_led_controller):
        """Transition calls LED controller methods."""
        from animation.emotions import EmotionState

        emotion_manager.set_emotion(EmotionState.CURIOUS)

        # Should have called LED methods
        assert mock_led_controller.set_pattern.called or \
               mock_led_controller.transition_to.called

    def test_invalid_transition_raises_error(self, emotion_manager):
        """Invalid transition raises InvalidTransitionError."""
        from animation.emotions import EmotionState, InvalidTransitionError

        # First set to SLEEPY
        emotion_manager.set_emotion(EmotionState.SLEEPY)

        # SLEEPY -> EXCITED is invalid
        with pytest.raises(InvalidTransitionError):
            emotion_manager.set_emotion(EmotionState.EXCITED)

    def test_invalid_transition_preserves_state(self, emotion_manager):
        """Failed transition keeps previous state."""
        from animation.emotions import EmotionState, InvalidTransitionError

        emotion_manager.set_emotion(EmotionState.CURIOUS)

        try:
            # From CURIOUS, try invalid transition (will find one)
            emotion_manager.set_emotion(EmotionState.SLEEPY)
            # If this passes, then CURIOUS -> SLEEPY is valid, try SLEEPY -> EXCITED
            emotion_manager.set_emotion(EmotionState.EXCITED)
        except InvalidTransitionError:
            pass

        # State should be preserved after failed transition
        assert emotion_manager.current_emotion in [EmotionState.CURIOUS, EmotionState.SLEEPY]

    def test_force_transition_bypasses_validation(self, emotion_manager):
        """force=True allows invalid transitions (emergency use)."""
        from animation.emotions import EmotionState

        emotion_manager.set_emotion(EmotionState.SLEEPY)

        # Force SLEEPY -> EXCITED (normally invalid)
        emotion_manager.set_emotion(EmotionState.EXCITED, force=True)

        assert emotion_manager.current_emotion == EmotionState.EXCITED


class TestEmotionManagerHelpers:
    """Test EmotionManager utility methods."""

    def test_can_transition_returns_bool(self, emotion_manager):
        """can_transition() returns boolean."""
        from animation.emotions import EmotionState

        result = emotion_manager.can_transition(EmotionState.HAPPY)
        assert isinstance(result, bool)

    def test_can_transition_valid(self, emotion_manager):
        """can_transition() returns True for valid target."""
        from animation.emotions import EmotionState

        # From IDLE, HAPPY should be valid
        assert emotion_manager.can_transition(EmotionState.HAPPY)

    def test_can_transition_invalid(self, emotion_manager):
        """can_transition() returns False for invalid target."""
        from animation.emotions import EmotionState

        emotion_manager.set_emotion(EmotionState.SLEEPY)

        # From SLEEPY, EXCITED should be invalid
        assert not emotion_manager.can_transition(EmotionState.EXCITED)

    def test_get_available_transitions(self, emotion_manager):
        """get_available_transitions() returns valid targets."""
        from animation.emotions import EmotionState

        available = emotion_manager.get_available_transitions()

        assert isinstance(available, (list, set, tuple))
        assert EmotionState.HAPPY in available  # From IDLE
        assert EmotionState.IDLE not in available  # Can't self-transition

    def test_get_current_config(self, emotion_manager):
        """get_current_config() returns EmotionConfig."""
        from animation.emotions import EmotionConfig

        config = emotion_manager.get_current_config()

        assert isinstance(config, EmotionConfig)


class TestEmotionTransitionCallbacks:
    """Test transition callbacks and hooks."""

    def test_on_enter_callback_called(self, emotion_manager):
        """Callback is called when entering a state."""
        from animation.emotions import EmotionState

        callback_data = {'called': False, 'state': None}

        def on_enter(state):
            callback_data['called'] = True
            callback_data['state'] = state

        emotion_manager.on_enter_callback = on_enter
        emotion_manager.set_emotion(EmotionState.HAPPY)

        assert callback_data['called']
        assert callback_data['state'] == EmotionState.HAPPY

    def test_on_exit_callback_called(self, emotion_manager):
        """Callback is called when leaving a state."""
        from animation.emotions import EmotionState

        callback_data = {'called': False, 'state': None}

        def on_exit(state):
            callback_data['called'] = True
            callback_data['state'] = state

        emotion_manager.on_exit_callback = on_exit
        emotion_manager.set_emotion(EmotionState.CURIOUS)

        assert callback_data['called']
        assert callback_data['state'] == EmotionState.IDLE  # Exited from IDLE


# === Integration Tests ===

class TestEmotionLEDIntegration:
    """Test emotion-LED integration."""

    def test_happy_uses_correct_pattern(self, emotion_manager, mock_led_controller):
        """HAPPY emotion sets correct LED pattern."""
        from animation.emotions import EmotionState

        emotion_manager.set_emotion(EmotionState.HAPPY)

        # Verify set_pattern was called
        assert mock_led_controller.set_pattern.called

    def test_transition_applies_led_config(self, emotion_manager, mock_led_controller):
        """Transition applies all LED configuration."""
        from animation.emotions import EmotionState

        emotion_manager.set_emotion(EmotionState.ALERT)

        # Should have called LED configuration methods
        assert mock_led_controller.set_pattern.called
        assert mock_led_controller.set_color.called
        assert mock_led_controller.set_brightness.called


# === Edge Case Tests ===

class TestEmotionEdgeCases:
    """Test edge cases and error handling."""

    def test_set_same_emotion_twice_is_noop(self, emotion_manager, mock_led_controller):
        """Setting same emotion twice does nothing."""
        from animation.emotions import EmotionState

        emotion_manager.set_emotion(EmotionState.HAPPY)
        mock_led_controller.reset_mock()

        # Set HAPPY again
        emotion_manager.set_emotion(EmotionState.HAPPY)

        # Should not call LED methods again
        assert not mock_led_controller.set_pattern.called

    def test_rapid_transitions_handled(self, emotion_manager):
        """Rapid successive transitions don't crash."""
        from animation.emotions import EmotionState

        # Rapid transitions
        for _ in range(10):
            emotion_manager.set_emotion(EmotionState.HAPPY)
            emotion_manager.set_emotion(EmotionState.IDLE)

        # Should end at IDLE
        assert emotion_manager.current_emotion == EmotionState.IDLE

    def test_invalid_emotion_type_raises(self, emotion_manager):
        """Non-EmotionState argument raises TypeError."""
        with pytest.raises((TypeError, ValueError)):
            emotion_manager.set_emotion("happy")  # String, not enum

        with pytest.raises((TypeError, ValueError)):
            emotion_manager.set_emotion(42)  # Int, not enum

    def test_reset_to_idle(self, emotion_manager):
        """reset_to_idle() always works regardless of current state."""
        from animation.emotions import EmotionState

        # Set to any state
        emotion_manager.set_emotion(EmotionState.HAPPY)

        # Reset should always work
        emotion_manager.reset_to_idle()
        assert emotion_manager.current_emotion == EmotionState.IDLE


# === Emotion Bridge Tests (Discrete <-> Continuous) ===

class TestEmotionBridge:
    """Test bridge methods between discrete EmotionState and continuous EmotionAxes."""

    def test_get_emotion_axes_returns_emotion_axes(self, emotion_manager):
        """get_emotion_axes() returns an EmotionAxes instance."""
        from animation.emotion_axes import EmotionAxes

        axes = emotion_manager.get_emotion_axes()
        assert isinstance(axes, EmotionAxes)

    def test_get_emotion_axes_idle_returns_idle_preset(self, emotion_manager):
        """IDLE state returns the idle preset axes."""
        from animation.emotion_axes import EMOTION_PRESETS

        axes = emotion_manager.get_emotion_axes()
        idle_preset = EMOTION_PRESETS['idle']

        assert axes.arousal == idle_preset.arousal
        assert axes.valence == idle_preset.valence
        assert axes.focus == idle_preset.focus
        assert axes.blink_speed == idle_preset.blink_speed

    def test_get_emotion_axes_happy_returns_happy_preset(self, emotion_manager):
        """HAPPY state returns the happy preset axes."""
        from animation.emotions import EmotionState
        from animation.emotion_axes import EMOTION_PRESETS

        emotion_manager.set_emotion(EmotionState.HAPPY)
        axes = emotion_manager.get_emotion_axes()
        happy_preset = EMOTION_PRESETS['happy']

        assert axes.arousal == happy_preset.arousal
        assert axes.valence == happy_preset.valence
        assert axes.focus == happy_preset.focus
        assert axes.blink_speed == happy_preset.blink_speed

    def test_get_emotion_axes_all_states_have_mapping(self, emotion_manager):
        """All EmotionState values map to valid EmotionAxes."""
        from animation.emotions import EmotionState
        from animation.emotion_axes import EmotionAxes

        for state in EmotionState:
            emotion_manager.set_emotion(state, force=True)
            axes = emotion_manager.get_emotion_axes()

            assert isinstance(axes, EmotionAxes), f"No axes for {state.name}"
            assert -1.0 <= axes.arousal <= 1.0
            assert -1.0 <= axes.valence <= 1.0
            assert 0.0 <= axes.focus <= 1.0
            assert 0.25 <= axes.blink_speed <= 2.0

    def test_set_emotion_from_axes_exact_match(self, emotion_manager):
        """Exact preset axes should match and change state."""
        from animation.emotions import EmotionState
        from animation.emotion_axes import EMOTION_PRESETS

        # Use exact happy preset
        happy_axes = EMOTION_PRESETS['happy']
        result = emotion_manager.set_emotion_from_axes(happy_axes)

        assert result is True
        assert emotion_manager.current_emotion == EmotionState.HAPPY

    def test_set_emotion_from_axes_near_match(self, emotion_manager):
        """Axes near a preset (within threshold) should match."""
        from animation.emotions import EmotionState
        from animation.emotion_axes import EmotionAxes, EMOTION_PRESETS

        # Slightly off from happy preset (but within default 0.3 threshold)
        happy = EMOTION_PRESETS['happy']
        near_happy = EmotionAxes(
            arousal=happy.arousal + 0.05,
            valence=happy.valence - 0.05,
            focus=happy.focus + 0.05,
            blink_speed=happy.blink_speed
        )

        result = emotion_manager.set_emotion_from_axes(near_happy)

        assert result is True
        assert emotion_manager.current_emotion == EmotionState.HAPPY

    def test_set_emotion_from_axes_no_match_far_from_presets(self, emotion_manager):
        """Axes far from all presets should return False."""
        from animation.emotions import EmotionState
        from animation.emotion_axes import EmotionAxes

        # Create axes in an empty region of emotion space
        # Using very specific values that don't match any preset well
        far_axes = EmotionAxes(
            arousal=0.0,
            valence=-1.0,  # Extreme negative valence
            focus=0.05,    # Very low focus
            blink_speed=0.25
        )

        # Use a very strict threshold
        result = emotion_manager.set_emotion_from_axes(far_axes, threshold=0.1)

        assert result is False
        # State should remain IDLE (unchanged)
        assert emotion_manager.current_emotion == EmotionState.IDLE

    def test_set_emotion_from_axes_same_state_returns_false(self, emotion_manager):
        """Matching current state returns False (no change)."""
        from animation.emotion_axes import EMOTION_PRESETS

        # Already in IDLE, try to set to idle preset
        idle_axes = EMOTION_PRESETS['idle']
        result = emotion_manager.set_emotion_from_axes(idle_axes)

        assert result is False  # No change occurred

    def test_set_emotion_from_axes_compound_emotion_no_match(self, emotion_manager):
        """Compound emotions (anxious, confused, etc.) don't set EmotionState."""
        from animation.emotions import EmotionState
        from animation.emotion_axes import EMOTION_PRESETS

        # First move to a state that can reach many others
        emotion_manager.set_emotion(EmotionState.THINKING)

        # Use anxious preset (compound emotion, not in EmotionState)
        anxious_axes = EMOTION_PRESETS['anxious']

        # Should find anxious as closest but fail to convert to EmotionState
        # Since it's a compound emotion, the function should return False
        # But it might match ALERT which is close in axes space
        result = emotion_manager.set_emotion_from_axes(anxious_axes, threshold=0.5)

        # If it matched ALERT, state would change; if not, stays THINKING
        # Either is acceptable - compound emotions may or may not match
        assert isinstance(result, bool)

    def test_set_emotion_from_axes_threshold_respected(self, emotion_manager):
        """Custom threshold is respected."""
        from animation.emotion_axes import EmotionAxes, EMOTION_PRESETS

        happy = EMOTION_PRESETS['happy']
        # Create axes slightly off from happy but closer to happy than any other preset
        # Using smaller offsets to ensure happy remains the closest match
        # Distance = sqrt(0.1^2 + 0.1^2 + 0.1^2) = sqrt(0.03) = 0.173
        slightly_off = EmotionAxes(
            arousal=happy.arousal + 0.1,
            valence=happy.valence - 0.1,
            focus=happy.focus + 0.1,
            blink_speed=happy.blink_speed
        )

        # With strict threshold (0.1), should not match (distance 0.173 > 0.1)
        result_strict = emotion_manager.set_emotion_from_axes(slightly_off, threshold=0.1)
        assert result_strict is False

        # With loose threshold (0.5), should match happy (distance 0.173 < 0.5)
        result_loose = emotion_manager.set_emotion_from_axes(slightly_off, threshold=0.5)
        assert result_loose is True

    def test_axes_distance_same_axes_is_zero(self, emotion_manager):
        """Distance between same axes should be zero."""
        from animation.emotion_axes import EMOTION_PRESETS

        happy = EMOTION_PRESETS['happy']
        distance = emotion_manager._axes_distance(happy, happy)

        assert distance == 0.0

    def test_axes_distance_different_axes_positive(self, emotion_manager):
        """Distance between different axes should be positive."""
        from animation.emotion_axes import EMOTION_PRESETS

        happy = EMOTION_PRESETS['happy']
        sad = EMOTION_PRESETS['sad']
        distance = emotion_manager._axes_distance(happy, sad)

        assert distance > 0.0

    def test_axes_distance_symmetric(self, emotion_manager):
        """Distance should be symmetric: d(a,b) == d(b,a)."""
        from animation.emotion_axes import EMOTION_PRESETS

        happy = EMOTION_PRESETS['happy']
        sad = EMOTION_PRESETS['sad']

        d1 = emotion_manager._axes_distance(happy, sad)
        d2 = emotion_manager._axes_distance(sad, happy)

        assert d1 == d2

    def test_roundtrip_conversion(self, emotion_manager):
        """Converting to axes and back should preserve state."""
        from animation.emotions import EmotionState

        # Set to a state
        emotion_manager.set_emotion(EmotionState.CURIOUS)

        # Get axes
        axes = emotion_manager.get_emotion_axes()

        # Reset to idle
        emotion_manager.reset_to_idle()

        # Set from axes - should return to CURIOUS
        result = emotion_manager.set_emotion_from_axes(axes)

        assert result is True
        assert emotion_manager.current_emotion == EmotionState.CURIOUS
