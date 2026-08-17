# DARKI / OrchestraAI 🤖🪄

**Autonomous AI Desktop Companion, Executive Strategist & DevSecOps Guardian**

DARKI is a 100% local-first, privacy-preserving desktop AI companion running natively on Windows 10/11. It combines multi-LLM cognitive routing (NVIDIA NIM & Groq), an autonomous cybersecurity EDR engine, a proactive executive assistant, real-time bidirectional voice (Faster-Whisper + Kokoro-82M ONNX), a glassmorphic floating robot mascot, and Windows DPAPI encrypted memory.

---

## ⚡ 1-Click Download & Run (No Python or Terminal Needed!)

[![Download for Windows](https://img.shields.io/badge/Download_for_Windows-v1.0.0-238636?style=for-the-badge&logo=windows&logoColor=white)](https://github.com/Suyashtiwari-7/OrchestraAI/releases/latest)

1. **[Download the latest Release ZIP](https://github.com/Suyashtiwari-7/OrchestraAI/releases/latest)** (`DARKI-Desktop-Windows.zip`).
2. **Extract the ZIP file** to any folder on your PC.
3. **Double-click `DARKI.exe`** — DARKI will launch immediately!

> 💡 *Note: On first launch, open `.env` next to `DARKI.exe` in Notepad and paste your free API keys (NVIDIA NIM, Groq, Gemini).*

---

## 🛠️ Run from Source (Developers & Contributors)

### 1. Prerequisites
1. **Python 3.10, 3.11, or 3.12** installed on Windows.  
   *(⚠️ Important: During Python installation, check the box **"Add Python to PATH"**).*
2. **Git** (optional, if cloning from GitHub).

### 2. Automated Bootstrap Setup
Simply double-click:
👉 **`setup_env.bat`**

*What this script does automatically:*
- Creates the local virtual environment (`venv/`)
- Installs all dependencies from `requirements.txt`
- Sets up `.env` from `.env.example`
- Generates a **`DARKI AI`** shortcut directly on your Windows Desktop

### 3. Configure API Keys (`.env`)
Open `.env` in Notepad and insert your free API keys:

```ini
# Primary High-Intelligence LLMs (Llama 3.3 70B & DeepSeek R1)
NVIDIA_NIM_API_KEY=your_nvidia_nim_key_here

# Fast Inference & Urgency Scoring (<150ms)
GROQ_API_KEY=your_groq_key_here

# Image Generation (Imagen 3)
GEMINI_API_KEY=your_gemini_key_here
```

* **NVIDIA NIM (Free credits):** [build.nvidia.com](https://build.nvidia.com/)
* **Groq (Free fast API):** [console.groq.com/keys](https://console.groq.com/keys)
* **Google Gemini (Free tier):** [aistudio.google.com/apikey](https://aistudio.google.com/apikey)

---

## 🚀 How to Run DARKI

You have 3 easy ways to launch:
1. **Desktop Executable:** Double-click `dist/DARKI/DARKI.exe`.
2. **Desktop Shortcut:** Double-click **`DARKI AI`** on your Windows Desktop.
3. **Batch Script:** Double-click [`run_darki.bat`](file:///c:/Users/suyas/Documents/CODE/OrchestraAI-main/OrchestraAI-main/run_darki.bat).

---

## ⌨️ Activation & Hotkeys

* 🎙️ **Voice Wake-Up:** Say *"Hey DARKI"* or *"DARKI"* out loud for hands-free control.
* ⌨️ **Global Hotkey:** Press **`Ctrl + 0`** (or **`Ctrl + Num 0`** on Numpad) anywhere on your PC to instantly summon the floating chat box.
* 🖱️ **Desktop Mascot:** Click the 3D floating robot in the bottom-right corner of your screen.
* 🛑 **Emergency Kill-Switch:** Click the **`🛑`** button in the chat popup or call `/api/task/cancel` to instantly abort active automation steps.
* 🖱️ **Human Mouse Override:** Moving your mouse automatically pauses DARKI's clicks and yields control to you, resuming after 4.5s of idle.

---

## 🏗️ Architectural Overview

```
                                      🤖 DARKI
                                         │
 ┌───────────────────────┬───────────────┴───────────────┬───────────────────────┐
 ▼                       ▼                               ▼                       ▼
🧠 Multi-Model Router    🛡️ EDR Security Engine          🎙️ Voice Pipeline       🗄️ Storage & Memory
 ├─ NVIDIA NIM (70B/R1)   ├─ ARP Anti-Poisoning / MITM    ├─ Faster-Whisper (STT) ├─ SQLite WAL DB
 ├─ Groq (Llama 3.3)      ├─ BadUSB Keystroke Defense     ├─ Kokoro-82M ONNX(TTS) ├─ Connected Graph Memory
 └─ Local Ollama (Backup) └─ Intruder Remote Session Kill └─ Silero VAD Wake Word └─ Windows DPAPI Vault
```

---

## 🧪 Testing & Verification

Run the full automated test suite anytime to verify all modules:
```powershell
venv\Scripts\python.exe -m pytest tests/ --ignore=tests/e2e -v
```
*(All 85 unit tests pass cleanly).*
