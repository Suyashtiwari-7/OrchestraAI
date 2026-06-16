"""
OrchestraAI — Native Desktop Window Wrapper
============================================
Launches the FastAPI server in a background daemon thread and creates
a standalone desktop app window utilizing pywebview.
"""

import sys
import os
import time
import threading
from pathlib import Path
import uvicorn
import webview

# Add project root to sys.path to ensure uvicorn finds the 'orchestra' module
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

def run_server():
    """Start uvicorn web server in the background thread."""
    # We restrict it to 127.0.0.1 for desktop loopback security
    uvicorn.run("orchestra.server:app", host="127.0.0.1", port=8000, log_level="warning")

class MascotAPI:
    def __init__(self):
        self.window = None

    def resize_window(self, width, height):
        if self.window:
            self.window.resize(width, height)

def main():
    # Start the server daemon thread
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    
    # Wait for the FastAPI server to initialize
    time.sleep(1.2)
    
    # Check if running as a frozen executable
    is_frozen = getattr(sys, 'frozen', False)
    
    # Create pywebview native window wrapper
    # NOTE: Only creating a single window — dual windows (main + mascot)
    # cause WebView2 COM threading crashes on Windows.
    window = webview.create_window(
        title="OrchestraAI",
        url="http://127.0.0.1:8000?desktop=true",
        width=1100,
        height=850,
        min_size=(800, 600),
        resizable=True
    )
    
    # Start webview loop
    # debug=True enables F5/Ctrl+R live reload and right-click developer tools inspect
    webview.start(debug=not is_frozen)

if __name__ == "__main__":
    main()
