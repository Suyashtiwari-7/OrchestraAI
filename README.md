# OrchestraAI 🎵

**Intelligent AI Routing & Work Automation Agent**

OrchestraAI is a Python-based agent that acts as an intelligent traffic controller — analyzing incoming tasks and routing them to different free cloud LLM APIs based on their specific cognitive strengths.

## ✨ Features

- **🔀 Smart Routing** — Automatically classifies tasks and routes to the optimal AI model
- **🔄 Auto-Fallback** — If a provider fails (rate limit, timeout), seamlessly switches to a backup
- **🧠 Multi-Provider** — Google Gemini, Groq, and Cerebras — all free tiers
- **🖼️ Image Generation** — Create images via Gemini Imagen 3
- **🌐 Web Scraping** — Fetch, extract, and summarize web pages
- **📄 File Writer** — Automatically saves code blocks from AI responses to files
- **💬 Conversation Memory** — Maintains context across turns within a session
- **🎨 Beautiful CLI** — Rich terminal interface with colors, tables, and spinners

## 🏗️ Architecture

```
User Input → Classifier (Gemini Flash) → Router → Provider → Response
                                            ↓
                                    Auto-Fallback Chain
```

### Model Routing Table

| Task | Primary Model | Fallback Model |
|------|--------------|----------------|
| 🧠 Deep Reasoning | Gemini 2.5 Pro | DeepSeek R1 (Groq) |
| 💻 Code Generation | Gemini 2.5 Pro | Llama 3.3 (Cerebras) |
| 🎨 Creative | Gemini 2.0 Flash | Llama 3.3 (Groq) |
| ⚡ Fast Utility | Qwen QwQ 32B (Groq) | Llama 3.3 (Cerebras) |
| 🖼️ Image Gen | Imagen 3 (Google) | — |
| 🌐 Web Scrape | Gemini 2.0 Flash | Qwen (Groq) |

## 🚀 Quick Start

### 1. Prerequisites

- Python 3.10 or higher
- pip (Python package manager)

### 2. Clone & Setup

```bash
cd c:\Users\Lenovo\Documents\CODE\CereBro

# Create virtual environment
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure API Keys

Copy the example environment file and add your keys:

```bash
copy .env.example .env
```

Edit `.env` and add your free API keys:

```ini
GEMINI_API_KEY=your_key_from_aistudio_google_com
GROQ_API_KEY=your_key_from_console_groq_com
CEREBRAS_API_KEY=your_key_from_cloud_cerebras_ai
```

**Get your free keys:**
- 🔵 **Google Gemini**: [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
- 🟢 **Groq**: [console.groq.com/keys](https://console.groq.com/keys)
- 🟣 **Cerebras**: [cloud.cerebras.ai](https://cloud.cerebras.ai/)

### 4. Run OrchestraAI

```bash
python -m orchestra
```

## 📖 Usage

### Basic Chat
Just type naturally — OrchestraAI automatically classifies and routes:

```
╭─
╰─➤ Write a Python function to merge two sorted lists
  🔀 Routed to 🔵 Gemini 2.5 Pro │ code_generation (94% confidence)
```

### Commands

| Command | Description |
|---------|-------------|
| `/help` | Show all commands |
| `/models` | Display routing table |
| `/health` | Check provider status |
| `/image <prompt>` | Generate an image |
| `/scrape <url>` | Scrape and summarize a webpage |
| `/history` | Show conversation history |
| `/clear` | Clear history |
| `/export` | Export history to JSON |
| `/exit` | Quit |

### Force a Specific Provider

Use `@provider` prefix to override auto-routing:

```
╰─➤ @groq Format this JSON into a table: {"name": "OrchestraAI"}
╰─➤ @gemini Explain quantum entanglement in detail
╰─➤ @cerebras Write a binary search in Rust
```

## 📁 Project Structure

```
CereBro/
├── .env                          # Your API keys (gitignored)
├── .env.example                  # Key template
├── requirements.txt              # Dependencies
├── README.md                     # This file
├── orchestra/
│   ├── __init__.py
│   ├── __main__.py               # python -m orchestra entry
│   ├── main.py                   # CLI interface
│   ├── config.py                 # Settings & model configs
│   ├── classifier.py             # Task classification engine
│   ├── router.py                 # Model routing & fallback
│   ├── providers/
│   │   ├── base.py               # Abstract provider interface
│   │   ├── gemini_provider.py    # Google Gemini adapter
│   │   ├── groq_provider.py      # Groq adapter
│   │   └── cerebras_provider.py  # Cerebras adapter
│   ├── tools/
│   │   ├── file_writer.py        # Save code to files
│   │   ├── web_scraper.py        # Scrape URLs
│   │   └── image_saver.py        # Save generated images
│   └── memory/
│       └── session_memory.py     # Conversation history
├── output/
│   ├── code/                     # Saved code files
│   └── images/                   # Saved images
└── tests/
    ├── test_classifier.py
    └── test_router.py
```

## ⚠️ Free Tier Limits

| Provider | RPM | Daily Limit | Notes |
|----------|-----|-------------|-------|
| Google Gemini | ~15 | Varies | Most generous free tier |
| Groq | 30 | 14,400 req | Fastest inference |
| Cerebras | Varies | 1M tokens | Great fallback |

## 📄 License

MIT License — Use freely.
