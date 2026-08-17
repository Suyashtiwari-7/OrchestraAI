"""
OrchestraAI — Autonomous Cybersecurity & Incident Response (EDR) Engine
========================================================================
Real-time endpoint detection and automated incident response:
- NetworkGuard: ARP spoofing, MITM defense, WiFi BSSID integrity, network isolation kill-switch.
- BadUSBGuard: Keystroke velocity anomaly detection, DuckScript payload pattern analysis.
- IntruderGuard: Rogue remote session (RDP/SSH) & elevated shell scanner, session logoff, workstation lock.
- SecurityManager: Central security orchestrator & event dispatcher.
"""

from .network_guard import NetworkGuard
from .badusb_guard import BadUSBGuard
from .intruder_guard import IntruderGuard
from .security_manager import SecurityManager, SecurityIncident, ThreatLevel

__all__ = [
    "NetworkGuard",
    "BadUSBGuard",
    "IntruderGuard",
    "SecurityManager",
    "SecurityIncident",
    "ThreatLevel",
]
