# DARKI / OrchestraAI — Project Instructions & AI Knowledge Base

Welcome to **OrchestraAI / DARKI**! This document contains everything needed for any developer or AI assistant (such as Google Antigravity, Claude, Copilot, or Cursor) to immediately understand, install, run, and develop this repository from scratch.

---

## 📌 Project Summary
* **Repository:** `Suyashtiwari-7/OrchestraAI`
* **Primary Target:** Windows 10 / Windows 11 (64-bit)
* **Python Runtime:** Python 3.10, 3.11, or 3.12
* **Type:** Autonomous AI Desktop Companion, Executive Strategist, and DevSecOps Assistant

---

## 🛠️ Complete Setup from Scratch (Zero-Config)

### Step 1: Install Python & Clone Repo
Ensure Python 3.10+ is installed on Windows with **"Add Python to PATH"** enabled.

### Step 2: Run Automated Installer
In the project root folder, double-click or run:
```cmd
setup_env.bat
```
*This automatically creates `venv`, installs all packages from `requirements.txt`, creates `.env`, and sets up the Desktop shortcut.*

### Step 3: Run the Application
```cmd
run_darki.bat
```
*(Or press `Ctrl + 0` / `Ctrl + Num 0` / say "Hey DARKI" once running).*

---

## 📁 Repository Map

| Path | Purpose |
|---|---|
| [`requirements.txt`](file:///c:/Users/Lenovo/Documents/CODE/OrchestraAI/requirements.txt) | All project dependencies categorized and pinned |
| [`setup_env.bat`](file:///c:/Users/Lenovo/Documents/CODE/OrchestraAI/setup_env.bat) | 1-click Windows setup wizard |
| [`run_darki.bat`](file:///c:/Users/Lenovo/Documents/CODE/OrchestraAI/run_darki.bat) / [`run_darki.py`](file:///c:/Users/Lenovo/Documents/CODE/OrchestraAI/run_darki.py) | Standalone desktop launchers |
| [`orchestra/darki_main.py`](file:///c:/Users/Lenovo/Documents/CODE/OrchestraAI/orchestra/darki_main.py) | Main desktop app process |
| [`orchestra/darki_widget.py`](file:///c:/Users/Lenovo/Documents/CODE/OrchestraAI/orchestra/darki_widget.py) | PyQt6 floating robot mascot & chat UI |
| [`orchestra/hotkey_listener.py`](file:///c:/Users/Lenovo/Documents/CODE/OrchestraAI/orchestra/hotkey_listener.py) | Global hotkey listener (`Ctrl+0` / `Ctrl+Num0`) |
| [`orchestra/router.py`](file:///c:/Users/Lenovo/Documents/CODE/OrchestraAI/orchestra/router.py) | Multi-model routing engine (NVIDIA NIM, Groq, Ollama) |
| [`orchestra/voice/`](file:///c:/Users/Lenovo/Documents/CODE/OrchestraAI/orchestra/voice/) | Faster-Whisper STT, Kokoro-82M ONNX TTS, wake-word engine |
| [`orchestra/security/`](file:///c:/Users/Lenovo/Documents/CODE/OrchestraAI/orchestra/security/) | EDR Security Manager (ARP, BadUSB, Remote Intruder) |
| [`orchestra/assistant/`](file:///c:/Users/Lenovo/Documents/CODE/OrchestraAI/orchestra/assistant/) | Proactive Assistant (VIP filter, notifications, scheduler) |
| [`orchestra/memory/`](file:///c:/Users/Lenovo/Documents/CODE/OrchestraAI/orchestra/memory/) | SQLite database, Connected Graph Memory, Windows DPAPI Vault |
| [`orchestra/tools/`](file:///c:/Users/Lenovo/Documents/CODE/OrchestraAI/orchestra/tools/) | OS tools, UIA automation, DuckDuckGo search, scraper, email |
| [`tests/`](file:///c:/Users/Lenovo/Documents/CODE/OrchestraAI/tests/) | Automated unit tests (`85+ passed`) |

---

## 🧪 Testing
Run unit tests with:
```powershell
venv\Scripts\python.exe -m pytest tests/ --ignore=tests/e2e -v
```
