"""S9 GUI v2 MainWindow — 工程工作台 4 区组装（§2）。

设计依据：``docs/gui-design.md`` §2 组件树：
① 侧边栏（ProfileList + 转换历史 + 版本/verify）｜② 配置编辑器
（ProfileBar + StageTabs + YamlEditor 双通道）｜③ 转换执行区
（ConversionRunner）｜④ 结果面板（ResultDock：ReportView +
ManualMatchPanel + SchematicPreview）。
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QDockWidget,
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from cis2hdl import __version__

from ...gui.controller import PipelineController
from ...gui.yaml_bridge import (
    cfg_to_yaml_text,
    is_text_in_sync,
    set_stage_plugins,
    yaml_text_to_cfg,
)
from ..colors import Colors, Fonts, FontSize, Layout, Spacing
from .qss import STYLE_SIDEBAR, STYLE_V2
from .report_view import ManualMatchPanel, ReportView, SchematicPreview
from .runner import ConversionRunner
from .widgets import ProfileBar, ProfileList, StageTabs
from .yaml_editor import YamlEditor

logger = logging.getLogger(__name__)

__all__ = ["MainWindow"]


class MainWindow(QMainWindow):
    """CIS2HDL 工程工作台主窗口（S9）。"""

    def __init__(self, controller: PipelineController | None = None) -> None:
        super().__init__()
        self._controller = controller or PipelineController()
        self.setWindowTitle(f"CIS2HDL v{__version__} — 工程工作台")
        self.setMinimumSize(Layout.WINDOW_MIN_W, Layout.WINDOW_MIN_H)
        self.resize(1500, 920)

        self._history: list[str] = []
        self._build_menubar()
        self._build_central()
        self._build_result_dock()
        self._build_statusbar()
        self.setStyleSheet(STYLE_V2 + STYLE_SIDEBAR)

        self._wire_signals()
        self._refresh_all()

    # ── 布局构建 ──────────────────────────────────────────────────────────

    def _build_central(self) -> None:
        central = QWidget()
        central.setObjectName("v2_root")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter, 1)

        # ── ① 侧边栏 ────────────────────────────────────────────────
        sidebar = QWidget()
        sidebar.setObjectName("v2_sidebar")
        sidebar.setFixedWidth(Layout.SIDEBAR_WIDTH)
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(Spacing.MD, Spacing.BASE, Spacing.MD, Spacing.BASE)
        side_layout.setSpacing(Spacing.SM)

        brand = QLabel("CIS2HDL")
        brand.setStyleSheet(
            "font-family: %s; font-size: %dpx; font-weight: bold; color: %s;"
            % (Fonts.UI, FontSize.LG, Colors.TEXT_PRIMARY)
        )
        side_layout.addWidget(brand)

        side_layout.addWidget(self._section_label("PROFILE"))
        self.profile_list = ProfileList()
        self.profile_list.setMaximumHeight(220)
        side_layout.addWidget(self.profile_list)

        side_layout.addWidget(self._section_label("转换历史"))
        self.history_list = QListWidget()
        self.history_list.setMaximumHeight(180)
        side_layout.addWidget(self.history_list)

        side_layout.addStretch(1)

        verify_btn = QPushButton("⚡ verify 快捷入口")
        verify_btn.clicked.connect(self._on_verify)
        side_layout.addWidget(verify_btn)

        version_lbl = QLabel(f"v{__version__} · pipeline.yaml 权威")
        version_lbl.setStyleSheet(
            "color: %s; font-size: %dpx;" % (Colors.TEXT_MUTED, FontSize.XXS)
        )
        side_layout.addWidget(version_lbl)

        splitter.addWidget(sidebar)

        # ── ② 配置编辑器（中央核心） ────────────────────────────────
        editor = QWidget()
        editor_layout = QVBoxLayout(editor)
        editor_layout.setContentsMargins(Spacing.BASE, Spacing.BASE, Spacing.BASE, Spacing.SM)
        editor_layout.setSpacing(Spacing.SM)

        self.profile_bar = ProfileBar(self._controller)
        editor_layout.addWidget(self.profile_bar)

        # 手动干预面板先建（StageTabs 手动页承载）
        self.manual_panel = ManualMatchPanel(self._controller)
        self.stage_tabs = StageTabs(self._controller, manual_widget=self.manual_panel)
        editor_layout.addWidget(self.stage_tabs, 3)

        self.yaml_editor = YamlEditor(self._controller)
        self.yaml_editor.setMaximumHeight(300)
        editor_layout.addWidget(self.yaml_editor, 2)

        splitter.addWidget(editor)

        # ── ③ 转换执行区（底部） ────────────────────────────────────
        self.runner = ConversionRunner(self._controller)
        root.addWidget(self.runner)

        splitter.setSizes([Layout.SIDEBAR_WIDTH, 1100])

    def _build_result_dock(self) -> None:
        """④ 结果面板（可停靠）：报告 / 手动干预 / 原理图预览。"""
        self.result_dock = QDockWidget("结果面板", self)
        self.result_dock.setObjectName("v2_result")
        self.result_dock.setAllowedAreas(
            Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea | Qt.BottomDockWidgetArea
        )
        tabs = QTabWidget()
        self.report_view = ReportView(self._controller)
        tabs.addTab(self.report_view, "报告")
        tabs.addTab(self.manual_panel, "手动匹配")
        tabs.addTab(SchematicPreview(), "原理图预览")
        self.result_dock.setWidget(tabs)
        self.addDockWidget(Qt.RightDockWidgetArea, self.result_dock)

    def _build_statusbar(self) -> None:
        self._status = QLabel("就绪")
        self._status.setStyleSheet(
            "color: %s; font-size: %dpx;" % (Colors.TEXT_SECONDARY, FontSize.XXS)
        )
        self.statusBar().addWidget(self._status)

    def _build_menubar(self) -> None:
        menubar = self.menuBar()
        file_menu = menubar.addMenu("文件")
        save_action = QAction("保存 pipeline.yaml", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self._on_yaml_save)
        file_menu.addAction(save_action)
        file_menu.addSeparator()
        exit_action = QAction("退出", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        run_menu = menubar.addMenu("运行")
        run_action = QAction("运行转换", self)
        run_action.setShortcut("Ctrl+R")
        run_action.triggered.connect(lambda: self.runner._on_run())
        run_menu.addAction(run_action)

    @staticmethod
    def _section_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("section_title")
        return lbl

    # ── 信号接线 ──────────────────────────────────────────────────────────

    def _wire_signals(self) -> None:
        self.profile_list.profile_selected.connect(self._on_profile_selected)
        self.profile_bar.profile_selected.connect(self._on_profile_selected)
        self.profile_bar.profiles_changed.connect(self._on_profiles_changed)

        self.stage_tabs.plugin_toggled.connect(self._on_plugin_toggled)
        self.stage_tabs.plugin_reordered.connect(self._on_plugin_reordered)
        self.stage_tabs.param_changed.connect(self._on_param_changed)
        self.stage_tabs.reports_changed.connect(self._on_reports_changed)

        self.yaml_editor.apply_requested.connect(self._on_yaml_apply)
        self.yaml_editor.save_requested.connect(self._on_yaml_save)

        self.runner.run_finished.connect(self._on_run_finished)

        self.manual_panel.match_applied.connect(self._on_match_applied)

    # ── 双通道协调 ────────────────────────────────────────────────────────

    def _refresh_all(self) -> None:
        """profile 切换 / 启动后全量刷新。"""
        self._refresh_profiles()
        self._refresh_config_views()

    def _refresh_profiles(self) -> None:
        infos = self._controller.profile_infos()
        self.profile_list.set_profiles(infos)
        self.profile_bar.refresh(current=self._controller.current_config.profile)

    def _refresh_config_views(self) -> None:
        """按当前 cfg 刷新表单 + yaml 预览（external，不标记脏）。"""
        self.stage_tabs.refresh()
        self.manual_panel.refresh()
        self.yaml_editor.set_text(
            cfg_to_yaml_text(self._controller.current_config), external=True
        )
        self._set_status(f"Profile: {self._controller.current_config.profile}")

    def _sync_yaml_from_form(self) -> None:
        """表单改动 → 实时 yaml 预览（用户未手动编辑 yaml 时）。"""
        if not self.yaml_editor.is_dirty():
            self.yaml_editor.set_text(
                cfg_to_yaml_text(self._controller.current_config), external=True
            )
        self.yaml_editor.set_sync_state(
            is_text_in_sync(self.yaml_editor.text(), self._controller.current_config)
        )

    def _set_status(self, msg: str) -> None:
        self._status.setText(msg)
        self.statusBar().showMessage(msg, 5000)

    # ── 表单 → cfg ────────────────────────────────────────────────────────

    def _on_plugin_toggled(self, stage: str, name: str, enabled: bool) -> None:
        cfg = self._controller.current_config
        names = list(getattr(self._stage_section(cfg, stage), self._stage_attr(stage)))
        if enabled and name not in names:
            names.append(name)
        elif not enabled and name in names:
            names.remove(name)
        set_stage_plugins(cfg, stage, names)
        self._sync_yaml_from_form()

    def _on_plugin_reordered(self, stage: str, names: list[str]) -> None:
        set_stage_plugins(self._controller.current_config, stage, names)
        self._sync_yaml_from_form()

    def _on_param_changed(self, plugin: str, path: str, value: Any) -> None:
        try:
            self._controller.apply_plugin_param(plugin, path, value)
        except Exception as exc:  # noqa: BLE001 — 表单异常不崩溃
            logger.warning("param apply failed: %s", exc)
            return
        self._sync_yaml_from_form()

    def _on_reports_changed(self, reports: list[str]) -> None:
        self._controller.current_config.output.reports = list(reports)
        self._sync_yaml_from_form()

    @staticmethod
    def _stage_section(cfg: Any, stage: str) -> Any:
        return {
            "input": cfg.input,
            "match": cfg.match,
            "beautify": cfg.beautify,
            "output": cfg.output,
            "test": cfg.test,
        }[stage]

    @staticmethod
    def _stage_attr(stage: str) -> str:
        return {
            "input": "plugins",
            "match": "plugins",
            "beautify": "plugins",
            "output": "files",
            "test": "suites",
        }[stage]

    # ── yaml → 表单 ───────────────────────────────────────────────────────

    def _on_yaml_apply(self) -> None:
        """yaml 校验合法后刷新表单（§4 双通道反向）。"""
        text = self.yaml_editor.text()
        try:
            parsed = yaml_text_to_cfg(text)
        except Exception as exc:  # noqa: BLE001 — YamlValidationError
            self.yaml_editor.mark_invalid(str(exc))
            return
        self._controller.set_current_config(parsed)
        self._refresh_config_views()
        self.yaml_editor.set_sync_state(True)
        self._set_status("已应用 yaml → 表单")

    def _on_yaml_save(self) -> None:
        """保存（原子写）：yaml 与表单冲突时提示覆盖确认。"""
        cfg = self._controller.current_config
        if self.yaml_editor.is_dirty():
            if not self.yaml_editor.validate():
                QMessageBox.warning(self, "保存失败", "yaml 非法，无法保存")
                return
            parsed = yaml_text_to_cfg(self.yaml_editor.text())
            if parsed.to_dict() != cfg.to_dict():
                ret = QMessageBox.question(
                    self,
                    "yaml 与表单不同步",
                    "yaml 已手动编辑且与表单不同。保存时以哪一侧为准？\n"
                    "Yes = 以 yaml 为准（覆盖表单）\n"
                    "No = 以表单为准（丢弃 yaml 编辑）",
                )
                if ret == QMessageBox.Yes:
                    self._controller.set_current_config(parsed)
                    self._refresh_config_views()
                else:
                    self.yaml_editor.set_text(cfg_to_yaml_text(cfg), external=True)
        try:
            path = self._controller.save_pipeline()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "保存失败", str(exc))
            return
        self.yaml_editor.set_sync_state(True)
        self._set_status(f"已原子写保存: {path}")

    # ── Profile 动作 ──────────────────────────────────────────────────────

    def _on_profile_selected(self, name: str) -> None:
        try:
            self._controller.load_profile(name)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Profile 加载失败", str(exc))
            return
        self._refresh_config_views()

    def _on_profiles_changed(self) -> None:
        self._refresh_profiles()

    # ── 转换结果 ──────────────────────────────────────────────────────────

    def _on_run_finished(self, report: Any) -> None:
        self.report_view.refresh()
        self.manual_panel.refresh()
        if report.success:
            name = report.project_name or "design"
            self._history.insert(0, f"{name} · {report.pages}页/{report.instances}元件")
            self.history_list.clear()
            self.history_list.addItems(self._history[:20])
        self._set_status("转换完成，结果已刷新")

    def _on_match_applied(self, refdes: str, hdl: str, force_mock: bool) -> None:
        try:
            self._controller.set_manual_match(refdes, hdl or None, force_mock)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "手动匹配失败", str(exc))
            return
        self._sync_yaml_from_form()
        if hdl:
            self._set_status(f"手动匹配: {refdes} → {hdl}（已写入 chip_config_gui.yaml）")
        else:
            self._set_status(f"已撤销 {refdes} 的手动匹配")

    # ── verify 快捷入口 ───────────────────────────────────────────────────

    def _on_verify(self) -> None:
        try:
            lines = self._controller.run_verify()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "verify 失败", str(exc))
            return
        text = "\n".join(lines) if lines else "（无验证输出）"
        QMessageBox.information(self, "verify 结果", text)
