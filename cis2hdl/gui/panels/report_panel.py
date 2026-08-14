"""Report Panel — card-based conversion report visualization.

Displays the ConversionReport with:
- Status overview (success/warning/error counts)
- Per-stage collapsible detail sections (QTreeWidget)
- Match confidence color-scale table
- Generated output file manifest
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
    QSizePolicy,
)

from ...core.engine.conversion_engine import ConversionReport
from ...core.ir.match import MatchResult, MatchStrategy
from ...core.config import config
from ..colors import (
    Colors,
    FontSize,
    Radius,
    Spacing,
    rgba,
)


class ReportPanel(QWidget):
    """Card-based conversion report panel using Anthropic design tokens.

    Layout:
      - Top: Status overview cards (success/warning/error counts)
      - Middle: QTreeWidget with collapsible per-stage details
      - Bottom: Output file manifest
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self._report: ConversionReport | None = None

        self._build_ui()
        self._apply_styles()

    # ── UI Construction ──────────────────────────────────────────────────

    def _build_ui(self) -> None:
        """Build the card-style report layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Spacing.BASE, Spacing.BASE, Spacing.BASE, Spacing.BASE)
        layout.setSpacing(Spacing.MD)

        # ── Header ───────────────────────────────────────────────────────
        header = QLabel("Conversion Report")
        header.setStyleSheet(
            f"font-size: {FontSize.MD}px;"
            f"font-weight: 700;"
            f"color: {Colors.TEXT_PRIMARY};"
            f"border: none;"
            f"background: transparent;"
        )
        layout.addWidget(header)

        # ── Status Overview Row ──────────────────────────────────────────
        status_row = QHBoxLayout()
        status_row.setContentsMargins(0, 0, 0, 0)
        status_row.setSpacing(Spacing.BASE)

        self._status_success = self._make_status_badge("Success", "0", Colors.SUCCESS)
        self._status_warning = self._make_status_badge("Warnings", "0", Colors.WARNING)
        self._status_error = self._make_status_badge("Errors", "0", Colors.ERROR)

        status_row.addWidget(self._status_success)
        status_row.addWidget(self._status_warning)
        status_row.addWidget(self._status_error)
        status_row.addStretch()

        layout.addLayout(status_row)

        # ── Separator ────────────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {Colors.BORDER_SUBTLE};")
        sep.setFixedHeight(1)
        layout.addWidget(sep)

        # ── Detail Tree ──────────────────────────────────────────────────
        self._detail_tree = QTreeWidget()
        self._detail_tree.setHeaderLabels(["Section", "Details"])
        self._detail_tree.setRootIsDecorated(True)
        self._detail_tree.setAnimated(True)
        self._detail_tree.header().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self._detail_tree.header().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self._detail_tree.setAlternatingRowColors(True)
        layout.addWidget(self._detail_tree, 1)

        # ── Output Files ─────────────────────────────────────────────────
        files_label = QLabel("Generated Files")
        files_label.setStyleSheet(
            f"font-size: {FontSize.XXS}px;"
            f"font-weight: 600;"
            f"color: {Colors.TEXT_SECONDARY};"
            f"border: none;"
            f"background: transparent;"
        )
        layout.addWidget(files_label)

        self._files_label = QLabel("No files generated yet")
        self._files_label.setWordWrap(True)
        self._files_label.setStyleSheet(
            f"font-size: {FontSize.XS}px;"
            f"color: {Colors.TEXT_SECONDARY};"
            f"border: none;"
            f"background: transparent;"
            f"padding: {Spacing.XS}px {Spacing.SM}px;"
        )
        layout.addWidget(self._files_label)

    def _make_status_badge(
        self,
        title: str,
        value: str,
        color: str,
    ) -> QWidget:
        """Create a small status badge card.

        Args:
            title: Badge label (e.g., "Success").
            value: Badge value (e.g., "5").
            color: Accent color for the left border.

        Returns:
            QWidget badge.
        """
        badge = QWidget()
        badge.setFixedHeight(56)
        badge.setStyleSheet(
            f"QWidget {{"
            f"  background-color: {Colors.BG_BASE};"
            f"  border: 1px solid {Colors.BORDER_SUBTLE};"
            f"  border-left: 3px solid {color};"
            f"  border-radius: {Radius.MD};"
            f"  padding: {Spacing.SM}px {Spacing.MD}px;"
            f"}}"
        )

        inner = QVBoxLayout(badge)
        inner.setContentsMargins(0, 0, 0, 0)
        inner.setSpacing(2)

        value_label = QLabel(value)
        value_label.setStyleSheet(
            f"font-size: {FontSize.LG}px;"
            f"font-weight: 700;"
            f"color: {color};"
            f"border: none;"
            f"background: transparent;"
        )
        inner.addWidget(value_label, alignment=Qt.AlignmentFlag.AlignCenter)

        title_label = QLabel(title)
        title_label.setStyleSheet(
            f"font-size: {FontSize.XXS}px;"
            f"color: {Colors.TEXT_MUTED};"
            f"border: none;"
            f"background: transparent;"
        )
        inner.addWidget(title_label, alignment=Qt.AlignmentFlag.AlignCenter)

        # Store value label reference for updates
        badge._value_label = value_label
        badge._title_label = title_label

        return badge

    def _apply_styles(self) -> None:
        """Apply Anthropic card styling."""
        self.setStyleSheet(
            f"QWidget#card {{"
            f"  background-color: {Colors.BG_RAISED};"
            f"  border: 1px solid {Colors.BORDER_SUBTLE};"
            f"  border-radius: {Radius.LG};"
            f"}}"
        )
        self._detail_tree.setStyleSheet(
            f"QTreeWidget {{"
            f"  font-size: {FontSize.XS}px;"
            f"  background-color: {Colors.BG_BASE};"
            f"  border: 1px solid {Colors.BORDER_SUBTLE};"
            f"  border-radius: {Radius.MD};"
            f"  color: {Colors.TEXT_PRIMARY};"
            f"}}"
            f"QTreeWidget::item {{"
            f"  padding: 4px 8px;"
            f"}}"
            f"QTreeWidget::item:selected {{"
            f"  background-color: {rgba(Colors.ACCENT, 0.15)};"
            f"}}"
            f"QHeaderView::section {{"
            f"  background-color: {Colors.BG_BASE};"
            f"  border: none;"
            f"  border-bottom: 1px solid {Colors.BORDER_SUBTLE};"
            f"  padding: 4px 8px;"
            f"  font-size: {FontSize.XXS}px;"
            f"  color: {Colors.TEXT_SECONDARY};"
            f"}}"
            f"QTreeWidget {{"
            f"  alternate-background-color: {rgba(Colors.BG_BASE, 0.5)};"
            f"}}"
        )

    # ── Public API ───────────────────────────────────────────────────────

    def set_report(self, report: ConversionReport) -> None:
        """Populate the panel with a completed ConversionReport.

        Args:
            report: The ConversionReport from the engine pipeline.
        """
        self._report = report
        self._update_status_badges(report)
        self._update_detail_tree(report)
        self._update_file_list(report)

    # ── Internal Update Methods ──────────────────────────────────────────

    def _update_status_badges(self, report: ConversionReport) -> None:
        """Update the three status badge values."""
        # Count errors by severity
        error_count = len(report.errors)
        warning_count = len(report.warnings)

        # Count auto-matched (success) vs manual
        if report.match_results:
            success_count = sum(
                1 for m in report.match_results
                if m.strategy != MatchStrategy.MANUAL
            )
        else:
            success_count = 0

        self._status_success._value_label.setText(str(success_count))
        self._status_warning._value_label.setText(str(warning_count))
        self._status_error._value_label.setText(str(error_count))

    def _update_detail_tree(self, report: ConversionReport) -> None:
        """Populate the QTreeWidget with collapsible per-stage details.

        Args:
            report: The ConversionReport.
        """
        self._detail_tree.clear()

        # ── Root: Project Info ───────────────────────────────────────────
        proj_root = self._add_top_item(
            f"Project: {report.project_name}",
            f"{report.pages} page(s), {report.instances} instance(s), "
            f"{report.nets} net(s)",
        )

        # ── Diagnostic Report ────────────────────────────────────────────
        if report.diagnostic_report is not None:
            diag = report.diagnostic_report
            diag_item = self._add_child(
                proj_root,
                "Stage 1: Diagnose",
                f"{diag.total_issues} issue(s) — "
                f"{diag.fatal_count} FATAL, {diag.error_count} ERROR, "
                f"{diag.warning_count} WARNING",
            )
            for err in diag.errors[:20]:  # Cap at 20 to avoid bloat
                self._add_child(diag_item, f"[{err.severity.name}] {err.code}", str(err))
            if len(diag.errors) > 20:
                self._add_child(
                    diag_item,
                    f"... and {len(diag.errors) - 20} more",
                    "",
                )

        # ── Stage Errors (per-stage) ─────────────────────────────────────
        for stage_name, err_list in report.stage_errors.items():
            if stage_name == "diagnose":
                continue  # Already covered above
            fatal = sum(1 for e in err_list if hasattr(e, 'severity') and e.severity.value >= 3)
            stage_item = self._add_child(
                proj_root,
                f"Stage: {stage_name}",
                f"{len(err_list)} issue(s)" + (f" ({fatal} FATAL)" if fatal else ""),
            )
            for err in err_list[:10]:
                self._add_child(stage_item, str(err), "")
            if len(err_list) > 10:
                self._add_child(
                    stage_item,
                    f"... and {len(err_list) - 10} more",
                    "",
                )

        # ── Match Results ────────────────────────────────────────────────
        if report.match_results:
            match_item = self._add_child(
                proj_root,
                "Stage 4: Component Matches",
                f"{len(report.match_results)} total, "
                f"{len(report.manual_matches)} need manual review",
            )

            # Confidence distribution summary
            conf_bins = {"High (≥95%)": 0, "Medium (75-95%)": 0, "Low (60-75%)": 0, "Manual": 0}
            for m in report.match_results:
                if m.strategy == MatchStrategy.MANUAL:
                    conf_bins["Manual"] += 1
                elif m.confidence >= config.matching.exact_threshold:
                    conf_bins["High (≥95%)"] += 1
                elif m.confidence >= config.matching.fuzzy_threshold:
                    conf_bins["Medium (75-95%)"] += 1
                else:
                    conf_bins["Low (60-75%)"] += 1

            for label, count in conf_bins.items():
                if count > 0:
                    self._add_child(match_item, label, str(count))

            # Per-match detail (top 10)
            for result in report.match_results[:10]:
                target = result.target_library_id or "(none)"
                conf_str = f"{result.confidence:.0%}" if result.strategy != MatchStrategy.MANUAL else "MANUAL"
                self._add_child(
                    match_item,
                    f"{result.source_library_id} → {target} [{conf_str}]",
                    f"Strategy: {result.strategy.value}, "
                    f"Pins mapped: {len(result.pin_mapping)}",
                )
            if len(report.match_results) > 10:
                self._add_child(
                    match_item,
                    f"... and {len(report.match_results) - 10} more matches",
                    "",
                )

        # ── Validation Errors ────────────────────────────────────────────
        if report.validation_errors:
            val_item = self._add_child(
                proj_root,
                "Stage 5: Validation",
                f"{len(report.validation_errors)} issue(s)",
            )
            for ve in report.validation_errors[:10]:
                sev = ve.severity.name if hasattr(ve, 'severity') else "UNKNOWN"
                self._add_child(val_item, f"[{sev}] {ve.code}", str(ve))
            if len(report.validation_errors) > 10:
                self._add_child(
                    val_item,
                    f"... and {len(report.validation_errors) - 10} more",
                    "",
                )

        # ── Quality ──────────────────────────────────────────────────────
        if report.quality is not None:
            self._add_child(
                proj_root,
                "Quality Estimation",
                f"Overall: {report.quality.overall_score:.0%} — "
                f"{report.quality.summary() if hasattr(report.quality, 'summary') else 'N/A'}",
            )

        # ── Errors / Warnings Lists ──────────────────────────────────────
        if report.errors:
            err_item = self._add_child(
                proj_root,
                f"Errors ({len(report.errors)})",
                "",
            )
            for e in report.errors[:15]:
                self._add_child(err_item, e, "")

        if report.warnings:
            warn_item = self._add_child(
                proj_root,
                f"Warnings ({len(report.warnings)})",
                "",
            )
            for w in report.warnings[:15]:
                self._add_child(warn_item, w, "")

        # Expand top-level items
        self._detail_tree.expandAll()

    def _update_file_list(self, report: ConversionReport) -> None:
        """Update the generated files display.

        Args:
            report: The ConversionReport.
        """
        if report.output_files:
            files_text = "\n".join(f"  • {f}" for f in report.output_files)
            self._files_label.setText(files_text)
        else:
            self._files_label.setText("No files generated")

    # ── Tree Helpers ─────────────────────────────────────────────────────

    def _add_top_item(self, title: str, subtitle: str) -> QTreeWidgetItem:
        """Add a root-level item to the tree.

        Args:
            title: Item title (column 0).
            subtitle: Item detail (column 1).

        Returns:
            The created QTreeWidgetItem.
        """
        item = QTreeWidgetItem(self._detail_tree, [title, subtitle])
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsAutoTristate)
        font = item.font(0)
        font.setBold(True)
        item.setFont(0, font)
        return item

    def _add_child(
        self,
        parent: QTreeWidgetItem,
        title: str,
        subtitle: str,
    ) -> QTreeWidgetItem:
        """Add a child item to a parent tree item.

        Args:
            parent: Parent QTreeWidgetItem.
            title: Child title (column 0).
            subtitle: Child detail (column 1).

        Returns:
            The created child QTreeWidgetItem.
        """
        item = QTreeWidgetItem(parent, [title, subtitle])
        return item
