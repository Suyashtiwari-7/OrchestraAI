"""
OrchestraAI — DARKI Desktop Widget
====================================
Floating transparent robot widget that lives on the Windows desktop.
Draggable, always-on-top, with a chat bubble popup for quick commands
and a review-and-proceed dialog for actions requiring approval.
"""

import sys
import json
import threading
import requests
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QTextEdit, QSystemTrayIcon,
    QMenu, QDialog, QScrollArea, QFrame, QGraphicsDropShadowEffect,
    QSizePolicy, QGridLayout, QCheckBox, QSizeGrip,
)
from PyQt6.QtCore import (
    Qt, QPoint, QTimer, QSize, pyqtSignal, QThread, QPropertyAnimation,
    QEasingCurve, QRect,
)
from PyQt6.QtGui import (
    QPixmap, QPainter, QColor, QFont, QIcon, QBrush, QPen,
    QLinearGradient, QRadialGradient, QFontDatabase, QAction,
    QCursor,
)


# ============================================================
# Color Palette
# ============================================================
COLORS = {
    "bg_dark": QColor(15, 23, 42),          # Slate 900
    "bg_card": QColor(30, 41, 59, 230),     # Slate 800 with alpha
    "bg_input": QColor(15, 23, 42, 200),
    "accent_blue": QColor(59, 130, 246),
    "accent_green": QColor(16, 185, 129),
    "accent_red": QColor(239, 68, 68),
    "accent_yellow": QColor(245, 158, 11),
    "accent_cyan": QColor(0, 220, 220),
    "text_primary": QColor(248, 250, 252),
    "text_muted": QColor(148, 163, 184),
    "border": QColor(255, 255, 255, 20),
    "border_accent": QColor(59, 130, 246, 80),
}

API_BASE = "http://127.0.0.1:8000"


# ============================================================
# Worker Thread for API Calls
# ============================================================
class ChatWorker(QThread):
    """Runs chat API call in background to avoid freezing the UI."""
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, prompt: str, provider_override: str = ""):
        super().__init__()
        self.prompt = prompt
        self.provider_override = provider_override

    def run(self):
        try:
            resp = requests.post(
                f"{API_BASE}/api/chat",
                json={"prompt": self.prompt, "provider_override": self.provider_override},
                timeout=60,
            )
            if resp.status_code == 200:
                self.finished.emit(resp.json())
            else:
                self.error.emit(f"Server returned {resp.status_code}")
        except Exception as e:
            self.error.emit(str(e))


# ============================================================
# Robot Painter — draws the DARKI robot using Qt primitives
# ============================================================
class RobotWidget(QLabel):
    """Draws the DARKI robot mascot as a painted widget."""

    def __init__(self, size: int = 80, parent=None):
        super().__init__(parent)
        self.robot_size = size
        self.setFixedSize(size, size + 15)  # Add some extra vertical space for floating/shadow
        self._eye_color = COLORS["accent_cyan"]
        self._antenna_color = COLORS["accent_green"]
        self._state = "idle"  # idle, listening, success, error
        self._blink_timer = QTimer(self)
        self._blink_timer.timeout.connect(self._toggle_blink)
        self._blink_timer.start(3000)
        self._eyes_open = True

        # Hover animation variables
        self._tick = 0
        self._hover_offset = 0.0
        self._hover_timer = QTimer(self)
        self._hover_timer.timeout.connect(self._update_hover)
        self._hover_timer.start(25) # 40 fps

    def _update_hover(self):
        import math
        self._tick = (self._tick + 3) % 360
        # Hover up and down by 4 pixels
        self._hover_offset = 4.0 * math.sin(math.radians(self._tick))
        self.update()

    def set_state(self, state: str):
        self._state = state
        if state == "listening":
            self._eye_color = COLORS["accent_yellow"]
            self._antenna_color = COLORS["accent_yellow"]
        elif state == "success":
            self._eye_color = COLORS["accent_green"]
            self._antenna_color = COLORS["accent_green"]
        elif state == "error":
            self._eye_color = COLORS["accent_red"]
            self._antenna_color = COLORS["accent_red"]
        else:
            self._eye_color = COLORS["accent_cyan"]
            self._antenna_color = COLORS["accent_green"]
        self.update()

    def _toggle_blink(self):
        self._eyes_open = not self._eyes_open
        self.update()
        if not self._eyes_open:
            QTimer.singleShot(150, self._open_eyes)

    def _open_eyes(self):
        self._eyes_open = True
        self.update()

    def paintEvent(self, event):
        import math
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        s = self.robot_size
        cx = s // 2  # center x
        
        # Calculate vertical position based on hover
        y_offset = self._hover_offset
        
        # --- Draw Floating Shadow ---
        # The shadow is drawn on the ground, so it doesn't move with y_offset.
        # Instead, its size scales slightly with y_offset.
        shadow_y = s + 5
        shadow_max_w = 40
        shadow_h = 5
        # When robot is high (y_offset is negative), shadow is larger and lighter
        # When robot is low (y_offset is positive), shadow is smaller and darker
        scale_factor = 1.0 - (y_offset / 10.0) # range ~ 0.6 to 1.4
        shadow_w = int(shadow_max_w * (0.8 + 0.2 * scale_factor))
        shadow_alpha = int(40 * (1.0 - 0.25 * scale_factor))
        shadow_alpha = max(10, min(shadow_alpha, 80))
        
        shadow_color = QColor(0, 0, 0, shadow_alpha)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(shadow_color))
        painter.drawEllipse(cx - shadow_w // 2, shadow_y, shadow_w, shadow_h)
        
        # --- Draw Robot Body (shifted by y_offset) ---
        # Let's paint a futuristic rounded capsule orb with neon glows.
        body_w = 54
        body_h = 58
        body_x = cx - body_w // 2
        body_y = int(12 + y_offset)
        
        # Sleek glassmorphic gradient for body core
        body_gradient = QRadialGradient(cx, body_y + body_h // 2, body_w)
        # Deep translucent navy-slate core
        body_gradient.setColorAt(0, QColor(30, 41, 59, 240)) # Slate 800
        body_gradient.setColorAt(0.7, QColor(15, 23, 42, 250)) # Slate 900
        body_gradient.setColorAt(1.0, QColor(8, 10, 18, 255)) # Sleek dark edge
        
        painter.setBrush(QBrush(body_gradient))
        
        # Border style based on state (glowing neon border)
        border_color = QColor(255, 255, 255, 30) # Default soft white border
        if self._state == "listening":
            border_color = QColor(245, 158, 11, 150) # Glowing Gold
        elif self._state == "success":
            border_color = QColor(16, 185, 129, 150) # Glowing Green
        elif self._state == "error":
            border_color = QColor(239, 68, 68, 150) # Glowing Red
        elif self._state == "idle":
            border_color = QColor(6, 182, 212, 100) # Glowing Cyan
            
        painter.setPen(QPen(border_color, 1.8))
        painter.drawRoundedRect(QRect(int(body_x), int(body_y), int(body_w), int(body_h)), 22.0, 22.0)
        
        # Glossy highlight reflection on top of the capsule (simulates curved glass)
        gloss_gradient = QLinearGradient(body_x, body_y, body_x, body_y + 15)
        gloss_gradient.setColorAt(0, QColor(255, 255, 255, 40))
        gloss_gradient.setColorAt(1, QColor(255, 255, 255, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(gloss_gradient))
        painter.drawRoundedRect(QRect(int(body_x + 3), int(body_y + 2), int(body_w - 6), 14), 10.0, 10.0)
        
        # --- Head Screen/Visor (translucent dark panel) ---
        screen_w = 42
        screen_h = 24
        screen_x = int(cx - screen_w // 2)
        screen_y = int(body_y + 10)
        
        painter.setPen(QPen(QColor(255, 255, 255, 10), 1))
        painter.setBrush(QBrush(QColor(10, 12, 20, 220))) # Very dark screen
        painter.drawRoundedRect(QRect(screen_x, screen_y, screen_w, screen_h), 8.0, 8.0)
        
        # --- Visor Eyes ---
        eye_y = int(screen_y + 8)
        eye_size_w = 10
        eye_size_h = 6
        eye_radius = 3.0
        
        # Draw glowing neon background for eyes
        glow_color = QColor(self._eye_color.red(), self._eye_color.green(), self._eye_color.blue(), 60)
        painter.setBrush(QBrush(glow_color))
        painter.setPen(Qt.PenStyle.NoPen)
        # Draw soft outer glow circles
        painter.drawEllipse(int(cx - 13 - 2), int(eye_y - 2), int(eye_size_w + 4), int(eye_size_h + 4))
        painter.drawEllipse(int(cx + 3 - 2), int(eye_y - 2), int(eye_size_w + 4), int(eye_size_h + 4))
        
        # Draw eyes
        painter.setBrush(QBrush(self._eye_color))
        if self._eyes_open:
            painter.drawRoundedRect(QRect(int(cx - 13), int(eye_y), int(eye_size_w), int(eye_size_h)), eye_radius, eye_radius)
            painter.drawRoundedRect(QRect(int(cx + 3), int(eye_y), int(eye_size_w), int(eye_size_h)), eye_radius, eye_radius)
        else:
            # Closed blink state (thin horizontal line)
            painter.setPen(QPen(self._eye_color, 2))
            painter.drawLine(int(cx - 13), int(eye_y + 3), int(cx - 13 + eye_size_w), int(eye_y + 3))
            painter.drawLine(int(cx + 3), int(eye_y + 3), int(cx + 3 + eye_size_w), int(eye_y + 3))
            painter.setPen(Qt.PenStyle.NoPen)
            
        # --- Status LED Core (on chest) ---
        core_y = int(body_y + 40)
        core_r = 6
        
        # Inner LED color pulsing based on timer
        pulse_alpha = int(120 + 80 * math.sin(math.radians(self._tick * 4)))
        pulse_alpha = max(50, min(pulse_alpha, 255))
        core_color = QColor(self._antenna_color.red(), self._antenna_color.green(), self._antenna_color.blue(), pulse_alpha)
        
        # Outer core aura
        aura_color = QColor(self._antenna_color.red(), self._antenna_color.green(), self._antenna_color.blue(), 40)
        painter.setBrush(QBrush(aura_color))
        painter.drawEllipse(cx - core_r - 2, core_y - 2, (core_r + 2) * 2, (core_r + 2) * 2)
        
        # Center core
        painter.setBrush(QBrush(core_color))
        painter.drawEllipse(cx - core_r, core_y, core_r * 2, core_r * 2)
        
        # Tiny bright dot in middle of chest core
        painter.setBrush(QBrush(QColor(255, 255, 255, 200)))
        painter.drawEllipse(cx - 2, core_y + 4, 4, 4)

        painter.end()


# ============================================================
# Chat Bubble Popup — appears above the robot
# ============================================================
class ChatBubblePopup(QWidget):
    """Glassmorphic chat popup for quick commands."""

    send_message = pyqtSignal(str)
    open_full_chat = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(360, 300)
        self.setMinimumSize(320, 240)
        self.setMaximumSize(800, 600)
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)

        # Card container
        self.card = QFrame(self)
        self.card.setStyleSheet("""
            QFrame {
                background-color: rgba(15, 23, 42, 235);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 16px;
            }
        """)
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(14, 10, 14, 10)
        card_layout.setSpacing(8)

        # --- Header ---
        header = QHBoxLayout()
        title = QLabel("🤖 DARKI")
        title.setStyleSheet("""
            color: #f8fafc;
            font-size: 13px;
            font-weight: 700;
            font-family: 'Segoe UI', sans-serif;
        """)
        header.addWidget(title)
        header.addStretch()

        # Full chat button
        full_chat_btn = QPushButton("💬")
        full_chat_btn.setToolTip("Open Full Chat")
        full_chat_btn.setFixedSize(28, 28)
        full_chat_btn.setStyleSheet("""
            QPushButton {
                background: rgba(59, 130, 246, 0.15);
                border: 1px solid rgba(59, 130, 246, 0.25);
                border-radius: 8px;
                color: white;
                font-size: 14px;
            }
            QPushButton:hover {
                background: rgba(59, 130, 246, 0.3);
            }
        """)
        full_chat_btn.clicked.connect(self.open_full_chat.emit)
        header.addWidget(full_chat_btn)

        # Power Off button
        power_btn = QPushButton("⏻")
        power_btn.setToolTip("Shutdown DARKI")
        power_btn.setFixedSize(28, 28)
        power_btn.setStyleSheet("""
            QPushButton {
                background: rgba(239, 68, 68, 0.15);
                border: 1px solid rgba(239, 68, 68, 0.25);
                border-radius: 8px;
                color: #ef4444;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: rgba(239, 68, 68, 0.35);
                color: #fca5a5;
            }
        """)
        power_btn.clicked.connect(QApplication.instance().quit)
        header.addWidget(power_btn)

        # Close button
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(24, 24)
        close_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #94a3b8;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover { color: #f8fafc; }
        """)
        close_btn.clicked.connect(self.hide)
        header.addWidget(close_btn)
        card_layout.addLayout(header)

        # --- Response area ---
        self.response_area = QTextEdit()
        self.response_area.setReadOnly(True)
        self.response_area.setPlaceholderText("Hello! I'm DARKI. Ask me anything or give me a command...")
        self.response_area.setStyleSheet("""
            QTextEdit {
                background: rgba(15, 23, 42, 0.4);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 12px;
                color: #f8fafc;
                font-size: 13px;
                font-family: 'Segoe UI', 'Outfit', sans-serif;
                padding: 12px;
            }
        """)
        self.response_area.setMinimumHeight(100)
        card_layout.addWidget(self.response_area)

        # --- Input row ---
        input_row = QHBoxLayout()
        input_row.setSpacing(6)

        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Ask anything, or say 'Hey DARKI'...")
        self.input_field.setStyleSheet("""
            QLineEdit {
                background: rgba(15, 23, 42, 0.5);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 12px;
                color: #f8fafc;
                font-size: 13px;
                font-family: 'Segoe UI', 'Outfit', sans-serif;
                padding: 10px 14px;
            }
            QLineEdit:focus {
                border-color: rgba(59, 130, 246, 0.8);
                background: rgba(15, 23, 42, 0.7);
            }
        """)
        self.input_field.returnPressed.connect(self._on_send)
        input_row.addWidget(self.input_field)

        # Mic button
        self.mic_btn = QPushButton("🎙️")
        self.mic_btn.setFixedSize(32, 32)
        self.mic_btn.setToolTip("Push to Talk")
        self.mic_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 8px;
                font-size: 14px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.1);
            }
        """)
        input_row.addWidget(self.mic_btn)

        # Send button
        send_btn = QPushButton("→")
        send_btn.setFixedSize(32, 32)
        send_btn.setStyleSheet("""
            QPushButton {
                background: rgba(59, 130, 246, 0.2);
                border: 1px solid rgba(59, 130, 246, 0.3);
                border-radius: 8px;
                color: white;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: rgba(59, 130, 246, 0.35);
            }
        """)
        send_btn.clicked.connect(self._on_send)
        input_row.addWidget(send_btn)

        card_layout.addLayout(input_row)

        # Subtle size grip overlay at the bottom right
        grip_layout = QHBoxLayout()
        grip_layout.setContentsMargins(0, 0, 0, 0)
        grip_layout.addStretch()
        self.size_grip = QSizeGrip(self)
        self.size_grip.setStyleSheet("background: transparent;")
        grip_layout.addWidget(self.size_grip)
        card_layout.addLayout(grip_layout)

        main_layout.addWidget(self.card)

        # Shadow effect
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(25)
        shadow.setColor(QColor(0, 0, 0, 120))
        shadow.setOffset(0, 5)
        self.card.setGraphicsEffect(shadow)

    def _on_send(self):
        text = self.input_field.text().strip()
        if text:
            self.input_field.clear()
            self.send_message.emit(text)

    def set_response(self, text: str):
        """Display response text, stripping markdown artifacts."""
        clean = text.replace("**", "").replace("`", "")
        self.response_area.setPlainText(clean)

    def set_loading(self, loading: bool):
        if loading:
            self.response_area.setPlainText("✨ Processing request...")
            self.input_field.setEnabled(False)
        else:
            self.input_field.setEnabled(True)
            self.input_field.setFocus()


# ============================================================
# Winget Installation Worker and App Fallback Wizard Dialogs
# ============================================================

class WingetInstallWorker(QThread):
    finished = pyqtSignal(bool, str) # success, message

    def __init__(self, app_id: str):
        super().__init__()
        self.app_id = app_id

    def run(self):
        try:
            resp = requests.post(
                f"{API_BASE}/api/system/install_app",
                json={"app_id": self.app_id},
                timeout=190
            )
            if resp.status_code == 200:
                self.finished.emit(True, "Installation complete.")
            else:
                self.finished.emit(False, f"Failed with status code: {resp.status_code}")
        except Exception as e:
            self.finished.emit(False, str(e))


class AppFallbackWizard(QDialog):
    """Interactive multi-step questionnaire dialog for missing applications."""
    
    CHOICE_INSTALL = "install"
    CHOICE_ALTERNATIVE = "alternative"
    CHOICE_STORE = "store"
    CHOICE_FALLBACK = "fallback"
    CHOICE_CANCEL = "cancel"

    def __init__(self, app_name: str, winget_id: Optional[str] = None, web_fallback: Optional[str] = None, store_query: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.app_name = app_name
        self.winget_id = winget_id
        self.web_fallback = web_fallback
        self.store_query = store_query or app_name
        
        self.choice = self.CHOICE_CANCEL
        
        self.setWindowTitle("DARKI — Application Missing")
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Dialog)
        
        self._setup_ui()
        self._go_to_step(0)

    def _setup_ui(self):
        self.setMinimumSize(480, 280)
        self.resize(480, 280)
        self.setStyleSheet("""
            QDialog {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1e293b, stop:1 #0f172a);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 12px;
            }
            QLabel {
                color: #e2e8f0;
            }
        """)
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 16, 20, 16)
        self.layout.setSpacing(12)
        
        # Header/Title
        self.title_label = QLabel()
        self.title_label.setStyleSheet("font-size: 15px; font-weight: 700; color: #f59e0b;")
        self.layout.addWidget(self.title_label)
        
        # Description
        self.desc_label = QLabel()
        self.desc_label.setWordWrap(True)
        self.desc_label.setStyleSheet("color: #cbd5e1; font-size: 13px; line-height: 1.4;")
        self.layout.addWidget(self.desc_label)
        
        # Progress Bar (for installation step)
        from PyQt6.QtWidgets import QProgressBar
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background: rgba(0, 0, 0, 0.3);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 6px;
                text-align: center;
                color: #e2e8f0;
                height: 18px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3b82f6, stop:1 #10b981);
                border-radius: 5px;
            }
        """)
        self.progress_bar.setVisible(False)
        self.layout.addWidget(self.progress_bar)
        
        self.layout.addStretch()
        
        # Buttons layout
        self.btn_row = QHBoxLayout()
        self.btn_row.setSpacing(10)
        self.layout.addLayout(self.btn_row)

    def _clear_buttons(self):
        while self.btn_row.count():
            item = self.btn_row.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def _create_btn(self, text: str, is_accent: bool = False, is_danger: bool = False) -> QPushButton:
        btn = QPushButton(text)
        if is_accent:
            style = """
                QPushButton {
                    background: rgba(16, 185, 129, 0.2);
                    border: 1px solid rgba(16, 185, 129, 0.4);
                    border-radius: 8px;
                    color: #10b981;
                    font-size: 13px;
                    font-weight: 600;
                    padding: 8px 16px;
                }
                QPushButton:hover { background: rgba(16, 185, 129, 0.35); }
            """
        elif is_danger:
            style = """
                QPushButton {
                    background: rgba(239, 68, 68, 0.15);
                    border: 1px solid rgba(239, 68, 68, 0.3);
                    border-radius: 8px;
                    color: #ef4444;
                    font-size: 13px;
                    font-weight: 600;
                    padding: 8px 16px;
                }
                QPushButton:hover { background: rgba(239, 68, 68, 0.3); }
            """
        else:
            style = """
                QPushButton {
                    background: rgba(255, 255, 255, 0.05);
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    border-radius: 8px;
                    color: #cbd5e1;
                    font-size: 13px;
                    padding: 8px 16px;
                }
                QPushButton:hover { background: rgba(255, 255, 255, 0.12); color: #f8fafc; }
            """
        btn.setStyleSheet(style)
        return btn

    def _go_to_step(self, step: int):
        self._clear_buttons()
        self.progress_bar.setVisible(False)
        
        # Step 0: Check Download / winget
        if step == 0:
            self.title_label.setText(f"⚠️ Application Missing: {self.app_name}")
            if self.winget_id:
                self.desc_label.setText(f"The application '{self.app_name}' is not installed on your laptop.\n\nWould you like DARKI to attempt to download and install it automatically?")
                
                yes_btn = self._create_btn("✓ Yes, Download & Install", is_accent=True)
                yes_btn.clicked.connect(self._start_install)
                self.btn_row.addWidget(yes_btn)
                
                no_btn = self._create_btn("✕ No, Next Option")
                no_btn.clicked.connect(lambda: self._go_to_step(2)) # Skip to calendar/alternative
                self.btn_row.addWidget(no_btn)
            else:
                self.desc_label.setText(f"The application '{self.app_name}' is not installed on your laptop and does not have an automatic installer.\n\nLet's check alternative fallback options.")
                
                next_btn = self._create_btn("✓ Check Alternatives", is_accent=True)
                next_btn.clicked.connect(lambda: self._go_to_step(2))
                self.btn_row.addWidget(next_btn)
                
            cancel_btn = self._create_btn("✕ Cancel", is_danger=True)
            cancel_btn.clicked.connect(self.reject)
            self.btn_row.addWidget(cancel_btn)

        # Step 1: Installing (loading state)
        elif step == 1:
            self.title_label.setText(f"⚙️ Installing {self.app_name}...")
            self.desc_label.setText(f"Please wait. DARKI is downloading and installing '{self.app_name}' via winget...")
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0) # Marquee animation
            
            cancel_btn = self._create_btn("✕ Cancel (Running in background)")
            cancel_btn.setEnabled(False)
            self.btn_row.addWidget(cancel_btn)

        # Step 2: Use Web / Alternative Fallback
        elif step == 2:
            self.title_label.setText("🔄 Option 2: Use Alternative Fallback")
            if self.web_fallback:
                self.desc_label.setText(f"Would you like to open and use the web/alternative version of '{self.app_name}' instead?\n\nTarget URL: {self.web_fallback}")
            else:
                self.desc_label.setText(f"Would you like to use the default system alternative or local calendar file fallback?")
                
            yes_btn = self._create_btn("✓ Yes, Use Alternative", is_accent=True)
            yes_btn.clicked.connect(self._select_alternative)
            self.btn_row.addWidget(yes_btn)
            
            no_btn = self._create_btn("✕ No, Next Option")
            no_btn.clicked.connect(lambda: self._go_to_step(3))
            self.btn_row.addWidget(no_btn)
            
            cancel_btn = self._create_btn("✕ Cancel", is_danger=True)
            cancel_btn.clicked.connect(self.reject)
            self.btn_row.addWidget(cancel_btn)

        # Step 3: Search Microsoft Store
        elif step == 3:
            self.title_label.setText("🛍️ Option 3: Search Microsoft Store")
            self.desc_label.setText(f"Would you like to open the Microsoft Store to search for and download '{self.app_name}'?")
            
            yes_btn = self._create_btn("✓ Yes, Open Microsoft Store", is_accent=True)
            yes_btn.clicked.connect(self._select_store)
            self.btn_row.addWidget(yes_btn)
            
            no_btn = self._create_btn("✕ No, Next Option")
            no_btn.clicked.connect(lambda: self._go_to_step(4))
            self.btn_row.addWidget(no_btn)
            
            cancel_btn = self._create_btn("✕ Cancel", is_danger=True)
            cancel_btn.clicked.connect(self.reject)
            self.btn_row.addWidget(cancel_btn)

        # Step 4: Run default local fallback
        elif step == 4:
            self.title_label.setText("💻 Option 4: Local System Fallback")
            self.desc_label.setText(f"Would you like to run the default local fallback option? (e.g. native Windows notification box or basic shell/browser actions)")
            
            yes_btn = self._create_btn("✓ Yes, Run Fallback", is_accent=True)
            yes_btn.clicked.connect(self._select_fallback)
            self.btn_row.addWidget(yes_btn)
            
            cancel_btn = self._create_btn("✕ No, Cancel", is_danger=True)
            cancel_btn.clicked.connect(self.reject)
            self.btn_row.addWidget(cancel_btn)

    def _start_install(self):
        self._go_to_step(1)
        self.worker = WingetInstallWorker(self.winget_id)
        self.worker.finished.connect(self._on_install_finished)
        self.worker.start()

    def _on_install_finished(self, success: bool, message: str):
        if success:
            self.choice = self.CHOICE_INSTALL
            self.accept()
        else:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Installation Failed", f"Could not install application automatically:\n{message}\n\nMoving to fallback options.")
            self._go_to_step(2)

    def _select_alternative(self):
        self.choice = self.CHOICE_ALTERNATIVE
        self.accept()

    def _select_store(self):
        self.choice = self.CHOICE_STORE
        self.accept()

    def _select_fallback(self):
        self.choice = self.CHOICE_FALLBACK
        self.accept()


# ============================================================
# Review & Proceed Dialog
# ============================================================
class ReviewDialog(QDialog):
    """Modal popup showing a drafted action for user review."""

    def __init__(self, title: str, content: str, action_label: str = "Approve & Send", action_type: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("DARKI — Review Required")
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Dialog
        )
        self.action_type = action_type
        self._approved = False
        self._setup_ui(title, content, action_label)

    def _setup_ui(self, title: str, content: str, action_label: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        # Title
        title_label = QLabel(f"⚠️ {title}")
        title_label.setStyleSheet("font-size: 15px; font-weight: 700; color: #f59e0b;")
        layout.addWidget(title_label)

        # Content area (editable so user can modify)
        self.content_edit = QTextEdit()
        self.content_edit.setPlainText(content)
        self.content_edit.setStyleSheet("""
            QTextEdit {
                background: rgba(0, 0, 0, 0.3);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 10px;
                color: #e2e8f0;
                font-size: 12px;
                padding: 10px;
            }
        """)
        layout.addWidget(self.content_edit)

        # SMTP Setup UI if action is Email
        if self.action_type == "email":
            from orchestra.config import settings
            smtp_configured = bool(settings.smtp_server and settings.smtp_email and settings.smtp_password)

            # SMTP Container Widget
            self.smtp_widget = QWidget()
            smtp_layout = QVBoxLayout(self.smtp_widget)
            smtp_layout.setContentsMargins(0, 0, 0, 0)
            smtp_layout.setSpacing(6)

            # Subtitle/Warning
            warning_label = QLabel()
            if not smtp_configured:
                warning_label.setText("⚠️ Outlook New detected. SMTP settings required for background emailing:")
                warning_label.setStyleSheet("color: #f59e0b; font-size: 11px; font-weight: bold;")
            else:
                warning_label.setText("SMTP settings configured. Using background SMTP sending:")
                warning_label.setStyleSheet("color: #10b981; font-size: 11px;")
            smtp_layout.addWidget(warning_label)

            # Grid of inputs
            grid = QGridLayout()
            grid.setSpacing(6)

            grid.addWidget(QLabel("SMTP Server:"), 0, 0)
            self.smtp_server_input = QLineEdit(settings.smtp_server or "smtp.gmail.com")
            grid.addWidget(self.smtp_server_input, 0, 1)

            grid.addWidget(QLabel("Port:"), 0, 2)
            self.smtp_port_input = QLineEdit(str(settings.smtp_port or 587))
            grid.addWidget(self.smtp_port_input, 0, 3)

            grid.addWidget(QLabel("Sender Email:"), 1, 0)
            self.smtp_email_input = QLineEdit(settings.smtp_email or "")
            self.smtp_email_input.setPlaceholderText("your_email@gmail.com")
            grid.addWidget(self.smtp_email_input, 1, 1, 1, 3)

            grid.addWidget(QLabel("App Password:"), 2, 0)
            self.smtp_password_input = QLineEdit(settings.smtp_password or "")
            self.smtp_password_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.smtp_password_input.setPlaceholderText("Gmail App Password")
            grid.addWidget(self.smtp_password_input, 2, 1, 1, 3)

            smtp_layout.addLayout(grid)

            # Save checkbox
            self.smtp_save_checkbox = QCheckBox("Save configuration to .env for future use")
            self.smtp_save_checkbox.setChecked(True)
            self.smtp_save_checkbox.setStyleSheet("color: #94a3b8; font-size: 11px;")
            smtp_layout.addWidget(self.smtp_save_checkbox)

            # Styling fields
            field_style = """
                QLineEdit {
                    background: rgba(0, 0, 0, 0.4);
                    border: 1px solid rgba(255, 255, 255, 0.10);
                    border-radius: 6px;
                    color: #e2e8f0;
                    font-size: 11px;
                    padding: 4px;
                }
                QLineEdit:focus {
                    border-color: rgba(59, 130, 246, 0.5);
                }
            """
            self.smtp_server_input.setStyleSheet(field_style)
            self.smtp_port_input.setStyleSheet(field_style)
            self.smtp_email_input.setStyleSheet(field_style)
            self.smtp_password_input.setStyleSheet(field_style)

            # Collapsible button
            self.smtp_toggle_btn = QPushButton("⚙️ SMTP background settings")
            self.smtp_toggle_btn.setCheckable(True)
            self.smtp_toggle_btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    border: none;
                    color: #94a3b8;
                    font-size: 11px;
                    text-align: left;
                    padding: 2px 0px;
                }
                QPushButton:hover { color: #f8fafc; }
            """)

            def toggle_smtp(checked):
                self.smtp_widget.setVisible(checked)
                if checked:
                    self.setMinimumSize(480, 520)
                    self.resize(480, 520)
                else:
                    self.setMinimumSize(480, 360)
                    self.resize(480, 360)

            self.smtp_toggle_btn.toggled.connect(toggle_smtp)
            layout.addWidget(self.smtp_toggle_btn)
            layout.addWidget(self.smtp_widget)

            # Default state: if not configured, show expanded, else collapsed
            if not smtp_configured:
                self.smtp_toggle_btn.setChecked(True)
                self.smtp_widget.setVisible(True)
                self.setMinimumSize(480, 520)
                self.resize(480, 520)
            else:
                self.smtp_toggle_btn.setChecked(False)
                self.smtp_widget.setVisible(False)
                self.setMinimumSize(480, 360)
                self.resize(480, 360)
        else:
            self.setMinimumSize(480, 360)
            self.resize(480, 360)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        approve_btn = QPushButton(f"✓ {action_label}")
        approve_btn.setStyleSheet("""
            QPushButton {
                background: rgba(16, 185, 129, 0.2);
                border: 1px solid rgba(16, 185, 129, 0.4);
                border-radius: 8px;
                color: #10b981;
                font-size: 13px;
                font-weight: 600;
                padding: 8px 20px;
            }
            QPushButton:hover { background: rgba(16, 185, 129, 0.35); }
        """)
        approve_btn.clicked.connect(self._approve)

        reject_btn = QPushButton("✕ Reject")
        reject_btn.setStyleSheet("""
            QPushButton {
                background: rgba(239, 68, 68, 0.15);
                border: 1px solid rgba(239, 68, 68, 0.3);
                border-radius: 8px;
                color: #ef4444;
                font-size: 13px;
                font-weight: 600;
                padding: 8px 20px;
            }
            QPushButton:hover { background: rgba(239, 68, 68, 0.3); }
        """)
        reject_btn.clicked.connect(self.reject)

        btn_row.addStretch()
        btn_row.addWidget(reject_btn)
        btn_row.addWidget(approve_btn)
        layout.addLayout(btn_row)

    def _approve(self):
        self._approved = True
        self.accept()

    def was_approved(self) -> bool:
        return self._approved

    def get_edited_content(self) -> str:
        return self.content_edit.toPlainText()

    def get_smtp_details(self) -> dict:
        if self.action_type == "email" and hasattr(self, "smtp_server_input"):
            return {
                "smtp_server": self.smtp_server_input.text().strip(),
                "smtp_port": int(self.smtp_port_input.text().strip()) if self.smtp_port_input.text().strip().isdigit() else 587,
                "smtp_email": self.smtp_email_input.text().strip(),
                "smtp_password": self.smtp_password_input.text().strip(),
                "save_to_env": self.smtp_save_checkbox.isChecked(),
            }
        return {}


# ============================================================
# Main DARKI Floating Widget
# ============================================================
class DarkiFloatingWidget(QWidget):
    """The main floating robot that sits on the desktop."""

    request_full_chat = pyqtSignal()

    def __init__(self):
        super().__init__()

        # Window: frameless, transparent, always-on-top, tool (no taskbar entry)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(90, 100)

        # Position: bottom-right of screen
        screen = QApplication.primaryScreen()
        if screen:
            geom = screen.availableGeometry()
            self.move(geom.width() - 120, geom.height() - 130)

        # Drag state
        self._drag_pos = None
        self._is_dragging = False

        # UI
        self._setup_ui()

        # Chat popup
        self.chat_popup = ChatBubblePopup()
        self.chat_popup.send_message.connect(self._handle_chat)
        self.chat_popup.open_full_chat.connect(self.request_full_chat.emit)

        # Worker reference
        self._worker = None

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.robot = RobotWidget(size=80, parent=self)
        self.robot.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
        layout.addWidget(self.robot)

    # --- Drag handling ---
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self._is_dragging = False
            self.robot.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() == Qt.MouseButton.LeftButton:
            new_pos = event.globalPosition().toPoint() - self._drag_pos
            self.move(new_pos)
            self._is_dragging = True
            # Move popup with robot if visible
            if self.chat_popup.isVisible():
                self._position_popup()
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.robot.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
            if not self._is_dragging:
                self._toggle_popup()
            self._drag_pos = None
            self._is_dragging = False
            event.accept()

    def _toggle_popup(self):
        if self.chat_popup.isVisible():
            self.chat_popup.hide()
        else:
            self._position_popup()
            self.chat_popup.show()
            self.chat_popup.input_field.setFocus()

    def _position_popup(self):
        """Position the popup above the robot."""
        robot_pos = self.pos()
        popup_x = robot_pos.x() + self.width() // 2 - self.chat_popup.width() // 2
        popup_y = robot_pos.y() - self.chat_popup.height() - 5

        # Clamp to screen bounds
        screen = QApplication.primaryScreen()
        if screen:
            geom = screen.availableGeometry()
            popup_x = max(geom.x(), min(popup_x, geom.right() - self.chat_popup.width()))
            popup_y = max(geom.y(), popup_y)

        self.chat_popup.move(popup_x, popup_y)

    # --- Chat handling ---
    def _handle_chat(self, text: str):
        self.robot.set_state("listening")
        self.chat_popup.set_loading(True)

        self._worker = ChatWorker(text)
        self._worker.finished.connect(self._on_chat_response)
        self._worker.error.connect(self._on_chat_error)
        self._worker.start()

    def _on_chat_response(self, data: dict):
        self.chat_popup.set_loading(False)
        content = data.get("content", "No response.")

        # Check for pending actions that need review
        if content.startswith("PENDING_TERMINAL_COMMAND:"):
            parts = content.split(":", 2)
            command = parts[1] if len(parts) > 1 else ""
            reasoning = parts[2] if len(parts) > 2 else ""
            self._show_review("Terminal Command", f"Command: {command}\n\nReasoning: {reasoning}", command, "terminal")
            self.robot.set_state("idle")
            return

        if content.startswith("PENDING_SANDBOX_CODE:"):
            import base64
            parts = content.split(":", 2)
            try:
                code = base64.b64decode(parts[1]).decode("utf-8") if len(parts) > 1 else ""
            except Exception:
                code = parts[1] if len(parts) > 1 else ""
            reasoning = parts[2] if len(parts) > 2 else ""
            self._show_review("Python Execution", f"Code:\n{code}\n\nReasoning: {reasoning}", code, "sandbox")
            self.robot.set_state("idle")
            return

        if content.startswith("PENDING_EMAIL_SEND:"):
            parts = content.split(":", 1)[1].split("|", 2)
            to = parts[0] if len(parts) > 0 else ""
            subject = parts[1] if len(parts) > 1 else ""
            body = parts[2] if len(parts) > 2 else ""
            self._show_review("Send Email", f"To: {to}\nSubject: {subject}\n\n{body}", f"{to}|{subject}|{body}", "email")
            self.robot.set_state("idle")
            return

        if content.startswith("PENDING_MEETING_SCHEDULE:"):
            parts = content.split(":", 1)[1].split("|", 4)
            subject = parts[0] if len(parts) > 0 else ""
            date_s = parts[1] if len(parts) > 1 else ""
            time_s = parts[2] if len(parts) > 2 else ""
            duration = parts[3] if len(parts) > 3 else "60"
            body = parts[4] if len(parts) > 4 else ""
            self._show_review("Schedule Meeting", f"Subject: {subject}\nDate: {date_s}\nTime: {time_s}\nDuration: {duration} minutes\n\nBody: {body}", f"{subject}|{date_s}|{time_s}|{duration}|{body}", "meeting_schedule")
            self.robot.set_state("idle")
            return

        if content.startswith("PENDING_REMINDER_SET:"):
            parts = content.split(":", 1)[1].split("|", 2)
            message = parts[0] if len(parts) > 0 else ""
            date_s = parts[1] if len(parts) > 1 else ""
            time_s = parts[2] if len(parts) > 2 else ""
            self._show_review("Set Reminder", f"Message: {message}\nDate: {date_s}\nTime: {time_s}", f"{message}|{date_s}|{time_s}", "reminder_set")
            self.robot.set_state("idle")
            return

        if content.startswith("PENDING_FILE_DELETE:"):
            filepath = content.split(":", 1)[1]
            self._show_review("Delete File", filepath, filepath, "file_delete")
            self.robot.set_state("idle")
            return

        if content.startswith("PENDING_APP_INSTALL:"):
            parts = content.split(":", 3)
            app_to_install = parts[1] if len(parts) > 1 else "Unknown"
            orig_action = parts[2] if len(parts) > 2 else ""
            orig_data_encoded = parts[3] if len(parts) > 3 else ""
            self._show_app_fallback_wizard(app_to_install, orig_action, orig_data_encoded)
            self.robot.set_state("idle")
            return
            
        # If it's a normal response (no pending actions)
        self.chat_popup.set_response(content)
        self.robot.set_state("success")
        QTimer.singleShot(2500, lambda: self.robot.set_state("idle"))

    def _show_app_fallback_wizard(self, app_name: str, orig_action: str, orig_data_encoded: str):
        # 1. Fetch app status from backend
        try:
            resp = requests.get(f"{API_BASE}/api/system/check_app", params={"app_name": app_name}, timeout=10)
            status_data = resp.json()
        except Exception:
            status_data = {
                "installed": False,
                "app_name": app_name,
                "winget_id": None,
                "web_fallback": None,
                "store_query": app_name
            }

        # 2. Launch Wizard Dialog
        wizard = AppFallbackWizard(
            app_name=status_data.get("app_name", app_name),
            winget_id=status_data.get("winget_id"),
            web_fallback=status_data.get("web_fallback"),
            store_query=status_data.get("store_query"),
            parent=self
        )
        wizard.exec()

        choice = wizard.choice
        
        # Decode original context payload
        import base64
        import json
        orig_data = {}
        if orig_data_encoded:
            try:
                orig_data = json.loads(base64.b64decode(orig_data_encoded.encode('utf-8')).decode('utf-8'))
            except Exception as e:
                logger.error(f"Failed to decode orig_data: {e}")

        # 3. Process the choice
        if choice == AppFallbackWizard.CHOICE_INSTALL:
            self.chat_popup.set_response(f"✓ '{app_name}' installed successfully. Retrying action...")
            self._execute_fallback_action(orig_action, orig_data)
            
        elif choice == AppFallbackWizard.CHOICE_ALTERNATIVE:
            web_url = status_data.get("web_fallback")
            if web_url:
                import webbrowser
                webbrowser.open(web_url)
                self.chat_popup.set_response(f"✓ Opened web alternative at: {web_url}")
            else:
                if orig_action == "schedule_meeting":
                    resp = requests.post(
                        f"{API_BASE}/api/calendar/schedule",
                        json={
                            "subject": orig_data.get("subject", "Meeting"),
                            "date": orig_data.get("date", ""),
                            "time": orig_data.get("time", ""),
                            "duration": int(orig_data.get("duration", 60)),
                            "body": orig_data.get("body", "")
                        },
                        timeout=30
                    )
                    data = resp.json()
                    self.chat_popup.set_response(data.get("details", "Calendar file created and opened."))
                elif orig_action == "set_reminder":
                    resp = requests.post(
                        f"{API_BASE}/api/calendar/schedule",
                        json={
                            "subject": f"Reminder: {orig_data.get('message', 'Alert')}",
                            "date": orig_data.get("date", ""),
                            "time": orig_data.get("time", ""),
                            "duration": 15,
                            "body": "Reminder calendar entry created as email calendar fallback."
                        },
                        timeout=30
                    )
                    data = resp.json()
                    self.chat_popup.set_response(data.get("details", "Scheduled reminder on email calendar."))
                elif orig_action in ("draft_email", "send_email"):
                    import webbrowser
                    import urllib.parse
                    mailto_to = orig_data.get("to", "")
                    mailto_subj = urllib.parse.quote(orig_data.get("subject", ""))
                    mailto_body = urllib.parse.quote(orig_data.get("body", ""))
                    webbrowser.open(f"mailto:{mailto_to}?subject={mailto_subj}&body={mailto_body}")
                    self.chat_popup.set_response("✓ Opened default mail client via mailto: fallback.")
                else:
                    self.chat_popup.set_response("No alternative fallback available.")
                    
        elif choice == AppFallbackWizard.CHOICE_STORE:
            import webbrowser
            store_url = f"ms-windows-store://search/?query={status_data.get('store_query', app_name)}"
            webbrowser.open(store_url)
            self.chat_popup.set_response(f"✓ Opened Microsoft Store search for '{app_name}'.")
            
        elif choice == AppFallbackWizard.CHOICE_FALLBACK:
            if orig_action == "set_reminder":
                resp = requests.post(
                    f"{API_BASE}/api/calendar/reminder",
                    json={
                        "message": orig_data.get("message", ""),
                        "date": orig_data.get("date", ""),
                        "time": orig_data.get("time", "")
                    },
                    timeout=30
                )
                data = resp.json()
                self.chat_popup.set_response(data.get("details", "Scheduled native Windows popup reminder."))
            elif orig_action == "launch_app":
                resp = requests.post(
                    f"{API_BASE}/api/terminal/execute",
                    json={"command": orig_data.get("target", "")},
                    timeout=30
                )
                data = resp.json()
                self.chat_popup.set_response(data.get("formatted_output", "Raw command execution done."))
            else:
                self.chat_popup.set_response("No fallback execution handler configured.")
                
        elif choice == AppFallbackWizard.CHOICE_CANCEL:
            self.chat_popup.set_response("Canceled.")

    def _execute_fallback_action(self, orig_action: str, orig_data: dict):
        try:
            if orig_action == "launch_app":
                resp = requests.post(
                    f"{API_BASE}/api/terminal/execute",
                    json={"command": orig_data.get("target", "")},
                    timeout=30
                )
                data = resp.json()
                self.chat_popup.set_response(data.get("formatted_output", "Launched application."))
            elif orig_action == "schedule_meeting":
                resp = requests.post(
                    f"{API_BASE}/api/calendar/schedule",
                    json={
                        "subject": orig_data.get("subject", ""),
                        "date": orig_data.get("date", ""),
                        "time": orig_data.get("time", ""),
                        "duration": int(orig_data.get("duration", 60)),
                        "body": orig_data.get("body", "")
                    },
                    timeout=30
                )
                data = resp.json()
                self.chat_popup.set_response(data.get("details", "Meeting scheduled."))
            elif orig_action == "set_reminder":
                resp = requests.post(
                    f"{API_BASE}/api/calendar/reminder",
                    json={
                        "message": orig_data.get("message", ""),
                        "date": orig_data.get("date", ""),
                        "time": orig_data.get("time", "")
                    },
                    timeout=30
                )
                data = resp.json()
                self.chat_popup.set_response(data.get("details", "Reminder configured."))
            elif orig_action in ("draft_email", "send_email"):
                resp = requests.post(
                    f"{API_BASE}/api/email/send",
                    json={
                        "to": orig_data.get("to", ""),
                        "subject": orig_data.get("subject", ""),
                        "body": orig_data.get("body", "")
                    },
                    timeout=30
                )
                data = resp.json()
                self.chat_popup.set_response(data.get("details", "Email sent."))
        except Exception as e:
            self.chat_popup.set_response(f"Failed to execute retry action: {str(e)}")

        self.robot.set_state("success")
        QTimer.singleShot(2500, lambda: self.robot.set_state("idle"))

    def _on_chat_error(self, error_msg: str):
        self.chat_popup.set_loading(False)
        self.chat_popup.set_response(f"❌ Error: {error_msg}")
        self.robot.set_state("error")
        QTimer.singleShot(2500, lambda: self.robot.set_state("idle"))

    def _show_review(self, title: str, content: str, command: str, action_type: str):
        self.chat_popup.set_response(f"⚠️ Review required: {title}")
        dialog = ReviewDialog(title, content, action_type=action_type, parent=self)
        result = dialog.exec()

        if dialog.was_approved():
            try:
                if action_type == "terminal":
                    resp = requests.post(
                        f"{API_BASE}/api/terminal/execute",
                        json={"command": command},
                        timeout=30,
                    )
                    data = resp.json()
                    self.chat_popup.set_response(data.get("formatted_output", "Done."))
                elif action_type == "sandbox":
                    resp = requests.post(
                        f"{API_BASE}/api/sandbox/execute",
                        json={"code": command},
                        timeout=30,
                    )
                    data = resp.json()
                    self.chat_popup.set_response(data.get("formatted_output", "Done."))
                elif action_type == "email":
                    import re
                    to_s, subj_s, body_s = command.split("|", 2)
                    edited_body = dialog.get_edited_content()
                    prefix_match = re.match(r"^To:\s*.*?\nSubject:\s*.*?\n\n", edited_body, re.IGNORECASE)
                    if prefix_match:
                        edited_body = edited_body[prefix_match.end():]

                    smtp_details = dialog.get_smtp_details()
                    req_payload = {
                        "to": to_s,
                        "subject": subj_s,
                        "body": edited_body
                    }

                    if smtp_details and smtp_details.get("smtp_password"):
                        req_payload["smtp_server"] = smtp_details["smtp_server"]
                        req_payload["smtp_port"] = smtp_details["smtp_port"]
                        req_payload["smtp_email"] = smtp_details["smtp_email"]
                        req_payload["smtp_password"] = smtp_details["smtp_password"]

                        if smtp_details.get("save_to_env"):
                            try:
                                from orchestra.config import PROJECT_ROOT, settings
                                env_path = PROJECT_ROOT / ".env"
                                lines = []
                                if env_path.exists():
                                    with open(env_path, "r", encoding="utf-8") as f:
                                        lines = f.readlines()

                                updated_keys = {
                                    "SMTP_SERVER": smtp_details["smtp_server"],
                                    "SMTP_PORT": str(smtp_details["smtp_port"]),
                                    "SMTP_EMAIL": smtp_details["smtp_email"],
                                    "SMTP_PASSWORD": smtp_details["smtp_password"],
                                }

                                new_lines = []
                                written_keys = set()
                                for line in lines:
                                    matched = False
                                    for key, val in updated_keys.items():
                                        if line.strip().startswith(f"{key}="):
                                            new_lines.append(f"{key}={val}\n")
                                            written_keys.add(key)
                                            matched = True
                                            break
                                    if not matched:
                                        new_lines.append(line)

                                for key, val in updated_keys.items():
                                    if key not in written_keys:
                                        if new_lines and not new_lines[-1].endswith("\n"):
                                            new_lines[-1] += "\n"
                                        new_lines.append(f"{key}={val}\n")

                                with open(env_path, "w", encoding="utf-8") as f:
                                    f.writelines(new_lines)

                                # Update memory settings
                                settings.smtp_server = smtp_details["smtp_server"]
                                settings.smtp_port = smtp_details["smtp_port"]
                                settings.smtp_email = smtp_details["smtp_email"]
                                settings.smtp_password = smtp_details["smtp_password"]
                            except Exception as env_err:
                                logger.error(f"Failed to update .env: {env_err}")

                    resp = requests.post(
                        f"{API_BASE}/api/email/send",
                        json=req_payload,
                        timeout=30,
                    )
                    data = resp.json()
                    self.chat_popup.set_response(data.get("details", "Done."))
                elif action_type == "file_delete":
                    resp = requests.post(
                        f"{API_BASE}/api/files/delete",
                        json={"path": command},
                        timeout=30,
                    )
                    data = resp.json()
                    self.chat_popup.set_response(data.get("details", "Done."))
                elif action_type == "meeting_schedule":
                    subject_s, date_s, time_s, duration_s, body_s = command.split("|", 4)
                    resp = requests.post(
                        f"{API_BASE}/api/calendar/schedule",
                        json={
                            "subject": subject_s,
                            "date": date_s,
                            "time": time_s,
                            "duration": int(duration_s),
                            "body": body_s
                        },
                        timeout=30,
                    )
                    data = resp.json()
                    self.chat_popup.set_response(data.get("details", "Done."))
                elif action_type == "reminder_set":
                    message_s, date_s, time_s = command.split("|", 2)
                    resp = requests.post(
                        f"{API_BASE}/api/calendar/reminder",
                        json={
                            "message": message_s,
                            "date": date_s,
                            "time": time_s
                        },
                        timeout=30,
                    )
                    data = resp.json()
                    self.chat_popup.set_response(data.get("details", "Done."))
                elif action_type == "app_install":
                    resp = requests.post(
                        f"{API_BASE}/api/system/install_app",
                        json={"app_name": command},
                        timeout=190,
                    )
                    data = resp.json()
                    self.chat_popup.set_response(data.get("details", "Done."))
                self.robot.set_state("success")
            except Exception as e:
                self.chat_popup.set_response(f"❌ Execution failed: {e}")
                self.robot.set_state("error")
        else:
            self.chat_popup.set_response("❌ Action rejected by user.")

        QTimer.singleShot(2500, lambda: self.robot.set_state("idle"))

    # --- Public API for external triggers (voice, hotkey) ---
    def activate_popup(self, prefill_text: str = ""):
        """Show the popup and optionally prefill the input."""
        if not self.chat_popup.isVisible():
            self._position_popup()
            self.chat_popup.show()
        if prefill_text:
            self.chat_popup.input_field.setText(prefill_text)
        self.chat_popup.input_field.setFocus()

    def submit_command(self, text: str):
        """Programmatically submit a command (used by voice listener)."""
        if not self.chat_popup.isVisible():
            self._position_popup()
            self.chat_popup.show()
        self._handle_chat(text)

    def cleanup(self):
        """Clean up resources."""
        if self.chat_popup:
            self.chat_popup.close()
