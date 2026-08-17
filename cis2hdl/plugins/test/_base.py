"""test 阶段插件基类（FR6 / S8：3 个测试插件共用）。

设计依据：``docs/developer-guide.md`` S8 章节 / 方案 v2 §3.6 test 段 /
``docs/plugin-api.md`` §11。铁律：

- **插件是运行器，不重写测试**：现有 ``tests/`` 全部保持；插件只负责
  按 ``test.suites`` 选择并调用 pytest / 检查脚本，返回验证结果摘要。
- **run_verification 返回 ``list[str]``**（验证结果/报告行）；在
  ``convert()`` 主流程内**不调用**（S8 独立入口 ``cis2hdl verify`` 触发）。
- **套件启停双保险**：PluginManager 按 ``spec.name ∈ cfg.test.suites``
  过滤注册（未启用不注册）；插件运行时再查 ``ctx.cfg.test.suites``
  （直接触发钩子链时兜底，防御性检查）。
- **NFR3 独立降级**：单套件运行异常 → warning + 单行 ``[ERROR]`` 返回，
  不阻断其它套件。

返回行格式约定（``cis2hdl verify`` 退出码依据）：
- ``[PASS] <suite>: ...`` 成功
- ``[FAIL] <suite>: ...`` 失败（断言/子进程 rc 非 0）
- ``[ERROR] <suite>: ...`` 异常（NFR3 降级）
- ``[SKIP]/[INFO] <suite>: ...`` 未运行/信息（不判失败）
"""

from __future__ import annotations

import logging
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from ..context import ConversionContext
from ..hookspecs import hookimpl

logger = logging.getLogger(__name__)

__all__ = ["TestSuitePlugin", "parse_pytest_summary", "default_project_root"]

#: 默认 pytest 子进程超时（秒）：全量单测/端到端可能较久。
DEFAULT_TIMEOUT = 1800

#: pytest 输出摘要关键计数（pytest 只打印非零计数；"errors" 以 "error" 前缀匹配）。
_SUMMARY_PATTERNS: dict[str, re.Pattern[str]] = {
    "passed": re.compile(r"(\d+)\s+passed"),
    "failed": re.compile(r"(\d+)\s+failed"),
    "error": re.compile(r"(\d+)\s+error"),
    "skipped": re.compile(r"(\d+)\s+skipped"),
    "xfailed": re.compile(r"(\d+)\s+xfailed"),
    "xpassed": re.compile(r"(\d+)\s+xpassed"),
    "deselected": re.compile(r"(\d+)\s+deselected"),
}


def default_project_root() -> Path:
    """返回仓库根目录（``cis2hdl/plugins/test/`` 上溯 3 级）。"""
    return Path(__file__).resolve().parents[3]


def parse_pytest_summary(output: str) -> dict[str, int]:
    """从 pytest 输出提取关键计数（缺省 0）。

    支持形如 ``1238 passed, 17 skipped`` / ``5 failed, 2 passed`` /
    ``2 errors in 1.1s`` / ``10 deselected`` 的 pytest 摘要行。
    """
    counts: dict[str, int] = {key: 0 for key in _SUMMARY_PATTERNS}
    for key, pattern in _SUMMARY_PATTERNS.items():
        match = pattern.search(output or "")
        if match:
            counts[key] = int(match.group(1))
    return counts


def format_pytest_summary(counts: dict[str, int]) -> str:
    """把计数 dict 格式化为 ``"N passed, M failed"`` 风格摘要（零计数省略）。"""
    parts: list[str] = []
    for key in ("passed", "failed", "error", "skipped", "xfailed", "xpassed", "deselected"):
        if counts.get(key):
            parts.append(f"{counts[key]} {key}")
    return ", ".join(parts) if parts else "0 passed"


class TestSuitePlugin:
    """测试套件插件基类（run_verification 钩子，S8）。

    子类只需设置 ``name`` / ``description`` 并实现
    ``_build_command() -> list[str]``（pytest 目标路径/参数）；非 pytest
    套件（如 qa_package）覆盖 ``_run_checks(ctx)``。
    """

    __test__ = False  # 名称以 Test 开头，显式阻止 pytest 收集为测试类

    name: str = ""
    description: str = ""
    timeout: int = DEFAULT_TIMEOUT

    def __init__(
        self,
        suites: list[str] | None = None,
        root_dir: str | None = None,
        **params: Any,
    ) -> None:
        """构造。

        Args:
            suites: ``cfg.test.suites``（resolve_params 注入；运行时以
                ``ctx.cfg.test.suites`` 为准）。
            root_dir: 仓库根目录（默认自动探测；测试可显式注入）。
            **params: 其它构造参数（qa_package 支持 ``delivery_dir``）。
        """
        self.suites: list[str] = list(suites) if suites else []
        self.root_dir: Path = Path(root_dir) if root_dir else default_project_root()
        self.params: dict[str, Any] = dict(params)
        self.last_command: list[str] = []
        """最近一次子进程命令（测试/诊断用）。"""
        self.last_elapsed: float = 0.0
        """最近一次运行耗时（秒）。"""

    # ── 子类契约 ─────────────────────────────────────────────────────

    def _build_command(self) -> list[str]:
        """返回 pytest 子进程参数（不含 ``python -m pytest`` 前缀）。

        子类实现：返回目标测试路径/额外参数（如 ``["tests/unit"]``）。
        """
        raise NotImplementedError

    def _run_checks(self, ctx: ConversionContext) -> list[str]:
        """运行本套件并返回结果行（子类可覆盖非 pytest 套件）。"""
        args = self._build_command()
        return self._run_pytest(args)

    # ── 套件启停 ─────────────────────────────────────────────────────

    def _suite_enabled(self, ctx: ConversionContext) -> bool:
        """套件是否启用：``ctx.cfg.test.suites`` 含本插件名。

        管理器已按名过滤注册（未启用不注册）；此处为直接触发钩子链时的
        防御性检查（双保险）。
        """
        if ctx is None or ctx.cfg is None:
            return False
        return self.name in ctx.cfg.test.suites

    # ── 钩子实现 ─────────────────────────────────────────────────────

    @hookimpl
    def run_verification(self, ctx: ConversionContext) -> list[str] | None:
        """run_verification 钩子（S8 真实现）。

        - 套件未启用（``ctx.cfg.test.suites`` 不含本插件名）→ ``None``
          （pluggy 丢弃 None，不产生结果行）。
        - 运行异常（子进程超时等）→ warning + 单行 ``[ERROR]``（NFR3
          独立降级，不阻断其它套件）。
        """
        if not self._suite_enabled(ctx):
            return None
        try:
            return self._run_checks(ctx)
        except Exception as exc:  # noqa: BLE001 — NFR3 独立降级
            logger.warning("test 插件 %s 运行失败: %s", self.name, exc)
            return [f"[ERROR] {self.name}: {exc}"]

    # ── pytest 运行器 ────────────────────────────────────────────────

    def _run_pytest(self, args: list[str]) -> list[str]:
        """运行 ``python -m pytest <args> -q --tb=short``（cwd=项目根）。

        返回单行结果摘要；rc=0 且无 failed/error 计数 → ``[PASS]``。
        """
        cmd = [sys.executable, "-m", "pytest", *args, "-q", "--tb=short"]
        self.last_command = cmd
        start = time.monotonic()
        proc = self._subprocess_run(cmd, cwd=str(self.root_dir), timeout=self.timeout)
        self.last_elapsed = time.monotonic() - start
        output = (proc.stdout or "") + "\n" + (proc.stderr or "")
        counts = parse_pytest_summary(output)
        ok = proc.returncode == 0 and counts["failed"] == 0 and counts["error"] == 0
        status = "PASS" if ok else "FAIL"
        summary = format_pytest_summary(counts)
        return [
            f"[{status}] {self.name}: pytest {' '.join(args)} → {summary} "
            f"(rc={proc.returncode}, {self.last_elapsed:.1f}s)",
        ]

    def _subprocess_run(
        self, cmd: list[str], cwd: str, timeout: int,
    ) -> subprocess.CompletedProcess[str]:
        """子进程执行（测试可 monkeypatch 以伪造 pytest 输出）。"""
        return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)

    # ── 可逆卸载（Cordis unload 理念） ───────────────────────────────

    def cleanup(self) -> None:
        """复位状态（幂等）。"""
        self.suites = []
        self.params = {}
