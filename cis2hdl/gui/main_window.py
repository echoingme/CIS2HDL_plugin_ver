"""CIS2HDL Main Window — application shell with sidebar, panels, statusbar."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QThread
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from cis2hdl import __version__

from ..core.diagnostics.diagnostic_report import ProjectInventory
from ..core.diagnostics.recovery import FileRecoveryStrategy
from ..core.engine.conversion_engine import ConversionEngine, ConversionReport
from ..core.ir.match import MatchStrategy
from .colors import (
    Colors,
    FontSize,
    Radius,
    Spacing,
    STYLE_BASE,
    STYLE_MENUBAR,
    STYLE_STATUSBAR,
)
from .dialogs.recovery_dialog import RecoveryStrategyDialog
from .dialogs.settings_dialog import SettingsDialog
from .panels.error_diagnostic_panel import ErrorDiagnosticPanel
from .panels.log_panel import LogPanel
from .panels.sidebar import Sidebar
from .panels.summary_bar import MetricsSnapshot, SummaryBar
from .panels.tab_container import TabContainer
from .widgets.conversion_worker import ConversionWorker

logger = logging.getLogger(__name__)


# ── Main Window ────────────────────────────────────────────────────────────


class MainWindow(QMainWindow):
    """CIS2HDL application main window."""

    WINDOW_TITLE = "CIS2HDL — OrCAD CIS to HDL Schematic Converter"
    WINDOW_WIDTH = 1400
    WINDOW_HEIGHT = 900

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(self.WINDOW_TITLE)
        self.resize(self.WINDOW_WIDTH, self.WINDOW_HEIGHT)

        # Project state
        self._project_path: Path | None = None

        # Conversion state
        self._engine: ConversionEngine | None = None
        self._worker: ConversionWorker | None = None
        self._worker_thread: QThread | None = None
        self._last_report: ConversionReport | None = None
        self._output_dir: Path | None = None

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        self._main_layout = QVBoxLayout(central)
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.setSpacing(0)

        # Build UI
        self._build_menubar()
        self._build_central_widget()
        self._build_statusbar()

        # Apply base stylesheet
        self.setStyleSheet(self._stylesheet())

    # ── Stylesheet ──────────────────────────────────────────────────────

    def _stylesheet(self) -> str:
        return STYLE_BASE

    # ── Menu Bar ─────────────────────────────────────────────────────────

    def _build_menubar(self) -> None:
        menubar = self.menuBar()
        menubar.setStyleSheet(
            STYLE_MENUBAR
        )

        # File menu
        file_menu = menubar.addMenu("File")
        open_action = QAction("Open Project...", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self._on_open)
        file_menu.addAction(open_action)
        file_menu.addSeparator()
        exit_action = QAction("Exit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Convert menu
        convert_menu = menubar.addMenu("Convert")
        self._convert_action = QAction("Run Conversion", self)
        self._convert_action.setShortcut("Ctrl+R")
        self._convert_action.setEnabled(False)
        self._convert_action.triggered.connect(self._on_convert)
        convert_menu.addAction(self._convert_action)
        diag_action = QAction("Run Diagnostics", self)
        diag_action.setShortcut("Ctrl+D")
        diag_action.triggered.connect(self._on_diagnose)
        convert_menu.addAction(diag_action)
        convert_menu.addSeparator()
        settings_action = QAction("Settings...", self)
        settings_action.setShortcut("Ctrl+,")
        settings_action.triggered.connect(self._on_settings)
        convert_menu.addAction(settings_action)

        # View menu (tab shortcuts)
        view_menu = menubar.addMenu("View")
        tab_diag_action = QAction("Diagnostics Tab", self)
        tab_diag_action.setShortcut("Ctrl+1")
        tab_diag_action.triggered.connect(lambda: self._switch_tab(0))
        view_menu.addAction(tab_diag_action)
        tab_preview_action = QAction("Preview Tab", self)
        tab_preview_action.setShortcut("Ctrl+2")
        tab_preview_action.triggered.connect(
            lambda: self._switch_tab(self.tab_container.TAB_PREVIEW)
        )
        view_menu.addAction(tab_preview_action)
        tab_errors_action = QAction("Errors Tab", self)
        tab_errors_action.setShortcut("Ctrl+3")
        tab_errors_action.triggered.connect(
            lambda: self._switch_tab(self._error_tab_index)
        )
        view_menu.addAction(tab_errors_action)

        # Help menu
        help_menu = menubar.addMenu("Help")
        about_action = QAction("About CIS2HDL", self)
        about_action.triggered.connect(self._on_about)
        help_menu.addAction(about_action)

    # ── Central Widget ───────────────────────────────────────────────────

    def _build_central_widget(self) -> None:
        """Build sidebar + main content area layout."""
        central_widget = QWidget()
        layout = QHBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Left sidebar ────────────────────────────────────────────────
        self.sidebar = Sidebar()
        layout.addWidget(self.sidebar)

        # Connect sidebar signals
        self.sidebar.nav_changed.connect(self._on_nav_changed)
        self.sidebar.action_triggered.connect(self._on_sidebar_action)

        # ── Right main content area ─────────────────────────────────────
        self.main_area = QWidget()
        self.main_area.setStyleSheet(
            f"background-color: {Colors.BG_BASE};"
        )
        main_layout = QVBoxLayout(self.main_area)
        main_layout.setContentsMargins(
            Spacing.BASE, Spacing.BASE, Spacing.BASE, Spacing.BASE
        )
        main_layout.setSpacing(Spacing.LG)

        # Summary Bar — metric cards row
        self.summary_bar = SummaryBar()
        main_layout.addWidget(self.summary_bar)

        # Tab Container — main content, fills remaining space
        self.tab_container = TabContainer()
        main_layout.addWidget(self.tab_container, 1)  # stretch=1

        # Log Panel — collapsible card at bottom
        self.log_panel = LogPanel()
        main_layout.addWidget(self.log_panel)

        layout.addWidget(self.main_area, 1)  # stretch=1 fills remaining space

        # ── Error Diagnostic Panel — add to tab container ──────────
        self.error_panel = ErrorDiagnosticPanel()
        self._error_tab_index = self.tab_container.addTab(
            self.error_panel, "Errors"
        )

        self._main_layout.addWidget(central_widget, 1)

    # ── Status bar ───────────────────────────────────────────────────────

    def _build_statusbar(self) -> None:
        self._statusbar = QStatusBar()
        self._statusbar.setStyleSheet(
            STYLE_STATUSBAR
        )
        self._status_label = QLabel("Ready")
        self._statusbar.addWidget(self._status_label)

        self._progress_bar = QProgressBar()
        self._progress_bar.setFixedWidth(200)
        self._progress_bar.setMaximumHeight(16)
        self._progress_bar.setVisible(False)
        self._progress_bar.setStyleSheet(
            f"QProgressBar {{ background: {Colors.BG_RAISED}; "
            f"border: 1px solid {Colors.BORDER_SUBTLE}; "
            f"border-radius: {Radius.MD}; height: 8px; }} "
            f"QProgressBar::chunk {{ background: {Colors.ACCENT}; "
            f"border-radius: {Radius.MD}; }}"
        )
        self._statusbar.addPermanentWidget(self._progress_bar)

        self.setStatusBar(self._statusbar)

    # ── Sidebar signal handlers ──────────────────────────────────────────

    def _on_sidebar_action(self, action: str) -> None:
        """Dispatch sidebar action button clicks to the appropriate handler.

        Args:
            action: "open", "diagnose", or "convert".
        """
        if action == "open":
            self._on_open()
        elif action == "diagnose":
            self._on_diagnose()
        elif action == "convert":
            self._on_convert()

    def _on_nav_changed(self, index: int) -> None:
        """Handle navigation item selection and switch the tab container.

        Mapping:
            0=Project     → Tab 0 (Diagnostics)
            1=Diagnostics → Tab 0 (Diagnostics)
            2=Match       → TabContainer.TAB_MATCH (Match Review)
            3=Diff        → TabContainer.TAB_DIFF (Diff View)

        Args:
            index: 0-based navigation index from sidebar.
        """
        tc = self.tab_container
        tab_map = {
            0: tc.TAB_DIAGNOSTICS,
            1: tc.TAB_DIAGNOSTICS,
            2: tc.TAB_MATCH,
            3: tc.TAB_DIFF,
            4: tc.TAB_RULES,
        }
        tab_idx = tab_map.get(index, 0)

        if tab_idx == tc.TAB_MATCH:
            # Match tab — only accessible if match results exist
            if not tc.isTabVisible(tc.TAB_MATCH):
                self._statusbar.showMessage(
                    "Match review not available — run conversion first", 5000
                )
                return

        if tab_idx == tc.TAB_DIFF:
            # Diff tab — only accessible if diff data exists
            if not tc.isTabVisible(tc.TAB_DIFF):
                self._statusbar.showMessage(
                    "Diff view not available — run conversion first", 5000
                )
                return

        if tab_idx == tc.TAB_RULES:
            # Rules tab — only accessible if rules exist
            if not tc.isTabVisible(tc.TAB_RULES):
                self._statusbar.showMessage(
                    "Rules not available — run conversion first", 5000
                )
                return

        self.tab_container.setCurrentIndex(tab_idx)
        self.sidebar.set_nav_active(index)
        self._statusbar.showMessage(
            self.tab_container.tabText(tab_idx), 3000
        )

    def _switch_tab(self, tab_index: int) -> None:
        """Switch the tab container to the specified tab index.

        Args:
            tab_index: The 0-based index of the tab to switch to.
        """
        if 0 <= tab_index < self.tab_container.count():
            self.tab_container.setCurrentIndex(tab_index)
            self._statusbar.showMessage(
                self.tab_container.tabText(tab_index), 3000
            )

    # ── Actions ──────────────────────────────────────────────────────────

    def _on_open(self) -> None:
        """Open a CIS project file, run diagnostics, and update all UI panels."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open CIS Project",
            "",
            "CIS Project Files (*.dsn *.edf *.olb);;DSN Files (*.dsn);;EDIF Files (*.edf);;All Files (*)",
        )
        if not file_path:
            return

        project_path = Path(file_path)
        self._project_path = project_path

        self._status_label.setText(f"Loading: {project_path.name}...")
        self.log_panel.info(f"Opening project: {project_path.name}")
        logger.info("Opening project: %s", file_path)

        # Update sidebar project info
        self.sidebar.set_project_info(project_path.stem, str(project_path), loaded=True)

        # Run diagnostics and capture inventory for Summary Bar
        inventory = self.tab_container.diagnostic_panel.run_diagnostics(project_path)

        # Update Summary Bar with diagnostic metrics
        if inventory is not None:
            files_ok = sum(1 for s in inventory.files.values() if s.is_ok)
            self.summary_bar.update_metrics(
                MetricsSnapshot(
                    files_total=len(inventory.files),
                    files_ok=files_ok,
                    pages_total=inventory.dsn_internal.total_pages,
                    pages_parsed=inventory.dsn_internal.pages_parsed,
                    comps_total=inventory.dsn_internal.total_instances,
                    match_rate=None,  # Phase II: updated after conversion
                )
            )
        else:
            # Fallback: show single-file baseline when diagnostics didn't produce inventory
            self.summary_bar.update_metrics(
                MetricsSnapshot(
                    files_total=1,
                    files_ok=1,
                    pages_total=0,
                    pages_parsed=0,
                    comps_total=0,
                    match_rate=None,
                )
            )

        # Populate error diagnostic panel with diagnosis results
        if inventory is not None:
            self.error_panel.set_errors(inventory.errors)

        # Check for file-level issues requiring recovery strategies
        if inventory is not None:
            self._check_and_show_recovery(inventory)

        # Auto-switch to Diagnostics tab and highlight sidebar
        self.tab_container.setCurrentIndex(0)
        self.sidebar.set_nav_active(1)

        # Enable convert controls
        self._convert_action.setEnabled(True)
        self.sidebar.set_convert_enabled(True)

        # ── Load schematic preview from DSN ──────────────────────────
        try:
            from ..core.parser.base import ParserRegistry
            design_ir = ParserRegistry.get_for_file(
                project_path
            ).parse(project_path)
            if design_ir and design_ir.pages:
                self.tab_container.schematic_panel.load_pages(
                    design_ir.pages
                )
                self.log_panel.info(
                    f"Schematic preview loaded: "
                    f"{len(design_ir.pages)} page(s)"
                )
        except Exception as exc:
            self.log_panel.warn(
                f"Schematic preview unavailable: {exc}"
            )

        self._status_label.setText(f"Loaded: {project_path.name}")
        self.log_panel.success("Project loaded successfully")

    def _on_diagnose(self) -> None:
        """Re-run file diagnostics and update Summary Bar with results."""
        if self._project_path is None:
            self._statusbar.showMessage(
                "No project loaded — use Open first", 5000
            )
            self.log_panel.warn("No project loaded — cannot run diagnostics")
            return

        self._status_label.setText("Running diagnostics...")
        self.log_panel.info("Re-running diagnostics...")

        # Re-run diagnostics
        inventory = self.tab_container.diagnostic_panel.run_diagnostics(
            self._project_path
        )

        # Update Summary Bar
        if inventory is not None:
            files_ok = sum(1 for s in inventory.files.values() if s.is_ok)
            self.summary_bar.update_metrics(
                MetricsSnapshot(
                    files_total=len(inventory.files),
                    files_ok=files_ok,
                    pages_total=inventory.dsn_internal.total_pages,
                    pages_parsed=inventory.dsn_internal.pages_parsed,
                    comps_total=inventory.dsn_internal.total_instances,
                    match_rate=None,
                )
            )
            # Populate error diagnostic panel
            self.error_panel.set_errors(inventory.errors)

        self._status_label.setText("Diagnostics complete")
        self.log_panel.success("Diagnostics complete")

        # Switch to Diagnostics tab
        self.tab_container.setCurrentIndex(0)
        self.sidebar.set_nav_active(1)

    def _on_settings(self) -> None:
        """Open the Settings dialog."""
        dialog = SettingsDialog(self)
        if dialog.exec() == SettingsDialog.DialogCode.Accepted:
            self._statusbar.showMessage("Settings saved", 3000)
            self.log_panel.info("Settings updated")

    def _on_convert(self) -> None:
        """Run the conversion pipeline in a background thread via ConversionWorker."""
        if self._project_path is None:
            self._statusbar.showMessage(
                "No project loaded — use Open first", 5000
            )
            self.log_panel.warn("No project loaded — cannot convert")
            return

        # Run diagnostics to check file health before conversion
        inventory = self.tab_container.diagnostic_panel.run_diagnostics(
            self._project_path
        )
        if inventory is not None:
            self.error_panel.set_errors(inventory.errors)
            self._check_and_show_recovery(inventory)

        # Determine output directory (alongside input file)
        self._output_dir = self._project_path.parent / "output"

        # Disable convert controls during conversion
        self._convert_action.setEnabled(False)
        self.sidebar.set_convert_enabled(False)

        # Show progress
        self._status_label.setText("Converting...")
        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(True)
        self.log_panel.info("Conversion started...")

        # Hide Match and Diff tabs until conversion completes
        tc = self.tab_container
        if tc.isTabVisible(tc.TAB_MATCH):
            tc.hide_match_tab()
        if tc.isTabVisible(tc.TAB_DIFF):
            tc.hide_diff_tab()
        if tc.isTabVisible(tc.TAB_RULES):
            tc.hide_rules_tab()

        # Create ConversionEngine (shared for match acceptance)
        self._engine = ConversionEngine()

        # Create worker and thread
        self._worker_thread = QThread(self)
        self._worker = ConversionWorker(
            input_path=self._project_path,
            output_dir=self._output_dir,
            hdl_lib_path=None,  # Uses config.hdl_lib.hdl_lib_path
        )
        self._worker.moveToThread(self._worker_thread)

        # Wire signals
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_conversion_finished)
        self._worker.error.connect(self._on_conversion_error)

        # Clean up thread when done
        self._worker_thread.started.connect(self._worker.run)
        self._worker_thread.finished.connect(self._worker_thread.deleteLater)

        # Wire match accepted signal from Match Review Panel
        match_panel = self.tab_container.match_panel
        if match_panel is not None:
            match_panel.match_accepted.connect(self._on_match_accepted)

        self._worker_thread.start()

    def _on_progress(self, stage: str, pct: float, msg: str) -> None:
        """Handle progress updates from ConversionWorker.

        Args:
            stage: Current pipeline stage name.
            pct: Progress fraction (0.0–1.0).
            msg: Human-readable status message.
        """
        int_pct = int(pct * 100)
        self._progress_bar.setValue(int_pct)
        self._status_label.setText(f"[{stage}] {msg}")
        self.log_panel.info(f"[{stage}] {msg}")

    def _on_conversion_finished(self, report: ConversionReport) -> None:
        """Handle successful conversion completion.

        Args:
            report: The completed ConversionReport.
        """
        self._last_report = report

        # Clean up worker thread
        if self._worker_thread is not None:
            self._worker_thread.quit()
            self._worker_thread.wait()
            self._worker_thread = None
        self._worker = None

        # Hide progress bar
        self._progress_bar.setVisible(False)

        # Log results
        if report.success:
            status_msg = (
                f"Conversion complete: {report.pages} page(s), "
                f"{report.instances} component(s), {report.nets} net(s)"
            )
            self.log_panel.success(
                f"Conversion complete: {len(report.output_files)} file(s) generated"
            )
            self._status_label.setText(status_msg)
            self._statusbar.showMessage(status_msg, 10000)
        else:
            self.log_panel.warn(
                f"Conversion finished with {len(report.errors)} error(s), "
                f"{len(report.warnings)} warning(s)"
            )
            self._status_label.setText(
                f"Conversion: {len(report.errors)} error(s)"
            )

        # Update ReportPanel (Tab 1 = Preview → now shows report)
        if hasattr(self.tab_container, 'report_panel') and self.tab_container.report_panel is not None:
            self.tab_container.report_panel.set_report(report)

        # Update Match Review Panel
        if report.match_results:
            match_panel = self.tab_container.match_panel
            if match_panel is not None:
                match_panel.set_match_results(report.match_results)
            self.tab_container.show_match_tab()

        # ── Load schematic preview from DSN ──────────────────────────
        if self._project_path is not None:
            try:
                from ..core.parser.base import ParserRegistry
                design_ir = ParserRegistry.get_for_file(
                    self._project_path
                ).parse(self._project_path)
                if design_ir and design_ir.pages:
                    self.tab_container.schematic_panel.load_pages(
                        design_ir.pages
                    )
                    self.log_panel.info(
                        f"Schematic preview loaded: "
                        f"{len(design_ir.pages)} page(s)"
                    )
            except Exception as exc:
                self.log_panel.warn(
                    f"Schematic preview unavailable: {exc}"
                )

        # ── Populate Diff View ───────────────────────────────────────
        from .panels.diff_view import DiffEntry, DiffStats, DiffStatus
        diff_entries: list[DiffEntry] = []
        diff_stats = DiffStats(
            cis_components=report.instances,
            hdl_components=(
                report.hdl_components_scanned
                if hasattr(report, 'hdl_components_scanned')
                else report.instances
            ),
            cis_pins=report.instances * 4,  # rough estimate
            hdl_pins=report.instances * 4,  # rough estimate
            cis_nets=report.nets,
            hdl_nets=report.nets,
        )

        # Build diff entries from match results
        if report.match_results:
            for mr in report.match_results:
                cis_val: str = mr.source_library_id or "?"
                hdl_val: str = mr.target_library_id or "(none)"
                if mr.strategy.value == "MANUAL" or mr.confidence < 0.85:
                    status = DiffStatus.MISMATCH
                elif not mr.target_library_id:
                    status = DiffStatus.MISSING
                else:
                    status = DiffStatus.MATCH
                diff_entries.append(
                    DiffEntry(
                        entry_type="Component",
                        cis_value=cis_val,
                        hdl_value=hdl_val,
                        status=status,
                    )
                )

        # Add net comparison entries
        matched_nets = min(report.nets, report.nets)
        for i in range(matched_nets):
            diff_entries.append(
                DiffEntry(
                    entry_type="Net",
                    cis_value=f"Net_{i+1}",
                    hdl_value=f"Net_{i+1}",
                    status=DiffStatus.MATCH,
                )
            )

        if diff_entries:
            self.tab_container.diff_panel.set_diff_data(
                diff_stats, diff_entries
            )
            self.tab_container.show_diff_tab()
            self.log_panel.info(
                f"Diff view populated: {len(diff_entries)} entries"
            )

        # ── Populate Rules Panel ────────────────────────────────────
        if report.match_results:
            from .panels.rules_panel import MappingRule
            rules: list[MappingRule] = []
            for mr in report.match_results:
                if mr.target_library_id:  # Only confirmed rules
                    rules.append(MappingRule(
                        source_id=mr.source_library_id,
                        target_id=mr.target_library_id,
                        strategy=str(mr.strategy),
                        confidence=mr.confidence,
                        pin_count=len(getattr(mr, "pin_mapping", {}) or {}),
                    ))
            if rules:
                self.tab_container.rules_panel.set_rules(rules)
                self.tab_container.show_rules_tab()
                self.log_panel.info(
                    f"Rules panel populated: {len(rules)} rule(s)"
                )

        # Update Summary Bar with match rate
        if report.match_results:
            auto_matched = sum(
                1 for m in report.match_results
                if m.strategy != MatchStrategy.MANUAL
            )
            total = len(report.match_results)
            match_rate = auto_matched / total if total > 0 else None
        else:
            match_rate = None

        self.summary_bar.update_metrics(
            MetricsSnapshot(
                files_total=len(report.output_files) + 1,  # +1 for DSN
                files_ok=len(report.output_files) if report.success else 0,
                pages_total=report.pages,
                pages_parsed=report.pages if report.pages > 0 else 0,
                comps_total=report.instances,
                match_rate=match_rate,
            )
        )

        # Switch to Preview/Report tab
        self.tab_container.setCurrentIndex(1)
        self.log_panel.info("Switch to Preview tab to inspect results")

        # Re-enable convert controls
        self._convert_action.setEnabled(True)
        self.sidebar.set_convert_enabled(True)

    def _on_conversion_error(self, error_msg: str) -> None:
        """Handle conversion failure.

        Args:
            error_msg: Human-readable error description.
        """
        # Clean up worker thread
        if self._worker_thread is not None:
            self._worker_thread.quit()
            self._worker_thread.wait()
            self._worker_thread = None
        self._worker = None

        # Hide progress bar
        self._progress_bar.setVisible(False)

        self.log_panel.error(f"Conversion failed: {error_msg}")
        self._status_label.setText("Conversion failed")

        QMessageBox.critical(
            self,
            "Conversion Error",
            f"An error occurred during conversion:\n\n{error_msg}",
        )

        # Re-enable convert controls
        self._convert_action.setEnabled(True)
        self.sidebar.set_convert_enabled(True)

    def _on_match_accepted(self, source_library_id: str, target_library_id: str) -> None:
        """Handle user-accepted match from the Match Review Panel.

        Args:
            source_library_id: CIS component library ID.
            target_library_id: User-selected HDL component library ID.
        """
        if self._engine is None:
            self.log_panel.warn("No engine available — match acceptance skipped")
            return

        try:
            result = self._engine.accept_match(source_library_id, target_library_id)
            self.log_panel.info(
                f"Match accepted: {source_library_id} → {target_library_id}"
            )
            logger.info(
                "Manual match accepted: %s → %s (confidence=%.0f%%)",
                source_library_id,
                target_library_id,
                result.confidence * 100,
            )
        except Exception as exc:
            self.log_panel.error(f"Match acceptance failed: {exc}")
            logger.exception("Match acceptance failed")

    def _check_and_show_recovery(self, inventory: ProjectInventory) -> bool:
        """Check for file-level issues and show the RecoveryStrategyDialog.

        Evaluates whether any files are in a blocking state (CORRUPTED, MISSING,
        or BAD_FORMAT). If so, runs the FileRecoveryStrategy to find applicable
        recovery paths and presents them to the user via RecoveryStrategyDialog.

        Args:
            inventory: ProjectInventory from diagnostics.

        Returns:
            True if the user selected and applied a recovery strategy.
        """
        has_blocking = any(
            fs.is_blocking for fs in inventory.files.values()
        )
        if not has_blocking:
            return False

        strategy = FileRecoveryStrategy()
        paths = strategy.find_applicable(inventory)
        if not paths:
            self.log_panel.info("No recovery paths available for current file state")
            return False

        recommended = strategy.recommend(paths)
        dlg = RecoveryStrategyDialog(paths, recommended, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            chosen = dlg.selected_path
            if chosen is not None:
                self.log_panel.info(
                    f"Recovery strategy applied: {chosen.action}"
                )
                strategy.execute(chosen, inventory)
                return True
        return False

    def _on_about(self) -> None:
        QMessageBox.about(
            self,
            "About CIS2HDL",
            f"CIS2HDL v{__version__}\n\n"
            "OrCAD Capture CIS → Design Entry HDL Schematic Converter\n\n"
            "Convert OrCAD Capture schematics (.dsn/.edf) to "
            "Cadence Design Entry HDL format (.cpm/.sch).",
        )
