"""
OrchestraAI — Python Sandbox Tests
===================================
Tests for the local python script sandbox runner.
"""

import pytest
from orchestra.tools.code_sandbox import execute_python_sandbox

class TestCodeSandbox:
    """Test standard execution, exceptions, and timeouts in code sandbox."""

    def test_sandbox_success(self):
        """Test standard python script runs successfully."""
        code = "print(10 + 20)"
        result = execute_python_sandbox(code)
        
        assert result["success"] is True
        assert result["output"] == "30"
        assert result["returncode"] == 0

    def test_sandbox_syntax_error(self):
        """Test script with errors returns failure and error output."""
        code = "print(invalid_var"
        result = execute_python_sandbox(code)
        
        assert result["success"] is False
        assert result["returncode"] != 0
        assert len(result["stderr"]) > 0

    def test_sandbox_timeout(self):
        """Test script that hangs triggers execution timeout handler."""
        code = "import time\ntime.sleep(5)"
        # Set a short timeout of 1.0s to trigger it quickly
        result = execute_python_sandbox(code, timeout=1.0)
        
        assert result["success"] is False
        assert "timed out" in result["error"]
        assert result["stdout"] == ""
