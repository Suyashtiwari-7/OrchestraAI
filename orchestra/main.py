"""
OrchestraAI — Main CLI Entry Point
=====================================
Beautiful, interactive terminal interface for the AI routing agent.
Uses the Rich library for styled output with colors, tables,
spinners, and panels.
"""

import sys
import time

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

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.markdown import Markdown
from rich.live import Live
from rich.spinner import Spinner
from rich.columns import Columns

from .config import (
    TaskType,
    ProviderName,
    MODELS,
    ROUTING_TABLE,
    api_keys,
    settings,
)
from .classifier import TaskClassifier
from .router import ModelRouter, RoutingDecision
from .memory.session_memory import SessionMemory
from .providers.base import ProviderError, ImageResult
from .tools.file_writer import process_response_for_files
from .tools.web_scraper import extract_url, scrape_url, format_scraped_content
from .tools.image_saver import save_image


console = Console()

PROVIDER_COLORS = {
    "gemini": "blue",
    "groq": "green",
    "cerebras": "magenta",
    "sambanova": "orange3",
    "mistral": "bright_red",
    "cohere": "cyan",
}

PROVIDER_EMOJIS = {
    "gemini": "🔵",
    "groq": "🟢",
    "cerebras": "🟣",
    "sambanova": "🌋",
    "mistral": "🌪️",
    "cohere": "🌿",
}

# System prompt that gives the AI its identity
SYSTEM_PROMPT = """You are OrchestraAI, an intelligent AI assistant powered by a multi-model routing system. 
You have been routed to the most appropriate AI model for this specific task.
Be helpful, accurate, and concise. When writing code, use fenced code blocks with the language specified.
When asked to create files, always output the complete code in a fenced code block."""


def print_banner():
    """Display the startup banner with ASCII art."""
    banner_text = """
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║    ♪  ╔═╗┬─┐┌─┐┬ ┬┌─┐┌─┐┌┬┐┬─┐┌─┐  ╔═╗╦              ║
║    ♫  ║ ║├┬┘│  ├─┤├┤ └─┐ │ ├┬┘├─┤  ╠═╣║              ║
║    ♪  ╚═╝┴└─└─┘┴ ┴└─┘└─┘ ┴ ┴└─┴ ┴  ╩ ╩╩═╝            ║
║                                                           ║
║       Intelligent AI Routing & Work Automation            ║
║                    v1.0.0                                 ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝"""

    console.print(banner_text, style="bold cyan")
    console.print()


def print_provider_status():
    """Display a table showing which providers are configured and active."""
    key_status = api_keys.validate()

    table = Table(
        title="[bold]Provider Status[/bold]",
        show_header=True,
        header_style="bold white",
        border_style="dim",
        padding=(0, 1),
    )
    table.add_column("Provider", style="bold")
    table.add_column("Status", justify="center")
    table.add_column("Models", style="dim")

    provider_models = {
        ProviderName.GEMINI: "Gemini 2.5 Pro, 2.0 Flash, Imagen 3",
        ProviderName.GROQ: "Qwen QwQ 32B, DeepSeek R1, Llama 3.3",
        ProviderName.CEREBRAS: "Llama 3.3 70B",
        ProviderName.SAMBANOVA: "Llama 3.1 405B, 70B",
        ProviderName.MISTRAL: "Codestral",
        ProviderName.COHERE: "Command R+",
    }

    for provider in ProviderName:
        is_active = key_status.get(provider, False)
        emoji = PROVIDER_EMOJIS.get(provider.value, "⚪")
        status = "[bold green]● Active[/bold green]" if is_active else "[red]○ Not configured[/red]"
        models = provider_models.get(provider, "")
        table.add_row(
            f"{emoji} {provider.value.capitalize()}",
            status,
            models,
        )

    console.print(table)
    console.print()

    # Warn if critical providers are missing
    if not key_status.get(ProviderName.GEMINI):
        console.print(
            "  [bold yellow]⚠ Gemini is not configured. "
            "This is the primary provider — most features will be limited.[/bold yellow]"
        )
        console.print(
            "  [dim]Get your free key at: https://aistudio.google.com/apikey[/dim]"
        )
        console.print()


def print_routing_decision(decision: RoutingDecision):
    """Display the routing decision in a compact, informative format."""
    provider = decision.provider_actually_used
    color = PROVIDER_COLORS.get(provider, "white")
    emoji = PROVIDER_EMOJIS.get(provider, "⚪")
    fallback_tag = " [yellow](fallback)[/yellow]" if decision.used_fallback else ""

    console.print(
        f"  [dim]🔀 Routed to[/dim] [{color}]{emoji} {decision.model_actually_used}[/{color}]"
        f"{fallback_tag}"
        f" [dim]│ {decision.task_type.value} "
        f"({decision.classification_confidence:.0%} confidence)[/dim]"
    )


def print_response(text: str, decision: RoutingDecision):
    """Display the model's response in a styled panel."""
    provider = decision.provider_actually_used
    color = PROVIDER_COLORS.get(provider, "white")
    emoji = PROVIDER_EMOJIS.get(provider, "⚪")

    console.print()
    console.print(
        Panel(
            Markdown(text),
            title=f"[bold {color}]{emoji} {decision.model_actually_used}[/bold {color}]",
            border_style=color,
            padding=(1, 2),
        )
    )


def print_stats(result, decision: RoutingDecision):
    """Display response statistics (latency, tokens)."""
    console.print(
        f"  [dim]⏱ {result.latency_ms:.0f}ms │ "
        f"📊 {result.input_tokens}→{result.output_tokens} tokens │ "
        f"🏷 {decision.task_type.value}[/dim]"
    )


def print_help():
    """Display available commands."""
    table = Table(
        title="[bold]Available Commands[/bold]",
        show_header=True,
        header_style="bold white",
        border_style="dim",
    )
    table.add_column("Command", style="bold cyan")
    table.add_column("Description")

    commands = [
        ("/help", "Show this help message"),
        ("/models", "List all available models and routing table"),
        ("/health", "Run health check on all providers"),
        ("/image <prompt>", "Generate an image from a text description"),
        ("/scrape <url>", "Scrape a webpage and summarize its content"),
        ("/history", "Show conversation history"),
        ("/clear", "Clear conversation history"),
        ("/export", "Export conversation history to JSON"),
        ("@gemini <msg>", "Force route to Gemini"),
        ("@groq <msg>", "Force route to Groq"),
        ("@cerebras <msg>", "Force route to Cerebras"),
        ("@sambanova <msg>", "Force route to SambaNova (Llama 405B)"),
        ("@mistral <msg>", "Force route to Mistral (Codestral)"),
        ("@cohere <msg>", "Force route to Cohere (Command R+)"),
        ("/exit or /quit", "Exit OrchestraAI"),
    ]

    for cmd, desc in commands:
        table.add_row(cmd, desc)

    console.print(table)


def print_models():
    """Display the full model routing table."""
    table = Table(
        title="[bold]Model Routing Table[/bold]",
        show_header=True,
        header_style="bold white",
        border_style="dim",
    )
    table.add_column("Task Type", style="bold")
    table.add_column("Primary Model", style="cyan")
    table.add_column("Fallback Model", style="yellow")
    table.add_column("Description", style="dim")

    task_emojis = {
        TaskType.DEEP_REASONING: "🧠",
        TaskType.CODE_GENERATION: "💻",
        TaskType.CREATIVE: "🎨",
        TaskType.FAST_UTILITY: "⚡",
        TaskType.IMAGE_GENERATION: "🖼️",
        TaskType.WEB_SCRAPE: "🌐",
        TaskType.GENERAL: "💬",
    }

    for task_type, route in ROUTING_TABLE.items():
        primary = MODELS[route.primary]
        fallback = MODELS[route.fallback]
        emoji = task_emojis.get(task_type, "")
        table.add_row(
            f"{emoji} {task_type.value}",
            primary.display_name,
            fallback.display_name,
            route.description,
        )

    console.print(table)


def print_history(memory: SessionMemory):
    """Display conversation history."""
    history = memory.get_full_history()

    if not history:
        console.print("  [dim]No conversation history yet.[/dim]")
        return

    console.print(f"\n  [bold]Conversation History ({memory.turn_count} turns)[/bold]\n")

    for entry in history:
        if entry.role == "user":
            console.print(f"  [bold cyan]You:[/bold cyan] {entry.content[:100]}{'...' if len(entry.content) > 100 else ''}")
        else:
            model_tag = f" [dim]({entry.model_used})[/dim]" if entry.model_used else ""
            console.print(f"  [bold green]AI{model_tag}:[/bold green] {entry.content[:100]}{'...' if len(entry.content) > 100 else ''}")


def handle_health_check(router: ModelRouter):
    """Run and display health check results."""
    console.print("\n  [bold]Running health checks...[/bold]\n")

    results = router.health_check_all()

    for provider, healthy in results.items():
        emoji = PROVIDER_EMOJIS.get(provider, "⚪")
        if healthy:
            console.print(f"  {emoji} {provider.capitalize()}: [bold green]✓ Healthy[/bold green]")
        else:
            console.print(f"  {emoji} {provider.capitalize()}: [bold red]✗ Unreachable[/bold red]")

    console.print()


def handle_image_generation(prompt: str, router: ModelRouter):
    """Handle the /image command."""
    console.print(f"\n  [bold]🖼️  Generating image...[/bold]")
    console.print(f"  [dim]Prompt: \"{prompt}\"[/dim]\n")

    try:
        image_result, decision = router.route_image(prompt)
        print_routing_decision(decision)
        save_image(image_result)
    except ProviderError as e:
        console.print(f"  [bold red]✗ {e}[/bold red]")


def handle_web_scrape(user_input: str, router: ModelRouter, classifier: TaskClassifier, memory: SessionMemory):
    """Handle the /scrape command or auto-detected URLs."""
    url = extract_url(user_input)

    if not url:
        console.print("  [red]✗ No valid URL found in input.[/red]")
        return

    # Scrape the URL
    scrape_result = scrape_url(url)

    if not scrape_result["success"]:
        console.print(f"  [red]✗ {scrape_result['error']}[/red]")
        return

    # Format the scraped content as a prompt
    formatted_prompt = format_scraped_content(scrape_result)

    # Route to an LLM for summarization
    from .classifier import ClassificationResult
    classification = ClassificationResult(
        task_type=TaskType.WEB_SCRAPE,
        confidence=1.0,
        reasoning="Web scrape — summarizing fetched content.",
        raw_input=formatted_prompt,
    )

    try:
        result, decision = router.route_text(
            prompt=formatted_prompt,
            classification=classification,
            system_prompt="You are a web content analyzer. Summarize the provided webpage content clearly and concisely. Highlight key points, main arguments, and important details.",
            history=None,  # Don't pollute scrape summaries with chat history
        )

        print_routing_decision(decision)
        print_response(result.content, decision)
        print_stats(result, decision)

        # Save to memory
        memory.add_user_message(f"/scrape {url}")
        memory.add_assistant_message(
            content=result.content,
            model_used=decision.model_actually_used,
            provider=decision.provider_actually_used,
            task_type="web_scrape",
        )

    except ProviderError as e:
        console.print(f"  [bold red]✗ {e}[/bold red]")


def main():
    """Main application loop."""
    # --- Startup ---
    print_banner()
    print_provider_status()

    # Check if any provider is configured
    key_status = api_keys.validate()
    if not any(key_status.values()):
        console.print(
            Panel(
                "[bold red]No API keys configured![/bold red]\n\n"
                "1. Copy [cyan].env.example[/cyan] to [cyan].env[/cyan]\n"
                "2. Add your API keys (at least one provider)\n"
                "3. Run again\n\n"
                "[dim]Get free keys at:\n"
                "  • Google: https://aistudio.google.com/apikey\n"
                "  • Groq:   https://console.groq.com/keys\n"
                "  • Cerebras: https://cloud.cerebras.ai/[/dim]",
                title="[bold red]⚠ Setup Required[/bold red]",
                border_style="red",
            )
        )
        sys.exit(1)

    # Initialize components
    classifier = TaskClassifier()
    router = ModelRouter()
    memory = SessionMemory()

    console.print("  [dim]Type [bold]/help[/bold] for commands, or just start chatting![/dim]")
    console.print("  [dim]Type [bold]/exit[/bold] to quit.[/dim]\n")

    # --- Main Loop ---
    while True:
        try:
            # Get user input
            console.print("[bold cyan]╭─[/bold cyan]")
            user_input = console.input("[bold cyan]╰─➤ [/bold cyan]").strip()

            if not user_input:
                continue

            # --- Handle special commands ---
            lower_input = user_input.lower()

            if lower_input in ("/exit", "/quit", "exit", "quit"):
                console.print("\n  [dim]👋 Goodbye! OrchestraAI signing off.[/dim]\n")
                break

            if lower_input == "/help":
                print_help()
                continue

            if lower_input == "/models":
                print_models()
                continue

            if lower_input == "/health":
                handle_health_check(router)
                continue

            if lower_input == "/history":
                print_history(memory)
                continue

            if lower_input == "/clear":
                memory.clear()
                console.print("  [green]✓ Conversation history cleared.[/green]")
                continue

            if lower_input == "/export":
                path = memory.export_to_json()
                console.print(f"  [green]✓ History exported to {path}[/green]")
                continue

            if lower_input.startswith("/image "):
                image_prompt = user_input[7:].strip()
                if image_prompt:
                    handle_image_generation(image_prompt, router)
                else:
                    console.print("  [red]Usage: /image <description>[/red]")
                continue

            if lower_input.startswith("/scrape "):
                handle_web_scrape(user_input, router, classifier, memory)
                continue

            # --- Classify and route ---
            console.print()

            # Classify the task
            classification = classifier.classify(user_input)

            # Handle URL detection (auto web scrape)
            if classification.task_type == TaskType.WEB_SCRAPE:
                handle_web_scrape(user_input, router, classifier, memory)
                continue

            # Handle image generation
            if classification.task_type == TaskType.IMAGE_GENERATION:
                # Extract the image prompt (remove /image prefix if present)
                image_prompt = classification.raw_input or user_input
                if image_prompt.lower().startswith("/image "):
                    image_prompt = image_prompt[7:]
                handle_image_generation(image_prompt, router)
                continue

            # Store user message in memory
            actual_prompt = classification.raw_input if classification.raw_input else user_input
            memory.add_user_message(actual_prompt)

            # Route to the appropriate model
            try:
                result, decision = router.route_text(
                    prompt=actual_prompt,
                    classification=classification,
                    system_prompt=SYSTEM_PROMPT,
                    history=memory.get_history()[:-1],  # Exclude the just-added message
                )

                # Display the response
                print_routing_decision(decision)
                print_response(result.content, decision)
                print_stats(result, decision)

                # Store assistant response in memory
                memory.add_assistant_message(
                    content=result.content,
                    model_used=decision.model_actually_used,
                    provider=decision.provider_actually_used,
                    task_type=classification.task_type.value,
                )

                # Check for code blocks and offer to save
                process_response_for_files(result.content)

            except ProviderError as e:
                console.print(f"\n  [bold red]✗ Routing failed: {e}[/bold red]")
                console.print("  [dim]Try a different provider with @gemini, @groq, or @cerebras[/dim]")

            console.print()

        except KeyboardInterrupt:
            console.print("\n\n  [dim]👋 Interrupted. Goodbye![/dim]\n")
            break
        except EOFError:
            break


def run():
    """Entry point wrapper."""
    main()


if __name__ == "__main__":
    main()
