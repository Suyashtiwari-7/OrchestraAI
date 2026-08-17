"""
OrchestraAI — Quick Launcher for DARKI Desktop Mascot & AI System
"""
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if __name__ == "__main__":
    from orchestra.darki_main import main
    main()
