"""ErrorDiagnosticPanel — error code classification tree with recovery suggestions.

Displays diagnosis errors in a four-level severity tree (FATAL/ERROR/WARNING/INFO),
shows fix suggestions per error, and provides an "Ignore and Continue" button.

Reference: ROADMAP F2.8.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
    QTextEdit,
)

from ..colors import (
    Colors,
    FontSize,
    Radius,
    Spacing,
    STYLE_CARD,
    rgba,
)
from ...core.diagnostics.diagnostic_report import DiagnosisError, Severity


class ErrorDiagnosticPanel(QWidget):
    """Panel displaying diagnosis errors in a structured tree with severity coloring.

    Groups errors by severity into a four-level tree:
      - FATAL (red) — blocks conversion
      - ERROR (orange) — recoverable issues
      - WARNING (yellow) — advisory
      - INFO (blue) — informational

    Each error node shows its code, message, and suggestion.
    An "Ignore and Continue" button allows bypassing non-fatal errors.

    Signals:
        ignore_requested: Emitted when user clicks "Ignore and Continue".
    """

    #: Emitted when user requests to ignore errors and continue
    ignore_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self.setStyleSheet(STYLE_CARD)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Spacing.SM)

        # ── Header ────────────────────────────────────────────────────
        header_row = QHBoxLayout()
        header = QLabel("Error Diagnostics")
        header.setStyleSheet(
            f"font-size: {FontSize.SM}px; font-weight: 600; "
            f"color: {Colors.TEXT_PRIMARY}; border: none; background: transparent;"
        )
        header_row.addWidget(header)
        header_row.addStretch()

        self._summary_label = QLabel("No errors")
        self._summary_label.setStyleSheet(
            f"font-size: {FontSize.XS}px; color: {Colors.TEXT_SECONDARY}; "
            f"border: none; background: transparent;"
        )
        header_row.addWidget(self._summary_label)
        layout.addLayout(header_row)

        # ── Error tree ────────────────────────────────────────────────
        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Code", "Severity", "Category", "Message"])
        self._tree.setColumnWidth(0, 50)
        self._tree.setColumnWidth(1, 70)
        self._tree.setColumnWidth(2, 80)
        self._tree.setColumnWidth(3, 300)
        self._tree.setAlternatingRowColors(False)
        self._tree.setStyleSheet(
            f"QTreeWidget {{"
            f"  font-size: {FontSize.XS}px;"
            f"  background-color: {Colors.BG_RAISED};"
            f"  border: 1px solid {Colors.BORDER_SUBTLE};"
            f"  border-radius: {Radius.MD};"
            f"  color: {Colors.TEXT_PRIMARY};"
            f"}}"
            f"QTreeWidget::item:selected {{"
            f"  background-color: {rgba(Colors.ACCENT, 0.12)};"
            f"}}"
        )
        self._tree.currentItemChanged.connect(self._on_item_selected)
        layout.addWidget(self._tree, 1)

        # ── Detail / suggestion area ──────────────────────────────────
        self._suggestion_label = QTextEdit()
        self._suggestion_label.setReadOnly(True)
        self._suggestion_label.setMaximumHeight(80)
        self._suggestion_label.setStyleSheet(
            f"QTextEdit {{"
            f"  font-size: {FontSize.XS}px;"
            f"  background-color: {Colors.BG_BASE};"
            f"  border: 1px solid {Colors.BORDER_SUBTLE};"
            f"  border-radius: {Radius.MD};"
            f"  padding: {Spacing.SM}px;"
            f"  color: {Colors.TEXT_PRIMARY};"
            f"}}"
        )
        self._suggestion_label.setPlaceholderText("Select an error to see details and fix suggestions...")
        layout.addWidget(self._suggestion_label)

        # ── Action row ────────────────────────────────────────────────
        action_row = QHBoxLayout()
        action_row.setContentsMargins(0, 0, 0, 0)

        self._ignore_btn = QPushButton("Ignore and Continue")
        self._ignore_btn.setObjectName("secondary")
        self._ignore_btn.setStyleSheet(
            f"QPushButton#secondary {{"
            f"  background-color: {Colors.BG_OVERLAY};"
            f"  color: {Colors.WARNING};"
            f"  border: 1px solid {Colors.WARNING};"
            f"  border-radius: {Radius.MD};"
            f"  padding: {Spacing.SM}px {Spacing.LG}px;"
            f"  font-size: {FontSize.SM}px;"
            f"  min-height: 32px;"
            f"}}"
            f"QPushButton#secondary:hover {{"
            f"  background-color: {rgba(Colors.WARNING, 0.10)};"
            f"}}"
        )
        self._ignore_btn.clicked.connect(self.ignore_requested.emit)
        self._ignore_btn.setVisible(False)

        action_row.addStretch()
        action_row.addWidget(self._ignore_btn)
        layout.addLayout(action_row)

        # State
        self._errors: list[DiagnosisError] = []
        self._has_fatal: bool = False

    # ── Public API ───────────────────────────────────────────────────

    def set_errors(self, errors: list[DiagnosisError]) -> None:
        """Populate the error tree with a list of diagnosis errors.

        Args:
            errors: List of DiagnosisError entries to display.
        """
        self._errors = errors
        self._has_fatal = any(e.severity == Severity.FATAL for e in errors)
        self._rebuild_tree()

        # Update summary
        fatal = sum(1 for e in errors if e.severity == Severity.FATAL)
        err = sum(1 for e in errors if e.severity == Severity.ERROR)
        warn = sum(1 for e in errors if e.severity == Severity.WARNING)
        info = sum(1 for e in errors if e.severity == Severity.INFO)
        self._summary_label.setText(
            f"F:{fatal} E:{err} W:{warn} I:{info}"
        )

        # Show "Ignore" button only for non-fatal errors
        self._ignore_btn.setVisible(not self._has_fatal and len(errors) > 0)

    def clear(self) -> None:
        """Clear all error entries."""
        self._tree.clear()
        self._errors.clear()
        self._suggestion_label.clear()
        self._summary_label.setText("No errors")
        self._ignore_btn.setVisible(False)

    # ── Internals ────────────────────────────────────────────────────

    def _rebuild_tree(self) -> None:
        """Rebuild the tree widget with severity-grouped error items."""
        self._tree.clear()

        # Group by severity
        groups: dict[Severity, list[DiagnosisError]] = {
            Severity.FATAL: [],
            Severity.ERROR: [],
            Severity.WARNING: [],
            Severity.INFO: [],
        }
        for err in self._errors:
            groups.setdefault(err.severity, []).append(err)

        # Add severity groups as top-level items
        severity_config = [
            (Severity.FATAL, "🔴 FATAL", Colors.ERROR),
            (Severity.ERROR, "🟠 ERROR", Colors.WARNING),
            (Severity.WARNING, "🟡 WARNING", Colors.WARNING),
            (Severity.INFO, "🔵 INFO", Colors.INFO),
        ]

        for severity, label, color in severity_config:
            group_errors = groups.get(severity, [])
            if not group_errors:
                continue

            parent = QTreeWidgetItem(self._tree)
            parent.setText(0, "")
            parent.setText(1, label)
            parent.setText(2, f"{len(group_errors)} items")
            parent.setText(3, "")
            parent.setForeground(1, Qt.GlobalColor.black)
            parent.setExpanded(True)

            # Style the parent row
            for col in range(4):
                parent.setBackground(col, Qt.GlobalColor.transparent)

            for err in group_errors:
                child = QTreeWidgetItem(parent)
                child.setText(0, f"E{err.code:02d}")
                child.setText(1, err.severity.name)
                child.setText(2, err.category)
                child.setText(3, err.message)

                # Store error data for selection
                child.setData(0, Qt.ItemDataRole.UserRole, err)

                # Color code by severity
                from PySide6.QtGui import QColor
                severity_color = QColor(color)
                for col in range(4):
                    child.setForeground(col, severity_color)

        self._tree.expandAll()

    def _on_item_selected(self, current: QTreeWidgetItem, _previous: QTreeWidgetItem | None) -> None:
        """Display suggestion text when an error item is selected."""
        if current is None:
            self._suggestion_label.clear()
            return

        err = current.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(err, DiagnosisError):
            lines = [
                f"Error E{err.code:02d}: {err.message}",
                f"Category: {err.category}  |  Severity: {err.severity.name}",
            ]
            if err.detail:
                lines.append(f"\nDetail: {err.detail}")
            if err.suggestion:
                lines.append(f"\n💡 Suggestion: {err.suggestion}")
            if err.source_file:
                lines.append(f"\nSource: {err.source_file}")
            self._suggestion_label.setPlainText("\n".join(lines))
        else:
            self._suggestion_label.clear()
