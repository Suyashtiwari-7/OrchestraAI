"""
OrchestraAI — Desktop Launcher Tests
====================================
Tests for the native desktop pywebview wrapper launcher.
Uses mocking to prevent actual window spawning or server execution.
"""

import pytest
import threading
from unittest.mock import patch, MagicMock
from orchestra.desktop import main, run_server

class TestDesktopLauncher:
    """Test launcher initialization, thread spawns, and window setup."""

    @patch("orchestra.desktop.uvicorn.run")
    def test_run_server_starts_uvicorn(self, mock_uvicorn_run):
        """Test that the run_server function launches uvicorn with correct parameters."""
        run_server()
        mock_uvicorn_run.assert_called_once_with(
            "orchestra.server:app", host="127.0.0.1", port=8000, log_level="warning"
        )

    @patch("orchestra.desktop.webview.start")
    @patch("orchestra.desktop.webview.create_window")
    @patch("orchestra.desktop.threading.Thread")
    @patch("orchestra.desktop.time.sleep")
    def test_main_initialization(self, mock_sleep, mock_thread_class, mock_create_window, mock_webview_start):
        """Test the orchestration flow of desktop thread launch and webview container execution."""
        mock_thread_instance = MagicMock()
        mock_thread_class.return_value = mock_thread_instance
        
        main()
        
        # Verify thread configuration and startup
        mock_thread_class.assert_called_once()
        mock_thread_instance.start.assert_called_once()
        
        # Verify webview container creation for the main app
        assert mock_create_window.call_count == 1
        
        main_call_args = mock_create_window.call_args_list[0][1]
        
        assert main_call_args["title"] == "OrchestraAI"
        assert main_call_args["width"] == 1100
        assert main_call_args["height"] == 850
        
        # Verify loop start
        mock_webview_start.assert_called_once()
