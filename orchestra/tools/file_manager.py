"""
OrchestraAI — File Manager Tool
=================================
File system operations: create, move, rename, search, delete files.
All operations include safety checks and user-friendly responses.
"""

import os
import shutil
import logging
from pathlib import Path
from typing import Dict, Any, List

logger = logging.getLogger("orchestra.file_manager")


def create_file(filepath: str, content: str = "") -> Dict[str, Any]:
    """Create a new file with optional content."""
    try:
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return {
            "success": True,
            "action": "create_file",
            "path": str(path.resolve()),
            "details": f"File created: {path.name} ({len(content)} chars)",
        }
    except Exception as e:
        return {"success": False, "error": f"Failed to create file: {e}"}


def move_file(source: str, destination: str) -> Dict[str, Any]:
    """Move a file or directory to a new location."""
    try:
        src = Path(source)
        if not src.exists():
            return {"success": False, "error": f"Source not found: {source}"}

        dst = Path(destination)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))

        return {
            "success": True,
            "action": "move_file",
            "from": str(src),
            "to": str(dst),
            "details": f"Moved: {src.name} → {dst}",
        }
    except Exception as e:
        return {"success": False, "error": f"Failed to move file: {e}"}


def rename_file(filepath: str, new_name: str) -> Dict[str, Any]:
    """Rename a file or directory."""
    try:
        path = Path(filepath)
        if not path.exists():
            return {"success": False, "error": f"File not found: {filepath}"}

        new_path = path.parent / new_name
        path.rename(new_path)

        return {
            "success": True,
            "action": "rename_file",
            "old_name": path.name,
            "new_name": new_name,
            "details": f"Renamed: {path.name} → {new_name}",
        }
    except Exception as e:
        return {"success": False, "error": f"Failed to rename file: {e}"}


def search_files(query: str, directory: str = None, max_results: int = 20) -> List[Dict[str, Any]]:
    """
    Search for files by name pattern in a directory tree.
    
    Args:
        query: Search term (matched against file names, case-insensitive).
        directory: Root directory to search. Defaults to user home.
        max_results: Maximum number of results to return.
    """
    if directory is None:
        directory = str(Path.home())

    results = []
    query_lower = query.lower()

    try:
        root = Path(directory)
        for item in root.rglob("*"):
            if len(results) >= max_results:
                break
            try:
                if query_lower in item.name.lower():
                    results.append({
                        "name": item.name,
                        "path": str(item),
                        "type": "directory" if item.is_dir() else "file",
                        "size_bytes": item.stat().st_size if item.is_file() else 0,
                    })
            except (PermissionError, OSError):
                continue
    except Exception as e:
        logger.warning(f"Search error in {directory}: {e}")

    return results


def delete_file(filepath: str) -> Dict[str, Any]:
    """
    Delete a file or empty directory.
    NOTE: This should only be called after user approval via ReviewDialog.
    """
    try:
        path = Path(filepath)
        if not path.exists():
            return {"success": False, "error": f"File not found: {filepath}"}

        if path.is_file():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(str(path))
        else:
            return {"success": False, "error": f"Unknown file type: {filepath}"}

        return {
            "success": True,
            "action": "delete_file",
            "path": str(path),
            "details": f"Deleted: {path.name}",
        }
    except Exception as e:
        return {"success": False, "error": f"Failed to delete: {e}"}


def read_file_content(filepath: str, max_chars: int = 5000) -> Dict[str, Any]:
    """Read and return the content of a text file."""
    try:
        path = Path(filepath)
        
        # If relative path doesn't exist, search common user directories
        if not path.exists() and not path.is_absolute():
            paths_to_check = [
                Path.home() / filepath,
                Path.home() / "Desktop" / filepath,
                Path.home() / "Documents" / filepath,
                Path.home() / "Downloads" / filepath
            ]
            try:
                from orchestra.config import settings
                paths_to_check.insert(0, Path(settings.project_root) / filepath)
            except Exception:
                pass
                
            for p in paths_to_check:
                try:
                    if p.exists() and p.is_file():
                        path = p
                        break
                except Exception:
                    continue

        if not path.exists():
            return {"success": False, "error": f"File not found: {filepath}"}
        if not path.is_file():
            return {"success": False, "error": f"Not a file: {filepath}"}

        content = path.read_text(encoding="utf-8", errors="replace")
        truncated = len(content) > max_chars
        if truncated:
            content = content[:max_chars] + "\n... [truncated]"

        return {
            "success": True,
            "action": "read_file",
            "path": str(path),
            "content": content,
            "truncated": truncated,
            "details": f"Read {path.name} ({len(content)} chars)",
        }
    except Exception as e:
        return {"success": False, "error": f"Failed to read file: {e}"}
