"""Diagnostic Panel — file status tree, quality scores, and action suggestions."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QWidget,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QProgressBar,
    QPushButton,
)

from ..colors import Colors, Radius, FontSize, STYLE_CARD, rgba
from ...core.diagnostics.diagnostic_report import ProjectInventory

logger = logging.getLogger(__name__)


class DiagnosticPanel(QWidget):
    """Center panel showing file status, quality scores, and conversion readiness.

    Wrapped in a card-style container with 16px padding per UI_DESIGN_SPEC v2.0.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self.setStyleSheet(STYLE_CARD)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # ── Header ────────────────────────────────────────────────────
        header = QLabel("File Status & Diagnostics")
        header.setStyleSheet(
            f"font-size: {FontSize.SM}px; font-weight: 600; "
            f"color: {Colors.TEXT_PRIMARY};"
        )
        layout.addWidget(header)

        # ── File status tree ──────────────────────────────────────────
        self._file_tree = QTreeWidget()
        self._file_tree.setHeaderLabels(["File", "Status", "Size", "Quality"])
        self._file_tree.setColumnWidth(0, 200)
        self._file_tree.setColumnWidth(1, 80)
        self._file_tree.setColumnWidth(2, 80)
        self._file_tree.setColumnWidth(3, 60)
        self._file_tree.setStyleSheet(
            f"font-size: {FontSize.XS}px; "
            f"background-color: {Colors.BG_RAISED}; "
            f"border: 1px solid {Colors.BORDER_SUBTLE}; "
            f"border-radius: {Radius.LG};"
        )
        layout.addWidget(self._file_tree)

        # ── Quality scores ────────────────────────────────────────────
        scores_widget = QWidget()
        scores_layout = QHBoxLayout(scores_widget)
        scores_layout.setContentsMargins(0, 0, 0, 0)
        scores_layout.setSpacing(8)

        self._score_bars: dict[str, tuple[QLabel, QProgressBar]] = {}
        for label, color in [
            ("Logic", Colors.AUX_BLUE),
            ("Coordinate", Colors.ACCENT),
            ("Match", Colors.WARNING),
            ("Symbol", Colors.ACCENT_MUTED),
        ]:
            vbox = QVBoxLayout()
            lbl = QLabel(label)
            lbl.setStyleSheet(
                f"font-size: {FontSize.XXS}px; color: {color}; font-weight: 600;"
            )
            vbox.addWidget(lbl)
            bar = QProgressBar()
            bar.setMaximumHeight(12)
            bar.setTextVisible(False)
            bar.setStyleSheet(
                f"QProgressBar {{ background: {Colors.BG_RAISED}; "
                f"border: 1px solid {Colors.BORDER_SUBTLE}; "
                f"border-radius: {Radius.SM}; height: 8px; }} "
                f"QProgressBar::chunk {{ background: {color}; border-radius: {Radius.SM}; }}"
            )
            vbox.addWidget(bar)
            scores_layout.addLayout(vbox)
            self._score_bars[label] = (lbl, bar)
        layout.addWidget(scores_widget)

        # ── Readiness verdict ─────────────────────────────────────────
        self._verdict_label = QLabel("No project loaded")
        self._verdict_label.setStyleSheet(
            f"font-size: {FontSize.SM}px; font-weight: 600; "
            f"color: {Colors.TEXT_MUTED}; padding: 8px; "
            f"background: {Colors.BG_RAISED}; border-radius: {Radius.MD};"
        )
        self._verdict_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._verdict_label)

        # ── Action suggestions ────────────────────────────────────────
        self._action_text = QTextEdit()
        self._action_text.setReadOnly(True)
        self._action_text.setMaximumHeight(80)
        self._action_text.setStyleSheet(
            f"font-size: {FontSize.XXS}px; "
            f"background-color: {Colors.BG_RAISED}; "
            f"border: 1px solid {Colors.BORDER_SUBTLE}; "
            f"border-radius: {Radius.MD}; padding: 4px;"
        )
        layout.addWidget(self._action_text)

        layout.addStretch()

    def run_diagnostics(self, file_path: Path | None) -> ProjectInventory | None:
        """Run diagnostic pipeline on the given project file.

        Returns:
            ProjectInventory if diagnostics ran successfully,
            None if file_path is None or an error occurred.
        """
        if file_path is None:
            self._verdict_label.setText("No project loaded")
            return None

        self._file_tree.clear()
        self._file_tree.addTopLevelItem(
            QTreeWidgetItem([str(file_path), "DSN", f"{file_path.stat().st_size:_}", "\u2014"])
        )

        try:
            from ...core.diagnostics.file_inventory import FileInventory, DSNInternalInventoryBuilder
            from ...core.diagnostics.file_validator import ProjectFileValidator, DependencyResolver
            from ...core.diagnostics.diagnostic_report import ConversionReadinessEvaluator

            inv_builder = FileInventory()
            inv = inv_builder.scan([file_path], file_path.parent)

            # Try DSN inventory if it's a .dsn file
            if file_path.suffix.lower() == ".dsn":
                dsn_builder = DSNInternalInventoryBuilder()
                inv.dsn_internal = dsn_builder.build(file_path)

                # Update file tree
                self._file_tree.clear()
                for key, status in inv.files.items():
                    status_icon = {"FOUND_OK": "\u2705", "MISSING": "\u274c", "CORRUPTED": "\U0001f4a5",
                                   "BAD_FORMAT": "\u26a0\ufe0f", "PARTIAL": "\u26a0\ufe0f"}.get(
                        status.state.value, "\u2014")
                    item = QTreeWidgetItem([
                        status.path.name,
                        f"{status_icon} {status.state.value}",
                        f"{status.size:_}",
                        f"{status.data_quality:.0%}",
                    ])
                    self._file_tree.addTopLevelItem(item)

                # Update DSN info
                dsn = inv.dsn_internal
                self._file_tree.addTopLevelItem(
                    QTreeWidgetItem([
                        f"DSN Internal", "INFO",
                        f"{dsn.pages_parsed}/{dsn.total_pages} pages",
                        f"stream:{dsn.stream_integrity_score:.0%}",
                    ])
                )

            # Readiness
            evaluator = ConversionReadinessEvaluator()
            readiness = evaluator.evaluate(inv)

            # Update scores
            for label, score in [
                ("Logic", readiness.logic_score),
                ("Coordinate", readiness.coordinate_score),
                ("Match", readiness.matchability_score),
                ("Symbol", readiness.symbol_score),
            ]:
                if label in self._score_bars:
                    _, bar = self._score_bars[label]
                    bar.setValue(int(score * 100))

            # Verdict
            if readiness.can_convert:
                self._verdict_label.setText(
                    f"\u2705 Ready for conversion (quality: {readiness.overall_score:.0%})"
                )
                self._verdict_label.setStyleSheet(
                    f"font-size: {FontSize.SM}px; font-weight: 600; "
                    f"color: {Colors.INFO}; padding: 8px; "
                    f"background: {Colors.ACCENT_MUTED}; border-radius: {Radius.MD};"
                )
            elif readiness.can_convert_with_degradation:
                self._verdict_label.setText(
                    f"\u26a0\ufe0f Degraded conversion \u2014 {readiness.degradation_detail}"
                )
                self._verdict_label.setStyleSheet(
                    f"font-size: {FontSize.SM}px; font-weight: 600; "
                    f"color: {Colors.WARNING}; padding: 8px; "
                    f"background: {Colors.BG_RAISED}; border-radius: {Radius.MD};"
                )
            else:
                self._verdict_label.setText("\u274c Cannot convert \u2014 check FATAL errors")
                self._verdict_label.setStyleSheet(
                    f"font-size: {FontSize.SM}px; font-weight: 600; "
                    f"color: {Colors.ERROR}; padding: 8px; "
                    f"background: {Colors.BG_RAISED}; border-radius: {Radius.MD};"
                )

            # Suggestions
            if readiness.suggestions:
                self._action_text.setHtml(
                    "<br>".join(f"\u2022 {s}" for s in readiness.suggestions)
                )

            return inv

        except Exception as exc:
            logger.error("Diagnostic pipeline failed: %s", exc)
            self._verdict_label.setText(f"\u274c Diagnostic error: {exc}")
            return None
