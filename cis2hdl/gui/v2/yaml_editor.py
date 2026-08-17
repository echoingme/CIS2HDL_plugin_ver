"""S9 GUI v2 YamlEditor — yaml 预览/直接编辑（双通道，§4）。

设计依据：``docs/gui-design.md`` §4 双通道同步规则：
- 表单改动 → 实时更新 yaml 预览（只读区高亮变更）
- yaml 直接编辑 → 校验合法后刷新表单（非法 → 红框提示不刷新）
- 冲突检测：表单与 yaml 不同步时保存 → 提示覆盖确认（MainWindow 协调）
- 保存原子写（``save_pipeline_atomic``）
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...gui.yaml_bridge import (
    YamlValidationError,
    yaml_text_to_cfg,
)
from ..colors import Colors, FontSize, Spacing

__all__ = ["YamlEditor"]


class YamlEditor(QWidget):
    """yaml 预览 / 直接编辑（等宽深色；状态提示）。"""

    apply_requested = Signal()
    """yaml → 表单 应用请求（MainWindow 监听：解析 + 刷新表单）。"""
    save_requested = Signal()
    """保存请求（MainWindow 监听：原子写 pipeline.yaml）。"""
    edited = Signal(str)
    """用户编辑（每次 textChanged 触发）。"""

    def __init__(self, controller: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._controller = controller
        self._dirty = False
        self._applying = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Spacing.SM)

        head = QHBoxLayout()
        head.setSpacing(Spacing.SM)
        title = QLabel("pipeline.yaml（权威 · 双通道）")
        title.setObjectName("section_title")
        head.addWidget(title)
        head.addStretch(1)
        self._status = QLabel("已同步")
        self._status.setStyleSheet(
            "color: %s; font-size: %dpx;" % (Colors.SUCCESS, FontSize.XXS)
        )
        head.addWidget(self._status)
        apply_btn = QPushButton("应用 yaml → 表单")
        apply_btn.setFixedHeight(28)
        apply_btn.clicked.connect(self._on_apply)
        head.addWidget(apply_btn)
        save_btn = QPushButton("保存")
        save_btn.setObjectName("primary")
        save_btn.setFixedHeight(28)
        save_btn.clicked.connect(lambda: self.save_requested.emit())
        head.addWidget(save_btn)
        layout.addLayout(head)

        self._editor = QPlainTextEdit()
        self._editor.setObjectName("yaml_editor")
        self._editor.setLineWrapMode(QPlainTextEdit.NoWrap)
        self._editor.textChanged.connect(self._on_edited)
        layout.addWidget(self._editor, 1)

        self._hint = QLabel("")
        self._hint.setObjectName("yaml_invalid")
        self._hint.setVisible(False)
        layout.addWidget(self._hint)

    # ── 对外 ─────────────────────────────────────────────────────────────

    def set_text(self, text: str, *, external: bool = False) -> None:
        """设置 yaml 文本（external=True = 来自表单/外部，不算用户脏编辑）。"""
        self._applying = True
        try:
            self._editor.setPlainText(text)
        finally:
            self._applying = False
        if external:
            self._dirty = False
            self._set_status_synced()

    def text(self) -> str:
        return self._editor.toPlainText()

    def is_dirty(self) -> bool:
        """用户是否手动编辑过 yaml（未应用/未保存）。"""
        return self._dirty

    def validate(self) -> bool:
        """校验当前文本；非法 → 红框 + 提示，返回 False。"""
        try:
            yaml_text_to_cfg(self.text())
        except YamlValidationError as exc:
            self.mark_invalid(str(exc))
            return False
        self._editor.setStyleSheet(
            "QPlainTextEdit#yaml_editor { background-color: %s; color: %s;"
            " border: 1px solid %s; border-radius: 8px;"
            " font-family: 'JetBrains Mono','Cascadia Code',monospace;"
            " font-size: %dpx; }"
            % (Colors.BG_INVERTED, Colors.TEXT_INVERTED, Colors.BORDER_SUBTLE, FontSize.XS)
        )
        self._hint.setVisible(False)
        return True

    def mark_invalid(self, msg: str) -> None:
        self._editor.setStyleSheet(
            "QPlainTextEdit#yaml_editor { background-color: %s; color: %s;"
            " border: 2px solid %s; border-radius: 8px;"
            " font-family: 'JetBrains Mono','Cascadia Code',monospace;"
            " font-size: %dpx; }"
            % (Colors.BG_INVERTED, Colors.TEXT_INVERTED, Colors.ERROR, FontSize.XS)
        )
        self._hint.setText(f"⚠ yaml 非法：{msg}")
        self._hint.setVisible(True)
        self._status.setText("yaml 非法")
        self._status.setStyleSheet("color: %s; font-size: %dpx;" % (Colors.ERROR, FontSize.XXS))

    def set_sync_state(self, synced: bool) -> None:
        """表单与 yaml 同步状态（MainWindow 冲突检测时更新）。"""
        if synced:
            self._set_status_synced()
        else:
            self._status.setText("表单有未同步改动")
            self._status.setStyleSheet(
                "color: %s; font-size: %dpx;" % (Colors.WARNING, FontSize.XXS)
            )

    # ── 内部 ─────────────────────────────────────────────────────────────

    def _set_status_synced(self) -> None:
        self._status.setText("已同步")
        self._status.setStyleSheet(
            "color: %s; font-size: %dpx;" % (Colors.SUCCESS, FontSize.XXS)
        )

    def _on_edited(self) -> None:
        if self._applying:
            return
        self._dirty = True
        # 实时校验状态（不刷新表单；非法 → 红框提示）
        try:
            yaml_text_to_cfg(self.text())
            self._editor.setStyleSheet("")
            self._hint.setVisible(False)
            self._status.setText("yaml 已编辑（未应用到表单）")
            self._status.setStyleSheet(
                "color: %s; font-size: %dpx;" % (Colors.INFO, FontSize.XXS)
            )
        except YamlValidationError as exc:
            self.mark_invalid(str(exc))
        self.edited.emit(self.text())

    def _on_apply(self) -> None:
        if self.validate():
            self._dirty = False
            self.apply_requested.emit()
