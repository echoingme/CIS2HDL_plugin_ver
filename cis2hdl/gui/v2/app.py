"""S9 GUI v2 启动入口 — run_gui()（PySide6 优雅降级）。

设计依据：``docs/gui-design.md`` 铁律（yaml 权威，GUI 编辑/执行入口）。
测试环境（无 PySide6）也可 import 本模块；仅调用 :func:`run_gui` 时
抛出友好 :class:`RuntimeError`（CLI 捕获后提示安装依赖，非 traceback）。
"""

from __future__ import annotations

import logging
import sys

try:
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QApplication

    HAS_PYSIDE6 = True
    _IMPORT_ERROR: str | None = None
except ImportError as _exc:  # pragma: no cover — 无 PySide6 环境
    HAS_PYSIDE6 = False
    _IMPORT_ERROR = str(_exc)

from cis2hdl import __version__

from ..colors import FontSize, Fonts

__all__ = ["run_gui", "HAS_PYSIDE6"]


def run_gui() -> int:
    """启动 CIS2HDL 工程工作台（S9 GUI）；返回 QApplication.exec 退出码。

    Raises:
        RuntimeError: 未安装 PySide6 时（CLI 捕获并友好提示）。
    """
    if not HAS_PYSIDE6:
        raise RuntimeError(
            "CIS2HDL GUI 需要 PySide6，但当前环境未安装"
            + (f"（{_IMPORT_ERROR}）" if _IMPORT_ERROR else "")
            + "\n请先安装：pip install PySide6"
        )

    # 延迟导入（main_window 依赖 PySide6；无 PySide6 时仅本模块可 import）
    from PySide6.QtWidgets import QApplication
    from .main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("CIS2HDL")
    app.setOrganizationName("CIS2HDL")

    ui_family = Fonts.UI.split(",")[0].strip().strip('"').strip("'")
    app.setFont(QFont(ui_family, FontSize.SM))

    window = MainWindow()
    window.setWindowTitle(f"CIS2HDL v{__version__} — 工程工作台")
    window.show()
    logging.info("CIS2HDL GUI v2 started")
    return app.exec()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        sys.exit(run_gui())
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
