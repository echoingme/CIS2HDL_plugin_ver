"""Settings Dialog — HDL library path and application configuration."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...core.config import config as cfg
from ..colors import (
    Colors,
    FontSize,
    Radius,
    Spacing,
    rgba,
)


class SettingsDialog(QDialog):
    """Application settings dialog with Anthropic design language styling.

    Provides configuration for:
    - HDL library root path (with Browse button)
    - Future: additional settings panels

    Settings are persisted to the global Config singleton immediately on accept.
    """

    WINDOW_TITLE = "Settings — CIS2HDL"
    MIN_WIDTH = 400

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.WINDOW_TITLE)
        self.setMinimumWidth(self.MIN_WIDTH)
        self.setModal(True)

        self._build_ui()
        self._apply_styles()

        # Load current config values into the form
        self._load_config()

    # ── UI Construction ──────────────────────────────────────────────────

    def _build_ui(self) -> None:
        """Build the dialog layout: card-style form inside a warm-beige shell."""
        # Outer shell
        outer = QVBoxLayout(self)
        outer.setContentsMargins(Spacing.LG, Spacing.LG, Spacing.LG, Spacing.LG)
        outer.setSpacing(Spacing.LG)

        # ── Title ────────────────────────────────────────────────────────
        title = QLabel("Settings")
        title.setStyleSheet(
            f"font-size: {FontSize.LG}px;"
            f"font-weight: 700;"
            f"color: {Colors.TEXT_PRIMARY};"
            f"border: none;"
            f"background: transparent;"
        )
        outer.addWidget(title)

        # ── Form Card ────────────────────────────────────────────────────
        card = QWidget()
        card.setObjectName("card")
        card.setStyleSheet(
            f"QWidget#card {{"
            f"  background-color: {Colors.BG_RAISED};"
            f"  border: 1px solid {Colors.BORDER_SUBTLE};"
            f"  border-radius: {Radius.LG};"
            f"  padding: {Spacing.BASE}px;"
            f"}}"
        )

        form = QFormLayout(card)
        form.setContentsMargins(Spacing.BASE, Spacing.BASE, Spacing.BASE, Spacing.BASE)
        form.setSpacing(Spacing.MD)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # ── HDL Library Path ─────────────────────────────────────────────
        path_label = QLabel("HDL Library Path:")
        path_label.setStyleSheet(
            f"font-size: {FontSize.SM}px;"
            f"color: {Colors.TEXT_PRIMARY};"
            f"border: none;"
            f"background: transparent;"
        )

        path_row = QHBoxLayout()
        path_row.setContentsMargins(0, 0, 0, 0)
        path_row.setSpacing(Spacing.SM)

        self._path_edit = QLineEdit()
        self._path_edit.setPlaceholderText("Select HDL component library root directory...")
        self._path_edit.setMinimumWidth(240)
        self._path_edit.setStyleSheet(
            f"QLineEdit {{"
            f"  background-color: {Colors.BG_BASE};"
            f"  border: 1px solid {Colors.BORDER_DEFAULT};"
            f"  border-radius: {Radius.MD};"
            f"  padding: {Spacing.SM}px {Spacing.MD}px;"
            f"  font-size: {FontSize.SM}px;"
            f"  color: {Colors.TEXT_PRIMARY};"
            f"}}"
            f"QLineEdit:focus {{"
            f"  border-color: {Colors.ACCENT};"
            f"}}"
        )

        browse_btn = QPushButton("Browse...")
        browse_btn.setObjectName("secondary")
        browse_btn.setStyleSheet(
            f"QPushButton#secondary {{"
            f"  background-color: {Colors.BG_OVERLAY};"
            f"  color: {Colors.ACCENT};"
            f"  border: 1px solid {Colors.ACCENT};"
            f"  border-radius: {Radius.MD};"
            f"  padding: {Spacing.SM}px {Spacing.BASE}px;"
            f"  font-size: {FontSize.SM}px;"
            f"  min-height: 32px;"
            f"}}"
            f"QPushButton#secondary:hover {{"
            f"  background-color: {rgba(Colors.ACCENT, 0.08)};"
            f"}}"
        )
        browse_btn.clicked.connect(self._on_browse)

        path_row.addWidget(self._path_edit, 1)
        path_row.addWidget(browse_btn)

        form.addRow(path_label, path_row)

        # ── Description ──────────────────────────────────────────────────
        desc = QLabel(
            "Set the root directory of your HDL component library.\n"
            "This is used by the component matching engine to find\n"
            "corresponding HDL parts for each CIS symbol."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(
            f"font-size: {FontSize.XS}px;"
            f"color: {Colors.TEXT_SECONDARY};"
            f"border: none;"
            f"background: transparent;"
            f"padding-top: {Spacing.XS}px;"
        )
        form.addRow("", desc)

        outer.addWidget(card)
        outer.addStretch()

        # ── Button Row ───────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.setSpacing(Spacing.SM)
        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("secondary")
        cancel_btn.setStyleSheet(
            f"QPushButton#secondary {{"
            f"  background-color: {Colors.BG_OVERLAY};"
            f"  color: {Colors.ACCENT};"
            f"  border: 1px solid {Colors.ACCENT};"
            f"  border-radius: {Radius.MD};"
            f"  padding: {Spacing.SM}px {Spacing.LG}px;"
            f"  font-size: {FontSize.SM}px;"
            f"  min-height: 32px;"
            f"}}"
            f"QPushButton#secondary:hover {{"
            f"  background-color: {rgba(Colors.ACCENT, 0.08)};"
            f"}}"
        )
        cancel_btn.clicked.connect(self.reject)

        save_btn = QPushButton("Save")
        save_btn.setObjectName("primary")
        save_btn.setStyleSheet(
            f"QPushButton#primary {{"
            f"  background-color: {Colors.ACCENT};"
            f"  color: {Colors.BG_OVERLAY};"
            f"  border: none;"
            f"  border-radius: {Radius.MD};"
            f"  padding: {Spacing.SM}px {Spacing.LG}px;"
            f"  font-size: {FontSize.SM}px;"
            f"  font-weight: bold;"
            f"  min-height: 32px;"
            f"}}"
            f"QPushButton#primary:hover {{"
            f"  background-color: {Colors.ACCENT_HOVER};"
            f"}}"
            f"QPushButton#primary:pressed {{"
            f"  background-color: {Colors.ACCENT_HOVER};"
            f"}}"
        )
        save_btn.clicked.connect(self._on_save)
        save_btn.setDefault(True)

        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)

        outer.addLayout(btn_row)

    def _apply_styles(self) -> None:
        """Apply the warm-beige Anthropic background to the dialog."""
        self.setStyleSheet(
            f"QDialog {{"
            f"  background-color: {Colors.BG_BASE};"
            f"}}"
        )

    # ── Config I/O ───────────────────────────────────────────────────────

    def _load_config(self) -> None:
        """Populate form fields from the current Config singleton."""
        current_path = cfg.hdl_lib.hdl_lib_path
        if current_path:
            self._path_edit.setText(current_path)

    def _save_config(self) -> None:
        """Persist form values back to the Config singleton."""
        new_path = self._path_edit.text().strip()
        cfg.hdl_lib.hdl_lib_path = new_path

    # ── Slot Handlers ────────────────────────────────────────────────────

    def _on_browse(self) -> None:
        """Open a directory chooser for the HDL library path."""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select HDL Component Library Root",
            self._path_edit.text() or "",
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks,
        )
        if directory:
            self._path_edit.setText(directory)

    def _on_save(self) -> None:
        """Save settings and close the dialog."""
        self._save_config()
        self.accept()
