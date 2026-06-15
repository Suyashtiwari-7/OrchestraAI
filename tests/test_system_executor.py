"""
OrchestraAI — System Command Executor Tests
===========================================
Tests for the local system command executor tool.
Uses mocking to prevent actual process spawns or browser opens during testing.
"""

import pytest
from unittest.mock import patch, MagicMock
from orchestra.tools.system_executor import execute_system_command, get_browser_path


class TestSystemExecutor:
    """Test system command parsing, whitelisting, and mocking execution."""

    @patch("orchestra.tools.system_executor.subprocess.Popen")
    @patch("orchestra.tools.system_executor.get_browser_path")
    def test_open_browser_in_specific_browser(self, mock_get_path, mock_popen):
        """Test opening a URL in a specific whitelisted browser (Brave)."""
        mock_get_path.return_value = "C:\\Program Files\\BraveSoftware\\Brave-Browser\\Application\\brave.exe"
        
        response_content = (
            '{"action": "open_browser", "target": "https://web.whatsapp.com", '
            '"browser": "brave", "reasoning": "Open WhatsApp in Brave"}'
        )
        
        result = execute_system_command(response_content)
        
        assert result["success"] is True
        assert result["action"] == "open_browser"
        assert result["target_url"] == "https://web.whatsapp.com"
        assert result["browser"] == "brave"
        mock_popen.assert_called_once_with([
            "C:\\Program Files\\BraveSoftware\\Brave-Browser\\Application\\brave.exe",
            "https://web.whatsapp.com"
        ])

    @patch("orchestra.tools.system_executor.webbrowser.open")
    def test_open_browser_default(self, mock_web_open):
        """Test opening a URL in the default browser."""
        response_content = (
            '{"action": "open_browser", "target": "https://youtube.com", '
            '"browser": "default", "reasoning": "Open YouTube in default"}'
        )
        
        result = execute_system_command(response_content)
        
        assert result["success"] is True
        assert result["browser"] == "default"
        mock_web_open.assert_called_once_with("https://youtube.com")

    @patch("orchestra.tools.system_executor.check_app_installation_status")
    @patch("orchestra.tools.system_executor.subprocess.Popen")
    def test_launch_whitelisted_app(self, mock_popen, mock_check):
        """Test launching a whitelisted local app (Notepad)."""
        mock_check.return_value = {"installed": True, "path": "notepad"}
        response_content = (
            '{"action": "launch_app", "target": "notepad", '
            '"browser": null, "reasoning": "Open Notepad"}'
        )
        
        result = execute_system_command(response_content)
        
        assert result["success"] is True
        assert result["action"] == "launch_app"
        assert result["target_app"] == "notepad"
        mock_popen.assert_called_once_with(["notepad.exe"], shell=True)

    @patch("orchestra.tools.system_executor.check_app_installation_status")
    @patch("orchestra.tools.system_executor.subprocess.Popen")
    def test_launch_non_whitelisted_app(self, mock_popen, mock_check):
        """Test that non-whitelisted apps are successfully launched (whitelist is lifted)."""
        mock_check.return_value = {"installed": True, "path": "malicious_app"}
        response_content = (
            '{"action": "launch_app", "target": "malicious_app", '
            '"browser": null, "reasoning": "Attempt launch"}'
        )
        
        result = execute_system_command(response_content)
        
        assert result["success"] is True
        assert result["target_app"] == "malicious_app"
        mock_popen.assert_called_once_with(["malicious_app"], shell=True)

    def test_invalid_json_payload(self):
        """Test handling of invalid or non-JSON payloads."""
        result = execute_system_command("This is just plain text response.")
        assert result["success"] is False
        assert "No JSON payload found" in result["error"]

    @patch("orchestra.tools.system_executor.check_app_installation_status")
    @patch("orchestra.tools.system_executor.subprocess.Popen")
    @patch("orchestra.tools.system_executor.get_outlook_path")
    def test_launch_outlook(self, mock_get_path, mock_popen, mock_check):
        """Test launching Outlook app."""
        mock_check.return_value = {"installed": True, "path": "outlook"}
        mock_get_path.return_value = "C:\\Program Files\\Microsoft Office\\root\\Office16\\OUTLOOK.EXE"
        response_content = (
            '{"action": "launch_app", "target": "outlook", '
            '"browser": null, "reasoning": "Open Outlook"}'
        )
        result = execute_system_command(response_content)
        assert result["success"] is True
        assert result["target_app"] == "outlook"
        mock_popen.assert_called_once_with(["C:\\Program Files\\Microsoft Office\\root\\Office16\\OUTLOOK.EXE"])

    @patch("orchestra.tools.system_executor.check_app_installation_status")
    @patch("orchestra.tools.system_executor.subprocess.Popen")
    @patch("orchestra.tools.system_executor.get_browser_path")
    def test_launch_brave_app(self, mock_get_path, mock_popen, mock_check):
        """Test launching Brave browser as app."""
        mock_check.return_value = {"installed": True, "path": "brave"}
        mock_get_path.return_value = "C:\\Program Files\\BraveSoftware\\Brave-Browser\\Application\\brave.exe"
        response_content = (
            '{"action": "launch_app", "target": "brave", '
            '"browser": null, "reasoning": "Open Brave Browser"}'
        )
        result = execute_system_command(response_content)
        assert result["success"] is True
        assert result["target_app"] == "brave"
        mock_popen.assert_called_once_with(["C:\\Program Files\\BraveSoftware\\Brave-Browser\\Application\\brave.exe"])

    @patch("orchestra.tools.system_executor.os.startfile")
    @patch("orchestra.tools.system_executor.Path.exists")
    @patch("orchestra.tools.system_executor.Path.is_file")
    def test_launch_safe_file(self, mock_is_file, mock_exists, mock_startfile):
        """Test launching a safe document file directly."""
        mock_exists.return_value = True
        mock_is_file.return_value = True
        response_content = (
            '{"action": "launch_app", "target": "TXT.txt", '
            '"browser": null, "reasoning": "Open TXT file"}'
        )
        result = execute_system_command(response_content)
        assert result["success"] is True
        assert "open_file:TXT.txt" in result["target_app"]
        mock_startfile.assert_called_once()
