"""MatchConfirmDialog — low-confidence match confirmation dialog.

When the matching pipeline produces a result below the confidence threshold,
this dialog presents the CIS component info alongside HDL candidates for
the user to Accept, Reject, or Skip.

Reference: ROADMAP F2.3, PHASE2_DESIGN §5.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..colors import (
    Colors,
    FontSize,
    Radius,
    Spacing,
    rgba,
)
from ...core.config import config


class MatchConfirmDialog(QDialog):
    """Dialog for confirming or rejecting a low-confidence component match.

    Displays:
      - CIS component info (library ID, part name, footprint, pin count)
      - HDL candidate list sorted by confidence with color coding
      - Accept / Reject / Skip action buttons

    Signals:
        match_decided(source_library_id, target_library_id, action)
            where action is "accept", "reject", or "skip".

    Usage:
        dialog = MatchConfirmDialog(cis_info, hdl_candidates)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            decision = dialog.decision  # ("accept", target_id) or ("skip", None)
    """

    WINDOW_TITLE = "Match Confirmation — Low Confidence"
    MIN_WIDTH = 600
    MIN_HEIGHT = 450

    def __init__(
        self,
        cis_info: dict[str, str],
        hdl_candidates: list[dict[str, object]],
        parent: QWidget | None = None,
    ) -> None:
        """Initialize the match confirmation dialog.

        Args:
            cis_info: Dict with keys: library_id, part_name, footprint,
                      value, pin_count.
            hdl_candidates: List of dicts with keys: library_id, part_name,
                            confidence, footprint, pin_count.
            parent: Parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle(self.WINDOW_TITLE)
        self.setMinimumSize(self.MIN_WIDTH, self.MIN_HEIGHT)
        self.setModal(True)

        self._cis_info = cis_info
        self._hdl_candidates = hdl_candidates
        self._selected_target: str | None = None
        self._decision: tuple[str, str | None] = ("skip", None)

        self._build_ui()
        self._apply_styles()

    # ── Public properties ────────────────────────────────────────────

    @property
    def decision(self) -> tuple[str, str | None]:
        """Return the user's decision: ("accept", target_id) or ("skip", None)."""
        return self._decision

    @property
    def selected_target_id(self) -> str | None:
        """The HDL component library ID the user selected."""
        return self._selected_target

    # ── UI Construction ──────────────────────────────────────────────

    def _build_ui(self) -> None:
        """Build the warm-beige Anthropic-styled dialog layout."""
        outer = QVBoxLayout(self)
        outer.setContentsMargins(Spacing.LG, Spacing.LG, Spacing.LG, Spacing.LG)
        outer.setSpacing(Spacing.LG)

        # ── Title ────────────────────────────────────────────────────
        title = QLabel("Low Confidence Match — Review Required")
        title.setStyleSheet(
            f"font-size: {FontSize.LG}px; font-weight: 700; "
            f"color: {Colors.TEXT_PRIMARY}; border: none; background: transparent;"
        )
        outer.addWidget(title)

        # ── CIS Info Card ─────────────────────────────────────────────
        cis_card = self._build_card("CIS Component")
        cis_layout = QVBoxLayout(cis_card)
        cis_layout.setSpacing(Spacing.XS)

        for label, key in [
            ("Library ID", "library_id"),
            ("Part Name", "part_name"),
            ("Footprint", "footprint"),
            ("Value", "value"),
            ("Pin Count", "pin_count"),
        ]:
            value = self._cis_info.get(key, "—")
            row = self._info_row(label, str(value))
            cis_layout.addWidget(row)

        outer.addWidget(cis_card)

        # ── HDL Candidates List ───────────────────────────────────────
        candidates_card = self._build_card("HDL Candidates")
        candidates_layout = QVBoxLayout(candidates_card)
        candidates_layout.setSpacing(Spacing.XS)

        self._candidates_list = QListWidget()
        self._candidates_list.setStyleSheet(
            f"QListWidget {{"
            f"  font-size: {FontSize.SM}px;"
            f"  background-color: {Colors.BG_BASE};"
            f"  border: 1px solid {Colors.BORDER_DEFAULT};"
            f"  border-radius: {Radius.MD};"
            f"  padding: {Spacing.XS}px;"
            f"  color: {Colors.TEXT_PRIMARY};"
            f"}}"
            f"QListWidget::item:selected {{"
            f"  background-color: {rgba(Colors.ACCENT, 0.15)};"
            f"  color: {Colors.TEXT_PRIMARY};"
            f"}}"
        )
        self._candidates_list.currentItemChanged.connect(self._on_candidate_selected)

        for i, cand in enumerate(self._hdl_candidates):
            conf = float(cand.get("confidence", 0))
            conf_pct = int(conf * 100)
            part_name = str(cand.get("part_name", cand.get("library_id", "?")))
            footprint = str(cand.get("footprint", ""))
            pin_count = str(cand.get("pin_count", ""))

            display = f"{part_name}"
            if footprint:
                display += f"  [{footprint}]"
            if pin_count:
                display += f"  ({pin_count} pins)"
            display += f"  — {conf_pct}%"

            item = QListWidgetItem(display)
            item.setData(Qt.ItemDataRole.UserRole, cand.get("library_id", ""))
            item.setData(Qt.ItemDataRole.UserRole + 1, conf)

            # Color-code by confidence
            if conf >= config.matching.fuzzy_threshold:
                color = Colors.SUCCESS
            elif conf >= config.matching.feature_threshold:
                color = Colors.WARNING
            else:
                color = Colors.ERROR

            item.setForeground(Qt.GlobalColor.black)  # placeholder, overridden by style
            self._candidates_list.addItem(item)

        if self._hdl_candidates:
            self._candidates_list.setCurrentRow(0)

        candidates_layout.addWidget(self._candidates_list)

        # ── Candidate detail ──────────────────────────────────────────
        self._candidate_detail = QLabel("Select a candidate to see details")
        self._candidate_detail.setWordWrap(True)
        self._candidate_detail.setStyleSheet(
            f"font-size: {FontSize.XS}px; color: {Colors.TEXT_SECONDARY}; "
            f"padding: {Spacing.SM}px; border: none; background: transparent;"
        )
        candidates_layout.addWidget(self._candidate_detail)

        outer.addWidget(candidates_card)
        outer.addStretch()

        # ── Button Row ────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.setSpacing(Spacing.SM)
        btn_row.addStretch()

        skip_btn = QPushButton("Skip")
        skip_btn.setObjectName("secondary")
        skip_btn.setStyleSheet(self._secondary_btn_style())
        skip_btn.clicked.connect(self._on_skip)

        reject_btn = QPushButton("Reject")
        reject_btn.setObjectName("danger")
        reject_btn.setStyleSheet(self._danger_btn_style())
        reject_btn.clicked.connect(self._on_reject)

        accept_btn = QPushButton("Accept")
        accept_btn.setObjectName("primary")
        accept_btn.setStyleSheet(self._primary_btn_style())
        accept_btn.clicked.connect(self._on_accept)
        accept_btn.setDefault(True)

        btn_row.addWidget(skip_btn)
        btn_row.addWidget(reject_btn)
        btn_row.addWidget(accept_btn)

        outer.addLayout(btn_row)

    def _apply_styles(self) -> None:
        """Apply warm-beige Anthropic style to the dialog."""
        self.setStyleSheet(
            f"QDialog {{ background-color: {Colors.BG_BASE}; }}"
        )

    # ── Widget builders ──────────────────────────────────────────────

    def _build_card(self, title_text: str) -> QWidget:
        """Build a card-style container widget."""
        card = QWidget()
        card.setObjectName("card")
        card.setStyleSheet(
            f"QWidget#card {{"
            f"  background-color: {Colors.BG_RAISED};"
            f"  border: 1px solid {Colors.BORDER_SUBTLE};"
            f"  border-radius: {Radius.LG};"
            f"  padding: {Spacing.BASE}px;"
            f"}}"
        )

        layout = QVBoxLayout(card)
        layout.setContentsMargins(Spacing.BASE, Spacing.BASE, Spacing.BASE, Spacing.BASE)
        layout.setSpacing(Spacing.SM)

        title = QLabel(title_text)
        title.setStyleSheet(
            f"font-size: {FontSize.SM}px; font-weight: 600; "
            f"color: {Colors.TEXT_PRIMARY}; border: none; background: transparent;"
        )
        layout.addWidget(title)

        return card

    def _info_row(self, label_text: str, value_text: str) -> QWidget:
        """Build a label: value row."""
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(Spacing.SM)

        label = QLabel(f"{label_text}:")
        label.setStyleSheet(
            f"font-size: {FontSize.SM}px; color: {Colors.TEXT_SECONDARY}; "
            f"border: none; background: transparent; min-width: 80px;"
        )

        value = QLabel(value_text)
        value.setStyleSheet(
            f"font-size: {FontSize.SM}px; color: {Colors.TEXT_PRIMARY}; "
            f"font-weight: 600; border: none; background: transparent;"
        )
        value.setWordWrap(True)

        row_layout.addWidget(label)
        row_layout.addWidget(value, 1)

        return row

    # ── Button styles ────────────────────────────────────────────────

    @staticmethod
    def _primary_btn_style() -> str:
        return (
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
        )

    @staticmethod
    def _secondary_btn_style() -> str:
        return (
            f"QPushButton#secondary {{"
            f"  background-color: {Colors.BG_OVERLAY};"
            f"  color: {Colors.ACCENT};"
            f"  border: 1px solid {Colors.ACCENT};"
            f"  border-radius: {Radius.MD};"
            f"  padding: {Spacing.SM}px {Spacing.LG}px;"
            f"  font-size: {FontSize.SM}px;"
            f"  min-height: 32px;"
            f"}}"
            f"QPushButton#secondary:hover {{"
            f"  background-color: {rgba(Colors.ACCENT, 0.08)};"
            f"}}"
        )

    @staticmethod
    def _danger_btn_style() -> str:
        return (
            f"QPushButton#danger {{"
            f"  background-color: {Colors.ERROR};"
            f"  color: {Colors.BG_OVERLAY};"
            f"  border: none;"
            f"  border-radius: {Radius.MD};"
            f"  padding: {Spacing.SM}px {Spacing.LG}px;"
            f"  font-size: {FontSize.SM}px;"
            f"  font-weight: bold;"
            f"  min-height: 32px;"
            f"}}"
            f"QPushButton#danger:hover {{"
            f"  background-color: #A83830;"
            f"}}"
        )

    # ── Slot Handlers ────────────────────────────────────────────────

    def _on_candidate_selected(self, current: QListWidgetItem, _previous: QListWidgetItem | None) -> None:
        """Update detail label when a candidate is selected."""
        if current is None:
            return

        idx = self._candidates_list.row(current)
        if 0 <= idx < len(self._hdl_candidates):
            cand = self._hdl_candidates[idx]
            detail_parts = []
            for key, label in [
                ("library_id", "Library ID"),
                ("part_name", "Part Name"),
                ("footprint", "Footprint"),
                ("pin_count", "Pin Count"),
            ]:
                val = cand.get(key)
                if val:
                    detail_parts.append(f"{label}: {val}")
            self._candidate_detail.setText("  |  ".join(detail_parts))

    def _on_accept(self) -> None:
        """Accept the currently selected candidate as the match."""
        current = self._candidates_list.currentItem()
        if current:
            target_id = current.data(Qt.ItemDataRole.UserRole)
            self._selected_target = str(target_id) if target_id else None
            self._decision = ("accept", self._selected_target)
        self.accept()

    def _on_reject(self) -> None:
        """Reject all candidates — no match will be made."""
        self._decision = ("reject", None)
        self.reject()

    def _on_skip(self) -> None:
        """Skip this component — mark for manual resolution later."""
        self._decision = ("skip", None)
        self.reject()
