"""Tab Container — tabbed panel hosting Diagnostics, Report, Preview, Match, Diff, Rules."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QTabWidget,
    QWidget,
)

from ..colors import STYLE_TAB_WIDGET, STYLE_CARD
from .diagnostic_panel import DiagnosticPanel
from .diff_view import DiffViewPanel
from .match_review import MatchReviewPanel
from .preview_panel import PreviewPanel
from .report_panel import ReportPanel
from .rules_panel import RulesPanel, MappingRule
from .schematic_view import SchematicPreviewPanel


class TabContainer(QTabWidget):
    """Tab widget with six tabs for the main content area.

    Tab 0: Diagnostics (DiagnosticPanel)
    Tab 1: Report (ReportPanel — conversion report)
    Tab 2: Preview (SchematicPreviewPanel — schematic preview)
    Tab 3: Match (MatchReviewPanel — hidden until conversion completes)
    Tab 4: Diff (DiffViewPanel — hidden, revealed after conversion)
    Tab 5: Rules (RulesPanel — hidden, shown when rules exist)
    """

    # Tab index constants
    TAB_DIAGNOSTICS: int = 0
    TAB_REPORT: int = 1
    TAB_PREVIEW: int = 2
    TAB_MATCH: int = 3
    TAB_DIFF: int = 4
    TAB_RULES: int = 5

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(STYLE_TAB_WIDGET)
        self.setDocumentMode(True)

        # ── Tab 0: Diagnostics ──────────────────────────────────────
        self._diag_panel = DiagnosticPanel()
        self.addTab(self._diag_panel, "诊断")

        # ── Tab 1: Report ───────────────────────────────────────────
        self._report_panel = ReportPanel()
        self.addTab(self._report_panel, "报告")

        # ── Tab 2: Schematic Preview (Phase III) ────────────────────
        self._schematic_panel = SchematicPreviewPanel()
        self.addTab(self._schematic_panel, "预览")

        # ── Tab 3: Match Review (Phase II) ──────────────────────────
        self._match_panel = MatchReviewPanel()
        self.addTab(self._match_panel, "匹配")
        self.setTabVisible(self.TAB_MATCH, False)

        # ── Tab 4: Diff (Phase III) ─────────────────────────────────
        self._diff_panel = DiffViewPanel()
        self.addTab(self._diff_panel, "差异")
        self.setTabVisible(self.TAB_DIFF, False)

        # ── Tab 5: Rules (Phase III, hidden by default) ──────────────
        self._rules_panel = RulesPanel()
        self.addTab(self._rules_panel, "规则")
        self.setTabVisible(self.TAB_RULES, False)

    # ── Public accessors ────────────────────────────────────────────

    @property
    def diagnostic_panel(self) -> DiagnosticPanel:
        """Return the embedded DiagnosticPanel instance."""
        return self._diag_panel

    @property
    def preview_panel(self) -> PreviewPanel:
        """Return the embedded PreviewPanel instance (backward-compatible alias).

        Deprecated in Phase II: use ``report_panel`` instead.
        """
        if not hasattr(self, '_preview_panel'):
            self._preview_panel = PreviewPanel()
        return self._preview_panel

    @property
    def report_panel(self) -> ReportPanel:
        """Return the embedded ReportPanel instance."""
        return self._report_panel

    @property
    def schematic_panel(self) -> SchematicPreviewPanel:
        """Return the embedded SchematicPreviewPanel instance."""
        return self._schematic_panel

    @property
    def match_panel(self) -> MatchReviewPanel | None:
        """Return the embedded MatchReviewPanel instance."""
        return self._match_panel

    @property
    def diff_panel(self) -> DiffViewPanel:
        """Return the embedded DiffViewPanel instance."""
        return self._diff_panel

    @property
    def rules_panel(self) -> RulesPanel:
        """Return the embedded RulesPanel instance."""
        return self._rules_panel

    def show_match_tab(self) -> None:
        """Reveal the Match tab (Phase II)."""
        self.setTabVisible(self.TAB_MATCH, True)

    def hide_match_tab(self) -> None:
        """Hide the Match tab (e.g., before re-conversion)."""
        self.setTabVisible(self.TAB_MATCH, False)

    def show_diff_tab(self) -> None:
        """Reveal the Diff tab (Phase III)."""
        self.setTabVisible(self.TAB_DIFF, True)

    def hide_diff_tab(self) -> None:
        """Hide the Diff tab."""
        self.setTabVisible(self.TAB_DIFF, False)

    def show_rules_tab(self) -> None:
        """Reveal the Rules tab when mapping rules exist."""
        self.setTabVisible(self.TAB_RULES, True)

    def hide_rules_tab(self) -> None:
        """Hide the Rules tab."""
        self.setTabVisible(self.TAB_RULES, False)

    def isTabVisible(self, index: int) -> bool:
        """Check if a tab at the given index is visible.

        Args:
            index: Tab index to check.

        Returns:
            True if the tab is visible.
        """
        return super().isTabVisible(index)
