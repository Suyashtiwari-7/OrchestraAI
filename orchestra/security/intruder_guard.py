"""
OrchestraAI — Active Intruder & Threat Containment Guard
=========================================================
Real-time endpoint defense against:
- Unauthorized Remote Desktop (RDP) & Remote Terminal sessions
- Rogue backdoor processes & reverse shells
- Automated "Kick Out" Incident Response containment sequence:
  1. Kill unauthorized process tree (`taskkill /F /T`)
  2. Logoff rogue user session (`logoff`)
  3. Lock workstation (`LockWorkStation`)
"""

import os
import re
import logging
import subprocess
from typing import Dict, Any, List, Optional

logger = logging.getLogger("orchestra.security.intruder")

# Known attack / reverse shell / credential dumping executable signatures
SUSPICIOUS_PROCESS_NAMES = {
    "mimikatz.exe", "mimikatz",
    "nc.exe", "ncat.exe", "netcat.exe",
    "meterpreter",
    "chisel.exe",
    "psexec.exe", "psexesvc.exe",
    "cain.exe",
    "pwdump.exe",
    "procdump.exe",
}


class IntruderGuard:
    """Detects unauthorized remote sessions and executes automated incident response containment."""

    def __init__(self):
        self._authorized_users: set = set()
        # Auto-detect current local Windows username
        current_user = os.getenv("USERNAME", "").lower()
        if current_user:
            self._authorized_users.add(current_user)

    def scan_active_sessions(self, custom_output: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Scan active Windows user sessions using qwinsta (Query Session).
        Detects active RDP / remote sessions not originating from the console.
        """
        sessions = []
        try:
            if custom_output is not None:
                output = custom_output
            else:
                res = subprocess.run(
                    ["qwinsta"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
                output = res.stdout

            # Parse qwinsta table
            lines = output.strip().split("\n")
            for line in lines[1:]:  # Skip header
                parts = line.split()
                if not parts:
                    continue

                session_name = parts[0].replace(">", "").strip()
                state = "Active" if "Active" in line or "Disc" in line else "Listen"
                session_id = None

                # Find numeric session ID
                for token in parts:
                    if token.isdigit():
                        session_id = int(token)
                        break

                is_rdp = "rdp" in session_name.lower() or "tcp" in session_name.lower()

                if session_id is not None and state == "Active" and is_rdp:
                    sessions.append({
                        "session_name": session_name,
                        "session_id": session_id,
                        "state": state,
                        "is_remote": True,
                        "suspicious": True,
                        "description": f"Active Remote Desktop (RDP) session detected on Session ID {session_id} ({session_name}).",
                    })

        except Exception as e:
            logger.debug(f"[Security] qwinsta session query failed: {e}")

        return sessions

    def scan_suspicious_processes(self) -> List[Dict[str, Any]]:
        """Scan running processes for known hacker tool binaries and reverse shells."""
        threats = []
        try:
            import psutil
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'username']):
                try:
                    name = proc.info.get('name') or ''
                    pid = proc.info.get('pid')
                    cmdline = " ".join(proc.info.get('cmdline') or [])

                    if name.lower() in SUSPICIOUS_PROCESS_NAMES:
                        threats.append({
                            "type": "suspicious_process",
                            "name": name,
                            "pid": pid,
                            "cmdline": cmdline[:200],
                            "severity": "CRITICAL",
                            "description": f"Known attack tool executable detected: {name} (PID: {pid}).",
                        })

                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue

        except ImportError:
            logger.debug("psutil not available for process scanning.")
        except Exception as e:
            logger.error(f"[Security] Process scan error: {e}")

        return threats

    def execute_kickout(self, session_id: Optional[int] = None, pid: Optional[int] = None) -> Dict[str, Any]:
        """
        Automated "Kick Out" Incident Response Sequence:
        1. Forcibly terminates the target process tree.
        2. Logs off the unauthorized session.
        3. Locks the workstation.
        """
        logger.critical(f"[Security] INITIATING INCIDENT RESPONSE: KICK OUT INTRUDER (Session={session_id}, PID={pid})")
        results = []

        # 1. Kill malicious process
        if pid:
            try:
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(pid)],
                    capture_output=True,
                    timeout=5,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
                results.append(f"Process PID {pid} killed.")
            except Exception as e:
                results.append(f"Process kill error: {e}")

        # 2. Logoff unauthorized remote session
        if session_id is not None:
            try:
                subprocess.run(
                    ["logoff", str(session_id)],
                    capture_output=True,
                    timeout=5,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
                results.append(f"Session {session_id} logged off.")
            except Exception as e:
                results.append(f"Session logoff error: {e}")

        # 3. Lock the workstation
        self.lock_workstation()
        results.append("Workstation locked.")

        return {
            "success": True,
            "action": "kickout_executed",
            "details": " | ".join(results),
        }

    def lock_workstation(self) -> bool:
        """Immediately lock the Windows workstation."""
        try:
            if os.name == "nt":
                subprocess.run(
                    ["rundll32.exe", "user32.dll,LockWorkStation"],
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                logger.info("[Security] Workstation successfully locked.")
                return True
        except Exception as e:
            logger.error(f"[Security] Failed to lock workstation: {e}")
        return False
