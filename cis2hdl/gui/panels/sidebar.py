"""Sidebar — brand, project info, navigation, actions, and footer."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from cis2hdl import __version__

from ..colors import (
    Colors,
    FontSize,
    Fonts,
    Layout,
    STYLE_SIDEBAR,
    STYLE_BUTTON_PRIMARY,
    STYLE_BUTTON_SECONDARY,
    rgba,
)


class Sidebar(QWidget):
    """Fixed-width sidebar with brand, project info, navigation, and actions.

    Signals:
        nav_changed(int):          Emitted when a navigation item is clicked.
        action_triggered(str):     Emitted when an action button is clicked.
                                   Values: "open", "diagnose", "convert".
    """

    nav_changed = Signal(int)
    action_triggered = Signal(str)

    _NAV_ITEMS: list[tuple[str, bool]] = [
        ("Project", False),
        ("Diagnostics", False),
        ("Match", True),
        ("Diff", True),
    ]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(Layout.SIDEBAR_WIDTH)
        self.setStyleSheet(STYLE_SIDEBAR)

        self._nav_buttons: list[QPushButton] = []
        self._nav_disabled: list[bool] = []
        self._active_index: int = 0

        self._build_ui()

    # ── Build UI ────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        """Construct the full sidebar layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Brand ───────────────────────────────────────────────────────
        layout.addLayout(self._build_brand())

        # ── Separator ───────────────────────────────────────────────────
        layout.addWidget(self._make_h_separator())

        # ── Project Info ────────────────────────────────────────────────
        self._info_container = QWidget()
        self._info_layout = QVBoxLayout(self._info_container)
        self._info_layout.setContentsMargins(16, 12, 16, 12)
        self._info_layout.setSpacing(2)

        # Row 1: name + status dot
        name_row = QHBoxLayout()
        name_row.setContentsMargins(0, 0, 0, 0)
        name_row.setSpacing(8)

        self._project_name_label = QLabel("No project loaded")
        self._project_name_label.setStyleSheet(
            f"font-size: {FontSize.SM}px; font-weight: 600; "
            f"color: {Colors.TEXT_PRIMARY};"
        )
        self._project_name_label.setWordWrap(False)
        name_row.addWidget(self._project_name_label, 1)

        self._status_dot = QLabel("\u25CF")
        self._status_dot.setStyleSheet(
            f"color: {Colors.TEXT_MUTED}; font-size: 14px;"
        )
        self._status_dot.setFixedWidth(16)
        name_row.addWidget(self._status_dot)

        self._status_text = QLabel("")
        self._status_text.setStyleSheet(
            f"font-size: {FontSize.XXS}px; color: {Colors.ACCENT};"
        )
        name_row.addWidget(self._status_text)

        self._info_layout.addLayout(name_row)

        # Row 2: file path
        self._project_path_label = QLabel("")
        self._project_path_label.setStyleSheet(
            f"font-size: {FontSize.XXS}px; color: {Colors.TEXT_MUTED};"
        )
        self._project_path_label.setWordWrap(True)
        self._info_layout.addWidget(self._project_path_label)

        layout.addWidget(self._info_container)

        # ── Separator ───────────────────────────────────────────────────
        layout.addWidget(self._make_h_separator())

        # ── Navigation ──────────────────────────────────────────────────
        nav_container = QWidget()
        nav_layout = QVBoxLayout(nav_container)
        nav_layout.setContentsMargins(0, 8, 0, 8)
        nav_layout.setSpacing(0)

        for idx, (text, disabled) in enumerate(self._NAV_ITEMS):
            btn = self._create_nav_button(text, disabled, idx)
            self._nav_buttons.append(btn)
            self._nav_disabled.append(disabled)
            nav_layout.addWidget(btn)

        nav_layout.addStretch()
        layout.addWidget(nav_container, 1)  # stretch to fill remaining space

        # ── Separator ───────────────────────────────────────────────────
        layout.addWidget(self._make_h_separator())

        # ── Actions ─────────────────────────────────────────────────────
        layout.addLayout(self._build_actions())

        # ── Footer ──────────────────────────────────────────────────────
        layout.addLayout(self._build_footer())

        # Set initial nav active state
        self.set_nav_active(0)

    def _build_brand(self) -> QVBoxLayout:
        """Build the brand / logo area."""
        brand_layout = QVBoxLayout()
        brand_layout.setContentsMargins(16, 20, 16, 12)
        brand_layout.setSpacing(2)

        brand_label = QLabel("CIS2HDL")
        brand_label.setStyleSheet(
            f"font-size: {FontSize.LG}px; font-weight: bold; "
            f"color: {Colors.TEXT_PRIMARY};"
        )
        brand_layout.addWidget(brand_label)

        subtitle = QLabel("(CIS \u2192 HDL)")
        subtitle.setStyleSheet(
            f"font-size: {FontSize.XXS}px; color: {Colors.TEXT_MUTED};"
        )
        brand_layout.addWidget(subtitle)

        return brand_layout

    def _build_actions(self) -> QVBoxLayout:
        """Build the action buttons area."""
        actions_layout = QVBoxLayout()
        actions_layout.setContentsMargins(16, 12, 16, 12)
        actions_layout.setSpacing(8)

        # Open button (secondary)
        self._open_btn = QPushButton("Open")
        self._open_btn.setFixedHeight(32)
        self._open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._open_btn.setStyleSheet(
            STYLE_BUTTON_SECONDARY
            + f"font-size: {FontSize.XS}px; padding: 4px 12px;"
        )
        self._open_btn.clicked.connect(lambda: self.action_triggered.emit("open"))
        actions_layout.addWidget(self._open_btn)

        # Diagnose button (secondary)
        self._diagnose_btn = QPushButton("Diagnose")
        self._diagnose_btn.setFixedHeight(32)
        self._diagnose_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._diagnose_btn.setStyleSheet(
            STYLE_BUTTON_SECONDARY
            + f"font-size: {FontSize.XS}px; padding: 4px 12px;"
        )
        self._diagnose_btn.clicked.connect(lambda: self.action_triggered.emit("diagnose"))
        actions_layout.addWidget(self._diagnose_btn)

        # Convert button (primary)
        self._convert_btn = QPushButton("Convert")
        self._convert_btn.setFixedHeight(32)
        self._convert_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._convert_btn.setStyleSheet(
            STYLE_BUTTON_PRIMARY
            + f"font-size: {FontSize.XS}px; padding: 4px 12px;"
        )
        self._convert_btn.setEnabled(False)
        self._convert_btn.clicked.connect(lambda: self.action_triggered.emit("convert"))
        actions_layout.addWidget(self._convert_btn)

        return actions_layout

    def _build_footer(self) -> QHBoxLayout:
        """Build the footer with version number."""
        footer_layout = QHBoxLayout()
        footer_layout.setContentsMargins(16, 8, 16, 12)
        footer_layout.setSpacing(0)

        footer_layout.addStretch()

        version_label = QLabel(f"v{__version__}")
        version_label.setStyleSheet(
            f"font-size: {FontSize.XXS}px; color: {Colors.TEXT_MUTED};"
        )
        footer_layout.addWidget(version_label)

        return footer_layout

    # ── Navigation helpers ──────────────────────────────────────────────────

    def _create_nav_button(self, text: str, disabled: bool, index: int) -> QPushButton:
        """Create a single navigation button."""
        btn = QPushButton(text)
        btn.setFixedHeight(36)
        btn.setFlat(True)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)

        if disabled:
            btn.setEnabled(False)
            btn.setStyleSheet(
                f"text-align: left; padding: 0 20px; "
                f"border-left: 2px solid transparent; "
                f"color: {rgba(Colors.TEXT_MUTED, 0.35)}; "
                f"font-size: {FontSize.SM}px; "
                f"border-top: none; border-right: none; border-bottom: none; "
                f"background: transparent;"
            )
        else:
            btn.setStyleSheet(
                f"text-align: left; padding: 0 20px; "
                f"border-left: 2px solid transparent; "
                f"color: {Colors.TEXT_MUTED}; "
                f"font-size: {FontSize.SM}px; "
                f"border-top: none; border-right: none; border-bottom: none; "
                f"background: transparent;"
            )
            btn.clicked.connect(lambda checked, idx=index: self._on_nav_click(idx))

        return btn

    def _on_nav_click(self, index: int) -> None:
        """Handle a navigation item click."""
        self.set_nav_active(index)
        self.nav_changed.emit(index)

    # ── Public API ──────────────────────────────────────────────────────────

    def set_project_info(self, name: str, path: str, loaded: bool = True) -> None:
        """Update the project information display.

        Args:
            name: Project name (will be truncated if > 24 chars).
            path: Full file path (will be truncated if > 30 chars).
            loaded: Whether the project is loaded.
        """
        # Truncate name
        display_name = name[:21] + "..." if len(name) > 24 else name
        self._project_name_label.setText(f"\U0001F4C1 {display_name}")

        # Truncate path from the left
        display_path = path
        if len(path) > 35:
            display_path = "..." + path[-32:]
        self._project_path_label.setText(display_path)

        if loaded:
            self._status_dot.setStyleSheet(
                f"color: {Colors.ACCENT}; font-size: 14px;"
            )
            self._status_text.setText("Loaded")
            self._status_text.setStyleSheet(
                f"font-size: {FontSize.XXS}px; color: {Colors.ACCENT};"
            )
        else:
            self._status_dot.setStyleSheet(
                f"color: {Colors.TEXT_MUTED}; font-size: 14px;"
            )
            self._status_text.setText("Not loaded")
            self._status_text.setStyleSheet(
                f"font-size: {FontSize.XXS}px; color: {Colors.TEXT_MUTED};"
            )

    def set_nav_active(self, index: int) -> None:
        """Highlight the navigation item at *index* and deactivate others.

        Args:
            index: 0-based index of the nav item to activate.
        """
        self._active_index = index
        for i, btn in enumerate(self._nav_buttons):
            if self._nav_disabled[i]:
                continue
            if i == index:
                btn.setStyleSheet(
                    f"text-align: left; padding: 0 20px; "
                    f"border-left: 2px solid {Colors.ACCENT}; "
                    f"color: {Colors.TEXT_PRIMARY}; "
                    f"font-size: {FontSize.SM}px; font-weight: 600; "
                    f"border-top: none; border-right: none; border-bottom: none; "
                    f"background: transparent;"
                )
            else:
                btn.setStyleSheet(
                    f"text-align: left; padding: 0 20px; "
                    f"border-left: 2px solid transparent; "
                    f"color: {Colors.TEXT_MUTED}; "
                    f"font-size: {FontSize.SM}px; "
                    f"border-top: none; border-right: none; border-bottom: none; "
                    f"background: transparent;"
                )

    def set_convert_enabled(self, enabled: bool) -> None:
        """Enable or disable the Convert button.

        Args:
            enabled: True to enable, False to disable.
        """
        self._convert_btn.setEnabled(enabled)

    # ── Utility ─────────────────────────────────────────────────────────────

    @staticmethod
    def _make_h_separator() -> QFrame:
        """Create a horizontal separator line."""
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(
            f"color: {Colors.BORDER_SUBTLE}; margin: 0 16px; max-height: 1px;"
        )
        return sep
