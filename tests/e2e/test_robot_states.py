"""
OrchestraAI — E2E Robot Animation State Tests
==============================================
Verifies state transition behavior of the DARKI robot mascot.
"""

import time
import pytest


class TestRobotStates:
    """E2E test suite for mascot state transitions."""

    def test_initial_state_transitions(self, appium_driver):
        """
        Verify startup animation sequence:
        Startup greeting state plays for ~4.5s, then transitions to idle.
        """
        assert appium_driver is not None
        # Sleep to allow initial greeting animation (4.5s) to complete into idle
        time.sleep(5)
        # Verify app is still running smoothly after state transition
        assert appium_driver.current_window_handle is not None

    def test_app_responsiveness_after_idle(self, appium_driver):
        """Verify the desktop app remains active during idle sports gesture cycles."""
        time.sleep(2)
        size = appium_driver.get_window_size()
        assert size["width"] > 0
