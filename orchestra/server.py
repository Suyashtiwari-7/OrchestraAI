"""
OrchestraAI — FastAPI Server
==============================
Backend server exposing routing, classification, memory, and tool actions
via a clean HTTP API. Serves static files for the responsive Web UI.
"""

import time
import sys
import socket
import logging

# Reconfigure stdout/stderr to UTF-8 to prevent encoding crashes on Windows console when printing emojis
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
if hasattr(sys.stderr, 'reconfigure'):
    try:
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass
from pathlib import Path
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse

from .config import (
    TaskType,
    ProviderName,
    MODELS,
    ROUTING_TABLE,
    api_keys,
    settings,
    PROJECT_ROOT,
    ENV_PATH,
)
from .classifier import TaskClassifier, ClassificationResult
from .router import ModelRouter, RoutingDecision
from .memory.session_memory import SessionMemory
from .memory.user_profile import UserProfileMemory
from .memory.extractor import InsightExtractor
from .providers.base import ProviderError
from .tools.file_manager import process_response_for_files
from .tools.web_scraper import extract_url, scrape_url, format_scraped_content
from .tools.image_saver import save_image
from .tools.system_executor import execute_system_command
from .tools.web_search import execute_web_search
from .tools.document_reader import gather_referenced_documents
from .tools.codebase_search import execute_codebase_search
from .tools.code_sandbox import execute_python_sandbox
import base64
import json

SYSTEM_COMMAND_PROMPT = """You are a system command interpreter for OrchestraAI.
Your job is to parse the user's intent to perform a local action (open browser, launch app, run terminal, run Python script, email operations, file system tasks, system settings, lock, screenshot, and info) and return a strict JSON block.

Action Types and Parameters:
1. "open_browser": target (URL). Optional browser: "brave" | "chrome" | "edge" | "default".
2. "launch_app": target (application name or command line, e.g. "notepad" or "calc" or "C:\\Windows\\notepad.exe").
3. "run_terminal": target (command to execute in cmd).
4. "run_python": target (Python code snippet to execute).
5. "draft_email" / "send_email": target (email address if specified), email_to (recipient), email_subject (subject line), email_body (body).
6. "read_inbox": email_index (number of messages to read, default 5).
7. "reply_email": email_index (index of message to reply to), email_body (reply body).
8. "file_create": target (filepath), file_content (content).
9. "file_move": target (source path), file_dest (destination path).
10. "file_rename": target (file path), file_new_name (new file name).
11. "file_search": target (query term), file_dest (optional root directory path to search).
12. "file_delete": target (filepath to delete).
13. "file_read": target (filepath to read).
14. "system_volume": level (0-100 or null to query).
15. "system_brightness": level (0-100 or null to query).
16. "system_lock": no parameters.
17. "system_screenshot": no parameters.
18. "system_info": no parameters.

Parser Priority & Agentic Scripting Rules:
- **General OS-Level Automation fallback**: For any custom, complex, or arbitrary task that does not fit a built-in action type (such as scheduling a meeting, setting system alerts, playbacks, controlling other apps, searching local files, modifying custom settings), you MUST choose "run_python" or "run_terminal" and generate a complete script/command to perform it.
- **Calendar & Meetings**: When the user requests to schedule a meeting or event, you MUST choose "schedule_meeting" action. The backend will automatically try Outlook Calendar or fall back to standard calendar event (.ics) files.
- **Reminders & Timers**: When asked to set a reminder or timer, you MUST choose the "set_reminder" action. The backend will automatically try Outlook Tasks or fall back to native Windows system scheduler alerts.
- **App Automation/Controls**: When asked to play music or search inside a specific app (e.g. Spotify, YouTube, Teams), write a script or command to open the browser search URL, or trigger the app's protocol scheme. For launching Microsoft Teams chat with a user, choose "open_browser" action with target "ms-teams:/l/chat/0/0?users=<email_address>&message=<message_body>". Since it is a protocol handler, the system will open it directly. Do not use terminal execution for Teams chat links to avoid command shell parsing errors.
- **Local App Routing**: Prioritize routing tasks to the local desktop apps listed as installed in the user profile context (e.g., Microsoft Outlook, Microsoft To Do, Brave browser, VLC, Spotify).

Response Format:
You MUST respond with a single JSON object. No markdown wrapping, no code blocks, no ```json formatting, no other explanation or text.

JSON Structure:
{
  "action": "<action_type>",
  "target": "<target_value_or_code_or_command>",
  "browser": "brave" | "chrome" | "edge" | "default" | null,
  "reasoning": "<A very simple, non-technical, human-friendly explanation of the proposed action. Do NOT use code syntax, command lines, or generic technical jargon (like 'local system', 'command prompt', or 'Windows task scheduler'). Instead, state the specific application name (e.g., 'MS To Do List', 'Outlook Calendar', 'Windows Clock'), the task description, exact dates/times, and the notification channel that will notify the user if applicable (e.g., 'via Outlook email alert', 'via desktop push notification', or 'via WhatsApp' if specified by user). For example: 'Setting up a reminder on MS To Do List for: Meeting tomorrow (June 22, 2026) at 12:00 PM, which will notify you on your laptop.' or 'Scheduling a meeting on Outlook Calendar: Sync with team on June 23 at 3:00 PM (notifies you by email).'>",
  "email_to": "<recipient_email_or_null>",
  "email_subject": "<subject_or_null>",
  "email_body": "<body_or_null>",
  "email_index": <int_or_null>,
  "file_content": "<file_content_or_null>",
  "file_dest": "<destination_path_or_null>",
  "file_new_name": "<new_name_or_null>",
  "level": <int_or_null>
}

Additional Actions available:
19. "clipboard_get": Read the current clipboard content.
20. "clipboard_set": target (text to copy to clipboard).
21. "screenshot_vision": Takes a screenshot and analyzes it with the AI vision model. target (optional question about the screenshot).
22. "system_power_mode": target ("saver", "balanced", or "high"). Set the Windows power plan.
"""

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("orchestra.server")

# Initialize components
classifier = TaskClassifier()
router = ModelRouter()
memory = SessionMemory()
profile_memory = UserProfileMemory(db=memory.db)
extractor = InsightExtractor(db=memory.db, router=router)
extractor.start_background_timer()  # Batch extraction every 5 minutes during idle



try:
    from .voice.tts_engine import TTSEngine
    tts_engine = TTSEngine(
        voice_name="af_heart",
        edge_voice=settings.voice_name or "en-US-GuyNeural",
    )
    _voice_enabled = settings.voice_enabled
    logger.info(f"Speech Engine (TTS) initialized (voice={settings.voice_name}, enabled={settings.voice_enabled}).")
except Exception as e:
    logger.error(f"Speech Engine (TTS) init failed: {e}")
    tts_engine = None
    _voice_enabled = False

# --- Initialize Autonomous Cybersecurity (EDR) Manager ---
try:
    from .security.security_manager import SecurityManager
    security_manager = SecurityManager(
        on_voice_alert=lambda msg: tts_engine.speak_text_async(msg) if tts_engine and _voice_enabled else None
    )
    security_manager.start()
    logger.info("Autonomous Cybersecurity (EDR) Manager started.")
except Exception as e:
    logger.error(f"Security Manager init failed: {e}")
    security_manager = None

# --- Initialize Proactive Executive Assistant Engine ---
try:
    from .assistant.proactive_engine import ProactiveEngine
    proactive_engine = ProactiveEngine(
        router=router,
        on_voice_alert=lambda msg: tts_engine.speak_text_async(msg) if tts_engine and _voice_enabled else None
    )
    proactive_engine.start()
    logger.info("Proactive Executive Assistant Engine started.")
except Exception as e:
    logger.error(f"Proactive Engine init failed: {e}")
    proactive_engine = None

# Auto-scan installed apps and save to user profile facts
try:
    from .tools.system_executor import check_app_installation_status, get_browser_path
    
    app_keys_to_scan = {
        "outlook": "Microsoft Outlook desktop app",
        "todo": "Microsoft To Do desktop app",
        "spotify": "Spotify app",
        "whatsapp": "WhatsApp app",
        "vlc": "VLC Media Player app"
    }
    for app_key, display_name in app_keys_to_scan.items():
        try:
            status = check_app_installation_status(app_key)
            if status.get("installed"):
                profile_memory.add_fact(f"{display_name} is installed on this machine.")
            else:
                if f"{display_name} is installed on this machine." in profile_memory._facts:
                    profile_memory._facts.remove(f"{display_name} is installed on this machine.")
                    profile_memory._save()
        except Exception:
            pass
            
    browsers_to_scan = ["brave", "chrome", "edge"]
    for browser in browsers_to_scan:
        try:
            browser_path = get_browser_path(browser)
            display_name = f"{browser.capitalize()} browser"
            if browser == "brave":
                display_name = "Brave browser"
            if browser_path:
                profile_memory.add_fact(f"{display_name} is installed on this machine.")
            else:
                if f"{display_name} is installed on this machine." in profile_memory._facts:
                    profile_memory._facts.remove(f"{display_name} is installed on this machine.")
                    profile_memory._save()
        except Exception:
            pass
except Exception as e:
    logger.error(f"Error scanning installed apps on startup: {e}")

app = FastAPI(
    title="OrchestraAI Server",
    description="Web server API for multi-model AI routing",
    version="1.0.0",
)

# Enable CORS for local network and cross-origin debugging
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Request/Response Models ---

class ChatRequest(BaseModel):
    prompt: str
    provider_override: Optional[str] = None  # e.g. "gemini", "groq", "cerebras"

class ExecuteCommandRequest(BaseModel):
    command: str

class ExecuteSandboxRequest(BaseModel):
    code: str

class InstallAppRequest(BaseModel):
    app_id: str

class HistoryItemActionRequest(BaseModel):
    timestamp: str


class EmailDraftRequest(BaseModel):
    to: str
    subject: str
    body: str
    cc: Optional[str] = ""
    bcc: Optional[str] = ""

class EmailSendRequest(BaseModel):
    to: str
    subject: str
    body: str
    cc: Optional[str] = ""
    bcc: Optional[str] = ""
    smtp_server: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_email: Optional[str] = None
    smtp_password: Optional[str] = None

class EmailReplyRequest(BaseModel):
    index: int
    reply_body: str
    reply_all: Optional[bool] = False

class FileCreateRequest(BaseModel):
    path: str
    content: Optional[str] = ""

class FileMoveRequest(BaseModel):
    source: str
    destination: str

class FileRenameRequest(BaseModel):
    path: str
    new_name: str

class FileDeleteRequest(BaseModel):
    path: str

class VolumeSetRequest(BaseModel):
    level: int

class BrightnessSetRequest(BaseModel):
    level: int

class InstallAppRequest(BaseModel):
    app_name: str

class MeetingScheduleRequest(BaseModel):
    subject: str
    date: str
    time: str
    duration: int = 60
    body: str = ""

class ReminderSetRequest(BaseModel):
    message: str
    date: str
    time: str

class ChatResponse(BaseModel):
    success: bool
    content: str
    task_type: str
    classification_confidence: float
    classification_reasoning: str
    model_used: str
    provider_used: str
    latency_ms: float
    used_fallback: bool
    image_url: Optional[str] = None
    saved_files: List[str] = []
    options: Optional[List[Dict[str, str]]] = []

class SaveKeysRequest(BaseModel):
    nvidia_nim_api_key: Optional[str] = None
    groq_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None

# --- API Endpoints ---

@app.get("/api/keys")
def get_api_keys():
    """Retrieve masked API key statuses for UI configuration."""
    def mask_key(k: Optional[str]) -> str:
        if not k or len(k) < 8:
            return ""
        return k[:4] + "•" * 12 + k[-4:]

    return {
        "nvidia_nim_configured": bool(api_keys.nvidia_nim_api_key),
        "groq_configured": bool(api_keys.groq_api_key),
        "gemini_configured": bool(api_keys.gemini_api_key),
        "nvidia_nim_masked": mask_key(api_keys.nvidia_nim_api_key),
        "groq_masked": mask_key(api_keys.groq_api_key),
        "gemini_masked": mask_key(api_keys.gemini_api_key),
    }

@app.post("/api/keys")
def save_api_keys(req: SaveKeysRequest):
    """Save provided API keys to .env file and active runtime config."""
    import os
    env_file = ENV_PATH if ENV_PATH.exists() else (PROJECT_ROOT / ".env")
    
    # Read existing .env lines
    existing_lines = []
    if env_file.exists():
        existing_lines = env_file.read_text(encoding="utf-8").splitlines()
        
    key_dict = {}
    for line in existing_lines:
        line_clean = line.strip()
        if line_clean and not line_clean.startswith("#") and "=" in line_clean:
            k, v = line_clean.split("=", 1)
            key_dict[k.strip()] = v.strip()
            
    updated = []
    if req.nvidia_nim_api_key is not None and req.nvidia_nim_api_key.strip():
        val = req.nvidia_nim_api_key.strip()
        api_keys.nvidia_nim_api_key = val
        key_dict["NVIDIA_NIM_API_KEY"] = val
        os.environ["NVIDIA_NIM_API_KEY"] = val
        updated.append("NVIDIA NIM")
        
    if req.groq_api_key is not None and req.groq_api_key.strip():
        val = req.groq_api_key.strip()
        api_keys.groq_api_key = val
        key_dict["GROQ_API_KEY"] = val
        os.environ["GROQ_API_KEY"] = val
        updated.append("Groq")
        
    if req.gemini_api_key is not None and req.gemini_api_key.strip():
        val = req.gemini_api_key.strip()
        api_keys.gemini_api_key = val
        key_dict["GEMINI_API_KEY"] = val
        os.environ["GEMINI_API_KEY"] = val
        updated.append("Gemini")

    # Reconstruct .env content
    out_lines = [
        "# ============================================",
        "# OrchestraAI / DARKI — Environment Config",
        "# ============================================",
        "",
    ]
    for k, v in key_dict.items():
        out_lines.append(f"{k}={v}")
        
    env_file.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    
    # Re-initialize router provider states
    try:
        router.reinitialize_providers()
    except Exception:
        pass
        
    return {
        "status": "success",
        "message": f"Successfully updated {', '.join(updated) if updated else 'keys'} in .env!",
        "configured": {
            "nvidia_nim": bool(api_keys.nvidia_nim_api_key),
            "groq": bool(api_keys.groq_api_key),
            "gemini": bool(api_keys.gemini_api_key),
        }
    }

@app.get("/api/status")
def get_status():
    """Check API key configurations and provider health."""
    key_status = api_keys.validate()
    # Skip health_check_all() — it makes real API calls to all providers
    # which blocks page load for 30-60s when providers are rate-limited or dead.
    # Instead, report status based on API key configuration.
    
    providers = []
    display_names = {
        "nvidia_nim": "NVIDIA NIM",
        "groq": "Groq",
        "gemini": "Gemini",
        "ollama": "Local Ollama",
    }
    for provider in ProviderName:
        is_configured = key_status.get(provider, False)
        providers.append({
            "name": provider.value,
            "display_name": display_names.get(provider.value, provider.value.capitalize()),
            "configured": is_configured,
            "healthy": is_configured,  # Assume healthy if configured; failures show on actual use
        })
        
    return {
        "app_name": settings.app_name,
        "version": settings.app_version,
        "tagline": settings.app_tagline,
        "providers": providers,
        "local_ip": get_local_ip(),
    }

@app.get("/api/models")
def get_models():
    """Retrieve model routing table configuration."""
    routes = []
    for task_type, route in ROUTING_TABLE.items():
        primary = MODELS[route.primary]
        fallback = MODELS[route.fallback]
        routes.append({
            "task_type": task_type.value,
            "description": route.description,
            "primary_model": primary.display_name,
            "primary_provider": primary.provider.value,
            "fallback_model": fallback.display_name,
            "fallback_provider": fallback.provider.value,
        })
    return {"routes": routes}

@app.get("/api/history")
def get_history(limit: int = 50):
    """Get conversation history for the current session."""
    entries = []
    for entry in memory.get_full_history(limit=limit):
        entries.append({
            "role": entry.role,
            "content": entry.content,
            "model_used": entry.model_used,
            "provider": entry.provider,
            "task_type": entry.task_type,
            "timestamp": entry.timestamp,
            "keep": getattr(entry, "keep", False),
        })
    return {"history": entries}

@app.get("/api/profile")
def get_profile():
    """Retrieve user facts and name from local memory."""
    name = "Alex"
    for fact in profile_memory._facts:
        if fact.lower().startswith("my name is "):
            name = fact[11:].strip()
            break
    return {
        "name": name,
        "facts": profile_memory._facts
    }


@app.post("/api/clear")
def clear_history():
    """Clear conversation history."""
    memory.clear()
    return {"success": True, "message": "Conversation history cleared."}

@app.post("/api/history/delete")
def delete_history_item(req: HistoryItemActionRequest):
    """Delete a specific chat turn by its user message timestamp."""
    success = memory.delete_turn(req.timestamp)
    if not success:
        raise HTTPException(status_code=404, detail="Chat history item not found.")
    return {"success": True, "message": "Chat history item deleted."}

@app.post("/api/history/toggle_keep")
def toggle_keep_history_item(req: HistoryItemActionRequest):
    """Toggle the keep/pinned flag for a specific chat turn."""
    toggled_status = memory.toggle_keep(req.timestamp)
    if toggled_status is None:
        raise HTTPException(status_code=404, detail="Chat history item not found.")
    return {
        "success": True, 
        "keep": toggled_status, 
        "message": f"Chat history item keep state set to {toggled_status}."
    }

@app.post("/api/email/draft")
def api_draft_email(req: EmailDraftRequest):
    from .tools.email_handler import draft_email
    res = draft_email(req.to, req.subject, req.body, req.cc, req.bcc)
    if not res.get("success"):
        raise HTTPException(status_code=500, detail=res.get("error"))
    return res

@app.post("/api/email/send")
def api_send_email(req: EmailSendRequest):
    from .tools.email_handler import send_email
    res = send_email(
        req.to, req.subject, req.body, req.cc, req.bcc,
        smtp_server=req.smtp_server,
        smtp_port=req.smtp_port,
        smtp_email=req.smtp_email,
        smtp_password=req.smtp_password
    )
    if not res.get("success"):
        raise HTTPException(status_code=500, detail=res.get("error"))
    return res

@app.get("/api/email/inbox")
def api_read_inbox(count: int = 5):
    from .tools.email_handler import read_inbox
    return read_inbox(count)

@app.post("/api/email/reply")
def api_reply_email(req: EmailReplyRequest):
    from .tools.email_handler import reply_to_email
    res = reply_to_email(req.index, req.reply_body, req.reply_all)
    if not res.get("success"):
        raise HTTPException(status_code=500, detail=res.get("error"))
    return res

@app.post("/api/calendar/schedule")
def api_schedule_meeting(req: MeetingScheduleRequest):
    from .tools.system_executor import schedule_meeting_handler
    res = schedule_meeting_handler(req.subject, req.date, req.time, req.duration, req.body)
    if not res.get("success"):
        raise HTTPException(status_code=500, detail=res.get("error"))
    return res

@app.post("/api/calendar/reminder")
def api_set_reminder(req: ReminderSetRequest):
    from .tools.system_executor import set_reminder_handler
    res = set_reminder_handler(req.message, req.date, req.time)
    if not res.get("success"):
        raise HTTPException(status_code=500, detail=res.get("error"))
    return res

@app.get("/api/system/check_app")
def api_check_app(app_name: str):
    from .tools.system_executor import check_app_installation_status
    return check_app_installation_status(app_name)




@app.post("/api/files/create")
def api_create_file(req: FileCreateRequest):
    from .tools.file_manager import create_file
    res = create_file(req.path, req.content)
    if not res.get("success"):
        raise HTTPException(status_code=500, detail=res.get("error"))
    return res

@app.get("/api/files/search")
def api_search_files(query: str, directory: Optional[str] = None):
    from .tools.file_manager import search_files
    return search_files(query, directory)

@app.post("/api/files/delete")
def api_delete_file(req: FileDeleteRequest):
    from .tools.file_manager import delete_file
    res = delete_file(req.path)
    if not res.get("success"):
        raise HTTPException(status_code=500, detail=res.get("error"))
    return res

@app.post("/api/system/volume")
def api_set_volume(req: VolumeSetRequest):
    from .tools.system_control import set_volume
    res = set_volume(req.level)
    if not res.get("success"):
        raise HTTPException(status_code=500, detail=res.get("error"))
    return res

@app.get("/api/system/volume")
def api_get_volume():
    from .tools.system_control import get_volume
    res = get_volume()
    if not res.get("success"):
        raise HTTPException(status_code=500, detail=res.get("error"))
    return res

@app.post("/api/system/brightness")
def api_set_brightness(req: BrightnessSetRequest):
    from .tools.system_control import set_brightness
    res = set_brightness(req.level)
    if not res.get("success"):
        raise HTTPException(status_code=500, detail=res.get("error"))
    return res

@app.get("/api/system/brightness")
def api_get_brightness():
    from .tools.system_control import get_brightness
    res = get_brightness()
    if not res.get("success"):
        raise HTTPException(status_code=500, detail=res.get("error"))
    return res

@app.post("/api/system/lock")
def api_lock_screen():
    from .tools.system_control import lock_screen
    res = lock_screen()
    if not res.get("success"):
        raise HTTPException(status_code=500, detail=res.get("error"))
    return res

@app.post("/api/system/screenshot")
def api_take_screenshot():
    from .tools.system_control import take_screenshot
    res = take_screenshot()
    if not res.get("success"):
        raise HTTPException(status_code=500, detail=res.get("error"))
    filepath = Path(res.get("path"))
    filename = filepath.name
    res["image_url"] = f"/output/images/{filename}"
    return res

@app.get("/api/system/info")
def api_get_system_info():
    from .tools.system_control import get_system_info
    return get_system_info()


# --- JARVIS Context & Telemetry Endpoints ---

@app.get("/api/context/active_window")
def api_active_window():
    """Get the currently focused window title and process."""
    from .tools.system_control import get_active_window_details
    return get_active_window_details()

@app.get("/api/telemetry")
def api_telemetry():
    """Get live hardware diagnostics: CPU, RAM, disk, battery."""
    from .tools.system_control import get_live_telemetry
    return get_live_telemetry()

@app.get("/api/clipboard")
def api_clipboard_get():
    """Read the current clipboard content."""
    from .tools.system_control import clipboard_get
    return clipboard_get()

class ClipboardSetRequest(BaseModel):
    text: str

@app.post("/api/clipboard")
def api_clipboard_set(req: ClipboardSetRequest):
    """Write text to the clipboard."""
    from .tools.system_control import clipboard_set
    return clipboard_set(req.text)

class SpeakRequest(BaseModel):
    text: str

@app.post("/api/voice/speak")
def api_voice_speak(req: SpeakRequest):
    """Speak the given text aloud using the TTS engine."""
    if tts_engine is None:
        return {"success": False, "error": "Speech engine not initialized."}
    tts_engine.speak_text_async(req.text)
    return {"success": True, "message": "Speaking..."}

@app.post("/api/voice/toggle")
def api_voice_toggle():
    """Toggle voice feedback on/off."""
    global _voice_enabled
    _voice_enabled = not _voice_enabled
    return {"success": True, "enabled": _voice_enabled}

@app.post("/api/voice/interrupt")
def api_voice_interrupt():
    """Interrupt and stop any currently playing TTS audio immediately."""
    if tts_engine:
        tts_engine.interrupt()
    return {"success": True, "message": "Voice playback interrupted."}



# --- Cybersecurity (EDR) Endpoints ---

@app.get("/api/security/audit")
def api_security_audit():
    """Run an on-demand comprehensive endpoint security audit."""
    if security_manager is None:
        return {"status": "UNAVAILABLE", "error": "Security manager not running."}
    return security_manager.run_full_audit()

@app.get("/api/security/incidents")
def api_security_incidents():
    """Get list of recorded security incidents."""
    if security_manager is None:
        return {"incidents": []}
    return {"incidents": security_manager.get_incidents()}

@app.post("/api/security/isolate")
def api_security_isolate():
    """Trigger emergency network kill-switch."""
    if security_manager is None:
        return {"success": False, "error": "Security manager not running."}
    return security_manager.network.isolate_network()

@app.post("/api/security/restore")
def api_security_restore():
    """Restore normal network connectivity."""
    if security_manager is None:
        return {"success": False, "error": "Security manager not running."}
    return security_manager.network.restore_network()

# --- Proactive Executive Assistant Endpoints ---

@app.get("/api/assistant/reminders")
def api_assistant_reminders():
    """Get list of scheduled reminders."""
    if proactive_engine is None:
        return {"reminders": []}
    return {"reminders": proactive_engine.get_all_reminders()}

class AddVIPRequest(BaseModel):
    name: str
    relationship: str = "VIP"

@app.post("/api/assistant/vip")
def api_assistant_add_vip(req: AddVIPRequest):
    """Add contact to Tier 1 VIP whitelist."""
    if proactive_engine is None:
        return {"success": False, "error": "Assistant engine not running."}
    proactive_engine.vip_filter.add_vip(req.name, req.relationship)
    return {"success": True, "message": f"Added {req.name} to VIP contacts."}

@app.get("/api/assistant/vip-feed")
def api_assistant_vip_feed():
    """Get live feed of VIP and high-priority messages."""
    if proactive_engine is None:
        return {"vip_contacts": [], "recent_alerts": []}
    return {
        "vip_contacts": [
            {"name": name, "relationship": rel}
            for name, rel in proactive_engine.vip_filter.vip_contacts.items()
        ],
        "recent_alerts": getattr(proactive_engine, "_recent_alerts", [])
    }

@app.get("/api/assistant/briefing")
def api_assistant_morning_briefing(city: Optional[str] = "Indore"):
    """Get the daily executive morning briefing text."""
    try:
        from .assistant.morning_briefing import MorningBriefing
        briefing = MorningBriefing(city=city, user_name=settings.user_name or "Suyash")
        script = briefing.generate_briefing_text()
        return {"success": True, "briefing_text": script}
    except Exception as e:
        return {"success": False, "error": str(e)}

# --- Task Kill-Switch / Cancellation Endpoint ---
_current_agent_exec = None

@app.post("/api/task/cancel")
def api_cancel_current_task():
    """Immediately stop/cancel the active agentic or background task."""
    global _current_agent_exec
    if _current_agent_exec:
        _current_agent_exec.cancel()
        logger.info("Server: Task cancellation signal dispatched to active executor.")
        return {"success": True, "message": "Cancellation signal sent."}
    return {"success": False, "message": "No active task running."}

@app.post("/api/system/install_app")
def api_install_app(req: InstallAppRequest):
    from .tools.system_executor import install_application
    return install_application(req.app_name)

@app.post("/api/terminal/execute")
def execute_terminal_command(request: ExecuteCommandRequest):
    """Execute a local terminal command after user approval."""
    import subprocess
    cmd = request.command.strip()
    if not cmd:
        raise HTTPException(status_code=400, detail="Command cannot be empty.")
        
    # Basic sanitization against destructive commands
    dangerous_commands = ["format", "del /s", "rm -rf", "reg delete", "shutdown", "diskpart"]
    cmd_lower = cmd.lower()
    if any(danger in cmd_lower for danger in dangerous_commands):
        return {
            "success": False,
            "stdout": "",
            "stderr": "Command blocked for safety reasons.",
            "returncode": -1,
            "formatted_output": f"❌ **Command Blocked**: The command `{cmd}` was blocked because it contains potentially destructive operations."
        }
        
    try:
        # Run command in the project root directory
        res = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30.0,
            cwd=str(settings.project_root)
        )
        
        output = res.stdout if res.returncode == 0 else res.stderr
        if not output:
            output = res.stderr if res.stderr else "[Command executed successfully with no output]"
            
        success = res.returncode == 0
        response_text = f"💻 **Terminal Output for `{cmd}`**:\n\n```\n{output.strip()}\n```"
        
        # Add to history
        memory.add_assistant_message(
            content=response_text,
            model_used="System Shell",
            provider="localhost",
            task_type="system_command"
        )
        
        return {
            "success": success,
            "stdout": res.stdout.strip(),
            "stderr": res.stderr.strip(),
            "returncode": res.returncode,
            "formatted_output": response_text
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "stdout": "",
            "stderr": "Command execution timed out (30 seconds limit exceeded).",
            "returncode": -1,
            "formatted_output": "❌ **Command execution timed out (30s limit).**"
        }
    except Exception as e:
        return {
            "success": False,
            "stdout": "",
            "stderr": str(e),
            "returncode": -2,
            "formatted_output": f"❌ **Command failed to run**: {str(e)}"
        }

@app.get("/api/codebase/search")
def search_codebase(q: str, limit: int = 5):
    """Search the local codebase using hybrid vector/keyword search."""
    results = execute_codebase_search(q, limit=limit)
    return {"results": results}

@app.post("/api/sandbox/execute")
def execute_sandbox(request: ExecuteSandboxRequest):
    """Run Python code inside the local sandbox subprocess."""
    code = request.code.strip()
    if not code:
        raise HTTPException(status_code=400, detail="Code cannot be empty.")
    res = execute_python_sandbox(code)
    
    success = res.get("success", False)
    output = res.get("output", "")
    response_text = f"🐍 **Python Sandbox Output**:\n\n```\n{output}\n```"
    
    # Add to history
    memory.add_assistant_message(
        content=response_text,
        model_used="Python Sandbox",
        provider="localhost",
        task_type="system_command"
    )
    
    return {
        "success": success,
        "output": output,
        "stdout": res.get("stdout", ""),
        "stderr": res.get("stderr", ""),
        "formatted_output": response_text
    }

@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    """Classify and route the user prompt, invoking fallbacks & tools as needed."""
    user_input = request.prompt.strip()
    if not user_input:
        raise HTTPException(status_code=400, detail="Prompt cannot be empty.")

    # Scan user prompt for profile memory facts
    profile_memory.extract_facts(user_input)

    start_time = time.time()
    
    # 1. Handle command shortcuts
    lower_input = user_input.lower()
    
    # Detect manual provider override in command or API field
    provider_override = request.provider_override
    clean_input = user_input
    
    if lower_input.startswith("@gemini "):
        provider_override = "gemini"
        clean_input = user_input[8:].strip()
    elif lower_input.startswith("@groq "):
        provider_override = "groq"
        clean_input = user_input[6:].strip()
    elif lower_input.startswith("@mistral "):
        provider_override = "mistral"
        clean_input = user_input[9:].strip()
    elif lower_input.startswith("@ollama "):
        provider_override = "ollama"
        clean_input = user_input[8:].strip()
    elif lower_input.startswith("@xai ") or lower_input.startswith("@grok "):
        provider_override = "xai"
        prefix_len = 5 if lower_input.startswith("@xai ") else 6
        clean_input = user_input[prefix_len:].strip()

    # Save user input before context injection for classification
    classification_prompt = clean_input

    # 1.5 Scan for local document references in prompt and inject content as context
    referenced_docs = gather_referenced_documents(clean_input, settings.project_root)
    if referenced_docs:
        doc_contexts = []
        for doc in referenced_docs:
            doc_contexts.append(
                f"--- File Content: {doc['filename']} ({doc['type'].upper()}) ---\n"
                f"{doc['content']}\n"
                f"--- End of File Content: {doc['filename']} ---"
            )
        combined_docs_text = "\n\n".join(doc_contexts)
        clean_input = (
            f"Here is the local file content context:\n\n"
            f"{combined_docs_text}\n\n"
            f"Please refer to the above file contents when answering the following prompt:\n"
            f"{clean_input}"
        )

    # 1.6 Scan for codebase RAG search requests (explicit slash commands or auto-detected keywords)
    is_rag_search = False
    search_query = clean_input
    
    if lower_input.startswith("/rag ") or lower_input.startswith("/searchcode "):
        is_rag_search = True
        if lower_input.startswith("/rag "):
            search_query = clean_input[5:].strip()
        else:
            search_query = clean_input[12:].strip()
    else:
        # Auto-detect general queries about project structure
        codebase_keywords = [
            "explain the codebase", "explain the project", "explain this project",
            "project structure", "whole project", "codebase structure", 
            "explain codebase", "search codebase for", "search code for"
        ]
        is_rag_search = any(k in lower_input for k in codebase_keywords)
        
    if is_rag_search:
        search_res = execute_codebase_search(search_query, limit=4)
        if search_res:
            context_parts = []
            for r in search_res:
                context_parts.append(
                    f"--- File: {r['rel_path']} (Similarity Score: {r['score']}, Match: {r['type'].upper()}) ---\n"
                    f"{r['content']}\n"
                    f"--- End File: {r['rel_path']} ---"
                )
            combined_context = "\n\n".join(context_parts)
            
            clean_input = (
                f"The user is asking a question about the project codebase. Here is the relevant code context retrieved from search:\n\n"
                f"{combined_context}\n\n"
                f"Please synthesize this codebase context to answer the user query accurately:\n"
                f"{search_query}"
            )
            # Override task type to CODE_GENERATION for proper codestral routing if not overridden by provider
            if not provider_override:
                classification = ClassificationResult(
                    task_type=TaskType.CODE_GENERATION,
                    confidence=1.0,
                    reasoning="Local Codebase RAG context injected",
                    raw_input=clean_input,
                )

    # 2. Classify task (with potential provider override config mapping)
    if provider_override:
        # Determine appropriate task type based on keyword, otherwise generic
        if "write code" in classification_prompt.lower() or "function" in classification_prompt.lower():
            t_type = TaskType.CODE_GENERATION
        else:
            t_type = TaskType.GENERAL
            
        classification = ClassificationResult(
            task_type=t_type,
            confidence=1.0,
            reasoning=f"Forced routing override to provider: {provider_override}",
            raw_input=classification_prompt,
        )
    else:
        classification = classifier.classify(classification_prompt)

    # 3. Handle Special Web Scrape Task
    if classification.task_type == TaskType.WEB_SCRAPE or lower_input.startswith("/scrape "):
        url = extract_url(classification_prompt)
        if not url:
            return ChatResponse(
                success=False,
                content="No valid URL found in scrape request.",
                task_type=TaskType.WEB_SCRAPE.value,
                classification_confidence=1.0,
                classification_reasoning="Failed to extract URL.",
                model_used="",
                provider_used="",
                latency_ms=0.0,
                used_fallback=False,
            )
            
        scrape_res = scrape_url(url)
        if not scrape_res["success"]:
            return ChatResponse(
                success=False,
                content=f"Web scraping failed: {scrape_res['error']}",
                task_type=TaskType.WEB_SCRAPE.value,
                classification_confidence=1.0,
                classification_reasoning="Scraping error.",
                model_used="",
                provider_used="",
                latency_ms=0.0,
                used_fallback=False,
            )
            
        formatted_prompt = format_scraped_content(scrape_res)
        classification = ClassificationResult(
            task_type=TaskType.WEB_SCRAPE,
            confidence=1.0,
            reasoning="Web scrape summarizing",
            raw_input=formatted_prompt,
        )
        clean_input = formatted_prompt

    # 3.5 Handle Web Search Task
    if classification.task_type == TaskType.WEB_SEARCH or lower_input.startswith("/search "):
        search_query = clean_input
        if search_query.lower().startswith("/search "):
            search_query = search_query[8:].strip()
            
        search_res = execute_web_search(search_query)
        if search_res["success"]:
            formatted_search_prompt = (
                f"The user wants information requiring a real-time web search.\n"
                f"Search Query: {search_query}\n\n"
                f"Here is the context scraped from the top search results:\n\n"
                f"{search_res['context_text']}\n\n"
                f"Please synthesize this search context to write a highly detailed, helpful, and accurate response to the user's query.\n"
                f"Include mentions of the source URLs/titles as references in your response.\n\n"
                f"User Query: {search_query}"
            )
            classification = ClassificationResult(
                task_type=TaskType.WEB_SEARCH,
                confidence=1.0,
                reasoning="DuckDuckGo Search Grounded Context",
                raw_input=formatted_search_prompt,
            )
            clean_input = formatted_search_prompt

    # 3.8 Handle Agentic Chains (Multi-Step Execution)
    if classification.task_type == TaskType.AGENTIC_CHAIN or lower_input.startswith("/agent "):
        goal = clean_input
        if goal.lower().startswith("/agent "):
            goal = goal[7:].strip()

        # Add user prompt to memory
        memory.add_user_message(f"/agent {goal}")

        try:
            global _current_agent_exec
            from .tools.agentic_executor import AgenticExecutor
            agent_exec = AgenticExecutor(router)
            _current_agent_exec = agent_exec
            
            # Gather profile memory system context
            from datetime import datetime
            now_str = datetime.now().strftime("%Y-%m-%d %I:%M %p (%A)")
            sys_context = profile_memory.get_system_context(goal) or ""
            full_context = f"Current Time: {now_str}\n{sys_context}"
            
            response_text, options = agent_exec.execute_chain(goal, system_context=full_context)
            options = options or []
            latency = (time.time() - start_time) * 1000
            _current_agent_exec = None

            # Default model used info
            model_used = MODELS[ROUTING_TABLE[TaskType.AGENTIC_CHAIN].primary].display_name
            provider_used = MODELS[ROUTING_TABLE[TaskType.AGENTIC_CHAIN].primary].provider.value

            memory.add_assistant_message(
                content=response_text,
                model_used=model_used,
                provider=provider_used,
                task_type="agentic_chain",
            )

            return ChatResponse(
                success=True,
                content=response_text,
                task_type=TaskType.AGENTIC_CHAIN.value,
                classification_confidence=classification.confidence,
                classification_reasoning=classification.reasoning,
                model_used=model_used,
                provider_used=provider_used,
                latency_ms=latency,
                used_fallback=False,
                options=options,
            )
        except Exception as e:
            logger.error(f"Agentic chain execution failed: {e}")
            latency = (time.time() - start_time) * 1000
            return ChatResponse(
                success=False,
                content=f"⚠️ **Agentic Chain Failed**: {str(e)}",
                task_type=TaskType.AGENTIC_CHAIN.value,
                classification_confidence=1.0,
                classification_reasoning="Agentic loop execution encountered an error.",
                model_used="",
                provider_used="",
                latency_ms=latency,
                used_fallback=False,
                options=[],
            )

    # 4. Handle Image Generation
    if classification.task_type == TaskType.IMAGE_GENERATION or lower_input.startswith("/image "):
        image_prompt = clean_input
        if image_prompt.lower().startswith("/image "):
            image_prompt = image_prompt[7:].strip()
            
        try:
            image_result, decision = router.route_image(image_prompt)
            # Save the image
            saved_path = save_image(image_result)
            filename = Path(saved_path).name
            latency = (time.time() - start_time) * 1000
            
            # Form image static path (FastAPI will serve output/images)
            image_url = f"/output/images/{filename}"
            
            response_text = f"Successfully generated your image based on prompt: *\"{image_prompt}\"*."
            
            # Add to memory
            memory.add_user_message(f"/image {image_prompt}")
            memory.add_assistant_message(
                content=response_text,
                model_used=decision.model_actually_used,
                provider=decision.provider_actually_used,
                task_type="image_generation",
            )
            
            return ChatResponse(
                success=True,
                content=response_text,
                task_type=TaskType.IMAGE_GENERATION.value,
                classification_confidence=1.0,
                classification_reasoning="Image generation request successfully executed.",
                model_used=decision.model_actually_used,
                provider_used=decision.provider_actually_used,
                latency_ms=latency,
                used_fallback=decision.used_fallback,
                image_url=image_url,
            )
        except Exception as e:
            logger.error(f"Image generation failed: {e}")
            return ChatResponse(
                success=False,
                content=f"⚠️ **Image Generation Failed**: {str(e)}\n\n*Note: Image generation requires a working Google Gemini API key. Please check your Gemini API key quota at [Google AI Studio](https://aistudio.google.com/apikey).*",
                task_type=TaskType.IMAGE_GENERATION.value,
                classification_confidence=1.0,
                classification_reasoning="Image generation failed due to API credentials/quota limit.",
                model_used="Imagen 3",
                provider_used="gemini",
                latency_ms=(time.time() - start_time) * 1000,
                used_fallback=False,
            )

    # 4.5 Handle System Commands
    if classification.task_type == TaskType.SYSTEM_COMMAND or lower_input.startswith("/system ") or lower_input.startswith("/open "):
        cmd_prompt = clean_input
        if cmd_prompt.lower().startswith("/system "):
            cmd_prompt = cmd_prompt[8:].strip()
        elif cmd_prompt.lower().startswith("/open "):
            cmd_prompt = cmd_prompt[6:].strip()

        # Add user prompt to memory
        memory.add_user_message(f"/system {cmd_prompt}")

        try:
            from datetime import datetime
            now_str = datetime.now().strftime("%Y-%m-%d %I:%M %p (%A)")
            sys_context = profile_memory.get_system_context(cmd_prompt)
            dynamic_system_prompt = SYSTEM_COMMAND_PROMPT + f"\n\nContext: The current local time on the user's machine is: {now_str}."
            if sys_context:
                dynamic_system_prompt += sys_context

            result, decision = router.route_text(
                prompt=f"Parse this system action request:\n\n{cmd_prompt}",
                classification=classification,
                system_prompt=dynamic_system_prompt,
                history=None
            )
            
            exec_res = execute_system_command(result.content)
            latency = (time.time() - start_time) * 1000

            if exec_res.get("success"):
                if exec_res.get("action") == "run_terminal":
                    import subprocess
                    cmd = exec_res.get('command', '')
                    try:
                        res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30.0, cwd=str(settings.project_root))
                        output = res.stdout if res.returncode == 0 else res.stderr
                        if not output:
                            output = res.stderr if res.stderr else "[Command executed successfully with no output]"
                        response_text = f"💻 **Terminal Output for `{cmd}`**:\n\n```\n{output.strip()}\n```"
                    except Exception as e:
                        response_text = f"⚠️ **Terminal execution failed**: {str(e)}"
                        
                elif exec_res.get("action") == "run_python":
                    import subprocess, tempfile, os
                    code = exec_res.get('command', '')
                    try:
                        fd, path = tempfile.mkstemp(suffix=".py")
                        with open(fd, 'w', encoding='utf-8') as f:
                            f.write(code)
                        res = subprocess.run(["python", path], capture_output=True, text=True, timeout=30.0, cwd=str(settings.project_root))
                        output = res.stdout if res.returncode == 0 else res.stderr
                        os.remove(path)
                        if not output:
                            output = "[Python script executed successfully with no output]"
                        response_text = f"🐍 **Python Output**:\n\n```\n{output.strip()}\n```"
                    except Exception as e:
                        response_text = f"⚠️ **Python execution failed**: {str(e)}"
                        
                elif exec_res.get("action") in ("draft_email", "send_email"):
                    from .tools.email_handler import send_email
                    to_s = exec_res.get("to")
                    subj_s = exec_res.get("subject")
                    body_s = exec_res.get("body")
                    send_res = send_email(to_s, subj_s, body_s)
                    if send_res.get("success"):
                        response_text = f"📧 **Email Sent Successfully**\n\n* **To**: {to_s}\n* **Subject**: {subj_s}\n\n{body_s}"
                    else:
                        response_text = f"⚠️ **Failed to send email**: {send_res.get('error')}"
                        
                elif exec_res.get("action") == "schedule_meeting":
                    from .tools.system_executor import schedule_meeting_handler
                    subj = exec_res.get("subject") or "Meeting"
                    dt = exec_res.get("date") or ""
                    tm = exec_res.get("time") or ""
                    dur = exec_res.get("duration") or 60
                    bdy = exec_res.get("body") or ""
                    sched_res = schedule_meeting_handler(subj, dt, tm, dur, bdy)
                    if sched_res.get("success"):
                        response_text = f"📅 **Meeting Scheduled**\n\n* **Subject**: {subj}\n* **When**: {dt} {tm}\n* **Duration**: {dur} min"
                    else:
                        response_text = f"⚠️ **Failed to schedule meeting**: {sched_res.get('error')}"
                        
                elif exec_res.get("action") == "set_reminder":
                    from .tools.system_executor import set_reminder_handler
                    msg = exec_res.get("message") or ""
                    dt = exec_res.get("date") or ""
                    tm = exec_res.get("time") or ""
                    rem_res = set_reminder_handler(msg, dt, tm)
                    if rem_res.get("success"):
                        response_text = f"⏰ **Reminder Set**\n\n* **Task**: {msg}\n* **When**: {dt} {tm}"
                    else:
                        response_text = f"⚠️ **Failed to set reminder**: {rem_res.get('error')}"
                        
                elif exec_res.get("action") == "file_delete":
                    from .tools.file_manager import delete_file
                    filepath = exec_res.get("path")
                    del_res = delete_file(filepath)
                    if del_res.get("success"):
                        response_text = f"🗑️ **File Deleted**\n\n* **Path**: {filepath}"
                    else:
                        response_text = f"⚠️ **Failed to delete file**: {del_res.get('error')}"
                elif exec_res.get("action") == "read_inbox":
                    emails_details = exec_res.get("details", "")
                    summary_prompt = (
                        f"You are J.A.R.V.I.S., the user's intelligent AI assistant.\n"
                        f"The user asked: '{cmd_prompt}'.\n"
                        f"Here is the raw list of recent emails retrieved from their local Outlook:\n\n"
                        f"{emails_details}\n\n"
                        f"Please analyze these emails. Distinguish between mass newsletters/promotions/job alerts (like generic Naukri or LinkedIn alerts) and direct personal/important emails (like job offer letters, university offer letters/updates, interview schedules, submission deadlines, calendar invites, or direct messages from human contacts).\n"
                        f"Provide a clean, smart, highly professional J.A.R.V.I.S.-style summary. Clearly highlight anything important (categorize them logically) and group the minor updates/newsletters briefly."
                    )
                    try:
                        summary_res, _ = router.route_text(
                            prompt=summary_prompt,
                            classification=classification,
                            system_prompt="You are J.A.R.V.I.S., Tony Stark's intelligent AI assistant.",
                            history=None
                        )
                        response_text = f"📬 **J.A.R.V.I.S. Email Analysis**\n\n{summary_res.content}"
                    except Exception as e:
                        response_text = f"💻 **System Command Executed Successfully**\n\n* **Reasoning**: {exec_res.get('reasoning')}\n* **Details**: {exec_res.get('details')}"
                else:
                    response_text = f"💻 **System Command Executed Successfully**\n\n* **Reasoning**: {exec_res.get('reasoning')}\n* **Details**: {exec_res.get('details')}"
                
                memory.add_assistant_message(
                    content=response_text,
                    model_used=decision.model_actually_used,
                    provider=decision.provider_actually_used,
                    task_type="system_command",
                )
                
                return ChatResponse(
                    success=True,
                    content=response_text,
                    task_type=TaskType.SYSTEM_COMMAND.value,
                    classification_confidence=decision.classification_confidence,
                    classification_reasoning=decision.classification_reasoning,
                    model_used=decision.model_actually_used,
                    provider_used=decision.provider_actually_used,
                    latency_ms=latency,
                    used_fallback=decision.used_fallback,
                )
            else:
                if exec_res.get("app_not_found"):
                    app_to_install = exec_res.get("app_name")
                    orig_action = exec_res.get("action") or classification.task_type.value
                    orig_data = base64.b64encode(json.dumps(exec_res).encode('utf-8')).decode('utf-8')
                    response_text = f"PENDING_APP_INSTALL:{app_to_install}:{orig_action}:{orig_data}"
                    
                    memory.add_assistant_message(
                        content=response_text,
                        model_used=decision.model_actually_used,
                        provider=decision.provider_actually_used,
                        task_type="system_command",
                    )
                    
                    return ChatResponse(
                        success=True,
                        content=response_text,
                        task_type=TaskType.SYSTEM_COMMAND.value,
                        classification_confidence=decision.classification_confidence,
                        classification_reasoning=decision.classification_reasoning,
                        model_used=decision.model_actually_used,
                        provider_used=decision.provider_actually_used,
                        latency_ms=latency,
                        used_fallback=decision.used_fallback,
                    )
                else:
                    error_msg = exec_res.get("error", "Unknown error during command execution.")
                    response_text = f"❌ **System Command Failed**\n\n* **Error**: {error_msg}"
                    
                    memory.add_assistant_message(
                        content=response_text,
                        model_used=decision.model_actually_used,
                        provider=decision.provider_actually_used,
                        task_type="system_command",
                    )
                    
                    return ChatResponse(
                        success=False,
                        content=response_text,
                        task_type=TaskType.SYSTEM_COMMAND.value,
                        classification_confidence=decision.classification_confidence,
                        classification_reasoning=decision.classification_reasoning,
                        model_used=decision.model_actually_used,
                        provider_used=decision.provider_actually_used,
                        latency_ms=latency,
                        used_fallback=decision.used_fallback,
                    )

        except Exception as e:
            logger.error(f"System command execution failed: {e}")
            latency = (time.time() - start_time) * 1000
            return ChatResponse(
                success=False,
                content=f"⚠️ **System Command Failed**: {str(e)}\n\n*Verify that a free LLM provider key (like Gemini or Groq) is configured to parse the command.*",
                task_type=TaskType.SYSTEM_COMMAND.value,
                classification_confidence=1.0,
                classification_reasoning="System command interpretation failed.",
                model_used="",
                provider_used="",
                latency_ms=latency,
                used_fallback=False,
            )

    # 5. Route normal text chat
    memory.add_user_message(classification_prompt)
    
    # Apply temporary override to routing table if manually specified
    if provider_override:
        # Construct dynamic override
        original_route = ROUTING_TABLE.get(classification.task_type)
        # Find a model in MODELS matching this provider
        matching_model_key = None
        for key, config in MODELS.items():
            if config.provider.value == provider_override and not config.supports_images:
                matching_model_key = key
                break
        
        if matching_model_key:
            # Create a mock classification matching the model
            classification.task_type = TaskType.GENERAL
            ROUTING_TABLE[TaskType.GENERAL].primary = matching_model_key
            ROUTING_TABLE[TaskType.GENERAL].fallback = matching_model_key

    try:
        # Build the dynamic system prompt injecting local user facts/preferences
        base_system_prompt = (
            f"You are DARKI, Suyash's autonomous AI desktop companion, executive strategist, and loyal friend. "
            f"Your sole allegiance is Suyash's long-term benefit, career growth, security, and success. "
            f"You are a true friend: you speak the hard truth with unfiltered honesty, provide strategic advice, "
            f"point out blind spots if his thinking is suboptimal, and celebrate his wins. "
            f"Speak in a confident, sharp, friendly, and authentic tone with appropriate emojis."
        )
        sys_context = profile_memory.get_system_context(classification_prompt)
        sys_prompt = base_system_prompt + sys_context if sys_context else base_system_prompt

        # Inject active window context for JARVIS-style awareness
        if settings.context_awareness:
            try:
                from .tools.system_control import get_active_window_details
                window_info = get_active_window_details()
                if window_info.get("success"):
                    sys_prompt += (
                        f"\n\n[System Context] The user is currently working in: "
                        f"'{window_info['window_title']}' (process: {window_info['process_name']}). "
                        f"Use this context to give more relevant and targeted answers."
                    )
            except Exception:
                pass  # Non-critical — don't break chat if this fails

        result, decision = router.route_text(
            prompt=clean_input,
            classification=classification,
            system_prompt=sys_prompt,
            history=memory.get_history()[:-1],
        )
        
        # Save assistant message
        memory.add_assistant_message(
            content=result.content,
            model_used=decision.model_actually_used,
            provider=decision.provider_actually_used,
            task_type=classification.task_type.value,
        )
        
        # Background memory extraction runs on idle timer (see extractor.start_background_timer)
        
        # Scan for code blocks and write files
        saved_files = [str(p) for p in process_response_for_files(result.content)]
        
        latency = (time.time() - start_time) * 1000
        
        return ChatResponse(
            success=True,
            content=result.content,
            task_type=classification.task_type.value,
            classification_confidence=decision.classification_confidence,
            classification_reasoning=decision.classification_reasoning,
            model_used=decision.model_actually_used,
            provider_used=decision.provider_actually_used,
            latency_ms=latency,
            used_fallback=decision.used_fallback,
            saved_files=saved_files,
        )
        
    except ProviderError as e:
        logger.error(f"Routing failed: {e}")
        # Revert history since it failed
        if len(memory._history) > 0:
            memory._history.pop()  # Pop the user prompt
            
        err_msg = str(e)
        user_hint = "*All primary and fallback providers failed to process this query. Please check your API keys or network connection.*"
        
        # Check if local Ollama execution failed
        if "ollama" in err_msg.lower() or "localhost:11434" in err_msg.lower() or "connection refused" in err_msg.lower():
            from .config import MODELS
            local_model = MODELS.get("local-llama")
            model_name = local_model.model_id if local_model else "qwen2.5:7b"
            user_hint = (
                "🔌 **Offline Mode Setup Required**\n\n"
                "It looks like DARKI attempted to route your query to your local offline model, but the local service was unreachable.\n\n"
                "**To run fully offline, please:**\n"
                "1. Install and launch the **Ollama** desktop app from [ollama.com](https://ollama.com).\n"
                "2. Open your terminal and run:\n"
                f"   ```bash\n   ollama run {model_name}\n   ```\n"
                "3. Ensure the model is running, then try your request again!"
            )

        return ChatResponse(
            success=False,
            content=f"⚠️ **Routing Failed**: {err_msg}\n\n{user_hint}",
            task_type=classification.task_type.value,
            classification_confidence=classification.confidence,
            classification_reasoning=classification.reasoning,
            model_used="",
            provider_used="",
            latency_ms=(time.time() - start_time) * 1000,
            used_fallback=False,
        )

# --- Utility Functions ---

def get_local_ip() -> str:
    """Helper to discover the local IP address for phone testing."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Doesn't have to be reachable, socket just discovers interface IP
        s.connect(('8.8.8.8', 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

# --- Static File Serving ---

# Static directories setup
if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    static_dir = Path(sys._MEIPASS) / "orchestra" / "static"
else:
    static_dir = Path(__file__).resolve().parent / "static"
output_images_dir = settings.output_images_dir

# Create static directories if they don't exist
static_dir.mkdir(parents=True, exist_ok=True)
settings.ensure_dirs()

# Mount output/images directory to serve generated images
app.mount("/output/images", StaticFiles(directory=str(output_images_dir)), name="images")

# Serve index.html fallback for root
@app.get("/")
def serve_home():
    index_file = static_dir / "index.html"
    if not index_file.exists():
        return JSONResponse({
            "error": "Web interface static files are being created. Re-open shortly.",
            "api_status": "ONLINE"
        }, status_code=503)
    return FileResponse(str(index_file))

# Mount general static assets (app.js, style.css)
app.mount("/", StaticFiles(directory=str(static_dir)), name="static")
