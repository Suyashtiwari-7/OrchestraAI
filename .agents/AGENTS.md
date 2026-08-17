# Workspace Rules & AI Knowledge for OrchestraAI / DARKI

## 1. Project Overview & Identity
- **Name:** OrchestraAI / DARKI
- **Persona:** DARKI is Suyash's autonomous AI desktop companion, executive strategist, and loyal friend. Dedicated entirely to Suyash's long-term success, career growth, cybersecurity, and productivity.
- **Platform:** Windows 10/11 x64 (Python 3.10+).

## 2. Directory Structure & Key Modules
- `orchestra/`: Main application package
  - `darki_main.py`: Entry point for desktop app (FastAPI server, PyQt6 floating mascot, system tray, hotkeys, voice session).
  - `darki_widget.py`: PyQt6 transparent desktop robot widget, glassmorphic chat popup, review dialogs, cancel button.
  - `hotkey_listener.py`: Global keyboard listener supporting `Ctrl+0` and `Ctrl+Num0` (all scancode variants).
  - `router.py`: Intelligent multi-model router (NVIDIA NIM primary, Groq fallback, local Ollama backup).
  - `server.py`: FastAPI server dispatching `/api/chat`, `/api/task/cancel`, and system endpoints.
  - `voice/`: Live voice pipeline (`live_session.py`, `stt_engine.py` using Faster-Whisper, `tts_engine.py` using Kokoro-82M ONNX).
  - `security/`: Autonomous Cybersecurity (EDR) Manager (`network_guard.py`, `badusb_guard.py`, `intruder_guard.py`).
  - `assistant/`: Proactive Executive Assistant (`proactive_engine.py`, `notification_listener.py`, `vip_filter.py`).
  - `memory/`: Storage & Memory (`database.py` SQLite + Connected Graph Memory, `vault.py` Windows DPAPI encryption, `user_profile.py`).
  - `tools/`: Native OS tools (`system_control.py`, `system_executor.py`, `gui_automation.py`, `uia_explorer.py`, `web_search.py`, `web_scraper.py`, `email_handler.py`, `agentic_executor.py`).
- `tests/`: Pytest suite (85+ tests covering all components).
- `setup_env.bat`: 1-click Windows virtual environment and dependency installer.
- `run_darki.bat` / `run_darki.py`: Desktop application launchers.

## 3. Environment & Dependencies
- Virtual Environment: `venv/`
- Dependencies File: `requirements.txt`
- Install Command: `venv\Scripts\python.exe -m pip install -r requirements.txt`
- Test Command: `venv\Scripts\python.exe -m pytest tests/ --ignore=tests/e2e -v`

## 4. Coding Standards & Behavioral Rules
- **GUI-First Automation:** Prefer performing Windows settings visually via `orchestra.tools.uia_explorer` / `gui_automation` before silent command-line tweaks, unless background execution is explicitly requested.
- **Anti-Hallucination:** Never guess API signatures; always read source code first.
- **Verification Loop:** Run `pytest tests/ --ignore=tests/e2e -v` after modifying files to ensure 100% test pass rate.
