"""Rules Panel — view and manage imported/confirmed mapping rules.

Displays all active CIS → HDL mapping rules in a QTableWidget with
support for viewing details and deleting individual rules.

Reference: ROADMAP F3.4.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..colors import Colors, FontSize, Radius, Spacing, STYLE_CARD, STYLE_BUTTON_PRIMARY


# ── Data model for a single mapping rule ─────────────────────────────────────


@dataclass
class MappingRule:
    """A single CIS → HDL mapping rule entry.

    Attributes:
        source_id: CIS component library ID.
        target_id: HDL component library ID.
        strategy: Matching strategy used (EXACT, FUZZY, FEATURE, MANUAL).
        confidence: Match confidence (0.0 – 1.0).
        pin_count: Number of pins mapped (0 if unknown).
    """

    source_id: str
    target_id: str
    strategy: str = ""
    confidence: float = 0.0
    pin_count: int = 0


# ── Rules Panel Widget ───────────────────────────────────────────────────────


class RulesPanel(QWidget):
    """Panel displaying mapped/confirmed CIS → HDL rules in a table.

    Signals:
        rule_deleted(source_id: str): Emitted when a rule is deleted by the user.

    Usage::

        panel = RulesPanel()
        panel.set_rules([
            MappingRule("CAP_0805", "Capacitor_0805", "EXACT", 0.98),
        ])
    """

    rule_deleted = Signal(str)
    """Emitted when a user deletes a rule. Carries the source_library_id."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("rules_panel")
        self.setStyleSheet(STYLE_CARD)

        self._rules: list[MappingRule] = []
        self._build_ui()

    # ── UI construction ──────────────────────────────────────────────────

    def _build_ui(self) -> None:
        """Build the panel layout: header bar + table."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Spacing.BASE, Spacing.BASE, Spacing.BASE, Spacing.BASE)
        layout.setSpacing(Spacing.MD)

        # ── Header ──────────────────────────────────────────────────
        header_layout = QHBoxLayout()

        title = QLabel("映射规则管理")
        title.setStyleSheet(
            f"font-size: {FontSize.MD}px; font-weight: 700; "
            f"color: {Colors.TEXT_PRIMARY};"
        )
        header_layout.addWidget(title)

        header_layout.addStretch()

        self._count_label = QLabel("0 条规则")
        self._count_label.setStyleSheet(
            f"font-size: {FontSize.XS}px; color: {Colors.TEXT_SECONDARY};"
        )
        header_layout.addWidget(self._count_label)

        # Delete selected button
        self._delete_btn = QPushButton("删除选中")
        self._delete_btn.setObjectName("danger")
        self._delete_btn.setStyleSheet(_danger_button_style())
        self._delete_btn.setEnabled(False)
        self._delete_btn.clicked.connect(self._on_delete_selected)
        header_layout.addWidget(self._delete_btn)

        layout.addLayout(header_layout)

        # ── Table ────────────────────────────────────────────────────
        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels([
            "CIS 组件 ID", "HDL 组件 ID", "策略", "置信度", "引脚数",
        ])
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self._table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(False)

        # Style the table
        self._table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {Colors.BG_RAISED};
                border: 1px solid {Colors.BORDER_SUBTLE};
                border-radius: {Radius.LG};
                font-size: {FontSize.SM}px;
                color: {Colors.TEXT_PRIMARY};
                gridline-color: transparent;
            }}
            QTableWidget::item {{
                padding: 8px 12px;
                border-bottom: 1px solid {Colors.BORDER_SUBTLE};
            }}
            QTableWidget::item:selected {{
                background-color: rgba(217, 119, 87, 0.12);
                color: {Colors.TEXT_PRIMARY};
            }}
            QHeaderView::section {{
                background-color: {Colors.BG_RAISED};
                color: {Colors.TEXT_SECONDARY};
                font-size: {FontSize.XS}px;
                font-weight: 600;
                padding: 8px 12px;
                border: none;
                border-bottom: 1px solid {Colors.BORDER_DEFAULT};
            }}
        """)

        self._table.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self._table, 1)  # stretch=1

    # ── Public API ────────────────────────────────────────────────────────

    def set_rules(self, rules: list[MappingRule]) -> None:
        """Replace all rules in the table.

        Args:
            rules: List of MappingRule entries to display.
        """
        self._rules = list(rules)
        self._rebuild_table()

    def add_rule(self, rule: MappingRule) -> None:
        """Append a single rule to the table.

        Args:
            rule: The MappingRule to add.
        """
        self._rules.append(rule)
        self._rebuild_table()

    def delete_rule(self, source_id: str) -> bool:
        """Delete a rule by its source library ID.

        Args:
            source_id: The CIS component library ID to remove.

        Returns:
            True if the rule was found and removed.
        """
        for i, rule in enumerate(self._rules):
            if rule.source_id == source_id:
                self._rules.pop(i)
                self._rebuild_table()
                return True
        return False

    def rule_count(self) -> int:
        """Return the number of rules currently displayed."""
        return len(self._rules)

    def has_rules(self) -> bool:
        """Return True if there are any rules to display."""
        return len(self._rules) > 0

    def rules(self) -> list[MappingRule]:
        """Return a copy of the current rules list."""
        return list(self._rules)

    # ── Internal helpers ──────────────────────────────────────────────────

    def _rebuild_table(self) -> None:
        """Rebuild the table from self._rules."""
        self._table.setRowCount(0)
        self._table.setRowCount(len(self._rules))

        for row, rule in enumerate(self._rules):
            # Source ID
            src_item = QTableWidgetItem(rule.source_id)
            src_item.setData(Qt.ItemDataRole.UserRole, rule.source_id)
            self._table.setItem(row, 0, src_item)

            # Target ID
            tgt_item = QTableWidgetItem(rule.target_id)
            self._table.setItem(row, 1, tgt_item)

            # Strategy
            strategy_text = _strategy_label(rule.strategy)
            strategy_item = QTableWidgetItem(strategy_text)
            strategy_item.setForeground(_strategy_color(rule.strategy))
            self._table.setItem(row, 2, strategy_item)

            # Confidence
            conf_pct = int(rule.confidence * 100)
            conf_item = QTableWidgetItem(f"{conf_pct}%")
            conf_color = _confidence_color(rule.confidence)
            conf_item.setForeground(conf_color)
            self._table.setItem(row, 3, conf_item)

            # Pin count
            pin_item = QTableWidgetItem(
                str(rule.pin_count) if rule.pin_count > 0 else "—"
            )
            pin_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, 4, pin_item)

        self._count_label.setText(f"{len(self._rules)} 条规则")
        self._delete_btn.setEnabled(len(self._rules) > 0)

    def _on_selection_changed(self) -> None:
        """Enable/disable delete button based on selection."""
        self._delete_btn.setEnabled(
            len(self._table.selectedItems()) > 0
        )

    def _on_delete_selected(self) -> None:
        """Delete the currently selected rule after user confirmation."""
        selected_rows = set()
        for item in self._table.selectedItems():
            selected_rows.add(item.row())

        if not selected_rows:
            return

        # Only handle single selection
        row = next(iter(selected_rows))
        source_item = self._table.item(row, 0)
        if source_item is None:
            return

        source_id = source_item.data(Qt.ItemDataRole.UserRole)
        target_item = self._table.item(row, 1)
        target_id = target_item.text() if target_item else "?"

        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除映射规则吗？\n\n"
            f"CIS: {source_id}\n"
            f"HDL: {target_id}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            if self.delete_rule(source_id):
                self.rule_deleted.emit(source_id)


# ── Style helpers ────────────────────────────────────────────────────────────


def _danger_button_style() -> str:
    """Return the QSS style string for the danger (delete) button."""
    return f"""
        QPushButton#danger {{
            background-color: {Colors.ERROR};
            color: {Colors.BG_OVERLAY};
            border: none;
            border-radius: {Radius.MD};
            padding: {Spacing.SM}px {Spacing.BASE}px;
            font-size: {FontSize.SM}px;
            font-weight: 600;
        }}
        QPushButton#danger:hover {{
            background-color: #A83830;
        }}
        QPushButton#danger:disabled {{
            background-color: {Colors.BORDER_SUBTLE};
            color: {Colors.TEXT_MUTED};
        }}
    """


def _strategy_label(strategy: str) -> str:
    """Return a human-readable label for a match strategy."""
    labels: dict[str, str] = {
        "EXACT": "精确匹配",
        "FUZZY": "模糊匹配",
        "FEATURE": "特征匹配",
        "MANUAL": "手动确认",
    }
    return labels.get(strategy.upper(), strategy)


def _strategy_color(strategy: str) -> str:
    """Return a QColor for a match strategy."""
    colors: dict[str, str] = {
        "EXACT": Colors.SUCCESS,
        "FUZZY": Colors.INFO,
        "FEATURE": Colors.WARNING,
        "MANUAL": Colors.ACCENT,
    }
    return colors.get(strategy.upper(), Colors.TEXT_SECONDARY)


def _confidence_color(confidence: float) -> str:
    """Return a QColor for a confidence score."""
    if confidence >= 0.90:
        return Colors.SUCCESS
    elif confidence >= 0.75:
        return Colors.INFO
    elif confidence >= 0.60:
        return Colors.WARNING
    elif confidence > 0.0:
        return Colors.ERROR
    else:
        return Colors.TEXT_MUTED
