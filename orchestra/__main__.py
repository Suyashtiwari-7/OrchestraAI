"""
OrchestraAI — Module Runner
============================
Allows running either the CLI interface or the API server:
- CLI mode: python -m orchestra
- Server mode: python -m orchestra --server
"""

import sys

def main_runner():
    # Check if server flag is present
    if "--server" in sys.argv or "-s" in sys.argv:
        import uvicorn
        # Import settings to print beautiful startup details
        from .config import settings
        from .server import get_local_ip
        
        print("\n" + "="*50)
        print(f"[*] Starting {settings.app_name} Web Server Mode...")
        print(f"[*] Local Web Interface:  http://localhost:8000")
        print(f"[*] Phone Web Interface:  http://{get_local_ip()}:8000")
        print("="*50 + "\n")
        
        uvicorn.run("orchestra.server:app", host="0.0.0.0", port=8000, log_level="info")
    else:
        from .main import main
        main()

if __name__ == "__main__":
    main_runner()
