"""
OrchestraAI — System Command Executor Tool
===========================================
Executes local actions on the host machine safely using a whitelisted set of
applications (browsers and utilities) to prevent arbitrary shell injection.
"""

import os
import json
import re
import subprocess
import webbrowser
from pathlib import Path
from typing import Dict, Any, Optional

# Whitelist of allowed apps and browsers
ALLOWED_BROWSERS = {"brave", "chrome", "edge", "default"}
ALLOWED_APPS = {
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "calc": "calc.exe",
    "explorer": "explorer.exe"
}

# Resolve common browser paths on Windows
def get_browser_path(browser: str) -> Optional[str]:
    program_files = os.environ.get("ProgramFiles", "C:\\Program Files")
    program_files_x86 = os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")
    local_app_data = os.environ.get("LocalAppData", str(Path.home() / "AppData" / "Local"))

    if browser == "brave":
        paths = [
            Path(program_files) / "BraveSoftware" / "Brave-Browser" / "Application" / "brave.exe",
            Path(program_files_x86) / "BraveSoftware" / "Brave-Browser" / "Application" / "brave.exe",
            Path(local_app_data) / "BraveSoftware" / "Brave-Browser" / "Application" / "brave.exe"
        ]
        for p in paths:
            if p.exists():
                return str(p)
    elif browser == "chrome":
        paths = [
            Path(program_files) / "Google" / "Chrome" / "Application" / "chrome.exe",
            Path(program_files_x86) / "Google" / "Chrome" / "Application" / "chrome.exe"
        ]
        for p in paths:
            if p.exists():
                return str(p)
    elif browser == "edge":
        paths = [
            Path(program_files_x86) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
            Path(program_files) / "Microsoft" / "Edge" / "Application" / "msedge.exe"
        ]
        for p in paths:
            if p.exists():
                return str(p)

    return None

def execute_system_command(response_content: str) -> Dict[str, Any]:
    """
    Parses a structured JSON response from the LLM and executes the specified system action.
    
    Expected JSON schema:
    {
      "action": "open_browser" | "launch_app" | "invalid",
      "target": "URL or app name",
      "browser": "brave" | "chrome" | "edge" | "default" | null,
      "reasoning": "explanation"
    }
    """
    try:
        # Extract JSON from response content (handling optional code blocks)
        json_match = re.search(r'\{[^}]+\}', response_content, re.DOTALL)
        if not json_match:
            return {"success": False, "error": "No JSON payload found in model output."}

        data = json.loads(json_match.group())
        action = data.get("action", "").lower().strip()
        target = data.get("target", "").strip()
        browser = data.get("browser", "").lower().strip() if data.get("browser") else None
        reasoning = data.get("reasoning", "")

        if action == "open_browser":
            # Sanitize URL: if it doesn't have http/https prefix, add it (except for common targets)
            url = target
            if not url.startswith("http://") and not url.startswith("https://"):
                # Check for popular aliases
                if "whatsapp" in url.lower():
                    url = "https://web.whatsapp.com"
                elif "youtube" in url.lower():
                    url = "https://youtube.com"
                elif "google" in url.lower():
                    url = "https://google.com"
                elif "github" in url.lower():
                    url = "https://github.com"
                else:
                    url = f"https://{url}"

            # Validate browser selection
            if browser not in ALLOWED_BROWSERS:
                browser = "default"

            # Execute browser opening
            if browser and browser != "default":
                browser_path = get_browser_path(browser)
                if browser_path:
                    subprocess.Popen([browser_path, url])
                    return {
                        "success": True,
                        "action": "open_browser",
                        "target_url": url,
                        "browser": browser,
                        "reasoning": reasoning,
                        "details": f"Opened {url} in {browser.capitalize()} browser."
                    }
                else:
                    # Fallback to default system browser if specific browser path not found
                    webbrowser.open(url)
                    return {
                        "success": True,
                        "action": "open_browser",
                        "target_url": url,
                        "browser": "default",
                        "reasoning": reasoning,
                        "details": f"Brave/specific browser executable not found. Fell back to default browser to open {url}."
                    }
            else:
                webbrowser.open(url)
                return {
                    "success": True,
                    "action": "open_browser",
                    "target_url": url,
                    "browser": "default",
                    "reasoning": reasoning,
                    "details": f"Opened {url} in default browser."
                }

        elif action == "launch_app":
            app_key = target.lower().strip()
            if app_key not in ALLOWED_APPS:
                return {
                    "success": False,
                    "error": f"App '{target}' is not in the safety whitelist. Allowed apps: {', '.join(ALLOWED_APPS.keys())}"
                }

            binary_name = ALLOWED_APPS[app_key]
            # Launch local system app (e.g. notepad.exe) safely
            subprocess.Popen([binary_name], shell=True)
            return {
                "success": True,
                "action": "launch_app",
                "target_app": target,
                "reasoning": reasoning,
                "details": f"Successfully launched local application: {target.capitalize()}."
            }

        elif action == "run_terminal":
            # For security, we don't run it right away. We return a status indicating
            # it needs manual confirmation.
            return {
                "success": True,
                "action": "run_terminal",
                "command": target,
                "reasoning": reasoning,
                "details": f"Needs approval to execute command: '{target}'"
            }

        else:
            return {
                "success": False,
                "error": f"Invalid or unsupported system command action: {action}."
            }

    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to execute system command: {str(e)}"
        }
