"""Diff View Panel — CIS source vs HDL target comparison.

Displays a statistics comparison bar and a detailed difference table
using the Anthropic color token system with semantic colors.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..colors import Colors, FontSize, Radius, Spacing, rgba


# ── Diff Data Models ─────────────────────────────────────────────────────────


class DiffStatus(str, Enum):
    """Status of a single diff entry between CIS source and HDL target."""

    MATCH = "MATCH"          # ✅ Values match
    MISMATCH = "MISMATCH"    # ⚠️ Values differ
    MISSING = "MISSING"      # ❌ Present in source but missing in target
    EXTRA = "EXTRA"          # ➕ Present in target but not in source


@dataclass
class DiffEntry:
    """A single difference entry between CIS source and HDL target.

    Attributes:
        entry_type: Category of the diff (e.g., "Component", "Pin", "Net").
        cis_value: The value from the CIS source.
        hdl_value: The value from the HDL target.
        status: Whether values match, differ, or are missing.
    """

    entry_type: str
    cis_value: str
    hdl_value: str
    status: DiffStatus = DiffStatus.MATCH


@dataclass
class DiffStats:
    """Summary statistics for CIS vs HDL comparison.

    Attributes:
        cis_components: Number of components in CIS source.
        hdl_components: Number of components in HDL target.
        cis_pins: Number of pins in CIS source.
        hdl_pins: Number of pins in HDL target.
        cis_nets: Number of nets in CIS source.
        hdl_nets: Number of nets in HDL target.
    """

    cis_components: int = 0
    hdl_components: int = 0
    cis_pins: int = 0
    hdl_pins: int = 0
    cis_nets: int = 0
    hdl_nets: int = 0


# ── Diff View Panel ──────────────────────────────────────────────────────────


class DiffViewPanel(QWidget):
    """Panel displaying CIS → HDL diff with stats bar and detailed table.

    Layout:
      - Top: Statistics comparison bar (components, pins, nets)
      - Separator
      - Middle: Difference table (type, CIS value, HDL value, status)
    """

    STATUS_LABELS: dict[DiffStatus, str] = {
        DiffStatus.MATCH: "✅ 匹配",
        DiffStatus.MISMATCH: "⚠️ 差异",
        DiffStatus.MISSING: "❌ 缺失",
        DiffStatus.EXTRA: "➕ 多余",
    }

    STATUS_COLORS: dict[DiffStatus, str] = {
        DiffStatus.MATCH: Colors.SUCCESS,
        DiffStatus.MISMATCH: Colors.WARNING,
        DiffStatus.MISSING: Colors.ERROR,
        DiffStatus.EXTRA: Colors.INFO,
    }

    TABLE_COLUMNS: list[str] = ["类型", "CIS 值", "HDL 值", "状态"]

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the diff view panel.

        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self.setObjectName("card")
        self._stats: DiffStats = DiffStats()
        self._entries: list[DiffEntry] = []

        self._build_ui()
        self._apply_styles()

    # ── UI Construction ──────────────────────────────────────────────────

    def _build_ui(self) -> None:
        """Build the card-style diff panel layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            Spacing.BASE, Spacing.BASE, Spacing.BASE, Spacing.BASE
        )
        layout.setSpacing(Spacing.MD)

        # ── Header ────────────────────────────────────────────────────
        header = QLabel("CIS → HDL 差异对比")
        header.setStyleSheet(
            f"font-size: {FontSize.MD}px;"
            f"font-weight: 700;"
            f"color: {Colors.TEXT_PRIMARY};"
            f"border: none;"
            f"background: transparent;"
        )
        layout.addWidget(header)

        # ── Stats Comparison Bar ──────────────────────────────────────
        stats_row = QHBoxLayout()
        stats_row.setContentsMargins(0, 0, 0, 0)
        stats_row.setSpacing(Spacing.BASE)

        self._stat_components = self._make_stat_card("器件数")
        self._stat_pins = self._make_stat_card("引脚数")
        self._stat_nets = self._make_stat_card("网络数")

        stats_row.addWidget(self._stat_components)
        stats_row.addWidget(self._stat_pins)
        stats_row.addWidget(self._stat_nets)
        stats_row.addStretch()

        layout.addLayout(stats_row)

        # ── Separator ─────────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {Colors.BORDER_SUBTLE};")
        sep.setFixedHeight(1)
        layout.addWidget(sep)

        # ── Diff Table ────────────────────────────────────────────────
        self._table = QTableWidget(0, len(self.TABLE_COLUMNS))
        self._table.setHorizontalHeaderLabels(self.TABLE_COLUMNS)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self._table.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection
        )
        self._table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self._table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        self._table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.ResizeToContents
        )

        layout.addWidget(self._table, 1)

        # ── Summary Footer ────────────────────────────────────────────
        self._summary_label = QLabel("未加载差异数据 — 请先运行转换")
        self._summary_label.setStyleSheet(
            f"font-size: {FontSize.XS}px;"
            f"color: {Colors.TEXT_SECONDARY};"
            f"border: none;"
            f"background: transparent;"
            f"padding: {Spacing.XS}px {Spacing.SM}px;"
        )
        layout.addWidget(self._summary_label)

    def _make_stat_card(self, label: str) -> QWidget:
        """Create a comparison stat card showing CIS → HDL values.

        Args:
            label: The stat category label (e.g., "器件数").

        Returns:
            A QWidget card with before/after values.
        """
        card = QWidget()
        card.setMinimumWidth(160)
        card.setStyleSheet(
            f"QWidget {{"
            f"  background-color: {Colors.BG_BASE};"
            f"  border: 1px solid {Colors.BORDER_SUBTLE};"
            f"  border-radius: {Radius.MD};"
            f"  padding: {Spacing.SM}px {Spacing.MD}px;"
            f"}}"
        )

        inner = QVBoxLayout(card)
        inner.setContentsMargins(0, 0, 0, 0)
        inner.setSpacing(4)

        # Title
        title_lbl = QLabel(label)
        title_lbl.setStyleSheet(
            f"font-size: {FontSize.XXS}px;"
            f"color: {Colors.TEXT_MUTED};"
            f"border: none;"
            f"background: transparent;"
        )
        inner.addWidget(title_lbl, alignment=Qt.AlignmentFlag.AlignLeft)

        # Values row: CIS → HDL
        values_row = QHBoxLayout()
        values_row.setContentsMargins(0, 0, 0, 0)
        values_row.setSpacing(Spacing.XS)

        cis_val = QLabel("—")
        cis_val.setStyleSheet(
            f"font-size: {FontSize.LG}px;"
            f"font-weight: 700;"
            f"color: {Colors.AUX_BLUE};"
            f"border: none;"
            f"background: transparent;"
        )
        values_row.addWidget(cis_val)

        arrow = QLabel("→")
        arrow.setStyleSheet(
            f"font-size: {FontSize.SM}px;"
            f"color: {Colors.TEXT_MUTED};"
            f"border: none;"
            f"background: transparent;"
        )
        values_row.addWidget(arrow)

        hdl_val = QLabel("—")
        hdl_val.setStyleSheet(
            f"font-size: {FontSize.LG}px;"
            f"font-weight: 700;"
            f"color: {Colors.AUX_GREEN};"
            f"border: none;"
            f"background: transparent;"
        )
        values_row.addWidget(hdl_val)

        values_row.addStretch()
        inner.addLayout(values_row)

        # Store references for updates
        card._cis_label = cis_val
        card._hdl_label = hdl_val

        return card

    # ── Styling ───────────────────────────────────────────────────────────

    def _apply_styles(self) -> None:
        """Apply Anthropic card and table styling."""
        self.setStyleSheet(
            f"QWidget#card {{"
            f"  background-color: {Colors.BG_RAISED};"
            f"  border: 1px solid {Colors.BORDER_SUBTLE};"
            f"  border-radius: {Radius.LG};"
            f"}}"
        )
        self._table.setStyleSheet(
            f"QTableWidget {{"
            f"  font-size: {FontSize.XS}px;"
            f"  background-color: {Colors.BG_BASE};"
            f"  border: 1px solid {Colors.BORDER_SUBTLE};"
            f"  border-radius: {Radius.MD};"
            f"  color: {Colors.TEXT_PRIMARY};"
            f"  gridline-color: {Colors.BORDER_SUBTLE};"
            f"}}"
            f"QTableWidget::item {{"
            f"  padding: 4px 8px;"
            f"}}"
            f"QTableWidget::item:selected {{"
            f"  background-color: {rgba(Colors.ACCENT, 0.15)};"
            f"}}"
            f"QTableWidget {{"
            f"  alternate-background-color: {rgba(Colors.BG_BASE, 0.5)};"
            f"}}"
            f"QHeaderView::section {{"
            f"  background-color: {Colors.BG_BASE};"
            f"  border: none;"
            f"  border-bottom: 1px solid {Colors.BORDER_SUBTLE};"
            f"  padding: 6px 8px;"
            f"  font-size: {FontSize.XXS}px;"
            f"  font-weight: 600;"
            f"  color: {Colors.TEXT_SECONDARY};"
            f"}}"
        )

    # ── Public API ────────────────────────────────────────────────────────

    def set_diff_data(
        self,
        stats: DiffStats,
        entries: list[DiffEntry],
    ) -> None:
        """Populate the diff panel with comparison data.

        Args:
            stats: Summary statistics for the comparison bar.
            entries: List of individual DiffEntry items for the table.
        """
        self._stats = stats
        self._entries = entries

        # Update stat cards
        self._update_stat_card(
            self._stat_components, stats.cis_components, stats.hdl_components
        )
        self._update_stat_card(
            self._stat_pins, stats.cis_pins, stats.hdl_pins
        )
        self._update_stat_card(
            self._stat_nets, stats.cis_nets, stats.hdl_nets
        )

        # Populate table
        self._populate_table(entries)

        # Update summary
        match_count = sum(
            1 for e in entries if e.status == DiffStatus.MATCH
        )
        mismatch_count = sum(
            1 for e in entries if e.status == DiffStatus.MISMATCH
        )
        missing_count = sum(
            1 for e in entries if e.status == DiffStatus.MISSING
        )
        extra_count = sum(
            1 for e in entries if e.status == DiffStatus.EXTRA
        )

        total = len(entries)
        if total == 0:
            self._summary_label.setText("无差异数据")
        else:
            match_rate = match_count / total * 100 if total > 0 else 0.0
            self._summary_label.setText(
                f"共 {total} 项  |  "
                f"✅ 匹配: {match_count} ({match_rate:.1f}%)  |  "
                f"⚠️ 差异: {mismatch_count}  |  "
                f"❌ 缺失: {missing_count}  |  "
                f"➕ 多余: {extra_count}"
            )

    def clear(self) -> None:
        """Clear all diff data and reset the panel."""
        self._stats = DiffStats()
        self._entries = []
        self._table.setRowCount(0)

        # Reset all stat cards
        for card in [
            self._stat_components,
            self._stat_pins,
            self._stat_nets,
        ]:
            if hasattr(card, "_cis_label"):
                card._cis_label.setText("—")
            if hasattr(card, "_hdl_label"):
                card._hdl_label.setText("—")

        self._summary_label.setText("未加载差异数据 — 请先运行转换")

    # ── Internal Helpers ──────────────────────────────────────────────────

    def _update_stat_card(
        self,
        card: QWidget,
        cis_value: int,
        hdl_value: int,
    ) -> None:
        """Update a stat comparison card with new values.

        Args:
            card: The stat card widget.
            cis_value: CIS source value.
            hdl_value: HDL target value.
        """
        if hasattr(card, "_cis_label"):
            card._cis_label.setText(str(cis_value))
        if hasattr(card, "_hdl_label"):
            card._hdl_label.setText(str(hdl_value))

    def _populate_table(self, entries: list[DiffEntry]) -> None:
        """Fill the difference table with entries.

        Args:
            entries: List of DiffEntry items to display.
        """
        self._table.setRowCount(len(entries))

        for row, entry in enumerate(entries):
            # Type column
            type_item = QTableWidgetItem(entry.entry_type)
            type_item.setTextAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )
            self._table.setItem(row, 0, type_item)

            # CIS value column
            cis_item = QTableWidgetItem(entry.cis_value)
            cis_item.setTextAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )
            self._table.setItem(row, 1, cis_item)

            # HDL value column
            hdl_item = QTableWidgetItem(entry.hdl_value)
            hdl_item.setTextAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )
            self._table.setItem(row, 2, hdl_item)

            # Status column
            status_text = self.STATUS_LABELS.get(entry.status, "未知")
            status_item = QTableWidgetItem(status_text)
            status_item.setTextAlignment(
                Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
            )

            # Apply semantic color
            status_color = self.STATUS_COLORS.get(
                entry.status, Colors.TEXT_SECONDARY
            )
            status_item.setForeground(QColor(status_color))
            font = status_item.font()
            font.setBold(True)
            status_item.setFont(font)

            self._table.setItem(row, 3, status_item)

            # Row height
            self._table.setRowHeight(row, 32)
