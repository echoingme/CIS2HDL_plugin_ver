"""ChipConfigPanel — M7 芯片/connector 手动配置面板（Phase XVII，用户 D6）。

复用 MatchReviewPanel 三栏骨架（CIS 元件列表 | 候选/匹配库 | 引脚映射
表），增加可编辑引脚映射（下拉选目标引脚）、[保存配置] → chip_config.yaml
（v2.0）、[标记悬空]（R9）、[分析]（M6 PinConnectAuditor 结果展示）。

设计原则（STANDARDS Part I）：PySide6 导入延迟 + 模块级守卫 —— 无
PySide6 环境导入本模块不抛错（CLI 转换不依赖 GUI）。

配置写入：统一 chip_config.yaml（v2.0，见 manual_matches.ManualMatchesConfig）
—— 用户 D7：用 chip_config 覆盖 manual_matches，不允许冗余。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from PySide6.QtCore import Qt, Signal
    from PySide6.QtWidgets import (
        QComboBox,
        QHBoxLayout,
        QHeaderView,
        QLabel,
        QListWidget,
        QListWidgetItem,
        QMessageBox,
        QPushButton,
        QSplitter,
        QTableWidget,
        QTableWidgetItem,
        QVBoxLayout,
        QWidget,
    )

    _HAS_PYSIDE = True
except Exception:  # pragma: no cover — GUI 可选
    _HAS_PYSIDE = False


if _HAS_PYSIDE:
    class ChipConfigPanel(QWidget):
        """三栏式芯片/connector 手动配置面板。

        Signals:
            config_saved(path): 保存 chip_config.yaml 后发出。
        """

        config_saved = Signal(str)

        def __init__(
            self,
            parent: "QWidget | None" = None,
            match_results: "list | None" = None,
            default_config_path: "str | Path | None" = None,
        ) -> None:
            """Initialize the panel.

            Args:
                parent: 父窗口。
                match_results: 转换后的 MatchResult 列表（可选）。
                default_config_path: chip_config.yaml 默认路径。
            """
            super().__init__(parent)
            self._match_results: dict[str, object] = {}
            self._config_path: Path = (
                Path(default_config_path)
                if default_config_path
                else Path.home() / ".cis2hdl" / "chip_config.yaml"
            )
            self._edits: dict[str, str] = {}
            self._pin_maps: dict[str, dict[str, str]] = {}
            self._hanging: dict[str, list[str]] = {}
            if match_results:
                self.load_match_results(match_results)
            self._build_ui()

        # ------------------------------------------------------------------
        #  Data loading
        # ------------------------------------------------------------------

        def load_match_results(self, match_results: "list") -> None:
            """载入匹配结果（source_library_id → MatchResult）。"""
            for m in match_results:
                sid = str(getattr(m, "source_library_id", "") or "")
                if sid:
                    self._match_results[sid] = m
            self._refresh_cis_list()

        # ------------------------------------------------------------------
        #  UI
        # ------------------------------------------------------------------

        def _build_ui(self) -> None:
            main = QVBoxLayout(self)
            main.setContentsMargins(12, 12, 12, 12)

            header = QLabel("Chip / Connector 手动配置")
            header.setStyleSheet("font-size: 15px; font-weight: 700;")
            main.addWidget(header)

            # 三栏：CIS 列表 | 候选库 | 引脚映射表。
            split = QSplitter(Qt.Orientation.Horizontal)
            split.addWidget(self._build_list_panel("CIS 元件", self._cis_list))
            split.addWidget(self._build_list_panel("候选/匹配库", self._cand_list))
            split.addWidget(self._build_pin_panel())
            split.setSizes([260, 260, 360])
            main.addWidget(split, 1)

            # 动作栏。
            bar = QHBoxLayout()
            bar.addStretch()
            save_btn = QPushButton("保存配置 → chip_config.yaml")
            save_btn.clicked.connect(self._on_save)
            bar.addWidget(save_btn)
            hang_btn = QPushButton("标记悬空")
            hang_btn.clicked.connect(self._on_mark_hanging)
            bar.addWidget(hang_btn)
            analyze_btn = QPushButton("分析 (M6 引脚审计)")
            analyze_btn.clicked.connect(self._on_analyze)
            bar.addWidget(analyze_btn)
            main.addLayout(bar)

        def _build_list_panel(self, title: str, widget: "QListWidget") -> QWidget:
            panel = QWidget()
            lay = QVBoxLayout(panel)
            lay.setContentsMargins(0, 0, 0, 0)
            label = QLabel(title)
            lay.addWidget(label)
            lay.addWidget(widget)
            return panel

        def _build_pin_panel(self) -> QWidget:
            panel = QWidget()
            lay = QVBoxLayout(panel)
            lay.setContentsMargins(0, 0, 0, 0)
            label = QLabel("引脚映射（CIS 引脚 ↔ 目标引脚，可编辑）")
            lay.addWidget(label)
            self._pin_table = QTableWidget(0, 4)
            self._pin_table.setHorizontalHeaderLabels(
                ["CIS 引脚", "功能名", "目标引脚", "状态"],
            )
            self._pin_table.horizontalHeader().setSectionResizeMode(
                QHeaderView.ResizeMode.Stretch,
            )
            lay.addWidget(self._pin_table)
            return panel

        # ------------------------------------------------------------------
        #  Internal widgets
        # ------------------------------------------------------------------

        @property
        def _cis_list(self) -> QListWidget:
            if not hasattr(self, "_cis_list_widget"):
                self._cis_list_widget = QListWidget()
                self._cis_list_widget.currentItemChanged.connect(
                    self._on_cis_selected,
                )
            return self._cis_list_widget

        @property
        def _cand_list(self) -> QListWidget:
            if not hasattr(self, "_cand_list_widget"):
                self._cand_list_widget = QListWidget()
                self._cand_list_widget.itemClicked.connect(
                    self._on_candidate_clicked,
                )
            return self._cand_list_widget

        def _refresh_cis_list(self) -> None:
            self._cis_list.clear()
            for sid in sorted(self._match_results.keys()):
                item = QListWidgetItem(sid)
                item.setData(Qt.ItemDataRole.UserRole, sid)
                self._cis_list.addItem(item)

        def _on_cis_selected(self, current, _previous) -> None:
            if current is None:
                return
            sid = str(current.data(Qt.ItemDataRole.UserRole) or "")
            self._refresh_candidates(sid)
            self._refresh_pin_table(sid)

        def _refresh_candidates(self, sid: str) -> None:
            self._cand_list.clear()
            m = self._match_results.get(sid)
            if m is None:
                return
            target = str(getattr(m, "target_library_id", "") or "")
            if target:
                item = QListWidgetItem(f"[当前] {target}")
                item.setData(Qt.ItemDataRole.UserRole, target)
                self._cand_list.addItem(item)
            for cand in (getattr(m, "extra_data", {}) or {}).get(
                "candidates", [],
            ) or []:
                lid = str(cand.get("library_id", "")) if isinstance(cand, dict) else str(cand)
                if not lid or lid == target:
                    continue
                item = QListWidgetItem(f"[候选] {lid}")
                item.setData(Qt.ItemDataRole.UserRole, lid)
                self._cand_list.addItem(item)

        def _on_candidate_clicked(self, item: "QListWidgetItem") -> None:
            current = self._cis_list.currentItem()
            if current is None:
                return
            sid = str(current.data(Qt.ItemDataRole.UserRole) or "")
            lid = str(item.data(Qt.ItemDataRole.UserRole) or "")
            if lid:
                self._edits[sid] = lid

        def _refresh_pin_table(self, sid: str) -> None:
            self._pin_table.setRowCount(0)
            m = self._match_results.get(sid)
            if m is None:
                return
            # CIS 引脚优先取自 extra_data.manual_pin_names（{pin: name}）；
            # 无则按 hdl_pin_count 生成序号占位（供手动填写）。
            extra = getattr(m, "extra_data", {}) or {}
            raw_names = extra.get("manual_pin_names", {})
            cis_pins: list[tuple[str, str]] = []
            if isinstance(raw_names, dict) and raw_names:
                for key, val in raw_names.items():
                    cis_pins.append((str(key), str(val or "")))
            else:
                n_pins = int(extra.get("hdl_pin_count", 0) or 0)
                for i in range(n_pins):
                    cis_pins.append((str(i + 1), ""))
            if not cis_pins:
                cis_pins.append(("1", ""))
            target_pins = [
                str(p.get("number", "")) if isinstance(p, dict) else str(p)
                for p in (getattr(m, "target_pins", None) or [])
            ]
            pin_map = self._pin_maps.get(sid, {})
            hanging = set(self._hanging.get(sid, []))
            for cis_pin, fname in cis_pins:
                row = self._pin_table.rowCount()
                self._pin_table.insertRow(row)
                self._pin_table.setItem(
                    row, 0, QTableWidgetItem(cis_pin),
                )
                self._pin_table.setItem(
                    row, 1, QTableWidgetItem(fname),
                )
                combo = QComboBox()
                combo.addItem("(自动)")
                for tp in target_pins:
                    combo.addItem(tp)
                preset = pin_map.get(cis_pin)
                if preset:
                    idx = combo.findText(preset)
                    if idx >= 0:
                        combo.setCurrentIndex(idx)
                combo.currentTextChanged.connect(
                    lambda _t, p=cis_pin: self._on_pin_map_changed(
                        sid, p, _t,
                    ),
                )
                self._pin_table.setCellWidget(row, 2, combo)
                status = "悬空" if cis_pin in hanging else ""
                self._pin_table.setItem(
                    row, 3, QTableWidgetItem(status),
                )

        def _on_pin_map_changed(
            self, sid: str, cis_pin: str, target_pin: str,
        ) -> None:
            if target_pin and target_pin != "(自动)":
                self._pin_maps.setdefault(sid, {})[cis_pin] = target_pin
            else:
                self._pin_maps.get(sid, {}).pop(cis_pin, None)

        def _on_mark_hanging(self) -> None:
            current = self._cis_list.currentItem()
            if current is None:
                QMessageBox.information(self, "提示", "请先选择 CIS 元件。")
                return
            sid = str(current.data(Qt.ItemDataRole.UserRole) or "")
            marked: list[str] = []
            for row in range(self._pin_table.rowCount()):
                item = self._pin_table.item(row, 0)
                status_item = self._pin_table.item(row, 3)
                if item is None:
                    continue
                pin = item.text()
                # 状态列已有"悬空" → 再点取消。
                if status_item is not None and status_item.text() == "悬空":
                    status_item.setText("")
                    continue
                if status_item is not None:
                    status_item.setText("悬空")
                marked.append(pin)
            self._hanging[sid] = marked
            QMessageBox.information(
                self, "标记悬空",
                f"{sid}: {len(marked)} 个引脚标记悬空（待 Allegro 布线）。",
            )

        def _on_analyze(self) -> None:
            """M6 引脚连接审计（PinConnectAuditor，数据源铁律）。"""
            try:
                from cis2hdl.core.writer.pin_connect_audit import (
                    PinConnectAuditor,
                )
                auditor = PinConnectAuditor(enabled=True, report_hanging=True)
                # GUI 无 DesignConnectivity 时输出空结果并提示。
                result = auditor.audit(getattr(self, "_conn", None))
                if result.total == 0:
                    QMessageBox.information(
                        self, "分析",
                        "无连接模型数据（请先运行转换）。",
                    )
                    return
                lines = [
                    f"总引脚: {result.total}  已接: {result.connected}  "
                    f"悬空: {result.hanging}  "
                    f"网名不匹配: {result.net_mismatch}  "
                    f"引脚名不匹配: {result.pin_mismatch}",
                ]
                for e in result.hanging_entries[:20]:
                    lines.append(
                        f"  [HANGING] page {e.page}: "
                        f"{e.refdes}.{e.pin_number} 待布线",
                    )
                QMessageBox.information(
                    self, "M6 引脚审计", "\n".join(lines),
                )
            except Exception as exc:
                QMessageBox.warning(self, "分析失败", str(exc))

        def set_connectivity(self, conn) -> None:
            """注入 DesignConnectivity（供 M6 分析）。"""
            self._conn = conn

        def _on_save(self) -> None:
            try:
                from cis2hdl.core.matcher.manual_matches import (
                    ManualMatch,
                    ManualMatchesConfig,
                )
                matches: list[ManualMatch] = []
                for sid, m in self._match_results.items():
                    lib_id = self._edits.get(
                        sid,
                        str(getattr(m, "target_library_id", "") or ""),
                    )
                    if not lib_id:
                        continue
                    matches.append(ManualMatch(
                        refdes=sid,
                        library_id=lib_id,
                        section=int(
                            (getattr(m, "extra_data", {}) or {}).get(
                                "manual_section", 1,
                            ) or 1,
                        ),
                        note="gui chip_config",
                        pin_map=self._pin_maps.get(sid, {}),
                        hanging=self._hanging.get(sid, []),
                    ))
                config = ManualMatchesConfig(version="2.0", matches=matches)
                path = config.write_yaml(self._config_path)
                self.config_saved.emit(str(path))
                QMessageBox.information(
                    self, "保存配置",
                    f"已保存 {len(matches)} 条 → {path}",
                )
            except Exception as exc:
                QMessageBox.warning(self, "保存失败", str(exc))


else:  # pragma: no cover
    class ChipConfigPanel:  # type: ignore[no-redef]
        """无 PySide6 环境下的占位（CLI 转换不依赖 GUI）。"""

        def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
            raise RuntimeError("PySide6 未安装，无法使用 GUI 面板")
