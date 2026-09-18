# DARKI / OrchestraAI — Technical Handover Document

> **Version:** 2.0.0 (Hardened & Modular)  
> **Target OS:** Windows 10 / 11 (x64)  
> **Python Version:** 3.10 - 3.12  
> **Repository:** [https://github.com/Suyashtiwari-7/OrchestraAI](https://github.com/Suyashtiwari-7/OrchestraAI)  
> **Test Status:** 94 / 94 Passing (100% test suite health)

---

## 1. Executive Summary

**DARKI (OrchestraAI)** is an autonomous, local-first AI desktop companion, executive strategist, and devsecops guardian built for Windows. It provides low-latency intelligent task automation, proactive executive briefings, dynamic multi-LLM cognitive routing (Groq, Cerebras, OpenRouter, NVIDIA NIM, Gemini, Ollama), voice interactions (Faster-Whisper STT + Kokoro-82M ONNX TTS), and persistent Windows DPAPI-encrypted associative memory.

This handover document describes the full technical architecture, recent security hardening, modular structure, configuration requirements, testing protocols, and future engineering roadmap.

---

## 2. System Architecture & Component Breakdown

```
                                      🤖 DARKI
                                         │
 ┌───────────────────────┬───────────────┴───────────────┬───────────────────────┐
 ▼                       ▼                               ▼                       ▼
🧠 Multi-Model Router    🛡️ EDR Security Engine          🎙️ Voice & UI Layer     🗄️ Memory & DB Layer
 ├─ Groq (<150ms)         ├─ ARP Spoof / MITM Guard       ├─ PySide6 Frameless    ├─ SQLite WAL Concurrency
 ├─ Cerebras              ├─ BadUSB Velocity Defense      ├─ Native Win32 Hotkey  ├─ Connected Memory Graph
 ├─ OpenRouter / NVIDIA   ├─ Remote Session Blocker       ├─ Faster-Whisper (STT) ├─ Deterministic CRC32 Hash
 └─ Local Ollama (Backup) └─ FIDO2 / YubiKey Audit        └─ Kokoro-82M ONNX(TTS) └─ Windows DPAPI Vault
```

### 2.1 Entrypoints & Process Architecture
* **`run_darki.py` / `run_darki.bat`**: Bootstraps the application, verifies Python virtual environment dependencies, spawns background services, and opens the UI.
* **`orchestra/__main__.py`**: Main orchestrator. Initializes the FastAPI background server, voice recognition worker, and loads the PySide6 Qt application.
* **`orchestra/server.py`**: FastAPI backend running on `127.0.0.1:8000`. Exposes REST and WebSocket endpoints for AI completions, memory operations, system controls, and proactive assistant feeds.

### 2.2 User Interface & Global Hotkey Subsystem
* **`orchestra/darki_widget.py`**: Frameless glassmorphic circular HUD mascot widget. Handles user chat input, voice animation pulses, notification banners, and status feedback.
* **`orchestra/hotkey_listener.py`**: Native Win32 `RegisterHotKey` implementation embedded directly in the PySide6 event loop (`nativeEventFilter`).
  * **Primary Shortcut:** `Alt + Space` (Instant toggle chat popup)
  * **Secondary Shortcuts:** `Ctrl + 0`, `Ctrl + Numpad 0`
  * **Zero Daemon / No Admin Required:** Completely replaces external keyboard hook daemons with zero background polling overhead.

### 2.3 Cognitive Routing & Model Layer
* **`orchestra/classifier.py`**: Rule-based & regex task intent classifier detecting system commands, code executions, web searches, UI automations, and queries.
* **`orchestra/router.py`**: Multi-provider cognitive routing engine with automatic fallback cascade.
* **`orchestra/providers/`**:
  * `groq_provider.py`: Ultra-low latency responses using Llama-3.3-70B.
  * `cerebras_provider.py`: Fast wafer-scale inference.
  * `openrouter_provider.py`: Access to Claude, GPT-4o, DeepSeek, and open models.
  * `nvidia_nim.py`: DeepSeek-R1 reasoning and high-context models.
  * `gemini_provider.py`: Multimodal analysis and Imagen 3 generation.
  * `ollama_provider.py`: 100% offline local inference fallback.

### 2.4 Persistent Memory Subsystem
* **`orchestra/memory/database.py`**: SQLite database managing chat history, system logs, task queues, and executive briefings. Configured with **Write-Ahead Logging (WAL)** mode and `busy_timeout=5000` to guarantee crash-free concurrent read/write operations.
* **`orchestra/memory/vector_engine.py`**: Vector memory engine utilizing deterministic `zlib.crc32` n-gram hashing and cosine similarity for semantic recall.
* **`orchestra/memory/graph_memory.py`**: Connected associative graph for concept linking across user conversations.
* **`orchestra/memory/vault.py`**: Encrypted credentials vault leveraging native Windows DPAPI (`CryptProtectData`).

### 2.5 Proactive Assistant & Morning Briefing
* **`orchestra/assistant/morning_briefing.py`**: Generates daily executive summaries (calendar tasks, pending high-priority actions, motivational note) upon first morning launch.
* **`orchestra/assistant/proactive_engine.py`**: Background scheduler for timed reminders, recurring automation, and follow-ups.
* **`orchestra/assistant/vip_filter.py`**: Multi-tier contact urgency filter prioritizing VIP messages while suppressing non-urgent group chat noise.
* **`orchestra/assistant/notification_listener.py`**: WhatsApp Web / Desktop notification scraper.

### 2.6 Agentic Tool Execution
* **`orchestra/agentic_executor.py`**: Multi-step autonomous agent planner that iterates across tool calls until goals are met.
* **`orchestra/tools/system_executor.py`**: Whitelisted desktop application launcher (Notepad, VS Code, Browser, Spotify, Calculator, etc.).
* **`orchestra/tools/system_control.py`**: Windows audio volume, display brightness, screenshot capture, and lock screen controls.
* **`orchestra/tools/file_manager.py`**: Safe file manipulation with path blacklist protection preventing destructive actions on critical OS and user root directories.
* **`orchestra/tools/web_search.py`**: Real-time web searching via DuckDuckGo HTML parser.
* **`orchestra/tools/code_sandbox.py`**: Isolated Python script sandbox for data processing and math tasks.
* **`orchestra/tools/codebase_search.py`**: Fast local repository code search and indexing.
* **`orchestra/tools/email_handler.py`**: SMTP/IMAP client for drafting, reading, and sending emails.

### 2.7 DevSecOps & EDR Guardian Subsystem
* **`orchestra/security/security_manager.py`**: Unified security audit controller.
* **`orchestra/security/network_guard.py`**: ARP cache monitoring for MITM/ARP spoofing attacks and Wi-Fi BSSID verification.
* **`orchestra/security/badusb_guard.py`**: Keystroke velocity anomaly detection protecting against malicious Rubber Ducky / BadUSB injections.
* **`orchestra/security/intruder_guard.py`**: Remote session monitoring (`qwinsta`) alerting or terminating unauthorized RDP logins.
* **`orchestra/security/device_auditor.py`**: Hardware inventory check verifying trusted USB peripherals and FIDO2 YubiKeys.

---

## 3. Recent Security Hardening & Critical Bug Fixes

The following critical flaws and stability issues were audited, resolved, and verified:

1. **Security Vulnerability: Remote API Exposure Patched**
   * *Problem:* `orchestra/__main__.py` previously bound Uvicorn to `0.0.0.0`, exposing local file management and system execution endpoints to the local network.
   * *Fix:* Changed binding to strictly local loopback `127.0.0.1`.

2. **Concurrency Crash: SQLite "Database is Locked" Resolved**
   * *Problem:* High-concurrency requests from the UI, voice worker, and API threads crashed SQLite in standard rollback journal mode.
   * *Fix:* Enabled SQLite Write-Ahead Logging (`PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000;`) in `database.py`.

3. **Memory Corruption: Vector Inconsistency Fixed**
   * *Problem:* `vector_engine.py` used Python's built-in `hash()`, which is randomized per process via Python hash seed randomization. Stored vector embeddings broke across app restarts.
   * *Fix:* Switched to deterministic `zlib.crc32()` feature hashing.

4. **Destructive Execution Protection: File Manager Blacklist Added**
   * *Problem:* `file_manager.py` lacked directory boundary checks, creating risk of accidental deletion of root folders (`C:\`, `C:\Windows`, `Desktop`).
   * *Fix:* Added strict path resolution checks against `PROTECTED_PATHS`.

5. **Credential Leak Prevention: Git Remote Config Scrubbed**
   * *Problem:* GitHub Personal Access Token was stored in `.git/config` remote URL.
   * *Fix:* Removed token from repository configuration and migrated to secure local credential storage.

6. **Hotkey Stability: Native Win32 Event Filter**
   * *Problem:* External `keyboard` hook library required elevated privileges, conflicted with background threads, and frequently dropped shortcuts.
   * *Fix:* Replaced with native Windows `RegisterHotKey` inside the PySide6 event loop (`Alt + Space`, `Ctrl + 0`).

7. **Dead Code & Unused Modules Pruned**
   * Removed legacy `phone_caller.py`, `plugin_manager.py`, and `self_updater.py`. Cleaned all dependent imports.

---

## 4. Configuration & Environment Setup

Create a `.env` file in the project root:

```ini
# --- LLM API Keys ---
GROQ_API_KEY=gsk_...
NVIDIA_NIM_API_KEY=nvapi-...
GEMINI_API_KEY=AIzaSy...
CEREBRAS_API_KEY=csk-...
OPENROUTER_API_KEY=sk-or-v1-...

# --- Local Ollama (Optional) ---
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3:8b

# --- Voice & Speech ---
VOICE_ENABLED=true
VOICE_ENGINE=kokoro
WAKE_WORD=hey darki

# --- Proactive Assistant & VIP Feed ---
VIP_CONTACTS=["Mom", "Manager", "CEO", "Partner"]
URGENT_KEYWORDS=["urgent", "asap", "emergency", "deadline", "production down"]
WHATSAPP_ENABLED=true

# --- Email Handler (Optional) ---
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
EMAIL_USER=your_email@gmail.com
EMAIL_PASS=your_app_password
```

---

## 5. Development & Operations Guide

### 5.1 Environment Setup
```powershell
# 1. Create and activate virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# 2. Install dependencies
pip install -r requirements.txt
```

### 5.2 Launching DARKI
```powershell
# Method A: Batch launcher
.\run_darki.bat

# Method B: Direct Python execution
.\venv\Scripts\python.exe run_darki.py
```

### 5.3 Running the Test Suite
```powershell
.\venv\Scripts\pytest.exe tests/ --ignore=tests/e2e -v
```
*Current test metrics: 94 passing unit & integration tests.*

---

## 6. Identified Technical Debt & Future Refactoring Roadmap

During the technical audit, several components were flagged as over-engineered for a personal desktop companion. Future maintainers can streamline these areas:

1. **EDR Security Suite (`orchestra/security/`):**
   * *Current State:* Runs ARP spoof detection, BadUSB typing velocity analysis, and RDP session scanning via background threads.
   * *Recommendation:* Keep these optional or modularize into an external security plugin so personal users don't pay background CPU cycles for enterprise-level device auditing.

2. **N-Gram Vector Hashing (`orchestra/memory/vector_engine.py`):**
   * *Current State:* 256-dimensional CRC32 n-gram sparse hashing with 5-minute background LLM insight extraction.
   * *Recommendation:* Modern lightweight embeddings (e.g. `fastembed` or `all-MiniLM-L6-v2`) or a structured SQLite User Profile JSON store would provide higher semantic precision with less complexity.

3. **15-State Classifier Regex Cascade (`orchestra/classifier.py`):**
   * *Current State:* Massive cascade of regexes for intent classification.
   * *Recommendation:* Migrate to native LLM tool calling (Function Calling / Structured Outputs) on fast providers like Groq or Cerebras (<100ms), eliminating regex maintenance.

4. **UI Automation Crawler (`orchestra/tools/uia_explorer.py`):**
   * *Current State:* Deep Windows UI Automation COM tree traversal.
   * *Recommendation:* Prefer direct app APIs, CLI commands, and URL launch handlers over fragile UI element hierarchy clicking.

---

## 7. Directory Map

```
OrchestraAI/
├── .env.example                  # Environment configuration template
├── README.md                     # Public project overview
├── HANDOVER.md                   # Complete architectural & technical handover
├── requirements.txt              # Python package dependencies
├── run_darki.py                  # Python launcher script
├── run_darki.bat                 # 1-Click Windows execution script
├── setup_env.bat                 # Automated venv installer
│
├── orchestra/                    # Main application package
│   ├── __init__.py
│   ├── __main__.py               # Core orchestrator & server bootstrap
│   ├── server.py                 # FastAPI backend (127.0.0.1:8000)
│   ├── darki_widget.py           # PySide6 Desktop GUI & Floating HUD
│   ├── hotkey_listener.py        # Native Win32 RegisterHotKey event filter
│   ├── classifier.py             # Intent classification engine
│   ├── router.py                 # Cognitive multi-LLM router
│   ├── agentic_executor.py       # Autonomous multi-step agent loop
│   │
│   ├── assistant/                # Proactive assistance & notifications
│   │   ├── morning_briefing.py   # Daily executive briefing engine
│   │   ├── proactive_engine.py   # Background reminder & task scheduler
│   │   ├── vip_filter.py         # Priority message & VIP contact filter
│   │   └── notification_listener.py # WhatsApp / desktop notification watcher
│   │
│   ├── memory/                   # Storage & associative memory
│   │   ├── database.py           # SQLite WAL persistence layer
│   │   ├── vector_engine.py      # Deterministic semantic vector search
│   │   ├── graph_memory.py       # Associative concept graph
│   │   └── vault.py              # Windows DPAPI credentials encryption
│   │
│   ├── providers/                # LLM API providers
│   │   ├── groq_provider.py      # Groq ultra-fast Llama-3.3
│   │   ├── cerebras_provider.py  # Cerebras inference
│   │   ├── nvidia_nim.py         # NVIDIA NIM / DeepSeek-R1
│   │   ├── openrouter_provider.py# OpenRouter multi-model gateway
│   │   ├── gemini_provider.py    # Google Gemini & Imagen 3
│   │   └── ollama_provider.py    # Local offline Ollama provider
│   │
│   ├── security/                 # EDR & hardware defenses
│   │   ├── security_manager.py   # Master security coordinator
│   │   ├── network_guard.py      # ARP anti-spoofing & BSSID check
│   │   ├── badusb_guard.py       # Keystroke velocity anomaly detection
│   │   ├── intruder_guard.py     # Unauthorized RDP session blocker
│   │   └── device_auditor.py     # USB peripheral & FIDO2 verification
│   │
│   ├── tools/                    # Agentic automation toolset
│   │   ├── system_executor.py    # Whitelisted desktop app runner
│   │   ├── system_control.py     # Windows volume, display, screenshots
│   │   ├── file_manager.py       # Protected local file operations
│   │   ├── web_search.py         # DuckDuckGo web search tool
│   │   ├── code_sandbox.py       # Isolated Python script sandbox
│   │   ├── codebase_search.py    # Local code repository semantic search
│   │   ├── email_handler.py      # SMTP/IMAP email composer & reader
│   │   └── uia_explorer.py       # Windows UI Automation accessibility tree
│   │
│   └── voice/                    # Audio & speech processing
│       ├── stt.py                # Faster-Whisper local transcription
│       ├── tts.py                # Kokoro-82M ONNX local synthesis
│       └── vad.py                # Silero voice activity & wake word detection
│
└── tests/                        # Automated test suite (94 tests)
    ├── test_classifier.py
    ├── test_router.py
    ├── test_agentic_executor.py
    ├── test_proactive_assistant.py
    ├── test_memory_upgrade.py
    ├── test_security_engine.py
    ├── test_system_executor.py
    ├── test_system_control.py
    ├── test_file_manager.py
    ├── test_web_search.py
    ├── test_code_sandbox.py
    ├── test_codebase_search.py
    ├── test_email_handler.py
    └── test_ollama.py
```

---

## 8. Handover Sign-Off

All stated project milestones, security remediations, native hotkey integrations, morning briefing capabilities, and test suite verifications have been fully implemented, validated, and finalized.

*Prepared for Suyashtiwari-7 / OrchestraAI Project Team.*
