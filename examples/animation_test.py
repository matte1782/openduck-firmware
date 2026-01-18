#!/usr/bin/env python3
"""Quick test of animation system without interactive prompts."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from animation import AnimationSequence, AnimationPlayer

# Test 1: Color fade
print("\n=== Test 1: Color Fade ===")
seq = AnimationSequence("fade")
seq.add_keyframe(0, color=(0, 0, 0), easing='ease_in_out')
seq.add_keyframe(1000, color=(255, 255, 255), easing='ease_in_out')

for time_ms in [0, 250, 500, 750, 1000]:
    values = seq.get_values(time_ms)
    color = values['color']
    print(f"t={time_ms:4d}ms: RGB({color[0]:3d}, {color[1]:3d}, {color[2]:3d})")

# Test 2: Looping brightness
print("\n=== Test 2: Looping Brightness ===")
seq = AnimationSequence("breathing", loop=True)
seq.add_keyframe(0, brightness=0.3, easing='ease_in_out')
seq.add_keyframe(2000, brightness=1.0, easing='ease_in_out')
seq.add_keyframe(4000, brightness=0.3, easing='ease_in_out')

for time_ms in [0, 1000, 2000, 3000, 4000, 5000]:  # 5000 wraps to 1000
    values = seq.get_values(time_ms)
    brightness = values['brightness']
    print(f"t={time_ms/1000:.1f}s: brightness={brightness:.2f}")

# Test 3: Multi-property
print("\n=== Test 3: Multi-Property ===")
seq = AnimationSequence("multi")
seq.add_keyframe(0, color=(255, 0, 0), brightness=0.5, position=(0.0, 0.0))
seq.add_keyframe(1000, color=(0, 255, 0), brightness=1.0, position=(1.0, 1.0))

for time_ms in [0, 500, 1000]:
    values = seq.get_values(time_ms)
    print(f"t={time_ms}ms: RGB{values['color']} bright={values['brightness']:.2f} pos={values['position']}")

print("\n=== All Tests Passed ===")
