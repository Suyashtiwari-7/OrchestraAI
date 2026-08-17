"""
OrchestraAI — System Control Tests
==================================
Tests for Windows system control methods (volume, brightness, screen lock, screenshot).
Uses mocking to prevent actual changes to system volume, screen brightness, or locking.
"""

import pytest
from unittest.mock import patch, MagicMock
from orchestra.tools.system_control import (
    set_volume,
    get_volume,
    set_brightness,
    get_brightness,
    lock_screen,
    take_screenshot,
    get_system_info,
)


class TestSystemControl:
    """Test suite for system settings adjustments and hardware query."""

    @patch("pycaw.pycaw.AudioUtilities.GetSpeakers")
    @patch("ctypes.cast")
    def test_set_volume(self, mock_cast, mock_get_speakers):
        """Test setting master volume."""
        mock_volume = MagicMock()
        mock_cast.return_value = mock_volume
        
        res = set_volume(75)
        
        assert res["success"] is True
        assert res["level"] == 75
        mock_volume.SetMasterVolumeLevelScalar.assert_called_once_with(0.75, None)

    @patch("pycaw.pycaw.AudioUtilities.GetSpeakers")
    @patch("ctypes.cast")
    def test_get_volume(self, mock_cast, mock_get_speakers):
        """Test getting master volume."""
        mock_volume = MagicMock()
        mock_volume.GetMasterVolumeLevelScalar.return_value = 0.50
        mock_cast.return_value = mock_volume
        
        res = get_volume()
        
        assert res["success"] is True
        assert res["level"] == 50

    @patch("screen_brightness_control.set_brightness")
    def test_set_brightness(self, mock_set_brightness):
        """Test setting brightness."""
        res = set_brightness(60)
        assert res["success"] is True
        assert res["level"] == 60
        mock_set_brightness.assert_called_once_with(60)

    @patch("screen_brightness_control.get_brightness")
    def test_get_brightness(self, mock_get_brightness):
        """Test getting brightness."""
        mock_get_brightness.return_value = [45]
        res = get_brightness()
        assert res["success"] is True
        assert res["level"] == 45

    @patch("orchestra.tools.system_control.ctypes.windll.user32.LockWorkStation")
    def test_lock_screen(self, mock_lock):
        """Test locking the screen."""
        res = lock_screen()
        assert res["success"] is True
        mock_lock.assert_called_once()

    @patch("PIL.ImageGrab.grab")
    def test_take_screenshot(self, mock_grab, tmp_path):
        """Test taking a screenshot."""
        mock_img = MagicMock()
        mock_grab.return_value = mock_img
        
        res = take_screenshot(save_dir=str(tmp_path))
        
        assert res["success"] is True
        mock_grab.assert_called_once()
        mock_img.save.assert_called_once()

    @patch("orchestra.tools.system_control.subprocess.run")
    def test_get_system_info(self, mock_run):
        """Test gathering system statistics."""
        mock_process = MagicMock()
        mock_process.stdout = " 82\n"
        mock_run.return_value = mock_process
        
        res = get_system_info()
        
        assert res["success"] is True
        assert res["info"]["battery_percent"] == 82
