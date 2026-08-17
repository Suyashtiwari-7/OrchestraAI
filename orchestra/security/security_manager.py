"""
OrchestraAI — Unified Security Manager (Autonomous EDR & IR Coordinator)
========================================================================
Coordinates all endpoint security defenses:
- NetworkGuard (ARP Spoofing, WiFi BSSID integrity, Network Kill-Switch)
- BadUSBGuard (Keystroke velocity, DuckScript pattern detection, FIDO2 keys)
- IntruderGuard (Remote RDP sessions, rogue processes, automated Kick-Out)
- Event Dispatcher & Voice Alert trigger
"""

import time
import logging
import threading
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable

from .network_guard import NetworkGuard
from .badusb_guard import BadUSBGuard
from .intruder_guard import IntruderGuard

logger = logging.getLogger("orchestra.security.manager")


class ThreatLevel(Enum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class SecurityIncident:
    """Represents a detected security incident."""
    title: str
    threat_level: ThreatLevel
    description: str
    source_guard: str
    action_taken: str = "logged"
    timestamp: float = field(default_factory=time.time)


class SecurityManager:
    """Central orchestrator for DARKI's autonomous EDR & Incident Response subsystem."""

    # Audit interval in seconds (runs lightweight checks on idle)
    AUDIT_INTERVAL = 10.0

    def __init__(
        self,
        on_incident: Optional[Callable[[SecurityIncident], None]] = None,
        on_voice_alert: Optional[Callable[[str], None]] = None,
    ):
        self.network = NetworkGuard()
        self.badusb = BadUSBGuard()
        self.intruder = IntruderGuard()

        self.on_incident = on_incident
        self.on_voice_alert = on_voice_alert

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._incidents: List[SecurityIncident] = []
        self._lock = threading.Lock()

    def start(self):
        """Start the background autonomous security monitor."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True, name="SecurityManagerThread")
        self._thread.start()
        logger.info("[*] Autonomous Security Manager (EDR) started.")

    def stop(self):
        """Stop the security monitor."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        logger.info("[*] Security Manager stopped.")

    def _monitor_loop(self):
        """Background loop: checks network ARP anomalies and active remote sessions."""
        while self._running:
            try:
                # 1. Check for ARP Poisoning / MITM anomalies
                arp_threats = self.network.check_arp_anomalies()
                for threat in arp_threats:
                    incident = SecurityIncident(
                        title="ARP Cache Poisoning Detected (MITM Attack)",
                        threat_level=ThreatLevel.HIGH,
                        description=threat["description"],
                        source_guard="NetworkGuard",
                        action_taken="warn_user",
                    )
                    self._dispatch_incident(incident, spoken_alert="Security Warning: Active ARP Poisoning attack detected on local network!")

                # 2. Check for unauthorized remote sessions (RDP/SSH)
                sessions = self.intruder.scan_active_sessions()
                for sess in sessions:
                    if sess.get("suspicious"):
                        incident = SecurityIncident(
                            title="Unauthorized Remote Session Detected",
                            threat_level=ThreatLevel.CRITICAL,
                            description=sess["description"],
                            source_guard="IntruderGuard",
                            action_taken="containment_ready",
                        )
                        self._dispatch_incident(incident, spoken_alert="Security Alert: Active remote desktop session detected!")

                # 3. Check for known malicious hacking binaries
                proc_threats = self.intruder.scan_suspicious_processes()
                for p_threat in proc_threats:
                    incident = SecurityIncident(
                        title=f"Malicious Binary Detected: {p_threat['name']}",
                        threat_level=ThreatLevel.CRITICAL,
                        description=p_threat["description"],
                        source_guard="IntruderGuard",
                        action_taken="kill_ready",
                    )
                    self._dispatch_incident(incident, spoken_alert=f"Critical Security Alert: Suspicious attack tool {p_threat['name']} detected!")

            except Exception as e:
                logger.error(f"[Security] Monitor loop tick error: {e}")

            time.sleep(self.AUDIT_INTERVAL)

    def _dispatch_incident(self, incident: SecurityIncident, spoken_alert: Optional[str] = None):
        """Log incident and notify callbacks/voice."""
        with self._lock:
            self._incidents.append(incident)

        logger.critical(f"[SECURITY INCIDENT] [{incident.threat_level.value}] {incident.title}: {incident.description}")

        if self.on_incident:
            try:
                self.on_incident(incident)
            except Exception as e:
                logger.error(f"[Security] Incident callback error: {e}")

        if spoken_alert and self.on_voice_alert:
            try:
                self.on_voice_alert(spoken_alert)
            except Exception as e:
                logger.error(f"[Security] Voice alert callback error: {e}")

    def run_full_audit(self) -> Dict[str, Any]:
        """
        Execute an on-demand comprehensive security audit of the endpoint.
        Returns full diagnostic report.
        """
        wifi_info = self.network.get_current_wifi()
        arp_threats = self.network.check_arp_anomalies()
        sessions = self.intruder.scan_active_sessions()
        proc_threats = self.intruder.scan_suspicious_processes()

        has_threats = bool(arp_threats or sessions or proc_threats)

        return {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "status": "THREATS_DETECTED" if has_threats else "SECURE",
            "wifi": wifi_info,
            "arp_threats_count": len(arp_threats),
            "arp_threats": arp_threats,
            "remote_sessions_count": len(sessions),
            "remote_sessions": sessions,
            "suspicious_processes_count": len(proc_threats),
            "suspicious_processes": proc_threats,
            "network_isolated": self.network.is_isolated,
            "total_incidents_recorded": len(self._incidents),
        }

    def handle_keystroke(self, char: str) -> Dict[str, Any]:
        """
        Feed typed character into BadUSB analysis engine.
        If an attack is detected, dispatches incident and locks workstation.
        """
        result = self.badusb.record_keystroke(char)
        if result.get("is_attack"):
            incident = SecurityIncident(
                title=f"BadUSB Hardware Attack Detected ({result.get('type')})",
                threat_level=ThreatLevel.CRITICAL,
                description=result.get("description", "BadUSB keystroke injection detected."),
                source_guard="BadUSBGuard",
                action_taken="lock_workstation",
            )
            # Neutralize: immediately lock the workstation
            self.intruder.lock_workstation()
            self._dispatch_incident(incident, spoken_alert="BadUSB Attack Detected! Workstation locked.")

        return result

    def get_incidents(self) -> List[Dict[str, Any]]:
        """Return list of recorded security incidents."""
        with self._lock:
            return [
                {
                    "title": inc.title,
                    "threat_level": inc.threat_level.value,
                    "description": inc.description,
                    "source_guard": inc.source_guard,
                    "action_taken": inc.action_taken,
                    "timestamp": inc.timestamp,
                }
                for inc in self._incidents
            ]
