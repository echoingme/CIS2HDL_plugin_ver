"""S9 GUI v2 结果面板 — ReportView / ManualMatchPanel / SchematicPreview（§2 ④）。

设计依据：``docs/gui-design.md`` §2 结果面板（可停靠）：
- ReportView：aesthetic / ioport / mapping / error 标签页（文本/表格）
- ManualMatchPanel：未匹配列表（get_unmatched）+ 手动指定 hdl 器件
  （set_manual_match）+ 强制 mock 开关（J/T/U/IC）（FR3）
- SchematicPreview：转换结果可视化（现有 schematic_view 增强，S10 接入占位）
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..colors import Colors, FontSize, Spacing, rgba
from .qss import STYLE_REPORT

__all__ = ["ReportView", "ManualMatchPanel", "SchematicPreview"]


class ReportView(QWidget):
    """报告视图：aesthetic / ioport / mapping / error 四标签页。"""

    REPORT_KINDS = [
        ("aesthetic", "aesthetic"),
        ("ioport", "ioport"),
        ("mapping", "mapping"),
        ("error", "error"),
    ]

    def __init__(self, controller: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._controller = controller
        self.setStyleSheet(STYLE_REPORT)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Spacing.MD, Spacing.MD, Spacing.MD, Spacing.MD)
        layout.setSpacing(Spacing.SM)

        head = QHBoxLayout()
        title = QLabel("转换报告")
        title.setObjectName("section_title")
        head.addWidget(title)
        head.addStretch(1)
        self._empty_hint = QLabel("运行转换后展示报告")
        self._empty_hint.setStyleSheet(
            "color: %s; font-size: %dpx;" % (Colors.TEXT_MUTED, FontSize.XS)
        )
        head.addWidget(self._empty_hint)
        layout.addLayout(head)

        self._tabs = QTabWidget()
        self._contents: dict[str, QPlainTextEdit] = {}
        for key, label in self.REPORT_KINDS:
            editor = QPlainTextEdit()
            editor.setObjectName("report_content")
            editor.setReadOnly(True)
            editor.setLineWrapMode(QPlainTextEdit.NoWrap)
            self._contents[key] = editor
            self._tabs.addTab(editor, label)
        layout.addWidget(self._tabs, 1)

    def refresh(self) -> None:
        for key, editor in self._contents.items():
            editor.setPlainText(self._controller.get_report(key))
        self._empty_hint.setVisible(False)


class ManualMatchPanel(QWidget):
    """未匹配元件干预（FR3）：列表 + 手动指定 hdl + 强制 mock 前缀。"""

    match_applied = Signal(str, str, bool)
    """(refdes, hdl, force_mock)"""

    MOCK_PREFIXES = ("J", "T", "U", "IC")

    def __init__(self, controller: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._controller = controller
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Spacing.SM, Spacing.SM, Spacing.SM, Spacing.SM)
        layout.setSpacing(Spacing.SM)

        head = QHBoxLayout()
        title = QLabel("手动匹配干预（FR3）")
        title.setObjectName("section_title")
        head.addWidget(title)
        head.addStretch(1)
        self._status = QLabel("")
        self._status.setStyleSheet(
            "color: %s; font-size: %dpx;" % (Colors.TEXT_SECONDARY, FontSize.XS)
        )
        head.addWidget(self._status)
        layout.addLayout(head)

        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(
            ["refdes", "CIS 库 ID", "置信度", "推荐 HDL", "手动指定 HDL"]
        )
        self._table.setColumnWidth(0, 90)
        self._table.setColumnWidth(1, 180)
        self._table.setColumnWidth(2, 70)
        self._table.setColumnWidth(3, 180)
        self._table.setColumnWidth(4, 220)
        self._table.verticalHeader().setVisible(False)
        layout.addWidget(self._table, 1)

        # 强制 mock 前缀
        mock_row = QHBoxLayout()
        mock_row.setSpacing(Spacing.SM)
        mock_row.addWidget(QLabel("强制 mock 前缀："))
        self._mock_checks: dict[str, QCheckBox] = {}
        for prefix in self.MOCK_PREFIXES:
            box = QCheckBox(prefix)
            box.toggled.connect(
                lambda checked, p=prefix: self._on_mock_toggled(p, checked)
            )
            self._mock_checks[prefix] = box
            mock_row.addWidget(box)
        mock_row.addStretch(1)
        layout.addLayout(mock_row)

        hint = QLabel(
            "选择行 → 在“手动指定 HDL”输入器件名（如 RES_0603）→ Enter 应用；"
            "清空并 Enter 撤销。写回 match.manual_overrides（chip_config.yaml）。"
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(
            "color: %s; font-size: %dpx;" % (Colors.TEXT_MUTED, FontSize.XS)
        )
        layout.addWidget(hint)

    # ── 刷新 ─────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        entries = self._controller.get_unmatched()
        self._table.setRowCount(0)
        for entry in entries:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(entry.refdes))
            self._table.setItem(row, 1, QTableWidgetItem(entry.source_library_id))
            conf = QTableWidgetItem(f"{entry.confidence:.0%}")
            conf.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self._table.setItem(row, 2, conf)
            self._table.setItem(row, 3, QTableWidgetItem(entry.recommended_hdl))
            edit = QLineEdit(entry.recommended_hdl)
            edit.setPlaceholderText("手动指定 HDL 器件…")
            edit.returnPressed.connect(
                lambda r=row, e=edit: self._apply_row(r, e)
            )
            self._table.setCellWidget(row, 4, edit)
        if entries:
            self._status.setText(f"{len(entries)} 项待处理")
        else:
            self._status.setText("无未匹配（或尚未运行转换）")
        self._refresh_mock_checks()

    def _refresh_mock_checks(self) -> None:
        prefixes = list(self._controller.current_config.match.mock.prefixes)
        for prefix, box in self._mock_checks.items():
            box.blockSignals(True)
            box.setChecked(prefix in prefixes)
            box.blockSignals(False)

    # ── 动作 ─────────────────────────────────────────────────────────────

    def _apply_row(self, row: int, edit: QLineEdit) -> None:
        refdes_item = self._table.item(row, 0)
        if refdes_item is None:
            return
        refdes = refdes_item.text()
        hdl = edit.text().strip()
        self.match_applied.emit(refdes, hdl, False)

    def _on_mock_toggled(self, prefix: str, checked: bool) -> None:
        self._controller.toggle_mock_prefix(prefix, checked)


class SchematicPreview(QWidget):
    """原理图预览（现有 schematic_view 增强；S10 接入占位）。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Spacing.MD, Spacing.MD, Spacing.MD, Spacing.MD)
        title = QLabel("原理图预览")
        title.setObjectName("section_title")
        layout.addWidget(title)
        placeholder = QLabel(
            "转换结果可视化（基于现有 schematic_view 增强）将在 S10 接入。\n"
            "当前版本请使用转换报告与手动匹配面板。"
        )
        placeholder.setAlignment(Qt.AlignCenter)
        placeholder.setStyleSheet(
            "color: %s; font-size: %dpx; background-color: %s;"
            " border: 1px dashed %s; border-radius: 12px; padding: 40px;"
            % (Colors.TEXT_MUTED, FontSize.SM, rgba(Colors.AUX_SAND, 0.08), Colors.BORDER_DEFAULT)
        )
        layout.addWidget(placeholder, 1)
