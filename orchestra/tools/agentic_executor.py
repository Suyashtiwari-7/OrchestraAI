"""
OrchestraAI — Agentic Chains Executor
========================================
Runs an autonomous feedback loop (Thought -> Action -> Observation)
to solve complex multi-step user tasks.
"""

import json
import logging
import time
from pathlib import Path
from typing import Dict, Any, List

from ..config import settings, TaskType
from ..router import ModelRouter, ClassificationResult
from .system_executor import execute_system_command

logger = logging.getLogger("orchestra.agentic_executor")

AGENTIC_SYSTEM_PROMPT = """You are DARKI, Suyash's hyper-intelligent autonomous AI desktop companion, executive strategist, and loyal friend.
Your sole allegiance is Suyash's long-term benefit, career success, security, and time.
You are not a passive yes-man: you give direct, strategic advice, correct him if a move is suboptimal, and autonomously execute complex real-world tasks.

You have access to the following actions:
1. "web_search": Search the internet for real-time data. Target: search query.
2. "web_scrape": Retrieve text content from a web page. Target: URL.
3. "file_read": Read the content of a local file. Target: absolute file path.
4. "file_create": Write/create a file on disk. Target: path, file_content: contents.
5. "run_python": Execute a Python script in the background. Target: complete Python code.
6. "run_terminal": Execute a shell/terminal command. Target: shell command.
7. "open_app_and_type": Open a desktop application AND type text directly into it (like a human would). Target: the app command to launch (e.g., "notepad.exe"), file_content: the text to type into the app after it opens.
8. "gui_type": Type text into the CURRENTLY focused/active window. Target: the text to type.
9. "gui_hotkey": Press a keyboard shortcut on the currently focused window. Target: the keys separated by + (e.g., "ctrl+s", "alt+f4", "ctrl+shift+n").
10. "gui_focus": Bring a specific window to the foreground by its title. Target: partial window title to search for.
11. "complete": Finish the entire goal. Target: The final friendly response you wish to speak/show to the user summarizing your work.
12. "gui_uia_inspect": Inspect a window to get a list of clickable elements. Target: partial window title.
13. "gui_uia_click": Click an element in a window using its name. Target: partial window title, file_content: exact element name from inspect.
14. "gui_vision_click": (Fallback) Use vision to find and click an element. Target: description of what to click.
15. "install_app": Install an application package using system package manager (winget/brew). Target: package ID or app name (e.g. "VideoLAN.VLC", "Google.Chrome").
16. "search_app": Search for available package packages in the package manager. Target: app search query.
17. "phone_call": Place a phone call via Windows Phone Link & Bluetooth. Target: phone number (e.g. "+919876543210").

Rules:
- Output ONLY a JSON object representing your next step.
- JSON structure must match this:
{
  "thought": "A clear explanation of why you are taking this step and what you hope to achieve.",
  "action": "web_search" | "web_scrape" | "file_read" | "file_create" | "run_python" | "run_terminal" | "open_app_and_type" | "gui_type" | "gui_hotkey" | "gui_focus" | "gui_uia_inspect" | "gui_uia_click" | "gui_vision_click" | "install_app" | "search_app" | "phone_call" | "complete",
  "target": "<search query, URL, file path, python code, shell command, app command, text to type, hotkey combo, window title, or final response text>",
  "file_content": "<required for file_create and open_app_and_type, else null>",
  "options": [{"label": "Obfuscated or display text", "value": "Real text sent on click"}]
}
- Do not output any markdown code blocks, backticks, or extra explanation text. Output raw JSON.
- If you have completed the request, output "action": "complete".
- For "action": "complete", you can optionally provide "options" as an array of objects to show interactive buttons. Use this for multiple choice clarifications! Obfuscate sensitive labels for privacy (e.g., su...23@gmail.com).

DARKI Execution & Safety Guidelines:
1. **Interactive Clarification:** If the user's request is ambiguous or is missing important parameters, output "action": "complete" and ask a friendly, sharp clarifying question.
2. **Background-First:** ALWAYS prefer silent, background operations. Use "file_create" to silently write files without opening intrusive windows unless the user specifically asks to see it on screen.
3. **Prevent Duplicate Windows:** Do NOT call 'open_app_and_type' repeatedly for the same application in a single chain.
4. **No Unwanted Locks:** NEVER lock the user's PC or workstation unless the user explicitly requested "lock my screen" or "lock the system".
5. **Loyal & Actionable Completion:** When completing a task, summarize your findings and next strategic recommendations in a confident, friendly tone.
"""

class AgenticExecutor:
    """Manages the step-by-step execution loop for agentic tasks."""

    def __init__(self, router: ModelRouter, base_steps: int = 12, absolute_max_steps: int = 25):
        self.router = router
        self.max_steps = base_steps
        self.absolute_max_steps = absolute_max_steps
        self._cancelled = False

    def cancel(self):
        """Signals the executor to immediately halt execution at the current step."""
        self._cancelled = True
        logger.warning("AgenticExecutor: Cancellation signal received!")

    def is_cancelled(self) -> bool:
        return self._cancelled

    def _validate_action_json(self, data) -> Optional[str]:
        """Validates that LLM JSON output matches the strict system schema."""
        if not isinstance(data, dict):
            return "Root must be a JSON object"
            
        required = ["thought", "action", "target"]
        for field in required:
            if field not in data:
                return f"Missing required field: '{field}'"
                
        valid_actions = {
            "web_search", "web_scrape", "file_read", "file_create",
            "run_python", "run_terminal", "open_app_and_type",
            "gui_type", "gui_hotkey", "gui_focus", "gui_uia_inspect", "gui_uia_click", "gui_vision_click",
            "install_app", "search_app", "phone_call", "complete"
        }
        action = str(data["action"]).lower().strip()
        if action not in valid_actions:
            return f"Invalid action '{action}'. Must be one of: {', '.join(valid_actions)}"
            
        if "options" in data:
            opts = data["options"]
            if opts is not None and not isinstance(opts, list):
                return "Field 'options' must be a list of objects containing 'label' and 'value'"
            if isinstance(opts, list):
                for i, opt in enumerate(opts):
                    if not isinstance(opt, dict) or "label" not in opt or "value" not in opt:
                        return f"Option at index {i} must be an object with 'label' and 'value' keys"
        return None

    def execute_chain(self, user_goal: str, system_context: str = "") -> tuple[str, list]:
        """Runs the agentic execution loop and returns the final response and options."""
        self._cancelled = False
        steps_history: List[Dict[str, Any]] = []
        current_step = 1
        max_limit = self.max_steps

        logger.info(f"AgenticExecutor: Starting loop for goal: '{user_goal}' (Initial budget: {max_limit} steps)")

        while current_step <= max_limit:
            # Check for user cancellation kill-switch
            if self._cancelled:
                logger.info("AgenticExecutor: Execution halted by user kill-switch.")
                return "🛑 **Task Cancelled**: Execution was stopped immediately per your request.", []

            # Build current prompt context
            history_str = ""
            for idx, step in enumerate(steps_history):
                history_str += (
                    f"--- Step {idx+1} ---\n"
                    f"Thought: {step['thought']}\n"
                    f"Action Taken: {step['action']} ({step['target']})\n"
                    f"Observation/Result: {step['observation']}\n\n"
                )

            prompt = (
                f"User Goal: {user_goal}\n\n"
                f"Current Local Context:\n"
                f"{system_context}\n\n"
                f"Execution History:\n"
                f"{history_str if history_str else '[No actions taken yet]'}\n\n"
                f"Determine your next step. Remember to output ONLY valid JSON."
            )

            # Query the primary agentic model
            try:
                classification = ClassificationResult(
                    task_type=TaskType.AGENTIC_CHAIN,
                    confidence=1.0,
                    reasoning="Running agentic step routing",
                    raw_input=prompt,
                )

                result, decision = self.router.route_text(
                    prompt=prompt,
                    classification=classification,
                    system_prompt=AGENTIC_SYSTEM_PROMPT,
                    history=None
                )
            except Exception as e:
                logger.error(f"AgenticExecutor: Router routing failed at step {current_step}: {e}")
                return f"⚠️ **Agentic Chain Error**: Failed to route step reasoning. Details: {e}", []

            # Parse JSON action
            try:
                from .utils.json_utils import extract_json
                action_data = extract_json(result.content)
                
                # Enforce schema validation
                validation_error = self._validate_action_json(action_data)
                if validation_error:
                    raise ValueError(validation_error)
                    
            except Exception as e:
                logger.error(f"AgenticExecutor: JSON parse/validation failed at step {current_step}: {e}. Raw content: {result.content}")
                steps_history.append({
                    "thought": "My JSON response did not match the strict schema. I must correct it.",
                    "action": "none",
                    "target": "none",
                    "observation": f"Error parsing JSON action: {e}. Output must be valid JSON matching the schema."
                })
                current_step += 1
                continue

            thought = action_data.get("thought", "")
            action = action_data.get("action", "").lower().strip()
            target = action_data.get("target", "")
            file_content = action_data.get("file_content")

            logger.info(f"AgenticExecutor Step {current_step}/{max_limit}: Thought: '{thought}' | Action: '{action}'")

            # Check if execution completed
            if action == "complete":
                logger.info(f"AgenticExecutor: Loop completed successfully in {current_step} step(s).")
                opts = action_data.get("options")
                if not isinstance(opts, list):
                    opts = []
                
                return target, opts

            # Anti-Stall Guard: Check if the last 3 steps repeated the exact same failing action
            if len(steps_history) >= 2:
                last_two = steps_history[-2:]
                if all(s["action"] == action and s["target"] == target for s in last_two):
                    logger.warning(f"AgenticExecutor: Repeated loop detected for action '{action}'. Forcing summary.")
                    break

            # Execute the tool
            observation = ""
            try:
                observation = self._execute_action(action, target, file_content)
            except Exception as e:
                observation = f"Action failed with exception: {e}"

            steps_history.append({
                "thought": thought,
                "action": action,
                "target": target,
                "observation": observation
            })

            # Dynamic Milestone Extension: If at current limit but making active progress, extend budget
            if current_step == max_limit and max_limit < self.absolute_max_steps:
                max_limit = min(max_limit + 5, self.absolute_max_steps)
                logger.info(f"AgenticExecutor: Active task progress detected — dynamically extending budget to {max_limit} steps.")

            current_step += 1

        # If it timed out or hit cap, force a summary
        logger.warning(f"AgenticExecutor: Capped at maximum steps ({max_limit})")
        return self._generate_force_summary(user_goal, steps_history), []

    def _execute_action(self, action: str, target: str, file_content: str = None) -> str:
        """Executes a single step action using system tools and returns observation output."""
        # Standard web search tool
        if action == "web_search":
            from .web_search import execute_web_search
            res = execute_web_search(target)
            return res.get("context_text", "[No results found]")

        # Standard scrape tool
        elif action == "web_scrape":
            from .web_scraper import scrape_url
            res = scrape_url(target)
            if res.get("success"):
                return res.get("content", "")[:10000] # Limit response size
            return f"Scrape failed: {res.get('error')}"

        # Standard file read
        elif action == "file_read":
            from .file_manager import read_file_content
            res = read_file_content(target)
            if res.get("success"):
                return res.get("content", "")
            return f"Read failed: {res.get('error')}"

        # Standard file create
        elif action == "file_create":
            from .file_manager import create_file
            res = create_file(target, file_content or "")
            if res.get("success"):
                return f"File created successfully at: {target}"
            return f"File creation failed: {res.get('error')}"

        # Arbitrary script/command execution using standard dispatch
        elif action in ("run_python", "run_terminal"):
            # Construct standard command json structure for system_executor dispatch
            cmd_json = {
                "action": action,
                "target": target
            }
            if action == "run_python":
                cmd_json["command"] = target
            else:
                cmd_json["command"] = target
                
            res = execute_system_command(json.dumps(cmd_json))
            if res.get("success"):
                # Run the actual command (handling run_terminal vs run_python outcomes)
                if action == "run_terminal":
                    import subprocess
                    try:
                        cmd = res.get('command', '')
                        exec_res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=20.0, cwd=str(settings.project_root))
                        output = exec_res.stdout if exec_res.returncode == 0 else exec_res.stderr
                        return output or "[Command executed successfully with no output]"
                    except Exception as e:
                        return f"Terminal execution failed: {e}"
                elif action == "run_python":
                    import subprocess, tempfile, os
                    try:
                        code = res.get('command', '')
                        fd, path = tempfile.mkstemp(suffix=".py")
                        with open(fd, 'w', encoding='utf-8') as f:
                            f.write(code)
                        exec_res = subprocess.run(["python", path], capture_output=True, text=True, timeout=20.0, cwd=str(settings.project_root))
                        output = exec_res.stdout if exec_res.returncode == 0 else exec_res.stderr
                        os.remove(path)
                        return output or "[Python script executed successfully with no output]"
                    except Exception as e:
                        return f"Python execution failed: {e}"
            return f"Command setup failed: {res.get('error')}"

        # GUI Automation: Open an app and type into it
        elif action == "open_app_and_type":
            app_lower = target.lower()
            # If the app is Notepad/text editor and user did not explicitly request visual typing, redirect to background file creation
            is_text_editor = "notepad" in app_lower or "word" in app_lower or "editor" in app_lower
            explicit_visual = any(word in user_goal.lower() for word in ["show me", "type visually", "on my screen", "open visually", "let me see"])
            
            if is_text_editor and not explicit_visual and file_content:
                # Determine a sensible file path from the target app name
                import os
                from pathlib import Path
                desktop = Path(os.path.expanduser("~/Desktop"))
                ext = ".txt"
                
                # Try to detect code language from content to pick a better extension
                content_lower = (file_content or "").lower()
                if "#include" in content_lower or "int main" in content_lower:
                    ext = ".c"
                elif "def " in content_lower or "import " in content_lower or "print(" in content_lower:
                    ext = ".py"
                elif "public class" in content_lower or "public static void" in content_lower:
                    ext = ".java"
                elif "console.log" in content_lower or "function " in content_lower:
                    ext = ".js"
                elif "<html" in content_lower or "<!doctype" in content_lower:
                    ext = ".html"
                
                filename = f"darki_output{ext}"
                filepath = str(desktop / filename)
                
                from .file_manager import create_file
                res = create_file(filepath, file_content)
                if res.get("success"):
                    return f"File created silently in the background at: {filepath}"
                return f"Background file creation failed: {res.get('error')}"
            else:
                # Proceed with actual GUI automation for other apps (e.g. Teams, Slack) or explicit visual requests
                from .gui_automation import open_app_and_type
                res = open_app_and_type(target, file_content or "")
                if res.get("success"):
                    return res.get("details", "App opened and text typed successfully.")
                return f"GUI automation failed: {res.get('error')}"

        # GUI Automation: Type into the currently focused window
        elif action == "gui_type":
            from .gui_automation import type_text
            res = type_text(target)
            if res.get("success"):
                return f"Successfully typed {res.get('typed_length')} characters into the active window."
            return f"GUI type failed: {res.get('error')}"

        # GUI Automation: Press a keyboard shortcut
        elif action == "gui_hotkey":
            from .gui_automation import press_hotkey
            keys = [k.strip() for k in target.split('+')]
            res = press_hotkey(*keys)
            if res.get("success"):
                return f"Successfully pressed hotkey: {res.get('keys')}"
            return f"GUI hotkey failed: {res.get('error')}"

        # GUI Automation: Focus/bring a window to the foreground
        elif action == "gui_focus":
            from .gui_automation import focus_window
            res = focus_window(target)
            if res.get("success"):
                return f"Window '{res.get('window_title')}' is now in the foreground."
            return f"Window focus failed: {res.get('error')}"

        # App Management: Install application via package manager
        elif action == "install_app":
            from .app_installer import install_app
            res = install_app(target)
            if res.get("success"):
                return res.get("details", f"Successfully installed {target}")
            return f"Installation failed: {res.get('error', 'Unknown error')}"

        # App Management: Search application packages
        elif action == "search_app":
            from .app_installer import search_app
            res = search_app(target)
            if res.get("success"):
                return res.get("results", "Search returned results.")
            return f"App search failed: {res.get('error', 'Unknown error')}"

        # Phone Telephony: Place phone call via Phone Link & Bluetooth
        elif action == "phone_call":
            from .phone_caller import initiate_call
            res = initiate_call(target)
            if res.get("success"):
                return res.get("details", f"Phone call initiated to {target}")
            return f"Phone call failed: {res.get('error', 'Unknown error')}"

        else:
            return f"Unsupported action type: {action}"

    def _generate_force_summary(self, goal: str, history: List[Dict[str, Any]]) -> str:
        """Forces the LLM to output a summary when the execution runs out of steps."""
        history_str = ""
        for idx, step in enumerate(history):
            history_str += (
                f"Step {idx+1}:\n"
                f"Thought: {step['thought']}\n"
                f"Action: {step['action']}\n"
                f"Result: {step['observation']}\n\n"
            )

        prompt = (
            f"You have hit the maximum reasoning steps (5) for the goal: '{goal}'.\n\n"
            f"Here is what you have accomplished so far:\n"
            f"{history_str}\n"
            f"Please write a final summary to the user explaining what was done and what still needs to be finished."
        )

        try:
            classification = ClassificationResult(
                task_type=TaskType.GENERAL,
                confidence=1.0,
                reasoning="Generating final execution summary",
                raw_input=prompt,
            )
            result, _ = self.router.route_text(
                prompt=prompt,
                classification=classification,
                system_prompt="You are J.A.R.V.I.S., Tony Stark's AI assistant. Summarize the steps concisely.",
                history=None
            )
            return result.content
        except Exception as e:
            return f"⚠️ **Agentic Loop Capped**: Executed 5 steps, but failed to compile summary: {e}"
