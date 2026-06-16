"""
OrchestraAI — DARKI Desktop Main Entry Point
===============================================
Launches the complete DARKI desktop assistant:
  1. FastAPI server in background thread (for API + full chat UI)
  2. DARKI floating robot widget (PyQt6)
  3. System tray icon
  4. Voice listener ("Hey DARKI")
  5. Global hotkey (Ctrl+0)
"""

import sys
import os
import time
import logging
import threading
from pathlib import Path

# ─── CRITICAL: Fix for PyInstaller --noconsole mode ───
# When bundled with --noconsole, sys.stdout and sys.stderr are None.
# This crashes uvicorn's logging (calls sys.stderr.isatty()).
# Redirect None streams to os.devnull BEFORE anything else.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

# Reconfigure stdout/stderr to UTF-8 to prevent encoding crashes on Windows console when printing emojis
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
if hasattr(sys.stderr, 'reconfigure'):
    try:
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Configure logging — log to file in headless mode since console is unavailable
_log_dir = Path.home() / ".orchestra_ai"
_log_dir.mkdir(parents=True, exist_ok=True)
_log_file = _log_dir / "darki.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.FileHandler(str(_log_file), encoding="utf-8"),
        logging.StreamHandler(sys.stderr),  # safe now — guaranteed not None
    ],
)
logger = logging.getLogger("orchestra.darki")


def run_server():
    """Start the FastAPI/uvicorn server in a background thread and write traceback on crash."""
    try:
        import uvicorn
        from orchestra.server import app
        logger.info("Uvicorn starting on 127.0.0.1:8000 ...")
        uvicorn.run(
            app,
            host="127.0.0.1",
            port=8000,
            log_level="warning",
            log_config=None,  # Disable uvicorn's custom logging to avoid isatty() crash
        )
    except Exception as e:
        import traceback
        from pathlib import Path
        log_dir = Path.home() / ".orchestra_ai"
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / "server_crash.log"
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"\n--- SERVER CRASH AT {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
                traceback.print_exc(file=f)
        except Exception:
            try:
                with open("server_crash.log", "a", encoding="utf-8") as f:
                    f.write(f"\n--- SERVER CRASH AT {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
                    traceback.print_exc(file=f)
            except Exception:
                pass
        raise e



def main():
    """Main entry point for DARKI desktop application."""

    # --- Global exception hooks to catch ALL unhandled errors ---
    def _global_excepthook(exc_type, exc_value, exc_tb):
        import traceback
        logger.critical("UNHANDLED EXCEPTION (main thread):")
        logger.critical("".join(traceback.format_exception(exc_type, exc_value, exc_tb)))

    def _thread_excepthook(args):
        import traceback
        logger.critical(f"UNHANDLED EXCEPTION in thread '{args.thread.name if args.thread else '?'}':")
        logger.critical("".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)))

    sys.excepthook = _global_excepthook
    threading.excepthook = _thread_excepthook

    try:
        from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
        from PyQt6.QtGui import QIcon, QAction, QPixmap, QPainter, QColor
        from PyQt6.QtCore import Qt, QTimer

        # --- 1. Start FastAPI server ---
        logger.info("Starting FastAPI server...")
        server_thread = threading.Thread(target=run_server, daemon=True, name="FastAPIServer")
        server_thread.start()
        time.sleep(1.5)  # Wait for server initialization
        logger.info("FastAPI server started on http://127.0.0.1:8000")

        # --- 2. Create Qt Application ---
        app = QApplication(sys.argv)
        app.setQuitOnLastWindowClosed(False)  # Keep running when windows are closed
        app.setApplicationName("DARKI")
        logger.info("QApplication created.")

        # --- 3. Create DARKI Widget ---
        from orchestra.darki_widget import DarkiFloatingWidget
        widget = DarkiFloatingWidget()
        widget.show()
        logger.info("DARKI widget launched on desktop.")

        # --- 4. System Tray ---
        tray_icon = _create_tray_icon(app, widget)
        if tray_icon:
            tray_icon.show()
            logger.info("System tray icon created.")

        # --- 5. Full Chat Window ---
        def open_full_chat():
            """Open the full DARKI web UI in a native desktop window."""
            try:
                import subprocess
                if getattr(sys, 'frozen', False):
                    subprocess.Popen([sys.executable, "--chat-window"])
                else:
                    script_path = Path(__file__).resolve()
                    subprocess.Popen([sys.executable, str(script_path), "--chat-window"])
                logger.info("Full chat window opened as native desktop window.")
            except Exception as e:
                logger.error(f"Failed to open native chat window: {e}")
                try:
                    import webbrowser
                    webbrowser.open("http://127.0.0.1:8000")
                except Exception:
                    pass

        widget.request_full_chat.connect(open_full_chat)

        # --- 6. Voice Listener ---
        voice_listener = None
        try:
            from orchestra.voice_listener import VoiceListener

            def on_voice_command(text):
                """Called from voice thread — use QTimer to cross into Qt thread."""
                QTimer.singleShot(0, lambda: widget.submit_command(text))

            def on_wake():
                """Called when wake word detected."""
                QTimer.singleShot(0, lambda: widget.robot.set_state("listening"))

            voice_listener = VoiceListener(on_command=on_voice_command, on_wake=on_wake)
            voice_listener.start()
            logger.info("Voice listener started (say 'Hey DARKI').")
        except Exception as e:
            logger.warning(f"Voice listener failed to start: {e}")

        # --- 7. Global Hotkey ---
        hotkey_listener = None
        try:
            from orchestra.hotkey_listener import HotkeyListener

            def on_hotkey():
                """Called from hotkey thread — cross into Qt thread."""
                QTimer.singleShot(0, lambda: widget.activate_popup())

            hotkey_listener = HotkeyListener(hotkey="ctrl+0", on_activate=on_hotkey)
            hotkey_listener.start()
            logger.info("Global hotkey registered: Ctrl+0")
        except Exception as e:
            logger.warning(f"Hotkey listener failed: {e}")

        # --- Keepalive timer — prevents Qt event loop from exiting prematurely ---
        keepalive = QTimer()
        keepalive.timeout.connect(lambda: None)  # no-op, just keeps event loop alive
        keepalive.start(5000)

        # --- Run Qt event loop ---
        logger.info("=" * 50)
        logger.info("  OrchestraAI DARKI is running!")
        logger.info("  - Click the robot to chat")
        logger.info("  - Say 'Hey DARKI' for voice commands")
        logger.info("  - Press Ctrl+0 to activate")
        logger.info("=" * 50)

        logger.info("Entering Qt event loop (app.exec())...")
        exit_code = app.exec()
        logger.info(f"Qt event loop exited with code: {exit_code}")

        # Cleanup
        if voice_listener:
            voice_listener.stop()
        if hotkey_listener:
            hotkey_listener.stop()
        widget.cleanup()

        sys.exit(exit_code)

    except Exception as e:
        import traceback
        logger.critical(f"FATAL ERROR in main(): {e}")
        logger.critical(traceback.format_exc())
        # Also write to a crash file as a last resort
        try:
            crash_file = Path.home() / ".orchestra_ai" / "darki_crash.log"
            with open(crash_file, "a", encoding="utf-8") as f:
                f.write(f"\n--- FATAL CRASH AT {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
                traceback.print_exc(file=f)
        except Exception:
            pass
        sys.exit(1)


def _create_tray_icon(app, widget):
    """Create a system tray icon with context menu."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QSystemTrayIcon, QMenu
    from PyQt6.QtGui import QIcon, QAction, QPixmap, QPainter, QColor

    if not QSystemTrayIcon.isSystemTrayAvailable():
        logger.warning("System tray not available.")
        return None

    # Create a simple icon (colored circle)
    pixmap = QPixmap(32, 32)
    pixmap.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor(59, 130, 246))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(2, 2, 28, 28)
    # Inner dot
    painter.setBrush(QColor(0, 220, 220))
    painter.drawEllipse(10, 10, 12, 12)
    painter.end()

    icon = QIcon(pixmap)
    tray = QSystemTrayIcon(icon, app)
    tray.setToolTip("DARKI — Personal AI Assistant")

    # Context menu
    menu = QMenu()

    show_action = QAction("👁 Show/Hide DARKI", menu)
    show_action.triggered.connect(lambda: widget.setVisible(not widget.isVisible()))
    menu.addAction(show_action)

    chat_action = QAction("💬 Open Full Chat", menu)
    chat_action.triggered.connect(widget.request_full_chat.emit)
    menu.addAction(chat_action)

    menu.addSeparator()

    quit_action = QAction("❌ Quit", menu)
    quit_action.triggered.connect(app.quit)
    menu.addAction(quit_action)

    tray.setContextMenu(menu)

    # Double-click tray to toggle widget
    tray.activated.connect(lambda reason: (
        widget.activate_popup() if reason == QSystemTrayIcon.ActivationReason.DoubleClick else None
    ))

    return tray


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--chat-window":
        try:
            import webview
            window = webview.create_window(
                title="DARKI",
                url="http://127.0.0.1:8000?desktop=true",
                width=1100,
                height=850,
                min_size=(800, 600),
                resizable=True
            )
            webview.start()
        except Exception as e:
            print(f"Failed to launch native webview window: {e}")
        sys.exit(0)
    else:
        main()
