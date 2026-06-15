"""
OrchestraAI — Desktop Build & Compilation Script
=================================================
Automates the compilation of the desktop app: installs dependencies,
compiles using PyInstaller with asset bundling, and configures templates.
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

def main():
    root_dir = Path(__file__).resolve().parent
    
    # 1. Resolve virtual environment python binary path
    venv_python = root_dir / "venv" / "Scripts" / "python.exe"
    if not venv_python.exists():
        # Fallback to active system interpreter
        venv_python = Path(sys.executable)
        
    print(f"[*] Using python interpreter: {venv_python}")
    
    # 2. Install packaging dependencies
    print("[*] Installing build requirements (pywebview, pyinstaller)...")
    try:
        subprocess.run([str(venv_python), "-m", "pip", "install", "pywebview", "pyinstaller"], check=True)
        print("[+] Requirements installed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"[!] Pip installation failed: {e}")
        sys.exit(1)
        
    # 3. Compile native application using PyInstaller
    print("[*] Running PyInstaller compiler...")
    pyinstaller_exe = venv_python.parent / "pyinstaller.exe"
    if not pyinstaller_exe.exists():
        pyinstaller_exe = "pyinstaller" # Fallback to system path
        
    cmd = [
        str(pyinstaller_exe),
        "--noconsole",          # Hides command terminal console window
        "--name=DARKI",   # Name of the output executable folder/file
        "--add-data=orchestra/static;orchestra/static", # Bundle static HTML/CSS/JS frontend
        "--hidden-import=uvicorn.loops",
        "--hidden-import=uvicorn.loops.auto",
        "--hidden-import=uvicorn.loops.asyncio",
        "--hidden-import=uvicorn.protocols",
        "--hidden-import=uvicorn.protocols.http",
        "--hidden-import=uvicorn.protocols.http.auto",
        "--hidden-import=uvicorn.protocols.http.h11_impl",
        "--hidden-import=uvicorn.protocols.websockets",
        "--hidden-import=uvicorn.protocols.websockets.auto",
        "--hidden-import=uvicorn.protocols.websockets.ws_impl",
        "--hidden-import=uvicorn.lifespan",
        "--hidden-import=uvicorn.lifespan.on",
        "--hidden-import=uvicorn.lifespan.off",
        "--hidden-import=anyio._backends._asyncio",
        "--clean",              # Clean cache directories before build
        "-y",                   # Overwrite existing build folders without prompting
        "orchestra/darki_main.py"  # Source entry script
    ]
    
    print(f"[*] Execute build command: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True)
        print("[+] PyInstaller compilation finished successfully.")
    except subprocess.CalledProcessError as e:
        print(f"[!] Compilation failed: {e}")
        sys.exit(1)
        
    # 4. Copy configuration to output distribution folder
    dist_dir = root_dir / "dist" / "DARKI"
    env_source = root_dir / ".env"
    env_example = root_dir / ".env.example"
    env_dest = dist_dir / ".env"
    
    if dist_dir.exists():
        if env_source.exists():
            shutil.copy(env_source, env_dest)
            print(f"[+] Active configuration (.env) copied to: {env_dest}")
        elif env_example.exists():
            shutil.copy(env_example, env_dest)
            print(f"[+] Configuration template (.env.example) copied to: {env_dest}")
        else:
            print("[!] Warning: Neither .env nor .env.example found.")
            
        print("\n" + "="*60)
        print("[+] DARKI Desktop build is complete!")
        print(f"[+] Output Folder:  {dist_dir}")
        print(f"[+] Executable:     {dist_dir / 'DARKI.exe'}")
        print("="*60 + "\n")
    else:
        print("[!] Warning: Distribution folder not found. Compilation might have failed.")

if __name__ == "__main__":
    main()
