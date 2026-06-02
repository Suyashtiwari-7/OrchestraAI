"""
OrchestraAI — Image Saver Tool
=================================
Handles saving generated images to disk with timestamped filenames,
and optionally opens them in the system's default image viewer.
"""

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console

from ..config import settings
from ..providers.base import ImageResult

console = Console()


def save_image(
    image_result: ImageResult,
    filename: Optional[str] = None,
    open_after_save: bool = True,
) -> Optional[Path]:
    """
    Save a generated image to the output directory.

    Args:
        image_result: The ImageResult from the provider.
        filename: Optional custom filename. Auto-generates if None.
        open_after_save: Whether to open the image in the default viewer.

    Returns:
        Path to the saved file, or None on failure.
    """
    settings.ensure_dirs()

    # Generate filename
    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Determine extension from MIME type
        ext = ".png" if "png" in image_result.mime_type else ".jpg"
        filename = f"orchestra_image_{timestamp}{ext}"

    filepath = settings.output_images_dir / filename

    try:
        # Write image bytes to file
        filepath.write_bytes(image_result.image_data)

        console.print(
            f"\n  [bold green]🖼️  Image saved to:[/bold green] "
            f"[cyan]{filepath}[/cyan]"
        )
        console.print(
            f"  [dim]Model: {image_result.model_used} | "
            f"Prompt: \"{image_result.prompt[:60]}...\"[/dim]"
        )

        # Open in default viewer
        if open_after_save:
            _open_image(filepath)

        return filepath

    except Exception as e:
        console.print(f"  [red]✗ Failed to save image: {e}[/red]")
        return None


def _open_image(filepath: Path):
    """Open an image file with the system's default image viewer."""
    try:
        if sys.platform == "win32":
            os.startfile(str(filepath))
        elif sys.platform == "darwin":
            subprocess.run(["open", str(filepath)], check=False)
        else:
            subprocess.run(["xdg-open", str(filepath)], check=False)
    except Exception:
        # Silently fail if we can't open the viewer
        console.print("  [dim]Could not open image viewer automatically.[/dim]")
