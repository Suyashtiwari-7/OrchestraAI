"""
OrchestraAI — Python Code Execution Sandbox
============================================
Safely runs generated python snippets in a restricted local subprocess,
captures stdout/stderr, handles timeouts, and performs file cleanup.
"""

import sys
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Any

from orchestra.config import settings

def execute_python_sandbox(code_content: str, timeout: float = 10.0) -> Dict[str, Any]:
    """
    Writes python code to a temporary file, executes it in a separate Python 
    subprocess, captures output and error streams, and handles timeouts.
    """
    # Create output directories if needed
    settings.ensure_dirs()
    
    # Ensure temporary file is written to the output/code directory
    temp_dir = settings.output_code_dir
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    # Create temp file
    fd, temp_file_path = tempfile.mkstemp(suffix=".py", dir=temp_dir)
    temp_path = Path(temp_file_path)
    
    try:
        # Write code content
        with open(fd, "w", encoding="utf-8") as f:
            f.write(code_content)
            
        # Run subprocess
        result = subprocess.run(
            [sys.executable, str(temp_path)],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=settings.project_root
        )
        
        # Prepare output response
        success = (result.returncode == 0)
        output = result.stdout if success else result.stderr
        
        return {
            "success": success,
            "output": output.strip(),
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "returncode": result.returncode
        }
        
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": f"Execution timed out after {timeout} seconds.",
            "output": f"Error: TimeoutExpired after {timeout}s",
            "stdout": "",
            "stderr": f"Error: TimeoutExpired after {timeout}s"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Sandbox execution error: {str(e)}",
            "output": f"Error: {str(e)}",
            "stdout": "",
            "stderr": str(e)
        }
    finally:
        # Clean up the script file
        try:
            if temp_path.exists():
                temp_path.unlink()
        except Exception:
            pass
