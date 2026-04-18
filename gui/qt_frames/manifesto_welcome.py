"""
Kingdom AI — Manifesto Welcome Screen
SOTA 2026: Full-screen cinematic welcome experience.

Displays Isaiah Marck Wright's manifesto with typewriter text effect
while KAI voices every word. Then walks the user through the entire
system with section-by-section explanations.

Used by both consumer and creator versions on first launch.
"""
import logging
import time
from typing import Any, Callable, Dict, List, Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QSizePolicy, QStackedWidget, QProgressBar,
    QGraphicsOpacityEffect, QApplication,
)
from PyQt6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtSignal, QThread,
)
from PyQt6.QtGui import QFont, QColor, QPalette, QPainter, QLinearGradient

logger = logging.getLogger("KingdomAI.GUI.ManifestoWelcome")

# Colors
GOLD = "#FFD700"
CYAN = "#00FFFF"
NEON_GREEN = "#39FF14"
WHITE = "#FFFFFF"
LIGHT_GRAY = "#CCCCCC"
DARK_BG = "#050510"
CARD_BG = "#0a0a20"
BORDER_GOLD = "#8B7536"


class TypewriterLabel(QLabel):
    """A QLabel that reveals text character by character."""

    finished = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._full_text = ""
        self._current_index = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._reveal_next)
        self._char_delay_ms = 30  # ms per character
        self._paragraph_delay_ms = 400  # pause between paragraphs

    def start_typewriter(self, text: str, char_delay_ms: int = 30):
        self._full_text = text
        self._current_index = 0
        self._char_delay_ms = char_delay_ms
        self.setText("")
        self._timer.start(self._char_delay_ms)

    def skip_to_end(self):
        self._timer.stop()
        self.setText(self._full_text)
        self._current_index = len(self._full_text)
        self.finished.emit()

    def _reveal_next(self):
        if self._current_index >= len(self._full_text):
            self._timer.stop()
            self.finished.emit()
            return

        self._current_index += 1
        self.setText(self._full_text[:self._current_index])

        # Pause at paragraph breaks
        if self._current_index < len(self._full_text):
            next_char = self._full_text[self._current_index - 1]
            if next_char == "\n" and self._current_index > 1:
                prev_char = self._full_text[self._current_index - 2]
                if prev_char == "\n":
                    self._timer.setInterval(self._paragraph_delay_ms)
                    return
        self._timer.setInterval(self._char_delay_ms)


class ManifestoWelcome(QWidget):
    """
    Full-screen cinematic welcome experience.

    Phase 1: Manifesto display with typewriter text + KAI voice
    Phase 2: System walkthrough section by section
    Phase 3: Getting started prompt
    """

    welcome_complete = pyqtSignal()

    def __init__(self, parent=None, event_bus=None):
        super().__init__(parent)
        self.event_bus = event_bus
        self._current_phase = 0  # 0=manifesto, 1+=walkthrough sections
        self._voice_queue: List[Dict] = []
        self._sections: List[Dict] = []
        self._manifesto_paragraphs: List[str] = []

        self.setStyleSheet(f"background-color: {DARK_BG};")

        self._load_content()
        self._build_ui()

    def _load_content(self):
        try:
            from core.manifesto import (
                get_manifesto_paragraphs,
                get_walkthrough_sections,
                get_all_voice_segments,
                MANIFESTO_TITLE,
                MANIFESTO_AUTHOR,
                WALKTHROUGH_INTRO,
            )
            self._manifesto_paragraphs = get_manifesto_paragraphs()
            self._sections = get_walkthrough_sections()
            self._voice_segments = get_all_voice_segments()
            self._manifesto_title = MANIFESTO_TITLE
            self._manifesto_author = MANIFESTO_AUTHOR
            self._walkthrough_intro = WALKTHROUGH_INTRO
        except ImportError:
            self._manifesto_paragraphs = ["Welcome to Kingdom AI."]
            self._sections = []
            self._voice_segments = []
            self._manifesto_title = "Welcome"
            self._manifesto_author = ""
            self._walkthrough_intro = ""

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Stacked widget for manifesto vs walkthrough
        self._stack = QStackedWidget()
        main_layout.addWidget(self._stack)

        # Page 0: Manifesto
        self._manifesto_page = self._build_manifesto_page()
        self._stack.addWidget(self._manifesto_page)

        # Page 1: Walkthrough
        self._walkthrough_page = self._build_walkthrough_page()
        self._stack.addWidget(self._walkthrough_page)

        # Bottom bar (always visible)
        bottom_bar = QHBoxLayout()
        bottom_bar.setContentsMargins(40, 10, 40, 20)

        self._progress = QProgressBar()
        self._progress.setMaximum(len(self._sections) + 1)
        self._progress.setValue(0)
        self._progress.setFixedHeight(4)
        self._progress.setStyleSheet(f"""
            QProgressBar {{
                background-color: #1a1a3e;
                border: none;
                border-radius: 2px;
            }}
            QProgressBar::chunk {{
                background-color: {GOLD};
                border-radius: 2px;
            }}
        """)
        bottom_bar.addWidget(self._progress, stretch=1)

        self._skip_btn = QPushButton("Skip →")
        self._skip_btn.setFixedWidth(100)
        self._skip_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._skip_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {LIGHT_GRAY};
                border: 1px solid #333;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                color: {GOLD};
                border-color: {GOLD};
            }}
        """)
        self._skip_btn.clicked.connect(self._skip_current)
        bottom_bar.addWidget(self._skip_btn)

        self._next_btn = QPushButton("Continue →")
        self._next_btn.setFixedWidth(140)
        self._next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._next_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #8B6914, stop:1 #DAA520);
                color: {DARK_BG};
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #DAA520, stop:1 #FFD700);
            }}
        """)
        self._next_btn.clicked.connect(self._advance)
        self._next_btn.setVisible(False)
        bottom_bar.addWidget(self._next_btn)

        main_layout.addLayout(bottom_bar)

    def _build_manifesto_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet(f"background-color: {DARK_BG};")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(60, 40, 60, 20)
        layout.setSpacing(20)

        # Crown icon
        crown = QLabel("👑")
        crown.setAlignment(Qt.AlignmentFlag.AlignCenter)
        crown.setFont(QFont("Segoe UI Emoji", 48))
        layout.addWidget(crown)

        # Title
        title = QLabel(self._manifesto_title)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Georgia", 28, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {GOLD}; margin-bottom: 5px;")
        layout.addWidget(title)

        # Author
        author = QLabel(self._manifesto_author)
        author.setAlignment(Qt.AlignmentFlag.AlignCenter)
        author.setFont(QFont("Georgia", 14))
        author.setStyleSheet(f"color: {LIGHT_GRAY}; margin-bottom: 20px;")
        layout.addWidget(author)

        # Divider
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet(f"color: {BORDER_GOLD}; margin: 10px 100px;")
        layout.addWidget(divider)

        # Scroll area for manifesto text
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"""
            QScrollArea {{
                background-color: transparent;
                border: none;
            }}
            QScrollBar:vertical {{
                background-color: {DARK_BG};
                width: 8px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {BORDER_GOLD};
                border-radius: 4px;
                min-height: 30px;
            }}
        """)

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(40, 10, 40, 10)

        self._manifesto_label = TypewriterLabel()
        self._manifesto_label.setWordWrap(True)
        self._manifesto_label.setFont(QFont("Georgia", 15))
        self._manifesto_label.setStyleSheet(f"color: {WHITE}; line-height: 1.8;")
        self._manifesto_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self._manifesto_label.finished.connect(self._on_manifesto_typed)
        scroll_layout.addWidget(self._manifesto_label)
        scroll_layout.addStretch()

        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, stretch=1)

        return page

    def _build_walkthrough_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet(f"background-color: {DARK_BG};")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(60, 30, 60, 20)
        layout.setSpacing(15)

        # Section header
        self._section_icon = QLabel("")
        self._section_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._section_icon.setFont(QFont("Segoe UI Emoji", 40))
        layout.addWidget(self._section_icon)

        self._section_title = QLabel("")
        self._section_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._section_title.setFont(QFont("Georgia", 24, QFont.Weight.Bold))
        self._section_title.setStyleSheet(f"color: {GOLD};")
        layout.addWidget(self._section_title)

        # Divider
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet(f"color: {BORDER_GOLD}; margin: 5px 80px;")
        layout.addWidget(divider)

        # Content area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"""
            QScrollArea {{ background-color: transparent; border: none; }}
            QScrollBar:vertical {{
                background-color: {DARK_BG}; width: 8px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {BORDER_GOLD}; border-radius: 4px; min-height: 30px;
            }}
        """)

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(40, 10, 40, 10)

        self._section_text = QLabel("")
        self._section_text.setWordWrap(True)
        self._section_text.setFont(QFont("Consolas", 13))
        self._section_text.setStyleSheet(f"color: {CYAN}; line-height: 1.6;")
        self._section_text.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        scroll_layout.addWidget(self._section_text)
        scroll_layout.addStretch()

        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, stretch=1)

        return page

    # ------------------------------------------------------------------
    # Flow control
    # ------------------------------------------------------------------

    def start(self):
        """Begin the welcome experience."""
        self._current_phase = 0
        self._stack.setCurrentIndex(0)

        # Join all paragraphs into full text
        full_text = "\n\n".join(self._manifesto_paragraphs)
        self._manifesto_label.start_typewriter(full_text, char_delay_ms=25)

        # Voice the manifesto
        self._voice_text(full_text, priority="critical")

        logger.info("Manifesto welcome experience started")

    def _on_manifesto_typed(self):
        """Called when typewriter finishes the manifesto."""
        self._next_btn.setVisible(True)
        self._next_btn.setText("Begin Walkthrough →")
        self._progress.setValue(1)

    def _advance(self):
        """Advance to next section."""
        if self._current_phase == 0:
            # Move from manifesto to walkthrough
            self._current_phase = 1
            self._stack.setCurrentIndex(1)

            # Voice the walkthrough intro
            if self._walkthrough_intro:
                self._voice_text(self._walkthrough_intro)

            self._show_section(0)
        else:
            section_idx = self._current_phase - 1 + 1
            if section_idx < len(self._sections):
                self._show_section(section_idx)
                self._current_phase += 1
            else:
                # Done
                self._finish()
                return

        self._progress.setValue(self._current_phase)

    def _show_section(self, idx: int):
        """Display a walkthrough section."""
        if idx >= len(self._sections):
            self._finish()
            return

        section = self._sections[idx]
        self._section_icon.setText(section.get("icon", ""))
        self._section_title.setText(section.get("title", ""))
        self._section_text.setText(section.get("display_text", ""))

        # Voice this section
        self._voice_text(section.get("voice_text", ""))

        # Update button text
        if idx >= len(self._sections) - 1:
            self._next_btn.setText("Enter Kingdom →")
        else:
            self._next_btn.setText("Continue →")

        self._next_btn.setVisible(True)
        self._current_phase = idx + 1

    def _skip_current(self):
        """Skip current display — advance immediately."""
        if self._current_phase == 0:
            self._manifesto_label.skip_to_end()
        self._advance()

    def _finish(self):
        """Welcome complete — enter the main application."""
        self._progress.setValue(self._progress.maximum())
        logger.info("Manifesto welcome experience complete")

        # Save that welcome was shown
        self._mark_welcome_shown()

        # Voice final welcome
        self._voice_text(
            "Welcome to the Kingdom. I am KAI, and I am honored to serve you. "
            "Let us build something great together.",
            priority="critical",
        )

        self.welcome_complete.emit()

    def _mark_welcome_shown(self):
        """Persist that welcome has been shown so it doesn't repeat."""
        if self.event_bus:
            self.event_bus.publish("system.welcome.completed", {
                "timestamp": time.time(),
            })

        # Also save to local config
        import json
        import os
        config_path = os.path.join("config", "welcome_state.json")
        try:
            os.makedirs("config", exist_ok=True)
            with open(config_path, "w") as f:
                json.dump({"welcome_shown": True, "timestamp": time.time()}, f)
        except Exception:
            pass

    @staticmethod
    def should_show_welcome() -> bool:
        """Check if welcome should be shown (first launch)."""
        import json
        import os
        config_path = os.path.join("config", "welcome_state.json")
        try:
            if os.path.exists(config_path):
                with open(config_path, "r") as f:
                    data = json.load(f)
                return not data.get("welcome_shown", False)
        except Exception:
            pass
        return True

    # ------------------------------------------------------------------
    # Voice integration
    # ------------------------------------------------------------------

    def _voice_text(self, text: str, priority: str = "high"):
        """Send text to KAI voice system via event bus."""
        if not self.event_bus:
            return
        self.event_bus.publish("voice.speak", {
            "text": text,
            "priority": priority,
            "source": "manifesto",
            "interruptible": True,
        })
