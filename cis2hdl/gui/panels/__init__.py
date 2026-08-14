"""CIS2HDL GUI panels — public exports."""

from __future__ import annotations

# Existing panels
from .project_panel import ProjectPanel
from .diagnostic_panel import DiagnosticPanel
from .log_panel import LogPanel

# New panels (T02/T03)
from .sidebar import Sidebar
from .summary_bar import SummaryBar
from .tab_container import TabContainer
from .preview_panel import PreviewPanel
from .schematic_view import SchematicPreviewPanel
from .diff_view import DiffViewPanel, DiffEntry, DiffStats, DiffStatus

# Phase II panels (T05)
from .match_review import MatchReviewPanel
from .report_panel import ReportPanel
from .error_diagnostic_panel import ErrorDiagnosticPanel

# Phase III panels
from .rules_panel import RulesPanel, MappingRule

# Phase II widgets (T05)
from ..widgets.conversion_worker import ConversionWorker

# Phase II dialogs (T05)
from ..dialogs.settings_dialog import SettingsDialog
from ..dialogs.match_confirm import MatchConfirmDialog
from ..dialogs.recovery_dialog import RecoveryStrategyDialog

__all__ = [
    # Existing
    "ProjectPanel",
    "DiagnosticPanel",
    "LogPanel",
    # T02
    "Sidebar",
    # T03
    "SummaryBar",
    "TabContainer",
    "PreviewPanel",
    "SchematicPreviewPanel",
    "DiffViewPanel",
    "DiffEntry",
    "DiffStats",
    "DiffStatus",
    # T05
    "MatchReviewPanel",
    "ReportPanel",
    "ErrorDiagnosticPanel",
    "ConversionWorker",
    "SettingsDialog",
    "MatchConfirmDialog",
    "RecoveryStrategyDialog",
    # Phase III
    "RulesPanel",
    "MappingRule",
]
