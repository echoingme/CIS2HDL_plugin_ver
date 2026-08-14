"""Log Panel — real-time log output with collapsible card wrapper."""

from __future__ import annotations

import logging
from datetime import datetime

from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QPlainTextEdit,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QWidget,
    QPushButton,
    QSizePolicy,
)

from ..colors import (
    Colors,
    Radius,
    FontSize,
    Fonts,
    Layout,
    STYLE_LOG,
    STYLE_CARD,
)


class LogPanel(QWidget):
    """Collapsible card panel for real-time log output.

    Collapsed state: title bar only (36 px).
    Expanded state: title bar + log content (160 px).
    """

    MIN_HEIGHT = 36

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self.setStyleSheet(STYLE_CARD)
        self.setMinimumHeight(Layout.LOG_COLLAPSED_H)

        # ── Outer layout ─────────────────────────────────────────────
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Title bar ────────────────────────────────────────────────
        self._collapsed = False

        title_bar = QWidget()
        title_bar.setFixedHeight(Layout.LOG_COLLAPSED_H)
        title_bar.setStyleSheet("background: transparent; border: none;")
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(12, 6, 12, 6)
        title_layout.setSpacing(8)

        # Toggle arrow + title
        self._toggle_btn = QPushButton("\u25bc  Log")  # ▼ Log
        self._toggle_btn.setFlat(True)
        self._toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle_btn.setStyleSheet(
            f"background: transparent; border: none; "
            f"font-size: {FontSize.SM}px; font-weight: 600; "
            f"color: {Colors.TEXT_PRIMARY}; padding: 2px 4px;"
        )
        self._toggle_btn.clicked.connect(self._on_toggle)
        title_layout.addWidget(self._toggle_btn)

        title_layout.addStretch()

        # Clear button
        clear_btn = QPushButton("Clear")
        clear_btn.setFixedHeight(24)
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.setStyleSheet(
            f"background: transparent; color: {Colors.ACCENT}; "
            f"border: none; font-size: {FontSize.XXS}px; padding: 2px 8px;"
        )
        clear_btn.clicked.connect(self.clear)
        title_layout.addWidget(clear_btn)

        outer.addWidget(title_bar)

        # ── Log content area ─────────────────────────────────────────
        self._content_area = QWidget()
        content_layout = QVBoxLayout(self._content_area)
        content_layout.setContentsMargins(8, 0, 8, 8)
        content_layout.setSpacing(0)

        self._editor = QPlainTextEdit()
        self._editor.setReadOnly(True)
        self._editor.setMaximumBlockCount(5000)
        self._editor.setStyleSheet(STYLE_LOG)
        self._editor.setMinimumHeight(80)
        content_layout.addWidget(self._editor)

        outer.addWidget(self._content_area)

        # Store target heights
        self._expanded_height = Layout.LOG_EXPANDED_H
        self._collapsed_height = Layout.LOG_COLLAPSED_H

        # Register as log handler
        self._setup_log_handler()

    # ── Collapse / Expand ────────────────────────────────────────────

    def _on_toggle(self) -> None:
        """Toggle between collapsed and expanded states."""
        if self._collapsed:
            self._expand()
        else:
            self._collapse()

    def _collapse(self) -> None:
        """Collapse: hide content, show only title bar."""
        self._collapsed = True
        self._content_area.setVisible(False)
        self.setFixedHeight(Layout.LOG_COLLAPSED_H)
        self._toggle_btn.setText("\u25b6  Log")  # ▶ Log

    def _expand(self) -> None:
        """Expand: show content + title bar."""
        self._collapsed = False
        self._content_area.setVisible(True)
        self.setMinimumHeight(Layout.LOG_EXPANDED_H)
        self.setMaximumHeight(16777215)  # QWIDGETSIZE_MAX
        self.setFixedHeight(Layout.LOG_EXPANDED_H)
        self._toggle_btn.setText("\u25bc  Log")  # ▼ Log

    # ── Log handler setup ────────────────────────────────────────────

    def _setup_log_handler(self) -> None:
        """Add a logging handler that routes to this panel."""
        handler = _LogPanelHandler(self)
        handler.setLevel(logging.INFO)
        fmt = logging.Formatter("%(asctime)s [%(levelname)-5s] %(message)s", "%H:%M:%S")
        handler.setFormatter(fmt)
        logging.getLogger().addHandler(handler)
        logging.getLogger("cis2hdl").addHandler(handler)

    # ── Public API ───────────────────────────────────────────────────

    def info(self, message: str) -> None:
        self._append(message, Colors.TEXT_PRIMARY)

    def warn(self, message: str) -> None:
        self._append(message, Colors.WARNING)

    def error(self, message: str) -> None:
        self._append(message, Colors.ERROR)

    def success(self, message: str) -> None:
        self._append(message, Colors.INFO)

    def clear(self) -> None:
        self._editor.clear()

    def _append(self, message: str, color_hex: str) -> None:
        """Append a timestamped message with the given hex color to the log.

        Args:
            message: The log message text.
            color_hex: A hex color string (e.g. \"#141413\").
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        html = (
            f'<span style="color:{color_hex}; '
            f'font-family:{Fonts.MONO}; '
            f'font-size:{FontSize.XS}px;">'
            f'[{timestamp}] {message}</span><br>'
        )
        self._editor.appendHtml(html)


class _LogPanelHandler(logging.Handler):
    """Logging handler that writes to the LogPanel widget."""

    LEVEL_COLORS = {
        logging.DEBUG: Colors.TEXT_MUTED,
        logging.INFO: Colors.TEXT_PRIMARY,
        logging.WARNING: Colors.WARNING,
        logging.ERROR: Colors.ERROR,
        logging.CRITICAL: Colors.ERROR,
    }

    def __init__(self, panel: LogPanel) -> None:
        super().__init__()
        self._panel = panel

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            color = self.LEVEL_COLORS.get(record.levelno, Colors.TEXT_PRIMARY)
            self._panel._append(msg, color)
        except Exception:
            pass
