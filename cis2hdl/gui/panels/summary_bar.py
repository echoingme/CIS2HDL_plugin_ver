"""Summary Bar — metric card row showing file/page/component/match counts."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
    QSizePolicy,
)

from ..colors import (
    Colors,
    Radius,
    FontSize,
    Spacing,
    Layout,
)


@dataclass
class MetricsSnapshot:
    """Immutable snapshot of project metrics for the Summary Bar.

    Encapsulates all values needed to update the four metric cards
    (Files, Pages, Components, Match Rate) in a single call.
    """

    files_total: int = 0
    files_ok: int = 0
    pages_total: int = 0
    pages_parsed: int = 0
    comps_total: int = 0
    match_rate: float | None = None


class SummaryBar(QWidget):
    """Horizontal row of metric cards summarizing project state.

    Displays four cards: Files, Pages, Components, Match Rate.
    Each card shows a colored indicator dot, a large value, and a label with status.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("summary_bar")
        self.setFixedHeight(Layout.SUMMARY_BAR_H)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Spacing.BASE)

        # ── Create four metric cards ─────────────────────────────────
        self._card_files = _MetricCard(
            label="Files",
            indicator_color=Colors.ACCENT,
            parent=self,
        )
        self._card_pages = _MetricCard(
            label="Pages",
            indicator_color=Colors.AUX_BLUE,
            parent=self,
        )
        self._card_comps = _MetricCard(
            label="Components",
            indicator_color=Colors.WARNING,
            parent=self,
        )
        self._card_match = _MetricCard(
            label="Match",
            indicator_color=Colors.ACCENT_MUTED,
            parent=self,
        )

        layout.addWidget(self._card_files)
        layout.addWidget(self._card_pages)
        layout.addWidget(self._card_comps)
        layout.addWidget(self._card_match)

        # Initialize with defaults
        self.set_match_na()

    def update_metrics(self, metrics: MetricsSnapshot) -> None:
        """Batch-update all metric card values from a MetricsSnapshot.

        Args:
            metrics: Snapshot containing file/page/component/match counts.
        """
        self._card_files.set_value(str(metrics.files_total))
        self._card_files.set_status(f"{metrics.files_ok} found")

        self._card_pages.set_value(str(metrics.pages_total))
        self._card_pages.set_status(f"{metrics.pages_parsed} parsed")

        self._card_comps.set_value(str(metrics.comps_total))
        self._card_comps.set_status(f"{metrics.comps_total} detected")

        if metrics.match_rate is not None:
            pct = int(round(metrics.match_rate * 100))
            self._card_match.set_value(f"{pct}%")
            self._card_match.set_status("matched")
        else:
            self.set_match_na()

    def set_match_na(self) -> None:
        """Set the match-rate card to N/A (Phase I / pre-conversion state)."""
        self._card_match.set_value("\u2014")  # em dash
        self._card_match.set_status("N/A")


class _MetricCard(QWidget):
    """A single metric card: indicator dot | value | label + status.

    Internal helper used exclusively by SummaryBar.
    """

    INDICATOR_SIZE = 10  # px diameter of the colored dot

    def __init__(
        self,
        label: str,
        indicator_color: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self.setMinimumWidth(Layout.METRIC_CARD_MIN)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self.setFixedHeight(Layout.SUMMARY_BAR_H - Spacing.BASE)

        # Card frame styling
        self.setStyleSheet(
            f"QWidget#card {{"
            f"  background-color: {Colors.BG_RAISED};"
            f"  border: 1px solid {Colors.BORDER_SUBTLE};"
            f"  border-radius: {Radius.LG};"
            f"  padding: {Spacing.BASE // 2}px {Spacing.BASE}px;"
            f"}}"
        )

        # ── Layout ──────────────────────────────────────────────────
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(12, 8, 12, 8)
        main_layout.setSpacing(10)

        # Left: colored dot indicator
        dot = QLabel()
        dot.setFixedSize(self.INDICATOR_SIZE, self.INDICATOR_SIZE)
        dot.setStyleSheet(
            f"background-color: {indicator_color};"
            f"border-radius: {self.INDICATOR_SIZE // 2}px;"
            f"border: none;"
        )
        main_layout.addWidget(dot, alignment=Qt.AlignmentFlag.AlignTop)

        # Right: value + label/status
        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)

        self._value_label = QLabel("\u2014")
        self._value_label.setStyleSheet(
            f"font-size: {FontSize.LG}px;"
            f"font-weight: 700;"
            f"color: {Colors.TEXT_PRIMARY};"
            f"border: none;"
            f"background: transparent;"
        )
        text_layout.addWidget(self._value_label)

        self._label_widget = QLabel(label)
        self._label_widget.setStyleSheet(
            f"font-size: {FontSize.XXS}px;"
            f"color: {Colors.TEXT_MUTED};"
            f"border: none;"
            f"background: transparent;"
        )
        text_layout.addWidget(self._label_widget)

        self._status_widget = QLabel("")
        self._status_widget.setStyleSheet(
            f"font-size: {FontSize.XXS}px;"
            f"color: {Colors.TEXT_MUTED};"
            f"border: none;"
            f"background: transparent;"
        )
        text_layout.addWidget(self._status_widget)

        main_layout.addLayout(text_layout)

    def set_value(self, value: str) -> None:
        """Set the large metric value text."""
        self._value_label.setText(value)

    def set_status(self, status: str) -> None:
        """Set the small status line below the label."""
        self._status_widget.setText(status)
