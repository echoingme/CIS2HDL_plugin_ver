"""Match Review Panel — interactive component matching review interface.

Three-panel layout:
  Left:   CIS component list (color-coded by match confidence)
  Center: HDL candidate list (click to select)
  Bottom: Pin mapping table (CIS Pin ↔ HDL Pin)

Low-confidence matches (< 0.60) are highlighted in red.
The user can accept a match, which emits ``match_accepted``.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...core.ir.match import MatchResult, MatchStrategy
from ...core.config import config
from ..colors import (
    Colors,
    FontSize,
    Radius,
    Spacing,
    rgba,
)



class MatchReviewPanel(QWidget):
    """Interactive panel for reviewing and accepting component matches.

    Signals:
        match_accepted(source_library_id, target_library_id):
            Emitted when the user clicks Accept with a selected match.
    """

    match_accepted = Signal(str, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("card")

        # Internal state
        self._match_results: dict[str, MatchResult] = {}
        self._selected_source_id: str = ""
        self._selected_target_id: str = ""

        self._build_ui()
        self._apply_styles()

    # ── UI Construction ──────────────────────────────────────────────────

    def _build_ui(self) -> None:
        """Build the three-panel splitter layout."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(Spacing.BASE, Spacing.BASE, Spacing.BASE, Spacing.BASE)
        main_layout.setSpacing(Spacing.MD)

        # ── Header ───────────────────────────────────────────────────────
        header = QLabel("Component Match Review")
        header.setStyleSheet(
            f"font-size: {FontSize.MD}px;"
            f"font-weight: 700;"
            f"color: {Colors.TEXT_PRIMARY};"
            f"border: none;"
            f"background: transparent;"
        )
        main_layout.addWidget(header)

        # ── Horizontal Splitter: Left (CIS) | Center (HDL) ──────────────
        horiz_splitter = QSplitter(Qt.Orientation.Horizontal)
        horiz_splitter.setHandleWidth(1)
        horiz_splitter.setStyleSheet(
            f"QSplitter::handle {{"
            f"  background-color: {Colors.BORDER_SUBTLE};"
            f"}}"
        )

        # Left panel: CIS component list
        left_panel = self._build_list_panel("CIS Components", self._cis_list)
        horiz_splitter.addWidget(left_panel)

        # Center panel: HDL candidate list
        center_panel = self._build_list_panel("HDL Candidates", self._hdl_list)
        horiz_splitter.addWidget(center_panel)

        # ── Vertical Splitter: Top (lists) | Bottom (pin table) ────────
        vert_splitter = QSplitter(Qt.Orientation.Vertical)
        vert_splitter.setHandleWidth(1)
        vert_splitter.setStyleSheet(
            f"QSplitter::handle {{"
            f"  background-color: {Colors.BORDER_SUBTLE};"
            f"}}"
        )

        vert_splitter.addWidget(horiz_splitter)

        # Bottom panel: Pin mapping table
        pin_panel = self._build_pin_panel()
        vert_splitter.addWidget(pin_panel)

        # Set initial sizes (60% lists, 40% pin table)
        vert_splitter.setSizes([400, 200])

        main_layout.addWidget(vert_splitter, 1)

        # ── Action Bar ───────────────────────────────────────────────────
        action_bar = QHBoxLayout()
        action_bar.setContentsMargins(0, 0, 0, 0)
        action_bar.setSpacing(Spacing.SM)
        action_bar.addStretch()

        info_label = QLabel("Select a CIS component and its HDL match, then click Accept.")
        info_label.setStyleSheet(
            f"font-size: {FontSize.XS}px;"
            f"color: {Colors.TEXT_SECONDARY};"
            f"border: none;"
            f"background: transparent;"
        )
        action_bar.addWidget(info_label)
        action_bar.addStretch()

        self._accept_btn = QPushButton("Accept Match")
        self._accept_btn.setObjectName("primary")
        self._accept_btn.setEnabled(False)
        self._accept_btn.clicked.connect(self._on_accept)
        action_bar.addWidget(self._accept_btn)

        main_layout.addLayout(action_bar)

    def _build_list_panel(self, title: str, list_widget: QListWidget) -> QWidget:
        """Build a labeled panel containing a QListWidget.

        Args:
            title: Panel title text.
            list_widget: The QListWidget to embed (mutated in-place).

        Returns:
            QWidget panel.
        """
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Spacing.SM)

        label = QLabel(title)
        label.setStyleSheet(
            f"font-size: {FontSize.XXS}px;"
            f"font-weight: 600;"
            f"color: {Colors.TEXT_SECONDARY};"
            f"border: none;"
            f"background: transparent;"
        )
        layout.addWidget(label)
        layout.addWidget(list_widget, 1)

        return panel

    def _build_pin_panel(self) -> QWidget:
        """Build the pin mapping table panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Spacing.SM)

        pin_header = QLabel("Pin Mapping")
        pin_header.setStyleSheet(
            f"font-size: {FontSize.XXS}px;"
            f"font-weight: 600;"
            f"color: {Colors.TEXT_SECONDARY};"
            f"border: none;"
            f"background: transparent;"
        )
        layout.addWidget(pin_header)

        self._pin_table = QTableWidget(0, 3)
        self._pin_table.setHorizontalHeaderLabels(["#", "CIS Pin", "HDL Pin"])
        self._pin_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._pin_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._pin_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._pin_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._pin_table.verticalHeader().setVisible(False)
        self._pin_table.setAlternatingRowColors(True)
        self._pin_table.setStyleSheet(
            f"QTableWidget {{"
            f"  font-size: {FontSize.XS}px;"
            f"  background-color: {Colors.BG_RAISED};"
            f"  border: 1px solid {Colors.BORDER_SUBTLE};"
            f"  border-radius: {Radius.MD};"
            f"  gridline-color: {Colors.BORDER_SUBTLE};"
            f"}}"
            f"QTableWidget::item {{"
            f"  padding: 4px 8px;"
            f"}}"
            f"QHeaderView::section {{"
            f"  background-color: {Colors.BG_BASE};"
            f"  border: none;"
            f"  border-bottom: 1px solid {Colors.BORDER_SUBTLE};"
            f"  padding: 4px 8px;"
            f"  font-size: {FontSize.XXS}px;"
            f"  color: {Colors.TEXT_SECONDARY};"
            f"}}"
            f"QTableWidget {{"
            f"  alternate-background-color: {rgba(Colors.BG_BASE, 0.5)};"
            f"}}"
        )

        layout.addWidget(self._pin_table, 1)

        return panel

    def _apply_styles(self) -> None:
        """Apply Anthropic card style and list widget styling."""
        self.setStyleSheet(
            f"QWidget#card {{"
            f"  background-color: {Colors.BG_RAISED};"
            f"  border: 1px solid {Colors.BORDER_SUBTLE};"
            f"  border-radius: {Radius.LG};"
            f"}}"
        )

        # Style both list widgets
        list_style = (
            f"QListWidget {{"
            f"  font-size: {FontSize.SM}px;"
            f"  background-color: {Colors.BG_BASE};"
            f"  border: 1px solid {Colors.BORDER_SUBTLE};"
            f"  border-radius: {Radius.MD};"
            f"  color: {Colors.TEXT_PRIMARY};"
            f"  outline: none;"
            f"}}"
            f"QListWidget::item {{"
            f"  padding: {Spacing.SM}px {Spacing.MD}px;"
            f"  border-bottom: 1px solid {Colors.BORDER_SUBTLE};"
            f"}}"
            f"QListWidget::item:selected {{"
            f"  background-color: {rgba(Colors.ACCENT, 0.15)};"
            f"  color: {Colors.TEXT_PRIMARY};"
            f"}}"
            f"QListWidget::item:hover {{"
            f"  background-color: {rgba(Colors.ACCENT, 0.06)};"
            f"}}"
        )
        self._cis_list.setStyleSheet(list_style)
        self._hdl_list.setStyleSheet(list_style)

        # Style the Accept button
        self._accept_btn.setStyleSheet(
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
            f"QPushButton#primary:disabled {{"
            f"  background-color: {Colors.ACCENT_MUTED};"
            f"}}"
        )

    # ── Internal widget refs (created early for _build_ui reference) ─────

    @property
    def _cis_list(self) -> QListWidget:
        """Lazy-initialize the CIS component list widget."""
        if not hasattr(self, "_cis_list_widget"):
            self._cis_list_widget = QListWidget()
            self._cis_list_widget.currentItemChanged.connect(self._on_cis_selected)
        return self._cis_list_widget

    @property
    def _hdl_list(self) -> QListWidget:
        """Lazy-initialize the HDL candidate list widget."""
        if not hasattr(self, "_hdl_list_widget"):
            self._hdl_list_widget = QListWidget()
            self._hdl_list_widget.currentItemChanged.connect(self._on_hdl_selected)
        return self._hdl_list_widget

    # ── Public API ───────────────────────────────────────────────────────

    def set_match_results(self, results: list[MatchResult]) -> None:
        """Populate the panel with match results from the conversion pipeline.

        Args:
            results: List of MatchResult objects from Stage 4 (Match).
        """
        self._match_results.clear()
        self._cis_list.clear()
        self._hdl_list.clear()
        self._clear_pin_table()
        self._selected_source_id = ""
        self._selected_target_id = ""
        self._accept_btn.setEnabled(False)

        if not results:
            return

        for result in results:
            self._match_results[result.source_library_id] = result

            # Build display text with confidence indicator
            if result.strategy == MatchStrategy.MANUAL:
                confidence_str = "MANUAL"
            else:
                confidence_str = f"{result.confidence:.0%}"

            display = f"{result.source_library_id}  [{confidence_str}]"
            if result.target_library_id:
                display += f"  →  {result.target_library_id}"

            item = QListWidgetItem(display)
            item.setData(Qt.ItemDataRole.UserRole, result.source_library_id)

            # Color-code by confidence: red for low-confidence
            if result.confidence < config.matching.feature_threshold and result.strategy != MatchStrategy.MANUAL:
                item.setForeground(Qt.GlobalColor.red)
                item.setToolTip(
                    f"Low confidence match ({result.confidence:.0%}) — "
                    f"manual review recommended"
                )
            elif result.strategy == MatchStrategy.EXACT:
                item.setToolTip(
                    f"Exact match ({result.confidence:.0%}) — auto-accepted"
                )
            elif result.strategy == MatchStrategy.FUZZY:
                item.setToolTip(
                    f"Fuzzy match ({result.confidence:.0%}) — review suggested"
                )
            else:
                item.setToolTip(
                    f"Manual match required — select an HDL candidate"
                )

            self._cis_list.addItem(item)

    # ── Slot Handlers ────────────────────────────────────────────────────

    def _on_cis_selected(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None = None) -> None:
        """Handle CIS component selection: populate HDL candidates and pin mapping.

        Args:
            current: The newly selected list item (may be None).
        """
        if current is None:
            self._selected_source_id = ""
            self._hdl_list.clear()
            self._clear_pin_table()
            self._accept_btn.setEnabled(False)
            return

        source_id = current.data(Qt.ItemDataRole.UserRole)
        self._selected_source_id = source_id
        result = self._match_results.get(source_id)

        # Populate HDL candidates
        self._hdl_list.clear()
        if result is not None:
            # Show candidates from the match result
            candidates = result.candidates if result.candidates else []
            if result.target_library_id and not candidates:
                # Single matched target — just show it
                item = QListWidgetItem(result.target_library_id)
                item.setData(Qt.ItemDataRole.UserRole, result.target_library_id)
                if result.strategy == MatchStrategy.EXACT:
                    item.setToolTip("Exact match — auto-accepted")
                self._hdl_list.addItem(item)
            else:
                for cand in candidates:
                    item = QListWidgetItem(cand)
                    item.setData(Qt.ItemDataRole.UserRole, cand)
                    self._hdl_list.addItem(item)

            # Populate pin mapping table
            self._populate_pin_table(result)

    def _on_hdl_selected(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None = None) -> None:
        """Handle HDL candidate selection: enable Accept button.

        Args:
            current: The newly selected list item (may be None).
        """
        if current is None:
            self._selected_target_id = ""
            self._accept_btn.setEnabled(False)
            return

        self._selected_target_id = current.data(Qt.ItemDataRole.UserRole)
        self._accept_btn.setEnabled(bool(self._selected_source_id) and bool(self._selected_target_id))

    def _on_accept(self) -> None:
        """Accept the current match and emit ``match_accepted`` signal."""
        if not self._selected_source_id or not self._selected_target_id:
            return

        self.match_accepted.emit(self._selected_source_id, self._selected_target_id)

        # Update the CIS list item to show accepted status
        for i in range(self._cis_list.count()):
            item = self._cis_list.item(i)
            if item is not None and item.data(Qt.ItemDataRole.UserRole) == self._selected_source_id:
                current_text = item.text()
                if "→" not in current_text:
                    item.setText(f"{current_text}  →  {self._selected_target_id}")
                item.setForeground(Qt.GlobalColor.darkGreen)
                item.setToolTip(f"Accepted: {self._selected_source_id} → {self._selected_target_id}")
                break

        # Disable accept until next valid selection
        self._accept_btn.setEnabled(False)

    # ── Pin Table Helpers ────────────────────────────────────────────────

    def _populate_pin_table(self, result: MatchResult) -> None:
        """Fill the pin mapping table from a MatchResult's pin_mapping dict.

        Args:
            result: The MatchResult containing pin_mapping.
        """
        self._clear_pin_table()

        pin_mapping = result.pin_mapping if result.pin_mapping else {}
        if not pin_mapping:
            return

        self._pin_table.setRowCount(len(pin_mapping))
        for row, (cis_pin, hdl_pin) in enumerate(sorted(pin_mapping.items())):
            # Row number
            num_item = QTableWidgetItem(str(row + 1))
            num_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._pin_table.setItem(row, 0, num_item)

            # CIS pin
            cis_item = QTableWidgetItem(cis_pin)
            self._pin_table.setItem(row, 1, cis_item)

            # HDL pin
            hdl_item = QTableWidgetItem(hdl_pin)
            self._pin_table.setItem(row, 2, hdl_item)

    def _clear_pin_table(self) -> None:
        """Clear all rows from the pin mapping table."""
        self._pin_table.setRowCount(0)
