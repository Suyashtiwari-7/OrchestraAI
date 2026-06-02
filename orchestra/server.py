"""
OrchestraAI — FastAPI Server
==============================
Backend server exposing routing, classification, memory, and tool actions
via a clean HTTP API. Serves static files for the responsive Web UI.
"""

import time
import socket
import logging
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
)
from .classifier import TaskClassifier, ClassificationResult
from .router import ModelRouter, RoutingDecision
from .memory.session_memory import SessionMemory
from .providers.base import ProviderError
from .tools.file_writer import process_response_for_files
from .tools.web_scraper import extract_url, scrape_url, format_scraped_content
from .tools.image_saver import save_image
from .tools.system_executor import execute_system_command

SYSTEM_COMMAND_PROMPT = """You are a system command interpreter for OrchestraAI.
Your job is to parse the user's intent to open a URL/website or launch a local application, and return a strict JSON block.

Supported Browsers:
- "brave": Brave Browser
- "chrome": Google Chrome
- "edge": Microsoft Edge
- "default": Default system browser

Supported Apps:
- "notepad": Windows Notepad
- "calculator": Windows Calculator
- "explorer": Windows File Explorer

Common URL/Alias Mapping:
- "whatsapp": "https://web.whatsapp.com"
- "youtube": "https://youtube.com"
- "google": "https://google.com"
- "github": "https://github.com"

Response Format:
You MUST respond with a single JSON object. No markdown wrapping, no code blocks, no ```json formatting, no other explanation or text.

JSON Structure:
{
  "action": "open_browser" | "launch_app" | "invalid",
  "target": "<url_or_app_name>",
  "browser": "brave" | "chrome" | "edge" | "default" | null,
  "reasoning": "<brief explanation of the extraction>"
}

Examples:
1. Input: "open whatsapp in brave browser"
Output: {"action": "open_browser", "target": "https://web.whatsapp.com", "browser": "brave", "reasoning": "Open WhatsApp Web in Brave Browser"}

2. Input: "open notepad"
Output: {"action": "launch_app", "target": "notepad", "browser": null, "reasoning": "Open local Notepad application"}

3. Input: "open cnn.com in chrome"
Output: {"action": "open_browser", "target": "https://cnn.com", "browser": "chrome", "reasoning": "Open cnn.com website in Google Chrome"}
"""

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("orchestra.server")

# Initialize components
classifier = TaskClassifier()
router = ModelRouter()
memory = SessionMemory()

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

# --- API Endpoints ---

@app.get("/api/status")
def get_status():
    """Check API key configurations and provider health."""
    key_status = api_keys.validate()
    health_status = router.health_check_all()
    
    providers = []
    display_names = {
        "gemini": "Gemini",
        "groq": "Groq",
        "cerebras": "Cerebras",
        "sambanova": "SambaNova",
        "mistral": "Mistral AI",
        "cohere": "Cohere",
    }
    for provider in ProviderName:
        providers.append({
            "name": provider.value,
            "display_name": display_names.get(provider.value, provider.value.capitalize()),
            "configured": key_status.get(provider, False),
            "healthy": health_status.get(provider.value, False),
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
def get_history():
    """Get conversation history for the current session."""
    entries = []
    for entry in memory.get_full_history():
        entries.append({
            "role": entry.role,
            "content": entry.content,
            "model_used": entry.model_used,
            "provider": entry.provider,
            "task_type": entry.task_type,
            "timestamp": entry.timestamp,
        })
    return {"history": entries}

@app.post("/api/clear")
def clear_history():
    """Clear conversation history."""
    memory.clear()
    return {"success": True, "message": "Conversation history cleared."}

@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    """Classify and route the user prompt, invoking fallbacks & tools as needed."""
    user_input = request.prompt.strip()
    if not user_input:
        raise HTTPException(status_code=400, detail="Prompt cannot be empty.")

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
    elif lower_input.startswith("@cerebras "):
        provider_override = "cerebras"
        clean_input = user_input[10:].strip()
    elif lower_input.startswith("@sambanova "):
        provider_override = "sambanova"
        clean_input = user_input[11:].strip()
    elif lower_input.startswith("@mistral "):
        provider_override = "mistral"
        clean_input = user_input[9:].strip()
    elif lower_input.startswith("@cohere "):
        provider_override = "cohere"
        clean_input = user_input[8:].strip()

    # 2. Classify task (with potential provider override config mapping)
    if provider_override:
        # Determine appropriate task type based on keyword, otherwise generic
        if "write code" in clean_input.lower() or "function" in clean_input.lower():
            t_type = TaskType.CODE_GENERATION
        else:
            t_type = TaskType.GENERAL
            
        classification = ClassificationResult(
            task_type=t_type,
            confidence=1.0,
            reasoning=f"Forced routing override to provider: {provider_override}",
            raw_input=clean_input,
        )
    else:
        classification = classifier.classify(clean_input)

    # 3. Handle Special Web Scrape Task
    if classification.task_type == TaskType.WEB_SCRAPE or lower_input.startswith("/scrape "):
        url = extract_url(clean_input)
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
            result, decision = router.route_text(
                prompt=f"Parse this system action request:\n\n{cmd_prompt}",
                classification=classification,
                system_prompt=SYSTEM_COMMAND_PROMPT,
                history=None
            )
            
            exec_res = execute_system_command(result.content)
            latency = (time.time() - start_time) * 1000

            if exec_res.get("success"):
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
    memory.add_user_message(clean_input)
    
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
        result, decision = router.route_text(
            prompt=clean_input,
            classification=classification,
            system_prompt=None,  # Config fallback matches system prompt
            history=memory.get_history()[:-1],
        )
        
        # Save assistant message
        memory.add_assistant_message(
            content=result.content,
            model_used=decision.model_actually_used,
            provider=decision.provider_actually_used,
            task_type=classification.task_type.value,
        )
        
        # Scan for code blocks and write files
        saved_files = process_response_for_files(result.content)
        
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
        return ChatResponse(
            success=False,
            content=f"⚠️ **Routing Failed**: {str(e)}\n\n*All primary and fallback providers failed to process this query. Please check your API keys or network connection.*",
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
