"""S9 GUI v2 核心组件 — ProfileList/ProfileBar/StageTabs/PluginCard/ParamForm。

设计依据：``docs/gui-design.md`` §2 组件树 + §3.2 组件职责表 + §3.3 控件映射。
PySide6 组件（仅由 v2 app 在 PySide6 存在时导入）。

排序交互（合理默认，标注偏差）：gui-design 要求"拖拽排序"；本实现用
**执行顺序 QListWidget（InternalMove 拖拽）+ 卡片 ↑/↓ 按钮**双通道，
语义等价（顺序 = 执行顺序，写回 ``plugins.<stage>``）。
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...core.profile_manager import DuplicateProfileError, ProfileError
from ..colors import Colors, FontSize, Spacing
from .qss import STYLE_V2

__all__ = [
    "ParamForm",
    "PluginCard",
    "ProfileBar",
    "ProfileList",
    "StageTabs",
    "ListEditor",
    "DictEditor",
]


# ─────────────────────────────────────────────────────────────────────────────
# 参数控件
# ─────────────────────────────────────────────────────────────────────────────


class ListEditor(QWidget):
    """list[str] 参数编辑器（QListWidget + 增删）。"""

    value_changed = Signal(object)

    def __init__(self, items: list[str] | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Spacing.XS)
        self._list = QListWidget()
        self._list.setMaximumHeight(110)
        layout.addWidget(self._list)
        btn_row = QHBoxLayout()
        btn_row.setSpacing(Spacing.XS)
        add_btn = QPushButton("＋ 添加")
        add_btn.setFixedWidth(76)
        del_btn = QPushButton("－ 删除")
        del_btn.setFixedWidth(76)
        add_btn.clicked.connect(self._on_add)
        del_btn.clicked.connect(self._on_delete)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(del_btn)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)
        self.set_items(list(items or []))

    def set_items(self, items: list[str]) -> None:
        self._list.clear()
        for it in items:
            self._list.addItem(str(it))

    def items(self) -> list[str]:
        return [self._list.item(i).text() for i in range(self._list.count())]

    def _on_add(self) -> None:
        self._list.addItem("")
        item = self._list.item(self._list.count() - 1)
        if item is not None:
            self._list.editItem(item)
        self._emit()

    def _on_delete(self) -> None:
        row = self._list.currentRow()
        if row >= 0:
            self._list.takeItem(row)
            self._emit()

    def _emit(self) -> None:
        self.value_changed.emit(self.items())


class DictEditor(QWidget):
    """dict 参数编辑器（QTreeWidget 折叠；叶子值可编辑）。

    叶子值按原类型解析：bool / int / float / list（逗号分隔）/ str。
    """

    value_changed = Signal(object)

    def __init__(self, value: dict | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Spacing.XS)
        self._tree = QTreeWidget()
        self._tree.setMaximumHeight(140)
        self._tree.setHeaderLabels(["key", "value"])
        self._tree.setColumnWidth(0, 120)
        layout.addWidget(self._tree)
        self._tree.itemChanged.connect(self._on_item_changed)
        self.set_value(dict(value or {}))

    def set_value(self, value: dict) -> None:
        self._tree.blockSignals(True)
        self._tree.clear()
        for key, val in sorted(value.items()):
            item = QTreeWidgetItem([str(key), _format_leaf(val)])
            item.setFlags(item.flags() | Qt.ItemIsEditable)
            self._tree.addTopLevelItem(item)
        self._tree.blockSignals(False)

    def value(self) -> dict:
        result: dict[str, Any] = {}
        for i in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(i)
            key = item.text(0)
            result[key] = _parse_leaf(item.text(1))
        return result

    def _on_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        if column == 1:
            self.value_changed.emit(self.value())


def _format_leaf(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    return str(value)


def _parse_leaf(text: str) -> Any:
    t = text.strip()
    low = t.casefold()
    if low in ("true", "false"):
        return low == "true"
    if "," in t:
        return [x.strip() for x in t.split(",") if x.strip()]
    try:
        if "." in t:
            return float(t)
        return int(t)
    except ValueError:
        return t


class ParamForm(QWidget):
    """schema 驱动参数表单（gui-design §3.3 控件映射）。

    信号：``param_changed(plugin_name, dotted_path, value)``。
    """

    param_changed = Signal(str, str, object)

    def __init__(
        self, schema: dict, values: dict[str, Any], plugin_name: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._schema = schema
        self._plugin_name = plugin_name
        self._widgets: dict[str, QWidget] = {}
        self._emitting = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Spacing.SM, Spacing.SM, Spacing.SM, Spacing.SM)
        layout.setSpacing(Spacing.SM)
        for field in schema.get("fields", []):
            layout.addWidget(self._build_field(field, values))
        layout.addStretch(1)

    # ── 构建 ─────────────────────────────────────────────────────────────

    def _path_for(self, field_key: str) -> str:
        section = self._schema.get("param_section", "")
        stage = self._schema.get("stage", "")
        if stage == "beautify":
            return f"beautify.{section}.{field_key}" if section else f"beautify.routing.{field_key}"
        return f"{stage}.{field_key}"

    def _build_field(self, field: dict, values: dict[str, Any]) -> QWidget:
        key = field["key"]
        path = self._path_for(key)
        current = values.get(path, field.get("default"))
        ftype = field.get("type", "str")

        if ftype == "bool":
            box = QCheckBox(str(field.get("label", key)))
            box.setChecked(bool(current))
            box.toggled.connect(lambda checked, p=path: self._emit(p, checked))
            self._widgets[path] = box
            return box

        if ftype == "int":
            spin = QSpinBox()
            spin.setRange(-1000000, 1000000)
            spin.setValue(int(current) if isinstance(current, (int, float)) and not isinstance(current, bool) else 0)
            spin.valueChanged.connect(lambda v, p=path: self._emit(p, int(v)))
            self._widgets[path] = spin
            return self._row(str(field.get("label", key)), spin)

        if ftype == "float":
            spin = QDoubleSpinBox()
            spin.setRange(-1000000.0, 1000000.0)
            spin.setDecimals(4)
            spin.setValue(float(current) if isinstance(current, (int, float)) and not isinstance(current, bool) else 0.0)
            spin.valueChanged.connect(lambda v, p=path: self._emit(p, float(v)))
            self._widgets[path] = spin
            return self._row(str(field.get("label", key)), spin)

        if ftype == "enum":
            combo = QComboBox()
            choices = field.get("choices") or []
            combo.addItems([str(c) for c in choices])
            if str(current) in choices:
                combo.setCurrentText(str(current))
            combo.currentTextChanged.connect(lambda t, p=path: self._emit(p, t))
            self._widgets[path] = combo
            return self._row(str(field.get("label", key)), combo)

        if ftype == "list":
            editor = ListEditor(current if isinstance(current, list) else [])
            editor.value_changed.connect(lambda v, p=path: self._emit(p, v))
            self._widgets[path] = editor
            return self._row(str(field.get("label", key)), editor)

        if ftype == "dict":
            editor = DictEditor(current if isinstance(current, dict) else {})
            editor.value_changed.connect(lambda v, p=path: self._emit(p, v))
            self._widgets[path] = editor
            return self._row(str(field.get("label", key)), editor)

        # str 默认
        edit = QLineEdit(str(current) if current is not None else "")
        edit.textChanged.connect(lambda t, p=path: self._emit(p, t))
        self._widgets[path] = edit
        return self._row(str(field.get("label", key)), edit)

    @staticmethod
    def _row(label: str, widget: QWidget) -> QWidget:
        wrap = QWidget()
        layout = QHBoxLayout(wrap)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Spacing.SM)
        lbl = QLabel(label)
        lbl.setFixedWidth(150)
        layout.addWidget(lbl)
        layout.addWidget(widget, 1)
        return wrap

    def _emit(self, path: str, value: Any) -> None:
        if self._emitting:
            return
        self.param_changed.emit(self._plugin_name, path, value)

    # ── 刷新 ─────────────────────────────────────────────────────────────

    def set_values(self, values: dict[str, Any]) -> None:
        """外部（yaml 编辑 / profile 切换）刷新控件值；blockSignals 防回环。"""
        self._emitting = True
        try:
            for path, widget in self._widgets.items():
                if path not in values:
                    continue
                value = values[path]
                if isinstance(widget, QCheckBox):
                    widget.setChecked(bool(value))
                elif isinstance(widget, QSpinBox):
                    widget.setValue(int(value) if isinstance(value, (int, float)) else 0)
                elif isinstance(widget, QDoubleSpinBox):
                    widget.setValue(float(value) if isinstance(value, (int, float)) else 0.0)
                elif isinstance(widget, QComboBox):
                    idx = widget.findText(str(value))
                    if idx >= 0:
                        widget.setCurrentIndex(idx)
                elif isinstance(widget, QLineEdit):
                    widget.setText(str(value))
                elif isinstance(widget, ListEditor):
                    widget.set_items(value if isinstance(value, list) else [])
                elif isinstance(widget, DictEditor):
                    widget.set_value(value if isinstance(value, dict) else {})
        finally:
            self._emitting = False


# ─────────────────────────────────────────────────────────────────────────────
# 插件卡片
# ─────────────────────────────────────────────────────────────────────────────


class PluginCard(QFrame):
    """插件勾选 + 参数折叠 + 顺序微调（启停态视觉反馈）。"""

    toggled = Signal(str, bool)
    moved_up = Signal(str)
    moved_down = Signal(str)
    param_changed = Signal(str, str, object)

    def __init__(
        self, meta: Any, enabled: bool, schema: dict, values: dict[str, Any],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._name = meta.name
        self._enabled = enabled
        self.setObjectName("card")
        self.setStyleSheet(
            "QFrame#card { background-color: %s; border: 1px solid %s; "
            "border-radius: 8px; }"
            % (Colors.BG_RAISED, Colors.BORDER_SUBTLE)
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Spacing.MD, Spacing.SM, Spacing.MD, Spacing.SM)
        layout.setSpacing(Spacing.SM)

        head = QHBoxLayout()
        head.setSpacing(Spacing.SM)
        self._checkbox = QCheckBox()
        self._checkbox.setChecked(enabled)
        self._checkbox.toggled.connect(self._on_toggled)
        head.addWidget(self._checkbox)

        name_lbl = QLabel(meta.name)
        name_lbl.setStyleSheet("font-weight: bold; font-size: %dpx;" % FontSize.SM)
        head.addWidget(name_lbl)

        if schema.get("fields"):
            self._collapse_btn = QPushButton("参数 ▾" if enabled else "参数 ▸")
            self._collapse_btn.setFixedWidth(64)
            self._collapse_btn.setCheckable(True)
            self._collapse_btn.setChecked(enabled)  # 启用插件展开（设计默认）
            self._collapse_btn.clicked.connect(self._on_collapse)
            head.addWidget(self._collapse_btn)
        else:
            self._collapse_btn = None

        head.addStretch(1)
        up_btn = QPushButton("↑")
        up_btn.setFixedWidth(30)
        up_btn.setToolTip("上移（执行顺序提前）")
        up_btn.clicked.connect(lambda: self.moved_up.emit(self._name))
        down_btn = QPushButton("↓")
        down_btn.setFixedWidth(30)
        down_btn.setToolTip("下移（执行顺序延后）")
        down_btn.clicked.connect(lambda: self.moved_down.emit(self._name))
        head.addWidget(up_btn)
        head.addWidget(down_btn)
        layout.addLayout(head)

        if meta.description:
            desc = QLabel(meta.description)
            desc.setObjectName("plugin_desc")
            desc.setWordWrap(True)
            layout.addWidget(desc)

        self._params_container = QWidget()
        self._params_layout = QVBoxLayout(self._params_container)
        self._params_layout.setContentsMargins(0, 0, 0, 0)
        self._params_layout.setSpacing(0)
        if schema.get("fields"):
            form = ParamForm(schema, values, meta.name)
            form.param_changed.connect(self.param_changed)
            self._params_layout.addWidget(form)
        layout.addWidget(self._params_container)

        self._apply_state(enabled)

    def _on_toggled(self, checked: bool) -> None:
        self._enabled = checked
        self._apply_state(checked)
        self.toggled.emit(self._name, checked)

    def _on_collapse(self) -> None:
        if self._collapse_btn is not None:
            visible = self._collapse_btn.isChecked()
            self._params_container.setVisible(visible)
            self._collapse_btn.setText("参数 ▾" if visible else "参数 ▸")

    def _apply_state(self, enabled: bool) -> None:
        """启停态视觉：禁用卡片置灰 + 参数隐藏。"""
        if self._collapse_btn is not None:
            self._collapse_btn.setChecked(enabled)
        self._params_container.setVisible(enabled and (self._collapse_btn is None or self._collapse_btn.isChecked()))
        base = "background-color: %s; border: 1px solid %s; border-radius: 8px;" % (
            Colors.BG_RAISED if enabled else Colors.BG_OVERLAY,
            Colors.BORDER_SUBTLE if enabled else Colors.BORDER_DEFAULT,
        )
        if not enabled:
            base += " color: %s;" % Colors.TEXT_MUTED
        self.setStyleSheet("QFrame#card { %s }" % base)

    def name(self) -> str:
        return self._name


# ─────────────────────────────────────────────────────────────────────────────
# Profile 工具栏
# ─────────────────────────────────────────────────────────────────────────────


class ProfileBar(QWidget):
    """Profile 下拉 + 新建/复制/重命名/保存/导入/导出/删除 + 查重反馈。"""

    profile_selected = Signal(str)
    profiles_changed = Signal()

    def __init__(self, controller: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._controller = controller
        self._current = ""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Spacing.SM)

        layout.addWidget(QLabel("Profile"))
        self._combo = QComboBox()
        self._combo.setMinimumWidth(180)
        self._combo.currentTextChanged.connect(self._on_selected)
        layout.addWidget(self._combo)

        for text, slot, obj_name in [
            ("新建", self._on_new, ""),
            ("复制", self._on_duplicate, ""),
            ("重命名", self._on_rename, ""),
            ("保存", self._on_save, "primary"),
            ("导入", self._on_import, ""),
            ("导出", self._on_export, ""),
            ("删除", self._on_delete, "danger"),
        ]:
            btn = QPushButton(text)
            if obj_name:
                btn.setObjectName(obj_name)
            btn.setFixedHeight(30)
            btn.clicked.connect(slot)
            layout.addWidget(btn)

        layout.addStretch(1)
        self._feedback = QLabel("")
        self._feedback.setObjectName("dup_feedback")
        self._feedback.setVisible(False)
        layout.addWidget(self._feedback)

    def refresh(self, current: str | None = None) -> None:
        self._combo.blockSignals(True)
        self._combo.clear()
        self._combo.addItems(self._controller.list_profiles())
        if current and current in self._controller.list_profiles():
            self._combo.setCurrentText(current)
            self._current = current
        elif self._combo.count():
            self._current = self._combo.currentText()
        self._combo.blockSignals(False)
        self._clear_feedback()

    def current_profile(self) -> str:
        return self._combo.currentText() if self._combo.count() else ""

    def show_feedback(self, text: str, *, error: bool = False) -> None:
        self._feedback.setText(text)
        if error:
            self._feedback.setStyleSheet(
                "color: %s; background-color: rgba(192,69,58,0.10);"
                " border: 1px solid %s; border-radius: 8px; padding: 6px 12px;"
                % (Colors.ERROR, Colors.ERROR)
            )
        else:
            self._feedback.setStyleSheet("")
            self._feedback.setObjectName("dup_feedback")
            self._feedback.setStyleSheet(
                "QLabel#dup_feedback { background-color: rgba(201,148,58,0.12);"
                " color: #C9943A; border: 1px solid rgba(201,148,58,0.4);"
                " border-radius: 8px; padding: 6px 12px; }"
            )
        self._feedback.setVisible(True)

    def _clear_feedback(self) -> None:
        self._feedback.setVisible(False)
        self._feedback.setText("")

    # ── 动作 ─────────────────────────────────────────────────────────────

    def _on_selected(self, name: str) -> None:
        if name:
            self._current = name
            self._clear_feedback()
            self.profile_selected.emit(name)

    def _on_new(self) -> None:
        name, ok = _prompt_name(self, "新建 Profile", "名称：", self._controller.list_profiles())
        if not ok or not name:
            return
        try:
            self._controller.save_profile(name, self._controller.current_config)
        except DuplicateProfileError as exc:
            self.show_feedback(f"⚠ 重复：{exc.duplicate_of}", error=True)
            return
        except ProfileError as exc:
            self.show_feedback(f"✗ {exc}", error=True)
            return
        except FileExistsError as exc:
            self.show_feedback(f"✗ {exc}", error=True)
            return
        self.profiles_changed.emit()
        self.show_feedback(f"✓ 已保存 {name}")
        self._set_combo(name)

    def _on_duplicate(self) -> None:
        base = self.current_profile()
        name, ok = _prompt_name(self, "复制 Profile", "新名称：", self._controller.list_profiles())
        if not ok or not name:
            return
        try:
            cfg = self._controller.load_profile(base)
            self._controller.save_profile(name, cfg)
        except (DuplicateProfileError, ProfileError, FileExistsError) as exc:
            self.show_feedback(f"✗ {exc}", error=True)
            return
        self.profiles_changed.emit()
        self.show_feedback(f"✓ 已复制为 {name}")
        self._set_combo(name)

    def _on_rename(self) -> None:
        base = self.current_profile()
        infos = {i["name"]: i for i in self._controller.profile_infos()}
        if infos.get(base, {}).get("builtin"):
            self.show_feedback("内置 profile 不可重命名", error=True)
            return
        name, ok = _prompt_name(self, "重命名 Profile", "新名称：", self._controller.list_profiles())
        if not ok or not name or name == base:
            return
        try:
            cfg = self._controller.load_profile(base)
            self._controller.save_profile(name, cfg)
            self._controller.delete_profile(base)
        except (DuplicateProfileError, ProfileError, FileExistsError) as exc:
            self.show_feedback(f"✗ {exc}", error=True)
            return
        self.profiles_changed.emit()
        self.show_feedback(f"✓ 已重命名 {base} → {name}")
        self._set_combo(name)

    def _on_save(self) -> None:
        name = self.current_profile()
        if not name:
            return
        try:
            self._controller.save_profile(name, self._controller.current_config)
        except DuplicateProfileError as exc:
            self.show_feedback(f"⚠ 重复：{exc.duplicate_of}", error=True)
            return
        except ProfileError as exc:
            self.show_feedback(f"✗ {exc}", error=True)
            return
        note = getattr(self._controller._pm, "last_note", "")  # 组合同、参数异提示
        self.show_feedback(f"✓ 已保存 {name}" + (f"（{note}）" if note else ""))
        self.profiles_changed.emit()

    def _on_import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "导入 Profile", "", "YAML (*.yaml *.yml)")
        if not path:
            return
        try:
            name = self._controller.import_profile(path)
        except ProfileError as exc:
            self.show_feedback(f"✗ 导入失败：{exc}", error=True)
            return
        except FileExistsError as exc:
            rename, ok = _prompt_name(self, "名称冲突", "新名称（重命名导入）：",
                                      self._controller.list_profiles())
            if not ok or not rename:
                return
            try:
                name = self._controller.import_profile(path, rename_to=rename)
            except (ProfileError, FileExistsError) as exc2:
                self.show_feedback(f"✗ 导入失败：{exc2}", error=True)
                return
        self.profiles_changed.emit()
        self.show_feedback(f"✓ 已导入 {name}")
        self._set_combo(name)

    def _on_export(self) -> None:
        name = self.current_profile()
        if not name:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "导出 Profile", f"{name}.yaml", "YAML (*.yaml)"
        )
        if not path:
            return
        try:
            out = self._controller.export_profile(name, path)
        except ProfileError as exc:
            self.show_feedback(f"✗ 导出失败：{exc}", error=True)
            return
        self.show_feedback(f"✓ 已导出 {out}")

    def _on_delete(self) -> None:
        name = self.current_profile()
        if not name:
            return
        infos = {i["name"]: i for i in self._controller.profile_infos()}
        if infos.get(name, {}).get("builtin"):
            self.show_feedback("内置 profile 不可删除", error=True)
            return
        ret = QMessageBox.question(
            self, "删除 Profile", f"确定删除自定义 profile {name!r}？",
        )
        if ret != QMessageBox.Yes:
            return
        try:
            self._controller.delete_profile(name)
        except ProfileError as exc:
            self.show_feedback(f"✗ {exc}", error=True)
            return
        self.profiles_changed.emit()
        self.show_feedback(f"✓ 已删除 {name}")

    def _set_combo(self, name: str) -> None:
        idx = self._combo.findText(name)
        if idx >= 0:
            self._combo.setCurrentIndex(idx)


def _prompt_name(parent: QWidget, title: str, label: str,
                 existing: list[str]) -> tuple[str, bool]:
    """简单名称输入框（带重名检查）。"""
    from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout

    dlg = QDialog(parent)
    dlg.setWindowTitle(title)
    form = QFormLayout(dlg)
    edit = QLineEdit()
    form.addRow(label, edit)
    buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    buttons.accepted.connect(dlg.accept)
    buttons.rejected.connect(dlg.reject)
    form.addRow(buttons)
    if dlg.exec() != QDialog.Accepted:
        return "", False
    name = edit.text().strip()
    if not name:
        return "", False
    if name in existing:
        QMessageBox.warning(parent, title, f"名称已存在：{name}")
        return "", False
    return name, True


# ─────────────────────────────────────────────────────────────────────────────
# Profile 列表（侧边栏）
# ─────────────────────────────────────────────────────────────────────────────


class ProfileList(QListWidget):
    """Profile 树：内置徽标（只读）/ 自定义（可删）。"""

    profile_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("profile_list")
        self.itemClicked.connect(self._on_click)

    def set_profiles(self, infos: list[dict]) -> None:
        self.clear()
        for info in infos:
            item = QListWidgetItem(info["name"])
            badge = "内置" if info.get("builtin") else "自定义"
            item.setToolTip(f"{badge} · {info.get('description') or '无描述'}")
            item.setData(Qt.UserRole, info.get("builtin", False))
            self.addItem(item)

    def _on_click(self, item: QListWidgetItem) -> None:
        self.profile_selected.emit(item.text())


# ─────────────────────────────────────────────────────────────────────────────
# 阶段标签页
# ─────────────────────────────────────────────────────────────────────────────


class StageTabs(QWidget):
    """6 阶段标签页：输入 | 匹配 | 手动干预 | 美化 | 输出 | 测试。

    每页（除手动干预）：插件卡片（勾选 + 参数）+ 执行顺序（拖拽）。
    手动干预页承载外部传入的 ManualMatchPanel。
    """

    plugin_toggled = Signal(str, str, bool)
    plugin_reordered = Signal(str, list)
    param_changed = Signal(str, str, object)
    reports_changed = Signal(list)

    STAGE_TABS = [
        ("input", "输入"),
        ("match", "匹配"),
        ("manual", "手动干预"),
        ("beautify", "美化"),
        ("output", "输出"),
        ("test", "测试"),
    ]

    def __init__(self, controller: Any, manual_widget: QWidget | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._controller = controller
        self._cards: dict[str, list[PluginCard]] = {}
        self._cards_hosts: dict[str, QVBoxLayout] = {}
        self._order_lists: dict[str, QListWidget] = {}
        self._report_grid: QWidget | None = None
        self._report_checks: list[QCheckBox] = []
        self._manual_widget = manual_widget

        from PySide6.QtWidgets import QTabWidget

        self._tabs = QTabWidget()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._tabs)

        for stage, label in self.STAGE_TABS:
            if stage == "manual":
                page = manual_widget if manual_widget is not None else QWidget()
                self._tabs.addTab(page, label)
                continue
            self._tabs.addTab(self._build_stage_page(stage), label)

        self._tabs.currentChanged.connect(lambda _: self.refresh_current())

    # ── 构建 ─────────────────────────────────────────────────────────────

    def _build_stage_page(self, stage: str) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(Spacing.XS, Spacing.SM, Spacing.XS, Spacing.XS)
        layout.setSpacing(Spacing.SM)

        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter, 1)

        # 左：插件卡片（滚动）
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        cards_host = QWidget()
        cards_layout = QVBoxLayout(cards_host)
        cards_layout.setContentsMargins(0, 0, 0, 0)
        cards_layout.setSpacing(Spacing.SM)
        scroll.setWidget(cards_host)
        splitter.addWidget(scroll)

        # 右：执行顺序（拖拽 InternalMove）
        right = QWidget()
        right.setFixedWidth(230)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(Spacing.XS)
        right_layout.addWidget(QLabel("执行顺序（拖拽调整）"))
        order_list = QListWidget()
        order_list.setDragDropMode(QListWidget.InternalMove)
        order_list.setDefaultDropAction(Qt.MoveAction)
        order_list.model().rowsMoved.connect(lambda *_: self._emit_order(stage))
        right_layout.addWidget(order_list, 1)
        splitter.addWidget(right)

        self._order_lists[stage] = order_list

        # 输出页附加：输出报告选择（独立行，不随卡片重建）
        if stage == "output":
            reports_wrap = QWidget()
            rl = QVBoxLayout(reports_wrap)
            rl.setContentsMargins(0, Spacing.SM, 0, 0)
            rl.setSpacing(Spacing.XS)
            rl.addWidget(QLabel("输出报告（output.reports）"))
            self._report_grid = QWidget()
            rg = QHBoxLayout(self._report_grid)
            rg.setContentsMargins(0, 0, 0, 0)
            rg.setSpacing(Spacing.SM)
            rl.addWidget(self._report_grid)
            layout.addWidget(reports_wrap)

        self._cards[stage] = []
        self._cards_hosts[stage] = cards_layout
        return page

    # ── 刷新 ─────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        """按当前配置重建全部阶段页（profile 切换 / yaml 外部编辑后调用）。"""
        from ...gui.yaml_bridge import stage_plugins

        for stage, _label in self.STAGE_TABS:
            if stage == "manual":
                continue
            self._rebuild_stage(stage, stage_plugins(self._controller.current_config, stage))

    def refresh_current(self) -> None:
        from ...gui.yaml_bridge import stage_plugins

        stage = self.current_stage()
        if stage and stage != "manual":
            self._rebuild_stage(stage, stage_plugins(self._controller.current_config, stage))

    def _rebuild_stage(self, stage: str, enabled: list[str]) -> None:
        """重建某阶段卡片（保持执行顺序列表焦点；顺序敏感）。"""
        cards_layout = self._cards_hosts.get(stage)
        if cards_layout is None:
            return
        # 清空卡片区（layout 中的控件全部移除并销毁）
        while cards_layout.count():
            item = cards_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        self._cards[stage] = []
        for meta in self._controller.list_plugins(stage):
            schema = self._controller.get_plugin_schema(meta.name)
            values = self._controller.current_plugin_params(meta.name)
            card = PluginCard(meta, meta.name in enabled, schema, values)
            card.toggled.connect(
                lambda name, checked, s=stage: self.plugin_toggled.emit(s, name, checked)
            )
            card.moved_up.connect(lambda name, s=stage: self._move(s, name, -1))
            card.moved_down.connect(lambda name, s=stage: self._move(s, name, 1))
            card.param_changed.connect(self.param_changed)
            cards_layout.addWidget(card)
            self._cards[stage].append(card)
        cards_layout.addStretch(1)

        order = self._order_lists[stage]
        order.blockSignals(True)
        order.clear()
        for name in enabled:
            order.addItem(name)
        order.blockSignals(False)

        if stage == "output":
            self._refresh_report_checks()

    def _refresh_report_checks(self) -> None:
        if not hasattr(self, "_report_grid"):
            return
        while self._report_grid.layout().count():
            item = self._report_grid.layout().takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
        self._report_checks = []
        current = list(self._controller.current_config.output.reports)
        for rep in ("aesthetic", "ioport", "mapping", "error"):
            box = QCheckBox(rep)
            box.setChecked(rep in current)
            box.toggled.connect(self._on_report_toggled)
            self._report_grid.layout().addWidget(box)
            self._report_checks.append(box)

    def _on_report_toggled(self, _checked: bool) -> None:
        reports = [b.text() for b in self._report_checks if b.isChecked()]
        self.reports_changed.emit(reports)

    # ── 顺序 / 状态 ──────────────────────────────────────────────────────

    def _move(self, stage: str, name: str, delta: int) -> None:
        order = self._order_lists[stage]
        row = None
        for i in range(order.count()):
            if order.item(i).text() == name:
                row = i
                break
        if row is None:
            return
        new_row = row + delta
        if new_row < 0 or new_row >= order.count():
            return
        item = order.takeItem(row)
        order.insertItem(new_row, item)
        self._emit_order(stage)

    def _emit_order(self, stage: str) -> None:
        order = self._order_lists[stage]
        names = [order.item(i).text() for i in range(order.count())]
        self.plugin_reordered.emit(stage, names)

    def current_stage(self) -> str:
        idx = self._tabs.currentIndex()
        if 0 <= idx < len(self.STAGE_TABS):
            return self.STAGE_TABS[idx][0]
        return ""

    def enabled_plugins(self, stage: str) -> list[str]:
        order = self._order_lists.get(stage)
        if order is None:
            return []
        return [order.item(i).text() for i in range(order.count())]
