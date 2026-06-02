"""
OrchestraAI — File Writer Tool
=================================
Detects code blocks in LLM responses and automatically extracts
them to physical files on disk. Supports multiple languages and
asks for user confirmation before writing.
"""

import re
from pathlib import Path
from datetime import datetime
from typing import Optional

from rich.console import Console
from rich.syntax import Syntax
from rich.prompt import Confirm
from rich.panel import Panel

from ..config import settings


console = Console()

# Map language identifiers to file extensions
LANGUAGE_EXTENSIONS = {
    "python": ".py",
    "py": ".py",
    "javascript": ".js",
    "js": ".js",
    "typescript": ".ts",
    "ts": ".ts",
    "html": ".html",
    "css": ".css",
    "json": ".json",
    "yaml": ".yaml",
    "yml": ".yml",
    "markdown": ".md",
    "md": ".md",
    "bash": ".sh",
    "shell": ".sh",
    "sh": ".sh",
    "sql": ".sql",
    "java": ".java",
    "cpp": ".cpp",
    "c++": ".cpp",
    "c": ".c",
    "rust": ".rs",
    "go": ".go",
    "ruby": ".rb",
    "php": ".php",
    "swift": ".swift",
    "kotlin": ".kt",
    "r": ".r",
    "text": ".txt",
    "txt": ".txt",
    "xml": ".xml",
    "toml": ".toml",
    "ini": ".ini",
    "dockerfile": ".dockerfile",
    "makefile": ".makefile",
}


def extract_code_blocks(text: str) -> list[dict]:
    """
    Extract all fenced code blocks from a text response.

    Detects patterns like:
        ```python
        print("hello")
        ```

    Returns:
        List of dicts with 'language', 'code', and 'extension' keys.
    """
    pattern = r'```(\w*)\n(.*?)```'
    matches = re.findall(pattern, text, re.DOTALL)

    blocks = []
    for lang, code in matches:
        lang = lang.lower().strip() if lang else "text"
        extension = LANGUAGE_EXTENSIONS.get(lang, ".txt")
        blocks.append({
            "language": lang,
            "code": code.strip(),
            "extension": extension,
        })

    return blocks


def save_code_to_file(
    code: str,
    extension: str,
    language: str,
    filename: Optional[str] = None,
    auto_confirm: bool = False,
) -> Optional[Path]:
    """
    Save a code block to a file in the output directory.

    Args:
        code: The code content to save.
        extension: File extension (e.g., '.py').
        language: Language name for display.
        filename: Optional custom filename. If None, auto-generates one.
        auto_confirm: If True, skip the confirmation prompt.

    Returns:
        Path to the saved file, or None if the user declined.
    """
    settings.ensure_dirs()

    # Generate filename if not provided
    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"orchestra_{timestamp}{extension}"

    filepath = settings.output_code_dir / filename

    # Preview the code
    console.print()
    console.print(
        Panel(
            Syntax(code, language, theme="monokai", line_numbers=True),
            title=f"[bold cyan]📄 Code Block Detected ({language})[/bold cyan]",
            subtitle=f"[dim]{filename}[/dim]",
            border_style="cyan",
        )
    )

    # Ask for confirmation
    if not auto_confirm:
        save = Confirm.ask(
            f"  [bold]Save to[/bold] [green]{filepath}[/green]?",
            default=True,
        )
        if not save:
            console.print("  [dim]Skipped.[/dim]")
            return None

    # Write the file
    filepath.write_text(code, encoding="utf-8")
    console.print(f"  [bold green]✓ Saved to {filepath}[/bold green]")
    return filepath


def process_response_for_files(response_text: str) -> list[Path]:
    """
    Scan an LLM response for code blocks and offer to save each one.

    Args:
        response_text: The full text response from the LLM.

    Returns:
        List of paths to saved files.
    """
    blocks = extract_code_blocks(response_text)

    if not blocks:
        return []

    saved_files = []
    console.print(
        f"\n  [bold yellow]📦 Found {len(blocks)} code block(s) in response.[/bold yellow]"
    )

    for i, block in enumerate(blocks):
        console.print(f"\n  [dim]Block {i + 1}/{len(blocks)}:[/dim]")
        path = save_code_to_file(
            code=block["code"],
            extension=block["extension"],
            language=block["language"],
        )
        if path:
            saved_files.append(path)

    return saved_files
