"""
OrchestraAI — Phone Caller (Windows Phone Link + Bluetooth)
=============================================================
Enables DARKI to place real phone calls via the user's paired
Android/iPhone using Windows Phone Link Bluetooth integration.

DARKI's AI voice (Kokoro-82M) speaks directly to the human on
the other end of the call while Faster-Whisper listens to their responses.

Prerequisites:
    - Windows 10/11 with Phone Link app installed and paired
    - Android/iPhone paired via Bluetooth
    - Microphone and speaker configured for Bluetooth audio routing
"""

import os
import logging
import subprocess
import time
from typing import Dict, Any, Optional

logger = logging.getLogger("orchestra.tools.phone_caller")


def check_phone_link_available() -> Dict[str, Any]:
    """
    Check if Windows Phone Link is installed and a phone is paired.

    Returns:
        Dict with 'available' bool and details.
    """
    try:
        # Check if Phone Link process is running
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq PhoneExperienceHost.exe"],
            capture_output=True, text=True, timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

        phone_link_running = "PhoneExperienceHost.exe" in result.stdout

        # Check if Bluetooth is available
        bt_result = subprocess.run(
            ["powershell", "-Command",
             "Get-PnpDevice -Class Bluetooth | Where-Object { $_.Status -eq 'OK' } | Select-Object -First 1 FriendlyName"],
            capture_output=True, text=True, timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

        bt_available = bool(bt_result.stdout.strip()) and bt_result.returncode == 0

        return {
            "available": phone_link_running and bt_available,
            "phone_link_running": phone_link_running,
            "bluetooth_available": bt_available,
            "bluetooth_device": bt_result.stdout.strip() if bt_available else None,
        }

    except Exception as e:
        logger.error(f"[!] Error checking Phone Link: {e}")
        return {"available": False, "error": str(e)}


def initiate_call(phone_number: str) -> Dict[str, Any]:
    """
    Initiate a phone call via Windows Phone Link using the tel: protocol.

    The call audio is routed through the laptop's speakers/mic via Bluetooth,
    allowing DARKI's voice pipeline to speak to the person on the other end.

    Args:
        phone_number: The phone number to call (e.g., "+919876543210").

    Returns:
        Dict with call initiation status.
    """
    # Sanitize phone number
    clean_number = "".join(c for c in phone_number if c.isdigit() or c == "+")
    if not clean_number or len(clean_number) < 7:
        return {"success": False, "error": f"Invalid phone number: {phone_number}"}

    logger.info(f"[*] Initiating call to: {clean_number}")

    try:
        # Check Phone Link availability first
        status = check_phone_link_available()
        if not status.get("available"):
            return {
                "success": False,
                "error": "Phone Link is not available. Ensure your phone is paired via Bluetooth.",
                "details": status,
            }

        # Use Windows tel: protocol handler to initiate the call
        # This triggers Phone Link to dial the number through the paired phone
        os.startfile(f"tel:{clean_number}")

        logger.info(f"[+] Call initiated to {clean_number} via Phone Link.")
        return {
            "success": True,
            "action": "call_initiated",
            "phone_number": clean_number,
            "details": "Call initiated via Phone Link. Audio routed through laptop.",
        }

    except Exception as e:
        logger.error(f"[!] Error initiating call: {e}")
        return {"success": False, "error": str(e)}


def end_call() -> Dict[str, Any]:
    """
    End the current phone call.

    Note: Programmatic call termination via Phone Link is limited.
    This sends a keyboard shortcut to the Phone Link app to hang up.
    """
    try:
        # Focus Phone Link window and send hang-up key
        subprocess.run(
            ["powershell", "-Command",
             """
             Add-Type -AssemblyName System.Windows.Forms;
             $wshell = New-Object -ComObject wscript.shell;
             $wshell.AppActivate('Phone Link');
             Start-Sleep -Milliseconds 500;
             [System.Windows.Forms.SendKeys]::SendWait('{ENTER}');
             """],
            capture_output=True, text=True, timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

        logger.info("[+] Call end signal sent.")
        return {"success": True, "action": "call_ended"}

    except Exception as e:
        logger.error(f"[!] Error ending call: {e}")
        return {"success": False, "error": str(e)}
