"""S9 GUI v2 ConversionRunner — 运行 + 进度 + 日志（§2 ③）。

设计依据：``docs/gui-design.md`` §2 转换执行区：运行按钮 + 6 阶段进度条
（Diagnose→Parse→Scan→Match→Validate→Generate）+ 日志流（实时）+
阶段耗时统计。转换在 QThread 中执行（不阻塞 UI）。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QThread, Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..colors import Colors, FontSize, Spacing, rgba
from .qss import STYLE_RUNNER

logger = logging.getLogger(__name__)

__all__ = ["ConversionRunner"]

#: 6 阶段展示序（引擎 progress 回调 stage 名 → 展示标签）。
STAGE_ORDER = [
    ("diagnose", "Diagnose"),
    ("parse", "Parse"),
    ("scan", "Scan"),
    ("match", "Match"),
    ("validate", "Validate"),
    ("generate", "Generate"),
]


class _ConversionWorker(QObject):
    """后台转换执行器（QThread 内运行；信号回传 UI 线程）。"""

    progress = Signal(str, float, str)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, controller: Any, cfg: Any) -> None:
        super().__init__()
        self._controller = controller
        self._cfg = cfg

    def run(self) -> None:
        try:
            report = self._controller.run_conversion(self._cfg, self._on_progress)
        except Exception as exc:  # noqa: BLE001 — UI 线程捕获
            self.failed.emit(str(exc))
            return
        self.finished.emit(report)

    def _on_progress(self, stage: str, pct: float, msg: str) -> None:
        self.progress.emit(stage, float(pct), str(msg))


class ConversionRunner(QWidget):
    """运行按钮 + 6 阶段进度 + 日志流 + 阶段耗时。"""

    run_finished = Signal(object)
    run_started = Signal()

    def __init__(self, controller: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("v2_runner")
        self.setStyleSheet(STYLE_RUNNER)
        self._controller = controller
        self._thread: QThread | None = None
        self._worker: _ConversionWorker | None = None
        self._stage_labels: dict[str, QLabel] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(Spacing.BASE, Spacing.MD, Spacing.BASE, Spacing.MD)
        layout.setSpacing(Spacing.SM)

        # ── 输入/输出行 ──────────────────────────────────────────────
        io_row = QHBoxLayout()
        io_row.setSpacing(Spacing.SM)
        self._input_edit = QLineEdit()
        self._input_edit.setPlaceholderText("选择输入文件（.dsn/.edf）…")
        self._input_edit.textChanged.connect(self._on_input_changed)
        input_btn = QPushButton("浏览")
        input_btn.setFixedHeight(28)
        input_btn.clicked.connect(self._pick_input)
        io_row.addWidget(QLabel("输入"))
        io_row.addWidget(self._input_edit, 2)
        io_row.addWidget(input_btn)

        self._output_edit = QLineEdit("output")
        self._output_edit.setPlaceholderText("输出目录（缺省 engine.output_dir）")
        self._output_edit.textChanged.connect(self._on_output_changed)
        output_btn = QPushButton("浏览")
        output_btn.setFixedHeight(28)
        output_btn.clicked.connect(self._pick_output)
        io_row.addWidget(QLabel("输出"))
        io_row.addWidget(self._output_edit, 1)
        io_row.addWidget(output_btn)

        self._run_btn = QPushButton("▶ 运行转换")
        self._run_btn.setObjectName("primary")
        self._run_btn.setFixedHeight(30)
        self._run_btn.clicked.connect(self._on_run)
        io_row.addWidget(self._run_btn)
        layout.addLayout(io_row)

        # ── 6 阶段进度条 ────────────────────────────────────────────
        stages_row = QHBoxLayout()
        stages_row.setSpacing(Spacing.SM)
        self._overall = QProgressBar()
        self._overall.setRange(0, 100)
        self._overall.setValue(0)
        stages_row.addWidget(self._overall, 2)
        for stage_key, label in STAGE_ORDER:
            lbl = QLabel(label)
            lbl.setObjectName("stage_label")
            lbl.setAlignment(Qt.AlignCenter)
            stages_row.addWidget(lbl)
            self._stage_labels[stage_key] = lbl
        layout.addLayout(stages_row)

        # ── 日志流 ──────────────────────────────────────────────────
        self._log = QPlainTextEdit()
        self._log.setObjectName("log_content")
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(150)
        self._log.setMinimumHeight(90)
        layout.addWidget(self._log, 1)

        self._set_stage_highlight("")

    # ── 输入/输出 ────────────────────────────────────────────────────────

    def _pick_input(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "选择输入文件", "", "CIS 工程 (*.dsn *.edf);;All Files (*)"
        )
        if path:
            self._input_edit.setText(path)

    def _pick_output(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if path:
            self._output_edit.setText(path)

    def _on_input_changed(self, text: str) -> None:
        self._controller.set_input_path(Path(text) if text.strip() else None)

    def _on_output_changed(self, text: str) -> None:
        if text.strip():
            self._controller.set_output_dir(Path(text.strip()))

    # ── 运行 ─────────────────────────────────────────────────────────────

    def _on_run(self) -> None:
        if self._thread is not None:
            self.log("转换正在进行中…")
            return
        cfg = self._controller.current_config
        self._overall.setValue(0)
        self.log("── 转换开始 ──")
        self._run_btn.setEnabled(False)
        self.run_started.emit()

        self._thread = QThread(self)
        self._worker = _ConversionWorker(self._controller, cfg)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def _on_progress(self, stage: str, pct: float, msg: str) -> None:
        int_pct = int(pct * 100)
        self._overall.setValue(int_pct)
        self._set_stage_highlight(stage)
        self.log(f"[{stage}] {msg}")

    def _on_finished(self, report: Any) -> None:
        self._cleanup_thread()
        self._run_btn.setEnabled(True)
        self._set_stage_highlight("")
        if report.success:
            self._overall.setValue(100)
            self.log(
                f"✔ 转换完成：{report.pages} 页 / {report.instances} 元件 / "
                f"{report.nets} 网络 / {len(report.output_files)} 输出文件"
            )
        else:
            self.log(f"✘ 转换结束（{len(report.errors)} 错误 / {len(report.warnings)} 警告）")
        self._log_timings(report)
        self.run_finished.emit(report)

    def _on_failed(self, msg: str) -> None:
        self._cleanup_thread()
        self._run_btn.setEnabled(True)
        self._set_stage_highlight("")
        self.log(f"✘ 转换失败：{msg}")

    def _cleanup_thread(self) -> None:
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait(3000)
            self._thread = None
        self._worker = None

    # ── 展示辅助 ─────────────────────────────────────────────────────────

    def _set_stage_highlight(self, current: str) -> None:
        for key, lbl in self._stage_labels.items():
            if key == current:
                lbl.setStyleSheet(
                    "QLabel#stage_label { color: %s; font-weight: bold;"
                    " background-color: %s; border-radius: 4px; padding: 2px 6px; }"
                    % (Colors.ACCENT, rgba(Colors.ACCENT, 0.12))
                )
            else:
                lbl.setStyleSheet(
                    "QLabel#stage_label { color: %s; font-size: %dpx; }"
                    % (Colors.TEXT_MUTED, FontSize.XXS)
                )

    def _log_timings(self, report: Any) -> None:
        timings = getattr(report, "stage_timings", None) or {}
        if not timings:
            return
        parts = []
        for key, label in STAGE_ORDER:
            if key in timings:
                parts.append(f"{label}={timings[key]:.2f}s")
        if parts:
            total = getattr(report, "total_elapsed", 0.0) or 0.0
            self.log(f"⏱ 阶段耗时：{'  '.join(parts)}（总 {total:.2f}s）")

    def log(self, msg: str) -> None:
        self._log.appendPlainText(msg)
        sb = self._log.verticalScrollBar()
        if sb is not None:
            sb.setValue(sb.maximum())
