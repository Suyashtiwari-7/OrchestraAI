"""
OrchestraAI — Autonomous Cybersecurity (EDR) Engine Tests
==========================================================
Tests for NetworkGuard, BadUSBGuard, IntruderGuard, and SecurityManager.
"""

import time
import pytest
from unittest.mock import patch, MagicMock

from orchestra.security.network_guard import NetworkGuard
from orchestra.security.badusb_guard import BadUSBGuard, FIDO2_USAGE_PAGE
from orchestra.security.intruder_guard import IntruderGuard
from orchestra.security.security_manager import SecurityManager, ThreatLevel, SecurityIncident


class TestNetworkGuard:
    """Test ARP spoofing detection and BSSID whitelisting."""

    def setup_method(self):
        self.guard = NetworkGuard()

    def test_arp_normal_output(self):
        """Test clean ARP table yields zero anomalies."""
        sample_arp = """
Interface: 192.168.1.5 --- 0x10
  Internet Address      Physical Address      Type
  192.168.1.1           a4-c3-f0-12-34-56     dynamic
  192.168.1.50          b0-48-1a-99-88-77     dynamic
  192.168.1.255         ff-ff-ff-ff-ff-ff     static
"""
        entries = self.guard.parse_arp_table(custom_output=sample_arp)
        assert len(entries) == 2
        anomalies = self.guard.check_arp_anomalies(entries)
        assert len(anomalies) == 0

    def test_arp_spoofing_anomaly_detection(self):
        """Test that multiple IPs with the same MAC address are flagged as ARP poisoning."""
        spoofed_arp = """
Interface: 192.168.1.5 --- 0x10
  Internet Address      Physical Address      Type
  192.168.1.1           a4-c3-f0-12-34-56     dynamic
  192.168.1.100         a4-c3-f0-12-34-56     dynamic
  192.168.1.50          b0-48-1a-99-88-77     dynamic
"""
        entries = self.guard.parse_arp_table(custom_output=spoofed_arp)
        anomalies = self.guard.check_arp_anomalies(entries)
        assert len(anomalies) == 1
        assert anomalies[0]["type"] == "arp_poisoning_suspected"
        assert anomalies[0]["mac"] == "a4:c3:f0:12:34:56"
        assert "192.168.1.1" in anomalies[0]["conflicting_ips"]
        assert "192.168.1.100" in anomalies[0]["conflicting_ips"]

    def test_bssid_whitelist(self):
        """Test BSSID trust tracking."""
        self.guard.add_trusted_bssid("A4-C3-F0-12-34-56")
        assert "a4:c3:f0:12:34:56" in self.guard._trusted_bssids


class TestBadUSBGuard:
    """Test keystroke velocity, payload pattern recognition, and FIDO2 device checks."""

    def setup_method(self):
        self.guard = BadUSBGuard()

    def test_normal_human_typing_speed(self):
        """Test normal typing rate is not flagged as an attack."""
        start = time.time()
        for i in range(15):
            # Simulate 100ms between keystrokes (approx 10 chars/sec = normal human)
            res = self.guard.record_keystroke(f"char_{i}", timestamp=start + (i * 0.1))
            assert res["is_attack"] is False

    def test_badusb_superhuman_velocity_attack(self):
        """Test that hyper-fast keystroke injection (>40 chars/sec) is flagged as BadUSB."""
        start = time.time()
        result = {"is_attack": False}
        for i in range(25):
            # Simulate 2ms between keystrokes (500 chars/sec = machine/Flipper Zero)
            result = self.guard.record_keystroke("a", timestamp=start + (i * 0.002))

        assert result["is_attack"] is True
        assert result["type"] == "badusb_velocity_anomaly"
        assert result["severity"] == "CRITICAL"

    def test_badusb_malicious_payload_detection(self):
        """Test signature detection for hidden PowerShell execution strings even when typed at human speed."""
        payload = "powershell -w hidden -enc aGVsbG8="
        start = time.time()
        result = {"is_attack": False}
        for idx, char in enumerate(payload):
            # 100ms per char = human typing speed, so velocity won't trigger, but payload pattern will
            result = self.guard.record_keystroke(char, timestamp=start + (idx * 0.1))

        assert result["is_attack"] is True
        assert result["type"] == "badusb_malicious_payload"

    def test_fido2_yubikey_device_verification(self):
        """Test that authentic FIDO2 hardware security keys are trusted."""
        res = self.guard.inspect_usb_device("1050", "0407", usage_page=FIDO2_USAGE_PAGE)
        assert res["is_fido2_key"] is True
        assert res["trusted"] is True
        assert res["action"] == "allow"


class TestIntruderGuard:
    """Test remote session detection and containment logic."""

    def setup_method(self):
        self.guard = IntruderGuard()

    def test_qwinsta_remote_session_parsing(self):
        """Test detection of active RDP sessions from qwinsta output."""
        mock_qwinsta = """
 SESSIONNAME       USERNAME              ID  STATE    TYPE        DEVICE
 services                                 0  Disc
 console           suyash                 1  Active
 rdp-tcp#0         attacker               2  Active   rdpwd
"""
        sessions = self.guard.scan_active_sessions(custom_output=mock_qwinsta)
        assert len(sessions) == 1
        assert sessions[0]["session_id"] == 2
        assert sessions[0]["is_remote"] is True
        assert sessions[0]["suspicious"] is True


class TestSecurityManager:
    """Test unified security coordinator."""

    def test_run_full_audit(self):
        """Test full diagnostic audit structure."""
        manager = SecurityManager()
        audit = manager.run_full_audit()
        assert "timestamp" in audit
        assert "status" in audit
        assert "arp_threats" in audit
        assert "remote_sessions" in audit
        assert "network_isolated" in audit
