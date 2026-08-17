"""
OrchestraAI — Smart App Installer
====================================
Provides tools to search, install, check, and uninstall applications
using the system package manager (winget on Windows, brew on macOS).

All installs go through official package manager repositories, ensuring
verified sources and automatic SHA-256 hash verification.
"""

import logging
import platform
import subprocess
from typing import Dict, Any, List, Optional

logger = logging.getLogger("orchestra.tools.app_installer")

# Determine the system package manager
_SYSTEM = platform.system()


def _run_cmd(args: List[str], timeout: int = 120) -> Dict[str, Any]:
    """Run a shell command and return structured result."""
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            # Suppress interactive prompts on Windows
            creationflags=subprocess.CREATE_NO_WINDOW if _SYSTEM == "Windows" else 0,
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "return_code": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"Command timed out after {timeout}s"}
    except FileNotFoundError:
        return {"success": False, "error": "Package manager not found. Ensure winget/brew is installed."}
    except Exception as e:
        return {"success": False, "error": str(e)}


def check_installed(name: str) -> Dict[str, Any]:
    """
    Check if an application is already installed on the system.

    Args:
        name: Application name to search for (e.g., "VLC", "VS Code").

    Returns:
        Dict with 'installed' bool and matched package info.
    """
    if _SYSTEM == "Windows":
        result = _run_cmd(["winget", "list", name, "--accept-source-agreements"], timeout=30)
    elif _SYSTEM == "Darwin":
        result = _run_cmd(["brew", "list", "--formula", name], timeout=15)
    else:
        return {"installed": False, "error": f"Unsupported OS: {_SYSTEM}"}

    if result.get("success") and result.get("stdout"):
        return {
            "installed": True,
            "details": result["stdout"][:500],
        }
    return {"installed": False, "details": result.get("stderr", "")}


def search_app(name: str) -> Dict[str, Any]:
    """
    Search the package manager for available applications matching the name.

    Args:
        name: Search query (e.g., "vlc media player").

    Returns:
        Dict with 'results' list of matching packages.
    """
    if _SYSTEM == "Windows":
        result = _run_cmd(["winget", "search", name, "--accept-source-agreements"], timeout=30)
    elif _SYSTEM == "Darwin":
        result = _run_cmd(["brew", "search", name], timeout=15)
    else:
        return {"success": False, "error": f"Unsupported OS: {_SYSTEM}"}

    if result.get("success"):
        return {
            "success": True,
            "results": result["stdout"][:2000],
        }
    return {
        "success": False,
        "error": result.get("stderr", result.get("error", "Search failed")),
    }


def install_app(package_id: str) -> Dict[str, Any]:
    """
    Install an application silently using the package manager.

    On Windows (winget): Downloads from official Microsoft Store or winget manifests.
    Automatically verifies SHA-256 hashes before installation.

    Args:
        package_id: The exact package identifier (e.g., "VideoLAN.VLC", "Google.Chrome").

    Returns:
        Dict with installation success/failure details.
    """
    logger.info(f"[*] Installing package: {package_id}")

    # Check if already installed first
    check = check_installed(package_id)
    if check.get("installed"):
        return {
            "success": True,
            "action": "already_installed",
            "details": f"{package_id} is already installed.",
        }

    if _SYSTEM == "Windows":
        result = _run_cmd([
            "winget", "install",
            "--id", package_id,
            "-e",                            # Exact match
            "--accept-source-agreements",     # Auto-accept source terms
            "--accept-package-agreements",    # Auto-accept package license
            "--silent",                       # Silent install (no UI)
        ], timeout=300)
    elif _SYSTEM == "Darwin":
        result = _run_cmd(["brew", "install", package_id], timeout=300)
    else:
        return {"success": False, "error": f"Unsupported OS: {_SYSTEM}"}

    if result.get("success"):
        logger.info(f"[+] Successfully installed: {package_id}")
        return {
            "success": True,
            "action": "installed",
            "details": result.get("stdout", "")[:500],
        }

    logger.error(f"[!] Failed to install {package_id}: {result.get('stderr', result.get('error'))}")
    return {
        "success": False,
        "action": "install_failed",
        "error": result.get("stderr", result.get("error", "Unknown error")),
    }


def uninstall_app(package_id: str) -> Dict[str, Any]:
    """
    Uninstall an application using the package manager.

    Args:
        package_id: The exact package identifier.

    Returns:
        Dict with uninstall success/failure details.
    """
    logger.info(f"[*] Uninstalling package: {package_id}")

    if _SYSTEM == "Windows":
        result = _run_cmd([
            "winget", "uninstall",
            "--id", package_id,
            "-e",
            "--silent",
        ], timeout=120)
    elif _SYSTEM == "Darwin":
        result = _run_cmd(["brew", "uninstall", package_id], timeout=60)
    else:
        return {"success": False, "error": f"Unsupported OS: {_SYSTEM}"}

    if result.get("success"):
        logger.info(f"[+] Successfully uninstalled: {package_id}")
        return {
            "success": True,
            "action": "uninstalled",
            "details": result.get("stdout", "")[:500],
        }

    return {
        "success": False,
        "action": "uninstall_failed",
        "error": result.get("stderr", result.get("error", "Unknown error")),
    }
