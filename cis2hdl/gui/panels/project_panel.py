"""Project Panel — tree view of CIS project structure."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QTreeView, QVBoxLayout, QWidget

from ..colors import Colors, FontSize

logger = logging.getLogger(__name__)


class ProjectPanel(QWidget):
    """Left-side panel showing the CIS project structure as a tree."""

    MIN_WIDTH = 200
    MAX_WIDTH = 250

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumWidth(self.MIN_WIDTH)
        self.setMaximumWidth(self.MAX_WIDTH)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Tree
        self._model = QStandardItemModel()
        self._model.setHorizontalHeaderLabels(["Name", "Type"])
        self._tree = QTreeView()
        self._tree.setModel(self._model)
        self._tree.setHeaderHidden(True)
        self._tree.setAnimated(True)
        self._tree.setIndentation(16)
        self._tree.setStyleSheet(
            f"font-size: {FontSize.XS}px; "
            f"background-color: {Colors.BG_RAISED}; "
            f"border: 1px solid {Colors.BORDER_SUBTLE}; "
            f"border-radius: 8px; "
            f"padding: 4px;"
        )
        layout.addWidget(self._tree)

        self._root: QStandardItem | None = None

    def load_project(self, file_path: Path) -> None:
        """Load a CIS project and display its structure."""
        self._model.clear()
        self._root = QStandardItem(f"\U0001F4C1 {file_path.stem}")
        self._root.setEditable(False)
        self._model.appendRow(self._root)

        # Try to parse and populate
        try:
            suffix = file_path.suffix.lower()
            if suffix == ".edf":
                self._load_edf(file_path)
            elif suffix == ".dsn":
                self._load_dsn(file_path)
            else:
                node = QStandardItem(f"\u26A0\uFE0F Unsupported format: {suffix}")
                node.setEditable(False)
                self._root.appendRow(node)
        except Exception as exc:
            logger.error("Failed to load project: %s", exc)
            error_node = QStandardItem(f"\u274C Error: {exc}")
            error_node.setEditable(False)
            error_node.setForeground(QColor(Colors.ERROR))
            self._root.appendRow(error_node)

        self._tree.expandAll()

    def _load_edf(self, path: Path) -> None:
        """Load an EDIF file into the tree."""
        from ...core.parser.edif_parser import EDIFParser

        parser = EDIFParser()
        design = parser.parse(path)
        for page in design.pages:
            page_node = QStandardItem(
                f"\U0001F4C4 {page.page_id} \u2014 {page.page_name}"
            )
            page_node.setEditable(False)
            self._root.appendRow(page_node)
            for inst in page.instances:
                inst_node = QStandardItem(f"\U0001F532 {inst.refdes}")
                inst_node.setEditable(False)
                page_node.appendRow(inst_node)

    def _load_dsn(self, path: Path) -> None:
        """Load a DSN file into the tree."""
        from ...core.parser.dsn.dsn_parser import DSNParser

        parser = DSNParser()
        design = parser.parse(path)
        for page in design.pages:
            page_node = QStandardItem(
                f"\U0001F4C4 {page.page_id} \u2014 {page.page_name}"
            )
            page_node.setEditable(False)
            self._root.appendRow(page_node)
            for inst in page.instances[:50]:  # Limit to avoid UI freeze
                inst_node = QStandardItem(f"\U0001F532 {inst.refdes}")
                inst_node.setEditable(False)
                page_node.appendRow(inst_node)

    def clear(self) -> None:
        """Clear the project tree."""
        self._model.clear()
        self._root = None
