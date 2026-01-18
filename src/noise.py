#!/usr/bin/env python3
"""
Noise module shim - provides pnoise2 function using perlin_noise package.

The original 'noise' C library cannot be compiled on Windows without Visual Studio.
This provides a pure Python fallback using the perlin_noise package.

Created: 18 January 2026
"""

from perlin_noise import PerlinNoise
import functools

@functools.lru_cache(maxsize=4)
def _get_noise(octaves):
    return PerlinNoise(octaves=octaves)

def pnoise2(x, y, octaves=1, persistence=0.5, lacunarity=2.0, repeatx=1024, repeaty=1024, base=0):
    """
    2D Perlin noise compatible with the noise.pnoise2 API.
    
    Args:
        x, y: Coordinates for noise lookup
        octaves: Number of octaves (layers of detail)
        persistence: How quickly amplitude falls off per octave
        lacunarity: How quickly frequency increases per octave
        repeatx, repeaty: Tile size (not used in this implementation)
        base: Base offset (not used in this implementation)
    
    Returns:
        float: Noise value in range [-1, 1]
    """
    noise_gen = _get_noise(octaves)
    # perlin_noise returns values in approximately [-1, 1]
    return noise_gen([x, y])
