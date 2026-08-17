"""
OrchestraAI — BadUSB & Flipper Zero Hardware Guard
===================================================
Real-time defense against:
- BadUSB / USB Rubber Ducky / Flipper Zero HID Keystroke Injection attacks
- Superhuman typing velocity (<10ms inter-key delays)
- Malicious DuckScript payloads (hidden PowerShell, Base64 execution, registry modifications)
- Distinguishes FIDO2/U2F security keys from attack keyboards
"""

import re
import time
import logging
from typing import Dict, Any, List, Optional
from collections import deque

logger = logging.getLogger("orchestra.security.badusb")

# Suspicious DuckScript / BadUSB payload patterns
MALICIOUS_PAYLOAD_PATTERNS = [
    re.compile(r"powershell(?:\.exe)?\s+.*(?:-w(?:indowstyle)?\s+hidden|-enc(?:odedcommand)?|-nop(?:rofile)?|-ep\s+bypass)", re.IGNORECASE),
    re.compile(r"Invoke-WebRequest\s+|Invoke-Expression\s+|IEX\s*\(|DownloadString\(", re.IGNORECASE),
    re.compile(r"cmd(?:\.exe)?\s+/c\s+start\s+/min", re.IGNORECASE),
    re.compile(r"reg\s+add\s+HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run", re.IGNORECASE),
    re.compile(r"net\s+user\s+\w+\s+\w+\s+/add", re.IGNORECASE),
    re.compile(r"bitsadmin\s+/transfer", re.IGNORECASE),
    re.compile(r"certutil(?:\.exe)?\s+-urlcache\s+-f", re.IGNORECASE),
]

# FIDO2 / U2F Security Key HID Usage Page identifier
FIDO2_USAGE_PAGE = 0xF1D0


class BadUSBGuard:
    """Detects and neutralizes BadUSB / Flipper Zero keystroke injection attacks."""

    # Velocity Thresholds
    HUMAN_MAX_CPS = 25.0       # Characters per second (approx 300 WPM)
    INJECTION_MIN_CPS = 40.0    # 40+ chars/sec indicates hardware automation
    MIN_KEYSTROKES_FOR_CHECK = 10

    def __init__(self):
        # Ring buffer of the last 100 keystroke timestamps
        self._timestamps: deque = deque(maxlen=100)
        # Ring buffer of the last typed characters
        self._input_buffer: deque = deque(maxlen=500)
        self._whitelisted_vids: set = set()

    def record_keystroke(self, char: str, timestamp: Optional[float] = None) -> Dict[str, Any]:
        """
        Record a keystroke event and evaluate velocity and payload patterns.
        Returns detection result dict.
        """
        now = timestamp if timestamp is not None else time.time()
        self._timestamps.append(now)
        self._input_buffer.append(char)

        # 1. Velocity Analysis
        velocity_alert = self._check_velocity()
        if velocity_alert["is_attack"]:
            return velocity_alert

        # 2. Payload Pattern Analysis
        payload_alert = self._check_payload()
        if payload_alert["is_attack"]:
            return payload_alert

        return {"is_attack": False, "reason": "normal"}

    def _check_velocity(self) -> Dict[str, Any]:
        """Check if keystroke speed exceeds human physical capability."""
        if len(self._timestamps) < self.MIN_KEYSTROKES_FOR_CHECK:
            return {"is_attack": False}

        times = list(self._timestamps)[-20:]
        duration = times[-1] - times[0]

        if duration <= 0:
            cps = 999.0
        else:
            cps = len(times) / duration

        # If typing speed is > 40 chars/second, this is hardware injection (Flipper Zero / BadUSB)
        if cps >= self.INJECTION_MIN_CPS:
            logger.critical(f"[Security] BADUSB VELOCITY DETECTED: {cps:.1f} chars/sec!")
            return {
                "is_attack": True,
                "type": "badusb_velocity_anomaly",
                "cps": round(cps, 1),
                "severity": "CRITICAL",
                "description": f"Superhuman typing speed detected ({round(cps, 1)} chars/sec). Keystroke injection attack in progress.",
            }

        return {"is_attack": False, "cps": round(cps, 1)}

    def _check_payload(self) -> Dict[str, Any]:
        """Inspect recent input buffer for signature DuckScript/BadUSB payloads."""
        current_text = "".join(self._input_buffer)

        for pattern in MALICIOUS_PAYLOAD_PATTERNS:
            match = pattern.search(current_text)
            if match:
                matched_str = match.group(0)
                logger.critical(f"[Security] BADUSB PAYLOAD DETECTED: {matched_str}")
                return {
                    "is_attack": True,
                    "type": "badusb_malicious_payload",
                    "matched_signature": matched_str,
                    "severity": "CRITICAL",
                    "description": f"Malicious command injection signature detected in keyboard buffer: '{matched_str}'.",
                }

        return {"is_attack": False}

    def inspect_usb_device(self, vid: str, pid: str, usage_page: Optional[int] = None) -> Dict[str, Any]:
        """
        Verify whether an attached USB device is an authentic FIDO2 security key
        or a potentially rogue HID keyboard.
        """
        device_id = f"{vid}:{pid}".lower()

        # Check FIDO2 / U2F hardware page
        if usage_page == FIDO2_USAGE_PAGE:
            return {
                "is_fido2_key": True,
                "trusted": True,
                "device_type": "FIDO2 / U2F Hardware Security Key (e.g. YubiKey)",
                "action": "allow",
            }

        is_whitelisted = device_id in self._whitelisted_vids

        return {
            "is_fido2_key": False,
            "trusted": is_whitelisted,
            "device_id": device_id,
            "action": "allow" if is_whitelisted else "prompt_user",
        }

    def whitelist_device(self, vid: str, pid: str):
        """Add authorized keyboard hardware VID:PID to whitelist."""
        self._whitelisted_vids.add(f"{vid}:{pid}".lower())
        logger.info(f"[Security] Whitelisted USB keyboard device: {vid}:{pid}")

    def clear_buffer(self):
        """Reset keystroke buffers."""
        self._timestamps.clear()
        self._input_buffer.clear()
