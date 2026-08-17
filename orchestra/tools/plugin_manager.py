"""
OrchestraAI — Plugin Manager
================================
Dynamically discovers and loads user-created plugins from the /plugins directory.
Each plugin is a Python file that exposes a `register()` function returning a dict
describing its capabilities (actions, keywords, handler functions).

Plugin Structure Example:
    plugins/
        spotify_control.py
        smart_home.py

Each plugin file must define:
    def register() -> dict:
        return {
            "name": "Spotify Control",
            "description": "Play, pause, and search music on Spotify.",
            "actions": {
                "spotify_play": handler_play,
                "spotify_pause": handler_pause,
            },
            "keywords": ["play music", "pause music", "spotify"],
        }
"""

import os
import sys
import importlib.util
import logging
from pathlib import Path
from typing import Dict, Any, Callable, List, Optional

logger = logging.getLogger("orchestra.plugins")


class PluginManager:
    """
    Discovers and manages user plugins for extending DARKI's capabilities.
    Plugins are Python scripts in the /plugins directory with a register() function.
    """

    def __init__(self, plugins_dir: Optional[Path] = None):
        """
        Args:
            plugins_dir: Path to the plugins directory. Defaults to PROJECT_ROOT/plugins.
        """
        if plugins_dir is None:
            from ..config import PROJECT_ROOT
            plugins_dir = PROJECT_ROOT / "plugins"

        self.plugins_dir = Path(plugins_dir)
        self._plugins: Dict[str, Dict[str, Any]] = {}
        self._actions: Dict[str, Callable] = {}
        self._keywords: Dict[str, str] = {}  # keyword -> plugin_name mapping

    def discover(self) -> int:
        """
        Scan the plugins directory and load all valid plugin files.
        Returns the number of plugins successfully loaded.
        """
        if not self.plugins_dir.exists():
            self.plugins_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created plugins directory: {self.plugins_dir}")
            return 0

        loaded = 0
        for filepath in self.plugins_dir.glob("*.py"):
            if filepath.name.startswith("_"):
                continue  # Skip __init__.py and private files

            try:
                plugin_info = self._load_plugin(filepath)
                if plugin_info:
                    name = plugin_info.get("name", filepath.stem)
                    self._plugins[name] = plugin_info

                    # Register actions
                    for action_name, handler in plugin_info.get("actions", {}).items():
                        self._actions[action_name] = handler
                        logger.info(f"  Registered action: {action_name}")

                    # Register keywords for intent matching
                    for keyword in plugin_info.get("keywords", []):
                        self._keywords[keyword.lower()] = name

                    loaded += 1
                    logger.info(f"Loaded plugin: {name} ({filepath.name})")
            except Exception as e:
                logger.error(f"Failed to load plugin {filepath.name}: {e}")

        logger.info(f"Plugin discovery complete: {loaded} plugin(s) loaded.")
        return loaded

    def _load_plugin(self, filepath: Path) -> Optional[Dict[str, Any]]:
        """Load a single plugin file and call its register() function."""
        spec = importlib.util.spec_from_file_location(filepath.stem, str(filepath))
        if spec is None or spec.loader is None:
            return None

        module = importlib.util.module_from_spec(spec)
        sys.modules[filepath.stem] = module
        spec.loader.exec_module(module)

        if not hasattr(module, "register"):
            logger.warning(f"Plugin {filepath.name} has no register() function — skipped.")
            return None

        return module.register()

    def get_action(self, action_name: str) -> Optional[Callable]:
        """Get a registered action handler by name."""
        return self._actions.get(action_name)

    def execute_action(self, action_name: str, **kwargs) -> Dict[str, Any]:
        """Execute a plugin action by name with the given arguments."""
        handler = self._actions.get(action_name)
        if handler is None:
            return {"success": False, "error": f"Unknown plugin action: {action_name}"}

        try:
            result = handler(**kwargs)
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": f"Plugin action '{action_name}' failed: {e}"}

    def match_keyword(self, user_input: str) -> Optional[str]:
        """
        Check if user input matches any plugin keyword.
        Returns the plugin name if matched, None otherwise.
        """
        lower_input = user_input.lower()
        for keyword, plugin_name in self._keywords.items():
            if keyword in lower_input:
                return plugin_name
        return None

    def list_plugins(self) -> List[Dict[str, Any]]:
        """Return a list of all loaded plugins with their metadata."""
        result = []
        for name, info in self._plugins.items():
            result.append({
                "name": name,
                "description": info.get("description", ""),
                "actions": list(info.get("actions", {}).keys()),
                "keywords": info.get("keywords", []),
            })
        return result
