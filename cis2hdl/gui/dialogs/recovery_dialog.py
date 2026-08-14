"""RecoveryStrategyDialog — file recovery path selection dialog.

When file issues are detected (corrupt DSN, missing OLB, etc.), this dialog
presents the available recovery paths sorted by data loss level, with the
recommended strategy highlighted. The user can select a path with one click.

Reference: ROADMAP F2.9.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..colors import (
    Colors,
    FontSize,
    Radius,
    Spacing,
    rgba,
)
from ...core.diagnostics.recovery import (
    DataLossLevel,
    RecoveryPath,
    FileRecoveryStrategy,
)
from ...core.diagnostics.diagnostic_report import ProjectInventory


# ── Data loss level display config ──────────────────────────────────────

DATA_LOSS_LABELS: dict[DataLossLevel, str] = {
    DataLossLevel.NONE: "无数据损失",
    DataLossLevel.COORDINATES: "坐标丢失",
    DataLossLevel.PARTIAL_PAGES: "部分页面丢失",
    DataLossLevel.SYMBOL_FIDELITY: "符号保真度降低",
    DataLossLevel.GRAPHICS: "图形全丢失",
}

DATA_LOSS_COLORS: dict[DataLossLevel, str] = {
    DataLossLevel.NONE: Colors.SUCCESS,
    DataLossLevel.COORDINATES: Colors.AUX_BLUE,
    DataLossLevel.PARTIAL_PAGES: Colors.WARNING,
    DataLossLevel.SYMBOL_FIDELITY: Colors.WARNING,
    DataLossLevel.GRAPHICS: Colors.ERROR,
}


class RecoveryStrategyDialog(QDialog):
    """Dialog for selecting a file recovery strategy.

    Shows a list of applicable recovery paths with:
      - Data loss level indicator (color-coded)
      - Quality impact description
      - Recommended path highlighted at the top
      - One-click selection with "Apply" button

    Usage:
        strategy = FileRecoveryStrategy()
        paths = strategy.evaluate(inventory)
        recommended = strategy.recommend(paths)

        dialog = RecoveryStrategyDialog(paths, recommended)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            chosen_path = dialog.selected_path
    """

    WINDOW_TITLE = "File Recovery — Select Strategy"
    MIN_WIDTH = 580
    MIN_HEIGHT = 420

    def __init__(
        self,
        recovery_paths: list[RecoveryPath],
        recommended: RecoveryPath | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Initialize the recovery strategy dialog.

        Args:
            recovery_paths: List of applicable RecoveryPath entries from
                            FileRecoveryStrategy.evaluate().
            recommended: The recommended (best) recovery path.
            parent: Parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle(self.WINDOW_TITLE)
        self.setMinimumSize(self.MIN_WIDTH, self.MIN_HEIGHT)
        self.setModal(True)

        self._paths = recovery_paths
        self._recommended = recommended
        self._selected_path: RecoveryPath | None = None

        self._build_ui()
        self._apply_styles()

        # Pre-select the recommended path
        if recommended and recommended in recovery_paths:
            idx = recovery_paths.index(recommended)
            self._path_list.setCurrentRow(idx)

    # ── Public properties ────────────────────────────────────────────

    @property
    def selected_path(self) -> RecoveryPath | None:
        """The recovery path the user selected."""
        return self._selected_path

    # ── UI Construction ──────────────────────────────────────────────

    def _build_ui(self) -> None:
        """Build the warm-beige Anthropic dialog layout."""
        outer = QVBoxLayout(self)
        outer.setContentsMargins(Spacing.LG, Spacing.LG, Spacing.LG, Spacing.LG)
        outer.setSpacing(Spacing.LG)

        # ── Header ────────────────────────────────────────────────────
        header_row = QHBoxLayout()

        title = QLabel("File Recovery Required")
        title.setStyleSheet(
            f"font-size: {FontSize.LG}px; font-weight: 700; "
            f"color: {Colors.ERROR}; border: none; background: transparent;"
        )
        header_row.addWidget(title)
        header_row.addStretch()

        warning_icon = QLabel("⚠️")
        warning_icon.setStyleSheet(
            f"font-size: {FontSize.LG}px; color: {Colors.WARNING}; "
            f"border: none; background: transparent;"
        )
        header_row.addWidget(warning_icon)

        outer.addLayout(header_row)

        # ── Explanation ───────────────────────────────────────────────
        explanation = QLabel(
            "One or more input files have issues that affect conversion quality. "
            "Please select a recovery strategy below. The recommended option "
            "minimizes data loss."
        )
        explanation.setWordWrap(True)
        explanation.setStyleSheet(
            f"font-size: {FontSize.SM}px; color: {Colors.TEXT_SECONDARY}; "
            f"border: none; background: transparent; padding-bottom: {Spacing.XS}px;"
        )
        outer.addWidget(explanation)

        # ── Recovery Paths List ───────────────────────────────────────
        self._path_list = QListWidget()
        self._path_list.setStyleSheet(
            f"QListWidget {{"
            f"  font-size: {FontSize.SM}px;"
            f"  background-color: {Colors.BG_BASE};"
            f"  border: 1px solid {Colors.BORDER_DEFAULT};"
            f"  border-radius: {Radius.LG};"
            f"  padding: {Spacing.XS}px;"
            f"  color: {Colors.TEXT_PRIMARY};"
            f"}}"
            f"QListWidget::item {{"
            f"  padding: {Spacing.SM}px {Spacing.MD}px;"
            f"  border-bottom: 1px solid {Colors.BORDER_SUBTLE};"
            f"}}"
            f"QListWidget::item:selected {{"
            f"  background-color: {rgba(Colors.ACCENT, 0.12)};"
            f"  color: {Colors.TEXT_PRIMARY};"
            f"}}"
        )
        self._path_list.currentItemChanged.connect(self._on_path_selected)

        for path in self._paths:
            is_recommended = (self._recommended is not None and path.id == self._recommended.id)
            prefix = "⭐ " if is_recommended else "   "
            loss_label = DATA_LOSS_LABELS.get(path.data_loss, str(path.data_loss))
            display = f"{prefix}{path.action}  [{loss_label}]"

            item = QListWidgetItem(display)
            item.setData(Qt.ItemDataRole.UserRole, path)

            # Color-code by data loss level
            loss_color = DATA_LOSS_COLORS.get(path.data_loss, Colors.TEXT_SECONDARY)
            self._path_list.addItem(item)

        outer.addWidget(self._path_list, 1)

        # ── Detail area ───────────────────────────────────────────────
        self._detail_label = QLabel("Select a recovery path to see details")
        self._detail_label.setWordWrap(True)
        self._detail_label.setStyleSheet(
            f"font-size: {FontSize.XS}px; color: {Colors.TEXT_SECONDARY}; "
            f"padding: {Spacing.SM}px {Spacing.MD}px; "
            f"background-color: {rgba(Colors.ACCENT, 0.05)}; "
            f"border-radius: {Radius.MD}; border: none;"
        )
        outer.addWidget(self._detail_label)

        # ── Button Row ────────────────────────────────────────────────
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

        apply_btn = QPushButton("Apply Selected Strategy")
        apply_btn.setObjectName("primary")
        apply_btn.setStyleSheet(
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
        )
        apply_btn.clicked.connect(self._on_apply)
        apply_btn.setDefault(True)

        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(apply_btn)

        outer.addLayout(btn_row)

    def _apply_styles(self) -> None:
        """Apply warm-beige Anthropic style to the dialog."""
        self.setStyleSheet(
            f"QDialog {{ background-color: {Colors.BG_BASE}; }}"
        )

    # ── Slot Handlers ────────────────────────────────────────────────

    def _on_path_selected(self, current: QListWidgetItem, previous: QListWidgetItem | None) -> None:
        """Update detail text when user selects a recovery path."""
        if current is None:
            self._detail_label.setText("Select a recovery path to see details")
            return

        path = current.data(Qt.ItemDataRole.UserRole)
        if not isinstance(path, RecoveryPath):
            return

        loss_label = DATA_LOSS_LABELS.get(path.data_loss, str(path.data_loss))
        detail = (
            f"Strategy: {path.action}\n"
            f"Data Loss: {loss_label}\n"
            f"Quality Impact: {path.quality_impact}"
        )
        self._detail_label.setText(detail)

    def _on_apply(self) -> None:
        """Accept the dialog with the currently selected path."""
        current = self._path_list.currentItem()
        if current:
            path = current.data(Qt.ItemDataRole.UserRole)
            if isinstance(path, RecoveryPath):
                self._selected_path = path
        self.accept()
