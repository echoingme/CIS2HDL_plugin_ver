"""S9 GUI 测试 — cli gui 子命令降级（无 PySide6 优雅提示，非 traceback）。

PySide6 已安装时跳过（无法在无显示环境测试真实 GUI 启动）。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from cis2hdl.cli import gui_main, main

REPO_ROOT = Path(__file__).resolve().parents[2]


def _pyside6_missing() -> bool:
    from cis2hdl.gui.v2.app import HAS_PYSIDE6

    return not HAS_PYSIDE6


@pytest.mark.skipif(not _pyside6_missing(), reason="PySide6 已安装，跳过降级测试")
def test_gui_main_degradation(capsys) -> None:
    rc = gui_main([])
    assert rc == 1
    err = capsys.readouterr().err
    assert "PySide6" in err
    assert "Traceback" not in err


@pytest.mark.skipif(not _pyside6_missing(), reason="PySide6 已安装，跳过降级测试")
def test_main_gui_subcommand_degradation(capsys) -> None:
    rc = main(["gui"])
    assert rc == 1
    err = capsys.readouterr().err
    assert "PySide6" in err


@pytest.mark.skipif(not _pyside6_missing(), reason="PySide6 已安装，跳过降级测试")
def test_main_no_args_degradation(capsys) -> None:
    rc = main([])
    assert rc == 1
    err = capsys.readouterr().err
    assert "PySide6" in err


@pytest.mark.skipif(not _pyside6_missing(), reason="PySide6 已安装，跳过降级测试")
def test_python_m_cis2hdl_gui_subprocess() -> None:
    """``python -m cis2hdl gui`` 无 PySide6 → 退出码 1 + 友好提示。"""
    proc = subprocess.run(
        [sys.executable, "-m", "cis2hdl", "gui"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 1
    assert "PySide6" in (proc.stdout + proc.stderr)
    assert "Traceback" not in proc.stderr


def test_version_still_works(capsys) -> None:
    rc = main(["--version"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "CIS2HDL" in out
