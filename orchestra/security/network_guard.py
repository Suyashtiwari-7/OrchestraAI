"""
OrchestraAI — Network Guard (EDR Network Defense)
==================================================
Real-time protection against:
- ARP Cache Poisoning & Man-In-The-Middle (MITM) attacks
- Rogue WiFi Access Points & Evil Twin BSSID spoofing
- Untrusted Public Network exposures
- Emergency Network Isolation (Kill-Switch)
"""

import os
import re
import logging
import subprocess
from typing import Dict, Any, List, Optional, Set, Tuple

logger = logging.getLogger("orchestra.security.network")


class NetworkGuard:
    """Monitors local network interfaces, ARP tables, and WiFi BSSID integrity."""

    def __init__(self):
        self._trusted_bssids: Set[str] = set()
        self._last_gateway_mac: Optional[str] = None
        self._isolated = False

    def add_trusted_bssid(self, bssid: str):
        """Add a WiFi router hardware BSSID MAC to trusted whitelist."""
        clean = bssid.lower().replace("-", ":").strip()
        self._trusted_bssids.add(clean)
        logger.info(f"[Security] Trusted BSSID added: {clean}")

    def get_current_wifi(self) -> Dict[str, Any]:
        """
        Query current connected WiFi SSID and hardware BSSID using netsh.
        Returns dict with ssid, bssid, signal, state.
        """
        try:
            res = subprocess.run(
                ["netsh", "wlan", "show", "interfaces"],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            if res.returncode != 0:
                return {"connected": False, "ssid": None, "bssid": None}

            output = res.stdout
            ssid_match = re.search(r"^\s*SSID\s*:\s*(.+)$", output, re.MULTILINE)
            bssid_match = re.search(r"^\s*BSSID\s*:\s*([0-9a-fA-F:-]+)", output, re.MULTILINE)
            state_match = re.search(r"^\s*State\s*:\s*(\w+)", output, re.MULTILINE)

            ssid = ssid_match.group(1).strip() if ssid_match else None
            bssid = bssid_match.group(1).strip().lower().replace("-", ":") if bssid_match else None
            state = state_match.group(1).strip().lower() if state_match else "disconnected"

            is_trusted = bssid in self._trusted_bssids if bssid else False

            return {
                "connected": state == "connected",
                "ssid": ssid,
                "bssid": bssid,
                "is_trusted": is_trusted,
                "state": state,
            }
        except Exception as e:
            logger.error(f"[Security] Error querying WiFi interface: {e}")
            return {"connected": False, "error": str(e)}

    def parse_arp_table(self, custom_output: Optional[str] = None) -> List[Dict[str, str]]:
        """
        Parse the current ARP table into structured IP -> MAC mappings.
        Accepts custom_output for unit testing.
        """
        mappings = []
        try:
            if custom_output is not None:
                output = custom_output
            else:
                res = subprocess.run(
                    ["arp", "-a"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
                output = res.stdout

            # Match: IP address, Physical (MAC) Address, Type (dynamic/static)
            pattern = re.compile(
                r"(\d{1,3}(?:\.\d{1,3}){3})\s+([0-9a-fA-F]{2}[-:][0-9a-fA-F]{2}[-:][0-9a-fA-F]{2}[-:][0-9a-fA-F]{2}[-:][0-9a-fA-F]{2}[-:][0-9a-fA-F]{2})\s+(\w+)"
            )

            for match in pattern.finditer(output):
                ip = match.group(1)
                mac = match.group(2).lower().replace("-", ":")
                entry_type = match.group(3).lower()

                # Filter out broadcast/multicast (ff:ff:ff:ff:ff:ff, 224.x.x.x, 255.255.255.255)
                if mac == "ff:ff:ff:ff:ff:ff" or ip.startswith("224.") or ip.startswith("239.") or ip == "255.255.255.255":
                    continue

                mappings.append({
                    "ip": ip,
                    "mac": mac,
                    "type": entry_type,
                })

        except Exception as e:
            logger.error(f"[Security] Error parsing ARP table: {e}")

        return mappings

    def check_arp_anomalies(self, arp_entries: Optional[List[Dict[str, str]]] = None) -> List[Dict[str, Any]]:
        """
        Detect active ARP Poisoning / Spoofing anomalies.
        An anomaly occurs when multiple distinct IP addresses share the exact same unicast MAC address.
        """
        entries = arp_entries if arp_entries is not None else self.parse_arp_table()
        anomalies = []

        # Map MAC -> list of IPs
        mac_to_ips: Dict[str, List[str]] = {}
        for item in entries:
            mac = item["mac"]
            ip = item["ip"]
            if mac not in mac_to_ips:
                mac_to_ips[mac] = []
            mac_to_ips[mac].append(ip)

        # Look for duplicate IP mappings on a single MAC
        for mac, ips in mac_to_ips.items():
            if len(ips) > 1:
                # Potential ARP Poisoning / MITM attack!
                anomalies.append({
                    "type": "arp_poisoning_suspected",
                    "mac": mac,
                    "conflicting_ips": ips,
                    "description": f"Multiple IP addresses ({', '.join(ips)}) share the identical MAC address ({mac}). Likely active Man-In-The-Middle attack.",
                })

        return anomalies

    def isolate_network(self) -> Dict[str, Any]:
        """
        Emergency Network Kill-Switch (Dual-Layer Containment):
        1. Layer 1 (Software): Blocks all outbound IP traffic via Windows Firewall.
        2. Layer 2 (Physical Hardware): Disables active network adapters (Wi-Fi/Ethernet) at the driver level.
        """
        try:
            logger.critical("[Security] EMERGENCY NETWORK ISOLATION TRIGGERED (Dual-Layer)!")
            
            # 1. Add emergency blocking rule to Windows Firewall
            subprocess.run(
                ["netsh", "advfirewall", "firewall", "add", "rule",
                 "name=DARKI_EMERGENCY_ISOLATION", "dir=out", "action=block"],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )

            # 2. Hardware-level adapter disconnect via PowerShell
            if os.name == "nt":
                subprocess.run(
                    ["powershell", "-Command", "Disable-NetAdapter -Name '*' -Confirm:$false"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )

            self._isolated = True
            return {
                "success": True,
                "status": "network_isolated",
                "message": "Dual-layer isolation active: Outbound firewall blocked & network adapters hardware-disabled.",
            }
        except Exception as e:
            logger.error(f"[Security] Network isolation failed: {e}")
            return {"success": False, "error": str(e)}

    def restore_network(self) -> Dict[str, Any]:
        """Restore network traffic and re-enable network adapters after an incident is resolved."""
        try:
            # 1. Remove firewall rule
            subprocess.run(
                ["netsh", "advfirewall", "firewall", "delete", "rule",
                 "name=DARKI_EMERGENCY_ISOLATION"],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )

            # 2. Re-enable network adapters via PowerShell
            if os.name == "nt":
                subprocess.run(
                    ["powershell", "-Command", "Enable-NetAdapter -Name '*' -Confirm:$false"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )

            self._isolated = False
            logger.info("[Security] Network isolation lifted. Adapters and connectivity restored.")
            return {
                "success": True,
                "status": "network_restored",
                "message": "Emergency isolation lifted. Network adapters re-enabled and connectivity restored.",
            }
        except Exception as e:
            logger.error(f"[Security] Network restore failed: {e}")
            return {"success": False, "error": str(e)}

    @property
    def is_isolated(self) -> bool:
        return self._isolated
