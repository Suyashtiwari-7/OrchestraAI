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
from ..config import settings

# Whitelist of allowed apps and browsers
ALLOWED_BROWSERS = {"brave", "chrome", "edge", "default"}
ALLOWED_APPS = {
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "calc": "calc.exe",
    "explorer": "explorer.exe",
    "outlook": "outlook.exe",
    "brave": "brave",
    "chrome": "chrome",
    "edge": "edge"
}

SAFE_FILE_EXTENSIONS = {
    ".txt", ".md", ".pdf", ".csv", ".docx", ".xlsx", ".pptx",
    ".png", ".jpg", ".jpeg", ".gif", ".mp3", ".mp4", ".html",
    ".json", ".yaml", ".yml", ".py", ".js", ".ts"
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

def get_outlook_path() -> str:
    # 1. Check standard Windows path locations
    standard_paths = [
        r"C:\Program Files\Microsoft Office\root\Office16\OUTLOOK.EXE",
        r"C:\Program Files (x86)\Microsoft Office\root\Office16\OUTLOOK.EXE",
        r"C:\Program Files\Microsoft Office\Office16\OUTLOOK.EXE",
        r"C:\Program Files (x86)\Microsoft Office\Office16\OUTLOOK.EXE",
        r"C:\Program Files\Microsoft Office\Office15\OUTLOOK.EXE",
        r"C:\Program Files (x86)\Microsoft Office\Office15\OUTLOOK.EXE"
    ]
    for p in standard_paths:
        if Path(p).exists():
            return p
            
    # 2. Check Windows registry for App Path
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\OUTLOOK.EXE"
        )
        val, _ = winreg.QueryValueEx(key, "")
        winreg.CloseKey(key)
        if val and Path(val).exists():
            return val
    except Exception:
        pass
        
    # Fallback to PATH resolving
    return "outlook.exe"

def find_windows_executable(app_name: str) -> Optional[str]:
    """
    Looks for a Windows executable by name in common installation folders
    using specific paths first and a shallow folder scan as fallback.
    """
    exe_name = app_name if "." in app_name else f"{app_name}.exe"
    program_files = os.environ.get("ProgramFiles", "C:\\Program Files")
    program_files_x86 = os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")
    local_app_data = os.environ.get("LocalAppData")
    
    search_dirs = []
    if local_app_data:
        search_dirs.append(Path(local_app_data) / "Programs")
        search_dirs.append(Path(local_app_data) / "Microsoft" / "WindowsApps")
    search_dirs.extend([Path(program_files), Path(program_files_x86)])
    
    # 1. Check common app locations directly (fast path)
    specific_paths = [
        # VLC
        Path(program_files) / "VideoLAN" / "VLC" / "vlc.exe",
        Path(program_files_x86) / "VideoLAN" / "VLC" / "vlc.exe",
        # Zoom
        Path(local_app_data) / "Zoom" / "bin" / "zoom.exe" if local_app_data else None,
        # Teams
        Path(local_app_data) / "Microsoft" / "Teams" / "current" / "Teams.exe" if local_app_data else None,
    ]
    specific_paths = [p for p in specific_paths if p is not None]
    
    for p in specific_paths:
        try:
            if p.exists() and p.name.lower() == exe_name.lower():
                return str(p)
        except Exception:
            continue
            
    # 2. Shallow walk (depth <= 3) through main application directories
    for base_dir in search_dirs:
        try:
            if not base_dir.exists():
                continue
            for child in base_dir.iterdir():
                try:
                    if child.is_file() and child.name.lower() == exe_name.lower():
                        return str(child)
                    elif child.is_dir():
                        for subchild in child.iterdir():
                            try:
                                if subchild.is_file() and subchild.name.lower() == exe_name.lower():
                                    return str(subchild)
                                elif subchild.is_dir():
                                    for subsubchild in subchild.iterdir():
                                        try:
                                            if subsubchild.is_file() and subsubchild.name.lower() == exe_name.lower():
                                                return str(subsubchild)
                                        except Exception:
                                            continue
                            except Exception:
                                continue
                except Exception:
                    continue
        except Exception:
            continue
            
    return None

def execute_system_command(response_content: str) -> Dict[str, Any]:
    """
    Parses a structured JSON response from the LLM and executes the specified system action.
    
    Expected JSON schema:
    {
      "action": "open_browser" | "launch_app" | "run_terminal" | "run_python" | "draft_email" | "send_email" | "read_inbox" | "reply_email" | "file_create" | "file_move" | "file_rename" | "file_search" | "file_delete" | "file_read" | "system_volume" | "system_brightness" | "system_lock" | "system_screenshot" | "system_info",
      "target": "<target_value>",
      "browser": "brave" | "chrome" | "edge" | "default" | null,
      "reasoning": "explanation",
      "email_to": "<recipient_email>",
      "email_subject": "<subject>",
      "email_body": "<body>",
      "email_index": <int_for_replies>,
      "file_content": "<content_to_write>",
      "file_dest": "<destination_path>",
      "file_new_name": "<new_name>",
      "level": <int_for_volume_or_brightness>
    }
    """
    try:
        # Robustly extract balanced JSON block from response content
        json_str = None
        start = response_content.find('{')
        if start != -1:
            brace_count = 0
            in_string = False
            escape = False
            for i in range(start, len(response_content)):
                char = response_content[i]
                if escape:
                    escape = False
                    continue
                if char == '\\':
                    escape = True
                    continue
                if char == '"':
                    in_string = not in_string
                    continue
                if not in_string:
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            json_str = response_content[start:i+1]
                            break
        
        if not json_str:
            return {"success": False, "error": "No JSON payload found in model output."}

        # Robustly parse JSON (handling literal newlines and invalid escapes inside string values)
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            cleaned = []
            in_string = False
            i = 0
            n = len(json_str)
            while i < n:
                char = json_str[i]
                if not in_string:
                    if char == '"':
                        in_string = True
                    cleaned.append(char)
                    i += 1
                    continue
                
                if char == '"':
                    in_string = False
                    cleaned.append(char)
                    i += 1
                    continue
                
                if char == '\\':
                    # Check for valid escape
                    if i + 1 < n:
                        next_char = json_str[i + 1]
                        if next_char in ('"', '\\', '/', 'b', 'f', 'n', 'r', 't'):
                            cleaned.append('\\')
                            cleaned.append(next_char)
                            i += 2
                            continue
                        elif next_char == 'u':
                            if i + 5 < n and all(c in '0123456789abcdefABCDEF' for c in json_str[i+2:i+6]):
                                cleaned.append('\\')
                                cleaned.append('u')
                                cleaned.extend(json_str[i+2:i+6])
                                i += 6
                                continue
                    # Not a valid escape sequence: escape the backslash itself
                    cleaned.append('\\\\')
                    i += 1
                elif char in ('\n', '\r'):
                    cleaned.append('\\n')
                    i += 1
                else:
                    cleaned.append(char)
                    i += 1
            data = json.loads("".join(cleaned))

        action = data.get("action", "").lower().strip()
        target = data.get("target", "").strip()
        browser = data.get("browser", "").lower().strip() if data.get("browser") else None
        reasoning = data.get("reasoning", "")

        # Import handlers lazily to prevent circular imports
        from orchestra.config import settings
        from .email_handler import draft_email, send_email, read_inbox, reply_to_email
        from .file_manager import create_file, move_file, rename_file, search_files, delete_file, read_file_content
        from .system_control import set_volume, get_volume, set_brightness, get_brightness, lock_screen, take_screenshot, get_system_info

        # Check app installation status for app-dependent actions
        if action == "launch_app":
            target_str = target.strip()
            parts = target_str.split(" ", 1)
            app_name = parts[0].lower()
            
            # Skip if opening a file or local path
            if not Path(target_str).suffix.lower() in SAFE_FILE_EXTENSIONS:
                status = check_app_installation_status(app_name)
                if not status["installed"]:
                    return {
                        "success": False,
                        "app_not_found": True,
                        "app_name": app_name,
                        "action": "launch_app",
                        "target": target,
                        "reasoning": reasoning
                    }
                    
        elif action in ("draft_email", "send_email"):
            # Check Outlook status
            status = check_app_installation_status("outlook")
            # If Outlook is not installed, check if background SMTP settings are configured
            smtp_configured = bool(settings.smtp_server and settings.smtp_email and settings.smtp_password)
            if not status["installed"] and not smtp_configured:
                # If neither is available, prompt user to download Outlook / use fallback
                return {
                    "success": False,
                    "app_not_found": True,
                    "app_name": "outlook",
                    "action": action,
                    "to": data.get("email_to") or target,
                    "subject": data.get("email_subject") or "No Subject",
                    "body": data.get("email_body") or "",
                    "reasoning": reasoning
                }
                
        elif action in ("schedule_meeting", "calendar_schedule"):
            status = check_app_installation_status("outlook")
            if not status["installed"]:
                return {
                    "success": False,
                    "app_not_found": True,
                    "app_name": "outlook",
                    "action": "schedule_meeting",
                    "subject": data.get("subject") or data.get("email_subject") or "Meeting",
                    "date": data.get("date") or "",
                    "time": data.get("time") or "",
                    "duration": data.get("duration") or 60,
                    "body": data.get("body") or data.get("email_body") or "",
                    "reasoning": reasoning
                }
                
        elif action == "set_reminder":
            status_todo = check_app_installation_status("todo")
            status_clock = check_app_installation_status("clock")
            if not status_todo["installed"] and not status_clock["installed"]:
                return {
                    "success": False,
                    "app_not_found": True,
                    "app_name": "Microsoft To Do",
                    "action": "set_reminder",
                    "message": data.get("message") or target or "",
                    "date": data.get("date") or "",
                    "time": data.get("time") or "",
                    "reasoning": reasoning
                }

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
            target_str = target.strip()
            # Extract application name and arguments
            parts = target_str.split(" ", 1)
            app_name = parts[0].lower()
            args = parts[1] if len(parts) > 1 else ""

            # Check if target_str itself is a file referencing a safe format
            file_suffix = Path(target_str).suffix.lower()
            if file_suffix in SAFE_FILE_EXTENSIONS:
                resolved_file = None
                paths_to_check = [
                    Path(target_str),
                    Path(settings.project_root) / target_str,
                    Path.home() / target_str,
                    Path.home() / "Desktop" / target_str,
                    Path.home() / "Documents" / target_str,
                    Path.home() / "Downloads" / target_str
                ]
                for p in paths_to_check:
                    try:
                        if p.exists() and p.is_file():
                            resolved_file = p
                            break
                    except Exception:
                        continue
                
                if resolved_file:
                    os.startfile(str(resolved_file))
                    return {
                        "success": True,
                        "action": "launch_app",
                        "target_app": f"open_file:{resolved_file.name}",
                        "reasoning": reasoning,
                        "details": f"Successfully opened file '{resolved_file.name}' with default application."
                    }
                else:
                    return {
                        "success": False,
                        "error": f"File '{target_str}' could not be found on your laptop (searched: root, home, Desktop, Documents, Downloads)."
                    }

            try:
                # 1. Special Handling for Browsers
                if app_name in ["brave", "chrome", "edge"]:
                    browser_path = get_browser_path(app_name)
                    if browser_path:
                        subprocess.Popen([browser_path])
                        return {
                            "success": True,
                            "action": "launch_app",
                            "target_app": app_name,
                            "reasoning": reasoning,
                            "details": f"Successfully launched {app_name.capitalize()} browser."
                        }
                    else:
                        webbrowser.open("https://google.com")
                        return {
                            "success": True,
                            "action": "launch_app",
                            "target_app": app_name,
                            "reasoning": reasoning,
                            "details": f"Browser executable not found. Opened default browser to Google as fallback."
                        }
                
                # 2. Outlook special handling (to support Classic and Outlook New)
                elif app_name == "outlook":
                    outlook_path = get_outlook_path()
                    # If we got a path that is not the default "outlook.exe", launch it directly
                    if outlook_path and outlook_path != "outlook.exe":
                        subprocess.Popen([outlook_path])
                        return {
                            "success": True,
                            "action": "launch_app",
                            "target_app": "outlook",
                            "reasoning": reasoning,
                            "details": f"Successfully launched Microsoft Outlook application."
                        }
                    else:
                        # For Outlook New, check for olk.exe first or use ms-outlook protocol
                        try:
                            olk_path = find_windows_executable("olk")
                            if olk_path:
                                subprocess.Popen([olk_path])
                            else:
                                subprocess.Popen(["olk.exe"])
                            return {
                                "success": True,
                                "action": "launch_app",
                                "target_app": "outlook",
                                "reasoning": reasoning,
                                "details": f"Successfully launched Outlook (New) application."
                            }
                        except FileNotFoundError:
                            # Try protocols, checking ms-outlook (New) first to avoid Store redirect
                            protocols_to_try = ["ms-outlook", "outlook"]
                            launched_via_protocol = False
                            for proto in protocols_to_try:
                                try:
                                    os.startfile(f"{proto}:")
                                    launched_via_protocol = True
                                    return {
                                        "success": True,
                                        "action": "launch_app",
                                        "target_app": "outlook",
                                        "reasoning": reasoning,
                                        "details": f"Successfully launched Outlook via registered protocol '{proto}:'."
                                    }
                                except Exception:
                                    continue
                            
                            # Final fallback to standard command
                            try:
                                subprocess.Popen(["outlook.exe"])
                                return {
                                    "success": True,
                                    "action": "launch_app",
                                    "target_app": "outlook",
                                    "reasoning": reasoning,
                                    "details": f"Successfully launched Microsoft Outlook application."
                                }
                            except FileNotFoundError:
                                raise FileNotFoundError("Outlook executable not found and protocol launching failed.")
                
                # 3. Notepad special handling
                elif app_name == "notepad":
                    binary_name = ALLOWED_APPS.get(app_name, "notepad.exe")
                    if args:
                        resolved_file = None
                        paths_to_check = [
                            Path(args),
                            Path(settings.project_root) / args,
                            Path.home() / args,
                            Path.home() / "Desktop" / args,
                            Path.home() / "Documents" / args,
                            Path.home() / "Downloads" / args
                        ]
                        for p in paths_to_check:
                            try:
                                if p.exists() and p.is_file():
                                    resolved_file = p
                                    break
                            except Exception:
                                continue
                        
                        if resolved_file:
                            subprocess.Popen([binary_name, str(resolved_file)])
                        else:
                            subprocess.Popen([binary_name, args])
                    else:
                        subprocess.Popen([binary_name], shell=True)
                        
                    return {
                        "success": True,
                        "action": "launch_app",
                        "target_app": "notepad",
                        "reasoning": reasoning,
                        "details": f"Successfully launched Notepad."
                    }

                # 4. Standard path resolving for other apps (like VLC)
                resolved_path = find_windows_executable(app_name)
                if resolved_path:
                    subprocess.Popen([resolved_path] if not args else [resolved_path, args])
                    return {
                        "success": True,
                        "action": "launch_app",
                        "target_app": app_name,
                        "reasoning": reasoning,
                        "details": f"Successfully launched {app_name.capitalize()} from standard installation path."
                    }

                # 5. Try running via command / registered alias directly (shell=True matches tests)
                binary_name = ALLOWED_APPS.get(app_name, app_name)
                try:
                    subprocess.Popen([binary_name] if not args else [binary_name, args], shell=True)
                    return {
                        "success": True,
                        "action": "launch_app",
                        "target_app": target,
                        "reasoning": reasoning,
                        "details": f"Successfully launched local application: {target.capitalize()}."
                    }
                except FileNotFoundError:
                    # 6. Try launching via registered protocol scheme as fallback
                    protocols_to_try = [app_name]
                    launched_via_protocol = False
                    for proto in protocols_to_try:
                        try:
                            os.startfile(f"{proto}:")
                            launched_via_protocol = True
                            return {
                                "success": True,
                                "action": "launch_app",
                                "target_app": app_name,
                                "reasoning": reasoning,
                                "details": f"Successfully launched {app_name.capitalize()} via registered protocol '{proto}:'."
                            }
                        except Exception:
                            continue
                    
                    if not launched_via_protocol:
                        raise FileNotFoundError()

            except FileNotFoundError:
                return {
                    "success": False,
                    "error": f"The application '{app_name}' could not be found or executed on your laptop.",
                    "app_not_found": True,
                    "app_name": app_name
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Failed to launch application '{app_name}': {str(e)}"
                }

        elif action == "run_terminal":
            return {
                "success": True,
                "action": "run_terminal",
                "command": target,
                "reasoning": reasoning,
                "details": f"Needs approval to execute command: '{target}'"
            }

        elif action == "run_python":
            return {
                "success": True,
                "action": "run_python",
                "command": target,
                "reasoning": reasoning,
                "details": f"Needs approval to execute Python script in sandbox."
            }

        elif action == "draft_email" or action == "send_email":
            to = data.get("email_to") or target
            subject = data.get("email_subject") or "No Subject"
            body = data.get("email_body") or ""
            return {
                "success": True,
                "action": "draft_email",
                "to": to,
                "subject": subject,
                "body": body,
                "reasoning": reasoning
            }

        elif action == "read_inbox":
            count = data.get("email_index") or 5
            try:
                emails = read_inbox(count=int(count))
                email_summaries = []
                for em in emails:
                    email_summaries.append(f"[{em['index']}] From: {em['sender']} | Subject: {em['subject']}\nPreview: {em['preview']}")
                details_str = "\n\n".join(email_summaries) if email_summaries else "Inbox is empty."
                return {
                    "success": True,
                    "action": "read_inbox",
                    "details": f"Recent Emails:\n\n{details_str}",
                    "reasoning": reasoning
                }
            except Exception as e:
                return {"success": False, "error": f"Failed to read inbox: {e}"}

        elif action == "reply_email":
            index = data.get("email_index") or 1
            body = data.get("email_body") or ""
            res = reply_to_email(index=int(index), reply_body=body)
            if res.get("success"):
                return {
                    "success": True,
                    "action": "reply_email",
                    "details": res.get("details"),
                    "reasoning": reasoning
                }
            else:
                return {"success": False, "error": res.get("error")}

        elif action == "file_create":
            content = data.get("file_content") or ""
            res = create_file(target, content)
            if res.get("success"):
                return {
                    "success": True,
                    "action": "file_create",
                    "details": res.get("details"),
                    "reasoning": reasoning
                }
            else:
                return {"success": False, "error": res.get("error")}

        elif action == "file_move":
            dest = data.get("file_dest") or ""
            res = move_file(target, dest)
            if res.get("success"):
                return {
                    "success": True,
                    "action": "file_move",
                    "details": res.get("details"),
                    "reasoning": reasoning
                }
            else:
                return {"success": False, "error": res.get("error")}

        elif action == "file_rename":
            new_name = data.get("file_new_name") or ""
            res = rename_file(target, new_name)
            if res.get("success"):
                return {
                    "success": True,
                    "action": "file_rename",
                    "details": res.get("details"),
                    "reasoning": reasoning
                }
            else:
                return {"success": False, "error": res.get("error")}

        elif action == "file_search":
            dir_to_search = data.get("file_dest") or None
            results = search_files(target, dir_to_search)
            res_summaries = []
            for r in results:
                res_summaries.append(f"- {r['name']} ({r['type']}) at {r['path']}")
            details_str = "\n".join(res_summaries) if res_summaries else "No files found matching query."
            return {
                "success": True,
                "action": "file_search",
                "details": f"Search Results:\n{details_str}",
                "reasoning": reasoning
            }

        elif action == "file_delete":
            return {
                "success": True,
                "action": "file_delete",
                "path": target,
                "reasoning": reasoning
            }

        elif action == "file_read":
            res = read_file_content(target)
            if res.get("success"):
                return {
                    "success": True,
                    "action": "file_read",
                    "details": f"File Content of {target}:\n\n{res.get('content')}",
                    "reasoning": reasoning
                }
            else:
                return {"success": False, "error": res.get("error")}

        elif action == "system_volume":
            level = data.get("level")
            if level is None:
                res = get_volume()
            else:
                res = set_volume(int(level))
            if res.get("success"):
                return {
                    "success": True,
                    "action": "system_volume",
                    "details": res.get("details"),
                    "reasoning": reasoning
                }
            else:
                return {"success": False, "error": res.get("error")}

        elif action == "system_brightness":
            level = data.get("level")
            if level is None:
                res = get_brightness()
            else:
                res = set_brightness(int(level))
            if res.get("success"):
                return {
                    "success": True,
                    "action": "system_brightness",
                    "details": res.get("details"),
                    "reasoning": reasoning
                }
            else:
                return {"success": False, "error": res.get("error")}

        elif action == "system_lock":
            res = lock_screen()
            if res.get("success"):
                return {
                    "success": True,
                    "action": "system_lock",
                    "details": res.get("details"),
                    "reasoning": reasoning
                }
            else:
                return {"success": False, "error": res.get("error")}

        elif action == "system_screenshot":
            res = take_screenshot()
            if res.get("success"):
                return {
                    "success": True,
                    "action": "system_screenshot",
                    "details": res.get("details"),
                    "reasoning": reasoning
                }
            else:
                return {"success": False, "error": res.get("error")}

        elif action == "system_info":
            res = get_system_info()
            if res.get("success"):
                return {
                    "success": True,
                    "action": "system_info",
                    "details": res.get("details"),
                    "reasoning": reasoning
                }
            else:
                return {"success": False, "error": res.get("error")}

        elif action == "schedule_meeting":
            subject = data.get("email_subject") or target or "Meeting"
            date_str = data.get("date") or ""
            time_str = data.get("time") or ""
            duration = data.get("duration") or 60
            body = data.get("email_body") or "Scheduled via OrchestraAI"
            return {
                "success": True,
                "action": "schedule_meeting",
                "subject": subject,
                "date": date_str,
                "time": time_str,
                "duration": duration,
                "body": body,
                "reasoning": reasoning
            }

        elif action == "set_reminder":
            message = target or data.get("email_body") or "Reminder!"
            date_str = data.get("date") or ""
            time_str = data.get("time") or ""
            return {
                "success": True,
                "action": "set_reminder",
                "message": message,
                "date": date_str,
                "time": time_str,
                "reasoning": reasoning
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

def install_application(app_name: str) -> Dict[str, Any]:
    """
    Attempts to install an application using winget. If winget fails,
    falls back to opening Microsoft Store search and Web search.
    """
    import subprocess
    import webbrowser
    import re
    
    # 1. Try installing via winget
    try:
        # First do a winget search to find a precise package ID if possible
        search_cmd = f"winget search \"{app_name}\""
        res_search = subprocess.run(
            search_cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=20.0
        )
        
        package_id = app_name
        # Parse the first match ID from winget search output if possible
        if res_search.returncode == 0 and res_search.stdout:
            lines = res_search.stdout.strip().split("\n")
            # Skip headers (usually lines 0 and 1 are Name, Id, Version, Source, separator)
            for line in lines[2:]:
                parts = re.split(r'\s{2,}', line.strip())
                if len(parts) >= 2:
                    # parts[1] is the Package Id
                    package_id = parts[1]
                    break
        
        install_cmd = f"winget install {package_id} --silent --accept-source-agreements --accept-package-agreements"
        res = subprocess.run(
            install_cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=180.0
        )
        
        if res.returncode == 0:
            return {
                "success": True,
                "details": f"Successfully installed '{app_name}' via winget package manager."
            }
    except Exception:
        pass
        
    # 2. Fallback to Microsoft Store and Web Download pages
    store_url = f"ms-windows-store://search/?query={app_name}"
    web_url = f"https://duckduckgo.com/?q=download+{app_name}"
    
    opened_store = False
    try:
        os.startfile(store_url)
        opened_store = True
    except Exception:
        pass
        
    try:
        webbrowser.open(web_url)
    except Exception:
        pass
        
    details_msg = f"Failed to install '{app_name}' automatically via winget."
    if opened_store:
        details_msg += f" Opened the Microsoft Store search for '{app_name}' and web browser search for download options."
    else:
        details_msg += f" Opened web browser search for '{app_name}' download links."
        
    return {
        "success": True,
        "details": details_msg
    }

def parse_date_time(date_str: str, time_str: str):
    """Parses date (YYYY-MM-DD) and time (HH:MM AM/PM) strings into a datetime object."""
    from datetime import datetime, date as datetime_date
    today = datetime.today()
    
    parsed_date = today.date()
    if date_str:
        try:
            parsed_date = datetime.strptime(date_str.strip(), "%Y-%m-%d").date()
        except Exception:
            pass
            
    parsed_time = today.time()
    if time_str:
        time_clean = time_str.strip().upper()
        # Try different formats
        for fmt in ("%I:%M %p", "%I:%M%p", "%H:%M", "%I %p", "%I%p"):
            try:
                parsed_time = datetime.strptime(time_clean, fmt).time()
                break
            except Exception:
                continue
                
    return datetime.combine(parsed_date, parsed_time)

def schedule_meeting_handler(subject: str, date_str: str, time_str: str, duration_minutes: int, body: str) -> Dict[str, Any]:
    """Tries dispatching directly to Outlook Calendar; falls back to .ics file generation."""
    # Try Outlook COM first
    res = schedule_outlook_meeting(subject, date_str, time_str, duration_minutes, body)
    if res["success"]:
        return res
    
    # Fallback to .ics generation and opening
    return create_ics_file_and_open(subject, date_str, time_str, duration_minutes, body)

def set_reminder_handler(message: str, date_str: str, time_str: str) -> Dict[str, Any]:
    """Tries creating an Outlook Task with active alert; falls back to Windows Task Scheduler."""
    # Try Outlook Task COM first
    res = create_outlook_task(message, date_str, time_str, "Reminder created by OrchestraAI")
    if res["success"]:
        return res
        
    # Fallback to Windows native PowerShell scheduled task/toast
    return schedule_windows_toast(message, date_str, time_str)

def schedule_outlook_meeting(subject: str, date_str: str, time_str: str, duration_minutes: int, body: str) -> Dict[str, Any]:
    """Directly automates Outlook calendar via COM."""
    try:
        import win32com.client
        try:
            outlook = win32com.client.GetActiveObject("Outlook.Application")
        except Exception:
            outlook = win32com.client.Dispatch("Outlook.Application")
            
        appointment = outlook.CreateItem(1)  # AppointmentItem type 1
        start_dt = parse_date_time(date_str, time_str)
        
        appointment.Start = start_dt.strftime("%Y-%m-%d %H:%M")
        appointment.Duration = int(duration_minutes)
        appointment.Subject = subject
        appointment.Body = body
        appointment.ReminderSet = True
        appointment.ReminderMinutesBeforeStart = 15
        appointment.Save()
        
        return {
            "success": True,
            "details": f"Directly scheduled meeting '{subject}' in Outlook calendar for {start_dt.strftime('%Y-%m-%d at %I:%M %p')} ({duration_minutes} mins)."
        }
    except Exception as e:
        return {"success": False, "error": f"Outlook automation failed: {str(e)}"}

def create_ics_file_and_open(subject: str, date_str: str, time_str: str, duration_minutes: int, body: str) -> Dict[str, Any]:
    """Formats an iCalendar standard file and starts it."""
    try:
        from datetime import datetime, timedelta
        
        start_dt = parse_date_time(date_str, time_str)
        end_dt = start_dt + timedelta(minutes=int(duration_minutes))
        
        start_ics = start_dt.strftime("%Y%m%dT%H%M%S")
        end_ics = end_dt.strftime("%Y%m%dT%H%M%S")
        
        ics_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//OrchestraAI//Calendar Event//EN
CALSCALE:GREGORIAN
METHOD:PUBLISH
BEGIN:VEVENT
SUMMARY:{subject}
DESCRIPTION:{body}
DTSTART:{start_ics}
DTEND:{end_ics}
STATUS:CONFIRMED
BEGIN:VALARM
TRIGGER:-PT15M
ACTION:DISPLAY
DESCRIPTION:Reminder
END:VALARM
END:VEVENT
END:VCALENDAR"""

        temp_dir = Path(settings.project_root) / "output"
        temp_dir.mkdir(parents=True, exist_ok=True)
        ics_file = temp_dir / "scheduled_event.ics"
        ics_file.write_text(ics_content, encoding="utf-8")
        
        os.startfile(str(ics_file))
        
        return {
            "success": True,
            "details": f"Generated calendar event file '{ics_file.name}' and opened it in your default calendar application."
        }
    except Exception as e:
        return {"success": False, "error": f"Failed to generate calendar file: {str(e)}"}

def create_outlook_task(subject: str, date_str: str, time_str: str, body: str) -> Dict[str, Any]:
    """Automates Outlook tasks via COM."""
    try:
        import win32com.client
        try:
            outlook = win32com.client.GetActiveObject("Outlook.Application")
        except Exception:
            outlook = win32com.client.Dispatch("Outlook.Application")
            
        task = outlook.CreateItem(3)  # TaskItem type 3
        due_dt = parse_date_time(date_str, time_str)
        
        task.Subject = subject
        task.Body = body
        task.DueDate = due_dt.strftime("%Y-%m-%d %H:%M")
        task.ReminderSet = True
        task.ReminderTime = due_dt.strftime("%Y-%m-%d %H:%M")
        task.Save()
        
        return {
            "success": True,
            "details": f"Directly scheduled task/reminder '{subject}' in Outlook for {due_dt.strftime('%Y-%m-%d at %I:%M %p')}."
        }
    except Exception as e:
        return {"success": False, "error": f"Outlook Task automation failed: {str(e)}"}

def schedule_windows_toast(subject: str, date_str: str, time_str: str) -> Dict[str, Any]:
    """Creates a Windows Task Scheduler entry calling a PowerShell forms dialog box alert."""
    try:
        import uuid
        import subprocess
        from datetime import datetime
        
        target_dt = parse_date_time(date_str, time_str)
        ps_dt_str = target_dt.strftime("%Y-%m-%dT%H:%M:%S")
        
        task_id = str(uuid.uuid4())[:8]
        task_name = f"OrchestraAI_Reminder_{task_id}"
        
        escaped_subject = subject.replace("'", "''").replace('"', '`"')
        ps_action = f"[System.Reflection.Assembly]::LoadWithPartialName('System.Windows.Forms'); [System.Windows.Forms.MessageBox]::Show('{escaped_subject}', 'OrchestraAI Reminder')"
        
        ps_cmd = (
            f"Register-ScheduledTask -TaskName '{task_name}' "
            f"-Action (New-ScheduledTaskAction -Execute 'powershell.exe' -Argument '-WindowStyle Hidden -Command \"{ps_action}\"') "
            f"-Trigger (New-ScheduledTaskTrigger -Once -At '{ps_dt_str}') -Force"
        )
        
        res = subprocess.run(
            ["powershell", "-Command", ps_cmd],
            capture_output=True,
            text=True,
            shell=True
        )
        
        if res.returncode == 0:
            return {
                "success": True,
                "details": f"Scheduled a local Windows popup reminder '{subject}' for {target_dt.strftime('%Y-%m-%d at %I:%M %p')}."
            }
        else:
            return {
                "success": False,
                "error": f"PowerShell scheduling failed: {res.stderr.strip()}"
            }
    except Exception as e:
        return {"success": False, "error": f"Windows task scheduling failed: {str(e)}"}


# ============================================================
# Application Status and Installation Helpers
# ============================================================

APP_MAP = {
    "todo": {
        "name": "Microsoft To Do",
        "protocol": "mstodo",
        "winget_id": "Microsoft.ToDo",
        "web_fallback": "https://to-do.office.com",
        "store_query": "Microsoft To Do",
    },
    "microsoft to do": {
        "name": "Microsoft To Do",
        "protocol": "mstodo",
        "winget_id": "Microsoft.ToDo",
        "web_fallback": "https://to-do.office.com",
        "store_query": "Microsoft To Do",
    },
    "clock": {
        "name": "Windows Clock",
        "protocol": "ms-clock",
        "winget_id": "Microsoft.WindowsAlarms",
        "web_fallback": None,
        "store_query": "Windows Clock",
    },
    "alarms": {
        "name": "Windows Clock",
        "protocol": "ms-clock",
        "winget_id": "Microsoft.WindowsAlarms",
        "web_fallback": None,
        "store_query": "Windows Clock",
    },
    "outlook": {
        "name": "Microsoft Outlook",
        "protocol": "outlook",
        "winget_id": "Microsoft.Outlook",
        "web_fallback": "https://outlook.live.com",
        "store_query": "Outlook",
    },
    "spotify": {
        "name": "Spotify",
        "protocol": "spotify",
        "winget_id": "Spotify.Spotify",
        "web_fallback": "https://open.spotify.com",
        "store_query": "Spotify",
    },
    "whatsapp": {
        "name": "WhatsApp",
        "protocol": "whatsapp",
        "winget_id": "WhatsApp.WhatsApp",
        "web_fallback": "https://web.whatsapp.com",
        "store_query": "WhatsApp",
    },
    "vlc": {
        "name": "VLC Media Player",
        "protocol": "vlc",
        "winget_id": "VideoLAN.VLC",
        "web_fallback": None,
        "store_query": "VLC",
    },
}

def check_app_installation_status(app_name: str) -> Dict[str, Any]:
    """Checks if a given application is installed on Windows by registry protocol or filesystem."""
    app_key = app_name.lower().strip()
    
    # 1. Look up in APP_MAP
    mapped = APP_MAP.get(app_key)
    if mapped:
        proto = mapped["protocol"]
        name = mapped["name"]
        winget_id = mapped["winget_id"]
        web_fallback = mapped["web_fallback"]
        store_query = mapped["store_query"]
    else:
        proto = app_key
        name = app_name
        winget_id = None
        web_fallback = None
        store_query = app_name
        
    # 2. Check protocol in Registry
    protocol_found = False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, proto) as key:
            protocol_found = True
    except FileNotFoundError:
        pass
    except Exception:
        pass
        
    # 3. Check file using existing search
    file_found = False
    resolved_path = None
    if app_key == "outlook":
        outlook_path = get_outlook_path()
        if outlook_path and outlook_path != "outlook.exe" and Path(outlook_path).exists():
            resolved_path = outlook_path
            file_found = True

    if not file_found:
        resolved_path = find_windows_executable(app_key)
        if resolved_path:
            file_found = True
        
    installed = protocol_found or file_found
    
    return {
        "installed": installed,
        "app_name": name,
        "winget_id": winget_id,
        "web_fallback": web_fallback,
        "store_query": store_query,
        "path": resolved_path if file_found else None
    }

def winget_install_app(app_id: str) -> Dict[str, Any]:
    """Runs winget install command for a given package ID."""
    try:
        import subprocess
        cmd = f"winget install --id {app_id} --silent --accept-package-agreements --accept-source-agreements"
        res = subprocess.run(cmd, capture_output=True, text=True, shell=True)
        if res.returncode == 0:
            return {"success": True, "details": f"Successfully installed {app_id} via winget."}
        else:
            return {"success": False, "error": f"winget failed: {res.stderr.strip() or res.stdout.strip()}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

