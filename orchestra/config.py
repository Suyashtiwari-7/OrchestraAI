"""
OrchestraAI — Configuration Module
===================================
Loads API keys, defines model routing table, and manages all settings.
"""

import os
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


# ============================================
# Load environment variables
# ============================================
# Look for .env in the project root (two levels up from this file) or next to the executable if frozen
if getattr(sys, 'frozen', False):
    PROJECT_ROOT = Path(sys.executable).parent
else:
    PROJECT_ROOT = Path(__file__).resolve().parent.parent

ENV_PATH = PROJECT_ROOT / ".env"
load_dotenv(ENV_PATH)


# ============================================
# Task Types — what the classifier outputs
# ============================================
class TaskType(Enum):
    """Categories of tasks that the classifier can identify."""
    DEEP_REASONING = "deep_reasoning"
    CODE_GENERATION = "code_generation"
    CREATIVE = "creative"
    FAST_UTILITY = "fast_utility"
    IMAGE_GENERATION = "image_generation"
    WEB_SCRAPE = "web_scrape"
    SYSTEM_COMMAND = "system_command"
    WEB_SEARCH = "web_search"
    GENERAL = "general"


# ============================================
# Provider Registry
# ============================================
class ProviderName(Enum):
    """Supported LLM API providers."""
    GEMINI = "gemini"
    GROQ = "groq"
    CEREBRAS = "cerebras"
    SAMBANOVA = "sambanova"
    MISTRAL = "mistral"
    COHERE = "cohere"
    HUGGINGFACE = "huggingface"
    OLLAMA = "ollama"


# ============================================
# Model Configuration
# ============================================
@dataclass
class ModelConfig:
    """Configuration for a specific model on a specific provider."""
    provider: ProviderName
    model_id: str
    display_name: str
    max_tokens: int = 4096
    temperature: float = 0.7
    supports_images: bool = False


# ============================================
# Pre-defined Models
# ============================================
MODELS = {
    # --- Google Gemini ---
    "gemini-2.5-pro": ModelConfig(
        provider=ProviderName.GEMINI,
        model_id="gemini-2.5-pro",
        display_name="Gemini 2.5 Pro",
        max_tokens=8192,
        temperature=0.7,
    ),
    "gemini-2.0-flash": ModelConfig(
        provider=ProviderName.GEMINI,
        model_id="gemini-2.0-flash",
        display_name="Gemini 2.0 Flash",
        max_tokens=4096,
        temperature=0.5,
    ),
    "gemini-imagen": ModelConfig(
        provider=ProviderName.GEMINI,
        model_id="imagen-3.0-generate-002",
        display_name="Imagen 3",
        supports_images=True,
    ),

    # --- Groq ---
    "groq-qwen": ModelConfig(
        provider=ProviderName.GROQ,
        model_id="qwen-qwq-32b",
        display_name="Qwen QwQ 32B (Groq)",
        max_tokens=4096,
        temperature=0.5,
    ),
    "groq-deepseek": ModelConfig(
        provider=ProviderName.GROQ,
        model_id="deepseek-r1-distill-llama-70b",
        display_name="DeepSeek R1 70B (Groq)",
        max_tokens=4096,
        temperature=0.6,
    ),
    "groq-llama": ModelConfig(
        provider=ProviderName.GROQ,
        model_id="llama-3.3-70b-versatile",
        display_name="Llama 3.3 70B (Groq)",
        max_tokens=4096,
        temperature=0.7,
    ),

    # --- Cerebras ---
    "cerebras-llama": ModelConfig(
        provider=ProviderName.CEREBRAS,
        model_id="llama-3.3-70b",
        display_name="Llama 3.3 70B (Cerebras)",
        max_tokens=4096,
        temperature=0.7,
    ),

    # --- SambaNova ---
    "sambanova-llama-405b": ModelConfig(
        provider=ProviderName.SAMBANOVA,
        model_id="Meta-Llama-3.1-405B-Instruct",
        display_name="Llama 3.1 405B (SambaNova)",
        max_tokens=4096,
        temperature=0.7,
    ),

    # --- Mistral ---
    "mistral-codestral": ModelConfig(
        provider=ProviderName.MISTRAL,
        model_id="codestral-latest",
        display_name="Codestral (Mistral)",
        max_tokens=4096,
        temperature=0.3,  # lower temp for coding tasks
    ),

    # --- Cohere ---
    "cohere-command-r-plus": ModelConfig(
        provider=ProviderName.COHERE,
        model_id="command-r-plus",
        display_name="Command R+ (Cohere)",
        max_tokens=4096,
        temperature=0.3,
    ),

    # --- Hugging Face ---
    "hf-llama": ModelConfig(
        provider=ProviderName.HUGGINGFACE,
        model_id="meta-llama/Llama-3.3-70B-Instruct",
        display_name="Llama 3.3 70B (Hugging Face)",
        max_tokens=2048,
        temperature=0.7,
    ),

    # --- Local Ollama ---
    "local-llama": ModelConfig(
        provider=ProviderName.OLLAMA,
        model_id=os.getenv("OLLAMA_MODEL", "llama3.2"),
        display_name="Local Llama (Ollama)",
        max_tokens=4096,
        temperature=0.7,
    ),
}


# ============================================
# Routing Table — Task → Model mapping
# ============================================
@dataclass
class RouteConfig:
    """Defines primary and fallback model for a task type."""
    primary: str        # Key into MODELS dict
    fallback: str       # Key into MODELS dict
    description: str    # Human-readable description


ROUTING_TABLE: dict[TaskType, RouteConfig] = {
    TaskType.DEEP_REASONING: RouteConfig(
        primary="groq-deepseek",
        fallback="gemini-2.5-pro",
        description="Complex analysis, math, logic, multi-step reasoning",
    ),
    TaskType.CODE_GENERATION: RouteConfig(
        primary="mistral-codestral",
        fallback="groq-deepseek",
        description="Write, debug, explain, or review code",
    ),
    TaskType.CREATIVE: RouteConfig(
        primary="groq-llama",
        fallback="gemini-2.5-pro",
        description="Brainstorming, creative writing, content generation",
    ),
    TaskType.FAST_UTILITY: RouteConfig(
        primary="groq-llama",
        fallback="mistral-codestral",
        description="Formatting, extraction, classification, quick summaries",
    ),
    TaskType.IMAGE_GENERATION: RouteConfig(
        primary="gemini-imagen",
        fallback="gemini-imagen",  # Pollinations.ai fallback handled in router code
        description="Generate images from text prompts",
    ),
    TaskType.WEB_SCRAPE: RouteConfig(
        primary="groq-llama",
        fallback="mistral-codestral",
        description="Scrape a URL and summarize/analyze its content",
    ),
    TaskType.GENERAL: RouteConfig(
        primary="groq-llama",
        fallback="gemini-2.5-pro",
        description="General conversation and Q&A",
    ),
    TaskType.SYSTEM_COMMAND: RouteConfig(
        primary="groq-llama",
        fallback="gemini-2.0-flash",
        description="Launch local applications or open websites in specific browsers",
    ),
    TaskType.WEB_SEARCH: RouteConfig(
        primary="groq-llama",
        fallback="mistral-codestral",
        description="Search the web for real-time information using DuckDuckGo",
    ),
}


# ============================================
# API Key Management
# ============================================
@dataclass
class APIKeys:
    """Container for all API keys."""
    gemini: Optional[str] = None
    groq: Optional[str] = None
    cerebras: Optional[str] = None
    sambanova: Optional[str] = None
    mistral: Optional[str] = None
    cohere: Optional[str] = None
    huggingface: Optional[str] = None
    ollama_host: Optional[str] = None
    ollama_model: Optional[str] = None

    @classmethod
    def from_env(cls) -> "APIKeys":
        """Load API keys from environment variables."""
        return cls(
            gemini=os.getenv("GEMINI_API_KEY"),
            groq=os.getenv("GROQ_API_KEY"),
            cerebras=os.getenv("CEREBRAS_API_KEY"),
            sambanova=os.getenv("SAMBANOVA_API_KEY"),
            mistral=os.getenv("MISTRAL_API_KEY"),
            cohere=os.getenv("COHERE_API_KEY"),
            huggingface=os.getenv("HUGGINGFACE_API_TOKEN"),
            ollama_host=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
            ollama_model=os.getenv("OLLAMA_MODEL", "llama3.2"),
        )

    def get_key(self, provider: ProviderName) -> Optional[str]:
        """Get the API key for a specific provider."""
        key_map = {
            ProviderName.GEMINI: self.gemini,
            ProviderName.GROQ: self.groq,
            ProviderName.CEREBRAS: self.cerebras,
            ProviderName.SAMBANOVA: self.sambanova,
            ProviderName.MISTRAL: self.mistral,
            ProviderName.COHERE: self.cohere,
            ProviderName.HUGGINGFACE: self.huggingface,
            ProviderName.OLLAMA: self.ollama_host,
        }
        return key_map.get(provider)

    def validate(self) -> dict[ProviderName, bool]:
        """Check which providers have valid (non-empty) keys configured."""
        return {
            ProviderName.GEMINI: bool(self.gemini and self.gemini != "your_gemini_api_key_here"),
            ProviderName.GROQ: bool(self.groq and self.groq != "your_groq_api_key_here"),
            ProviderName.CEREBRAS: bool(self.cerebras and self.cerebras != "your_cerebras_api_key_here" and self.cerebras != "your_key_here"),
            ProviderName.SAMBANOVA: bool(self.sambanova and self.sambanova != "your_sambanova_api_key_here" and self.sambanova != "your_key_here"),
            ProviderName.MISTRAL: bool(self.mistral and self.mistral != "your_mistral_api_key_here" and self.mistral != "your_key_here"),
            ProviderName.COHERE: bool(self.cohere and self.cohere != "your_cohere_api_key_here" and self.cohere != "your_key_here"),
            ProviderName.HUGGINGFACE: bool(self.huggingface),
            ProviderName.OLLAMA: bool(self.ollama_host),
        }


# ============================================
# Application Settings
# ============================================
@dataclass
class AppSettings:
    """Global application settings."""
    # Paths
    project_root: Path = field(default_factory=lambda: PROJECT_ROOT)
    output_code_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "output" / "code")
    output_images_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "output" / "images")

    # Retry & timeout
    max_retries: int = 1
    request_timeout: int = 30  # seconds
    retry_delay: float = 0.5   # seconds between retries

    # Memory
    max_history_turns: int = 20  # Keep last N conversation turns

    # Classifier
    classifier_model: str = "gemini-2.0-flash"

    # Display
    app_name: str = "DARKI"
    app_version: str = "1.0.0"
    app_tagline: str = "Your Personal AI Friend & Work Companion"

    # SMTP Settings (Optional, for background email fallback)
    smtp_server: Optional[str] = field(default_factory=lambda: os.getenv("SMTP_SERVER"))
    smtp_port: int = field(default_factory=lambda: int(os.getenv("SMTP_PORT", "587")) if os.getenv("SMTP_PORT") else 587)
    smtp_email: Optional[str] = field(default_factory=lambda: os.getenv("SMTP_EMAIL"))
    smtp_password: Optional[str] = field(default_factory=lambda: os.getenv("SMTP_PASSWORD"))

    def ensure_dirs(self):
        """Create output directories if they don't exist."""
        self.output_code_dir.mkdir(parents=True, exist_ok=True)
        self.output_images_dir.mkdir(parents=True, exist_ok=True)


# ============================================
# Global singletons — import these elsewhere
# ============================================
settings = AppSettings()
api_keys = APIKeys.from_env()
