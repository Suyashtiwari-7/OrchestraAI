"""
OrchestraAI — E2E Test Fixtures (Appium + WinAppDriver)
======================================================
Provides PyTest fixtures for automating the compiled DARKI.exe desktop application.
"""

import os
import time
import pytest
from pathlib import Path

# Path to compiled executable
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DARKI_EXE = PROJECT_ROOT / "dist" / "DARKI" / "DARKI.exe"


@pytest.fixture(scope="session")
def darki_exe_path():
    """Ensure DARKI.exe is built before running E2E tests."""
    if not DARKI_EXE.exists():
        pytest.skip(
            f"DARKI.exe not found at {DARKI_EXE}. "
            "Run 'python build_desktop.py' first to compile the app for E2E testing."
        )
    return str(DARKI_EXE)


@pytest.fixture(scope="function")
def appium_driver(darki_exe_path):
    """
    Appium WebDriver fixture for DARKI desktop UI testing.
    Connects to local WinAppDriver instance (http://127.0.0.1:4723).
    """
    try:
        from appium import webdriver
        from appium.options.windows import WindowsOptions
    except ImportError:
        pytest.skip("Appium-Python-Client not installed. Run 'pip install Appium-Python-Client'.")

    options = WindowsOptions()
    options.app = darki_exe_path
    options.platform_name = "Windows"
    options.device_name = "WindowsPC"

    driver = None
    try:
        # WinAppDriver default port
        driver = webdriver.Remote(
            command_executor="http://127.0.0.1:4723",
            options=options
        )
        time.sleep(3)  # Wait for startup animations and server initialization
        yield driver
    except Exception as e:
        pytest.skip(
            f"Could not connect to WinAppDriver at http://127.0.0.1:4723: {e}. "
            "Ensure WinAppDriver.exe is running on the target Windows system."
        )
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass
