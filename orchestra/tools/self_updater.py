"""
OrchestraAI — In-App Self Updater
====================================
Lightweight in-process Python update script that checks GitHub Releases
for new versions, downloads the update package, and applies it.

Replaces the previous standalone compiled updater.exe approach.
"""

import os
import sys
import json
import shutil
import logging
import tempfile
import zipfile
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

import httpx

from ..config import settings

logger = logging.getLogger("orchestra.tools.self_updater")

# GitHub repository for OrchestraAI
GITHUB_REPO = "Suyashtiwari-7/OrchestraAI"
RELEASES_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


def check_for_updates() -> Dict[str, Any]:
    """
    Check GitHub Releases API for the latest version.

    Returns:
        Dict with 'update_available', 'current_version', 'latest_version',
        and 'download_url' if an update is found.
    """
    current_version = settings.app_version

    try:
        response = httpx.get(RELEASES_API, timeout=10.0, follow_redirects=True)
        if response.status_code != 200:
            return {
                "update_available": False,
                "error": f"GitHub API returned status {response.status_code}",
                "current_version": current_version,
            }

        release = response.json()
        latest_tag = release.get("tag_name", "").lstrip("v")
        download_url = None

        # Find the zip asset in the release
        for asset in release.get("assets", []):
            if asset["name"].endswith(".zip"):
                download_url = asset["browser_download_url"]
                break

        # Fallback to source zip if no asset found
        if not download_url:
            download_url = release.get("zipball_url")

        is_newer = _compare_versions(latest_tag, current_version)

        return {
            "update_available": is_newer,
            "current_version": current_version,
            "latest_version": latest_tag,
            "download_url": download_url,
            "release_notes": release.get("body", "")[:500],
        }

    except Exception as e:
        logger.error(f"[!] Error checking for updates: {e}")
        return {
            "update_available": False,
            "error": str(e),
            "current_version": current_version,
        }


def download_update(download_url: str) -> Dict[str, Any]:
    """
    Download the update zip from the given URL to a temp directory.

    Args:
        download_url: The URL to download the update zip from.

    Returns:
        Dict with 'success', 'download_path' on success.
    """
    try:
        temp_dir = Path(tempfile.mkdtemp(prefix="darki_update_"))
        zip_path = temp_dir / "update.zip"

        logger.info(f"[*] Downloading update from: {download_url}")

        with httpx.stream("GET", download_url, timeout=60.0, follow_redirects=True) as response:
            if response.status_code != 200:
                return {"success": False, "error": f"Download failed with status {response.status_code}"}

            total = int(response.headers.get("content-length", 0))
            downloaded = 0

            with open(zip_path, "wb") as f:
                for chunk in response.iter_bytes(chunk_size=8192):
                    f.write(chunk)
                    downloaded += len(chunk)

        logger.info(f"[+] Downloaded {downloaded} bytes to {zip_path}")
        return {
            "success": True,
            "download_path": str(zip_path),
            "size_bytes": downloaded,
        }

    except Exception as e:
        logger.error(f"[!] Error downloading update: {e}")
        return {"success": False, "error": str(e)}


def apply_update(zip_path: str) -> Dict[str, Any]:
    """
    Extract the update zip and replace project files, then restart DARKI.

    Args:
        zip_path: Path to the downloaded update zip file.

    Returns:
        Dict with 'success' and details. On success, DARKI restarts automatically.
    """
    try:
        zip_file = Path(zip_path)
        if not zip_file.exists():
            return {"success": False, "error": f"Update file not found: {zip_path}"}

        extract_dir = zip_file.parent / "extracted"

        # Extract the zip
        with zipfile.ZipFile(zip_file, "r") as zf:
            zf.extractall(extract_dir)

        logger.info(f"[+] Extracted update to {extract_dir}")

        # Find the root directory in the extracted zip (GitHub zips have a nested folder)
        extracted_contents = list(extract_dir.iterdir())
        source_dir = extracted_contents[0] if len(extracted_contents) == 1 and extracted_contents[0].is_dir() else extract_dir

        # Copy updated files to project root
        target_dir = settings.project_root
        for item in source_dir.rglob("*"):
            if item.is_file():
                rel = item.relative_to(source_dir)
                dest = target_dir / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, dest)

        logger.info("[+] Update applied successfully. Restarting DARKI...")

        # Cleanup temp files
        shutil.rmtree(zip_file.parent, ignore_errors=True)

        return {
            "success": True,
            "action": "updated",
            "details": "Update applied. Please restart DARKI to use the new version.",
        }

    except Exception as e:
        logger.error(f"[!] Error applying update: {e}")
        return {"success": False, "error": str(e)}


def _compare_versions(latest: str, current: str) -> bool:
    """
    Compare version strings (e.g., '1.2.0' vs '1.1.0').
    Returns True if latest is newer than current.
    """
    try:
        latest_parts = [int(x) for x in latest.split(".")]
        current_parts = [int(x) for x in current.split(".")]

        # Pad shorter version with zeros
        max_len = max(len(latest_parts), len(current_parts))
        latest_parts.extend([0] * (max_len - len(latest_parts)))
        current_parts.extend([0] * (max_len - len(current_parts)))

        return latest_parts > current_parts
    except (ValueError, AttributeError):
        # If parsing fails, assume no update
        return False
