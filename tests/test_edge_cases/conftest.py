"""
Pytest configuration for edge case tests.

Registers custom markers for edge case test categories.

Author: Agent 3 - Edge Case Engineer
Created: 18 January 2026 (Day 13)
"""

import pytest


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
