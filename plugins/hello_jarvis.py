"""
OrchestraAI — Example Plugin: Hello World
=============================================
Demonstrates the plugin structure. Place this in /plugins/ to test.
Every plugin must define a `register()` function returning a dict.
"""


def greet(name: str = "Sir") -> str:
    """A simple greeting handler."""
    return f"Good evening, {name}. All systems are operational."


def system_status() -> str:
    """Return a quick system status summary."""
    import psutil
    cpu = psutil.cpu_percent(interval=0.3)
    mem = psutil.virtual_memory().percent
    return f"CPU at {cpu}%, Memory at {mem}%. Everything looks nominal."


def register() -> dict:
    """Register this plugin with OrchestraAI."""
    return {
        "name": "Hello JARVIS",
        "description": "Example plugin demonstrating the DARKI plugin architecture.",
        "actions": {
            "jarvis_greet": greet,
            "jarvis_status": system_status,
        },
        "keywords": ["hello jarvis", "jarvis status", "system status check"],
    }
