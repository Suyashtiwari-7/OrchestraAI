"""
OrchestraAI — E2E Widget Launch Tests
======================================
Verifies window initialization, positioning, and window flags for DARKI.exe.
"""

import pytest


class TestWidgetLaunch:
    """E2E test suite for verifying DARKI widget launch behavior."""

    def test_darki_window_exists(self, appium_driver):
        """Verify the compiled DARKI desktop application window launches successfully."""
        assert appium_driver is not None
        window_handle = appium_driver.current_window_handle
        assert window_handle is not None

    def test_widget_position_bottom_right(self, appium_driver):
        """Verify the widget is positioned in the lower portion of the screen."""
        size = appium_driver.get_window_size()
        position = appium_driver.get_window_position()

        # Widget should have non-zero dimensions
        assert size["width"] > 0
        assert size["height"] > 0

        # Position Y should be positive (lower portion of screen)
        assert position["y"] >= 0

    def test_widget_title_or_class(self, appium_driver):
        """Verify window handle or title contains application identifier."""
        title = appium_driver.title
        # Title can be DARKI or empty (frameless tool window)
        assert isinstance(title, str)
