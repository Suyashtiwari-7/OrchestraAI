"""
OrchestraAI — Image Saver Tool
=================================
Handles saving generated images to disk with timestamped filenames,
and optionally opens them in the system's default image viewer.
"""

import os
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..config import settings
from ..providers.base import ImageResult

logger = logging.getLogger("orchestra.image_saver")


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
        ext = ".png" if "png" in getattr(image_result, "mime_type", "image/png") else ".jpg"
        filename = f"orchestra_image_{timestamp}{ext}"

    filepath = settings.output_images_dir / filename

    try:
        # Write image bytes to file
        filepath.write_bytes(image_result.image_data)

        prompt_str = getattr(image_result, "prompt", "")
        model_str = getattr(image_result, "model_used", "Imagen")
        logger.info(f"[+] Image saved to: {filepath} (Model: {model_str} | Prompt: {prompt_str[:60]}...)")

        # Open in default viewer
        if open_after_save:
            _open_image(filepath)

        return filepath

    except Exception as e:
        logger.error(f"[!] Failed to save image: {e}")
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
    except Exception as e:
        logger.debug(f"Could not open image viewer automatically: {e}")
