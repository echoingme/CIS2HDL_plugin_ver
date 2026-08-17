"""qa_package 测试插件（FR6 / S8）：QA 交付包检查。

设计依据：``docs/developer-guide.md`` S8 章节。语义（S8 决策）：

- 主检查：调用 ``scripts/verify_phaseXXI_package.py <交付目录>``（Phase XXI
  QA 交付包验证清单：mock cell 数/引脚重叠/字号/off-grid/文本碰撞/版本
  目录等），解析 ``[PASS]/[FAIL]`` 计数返回结果行。
- 交付目录来源（优先级）：``ctx.output_dir``（convert 输出目录）→ 构造
  参数 ``delivery_dir`` → 项目根常见目录（``output_verify_final`` /
  ``output``）。
- 无交付目录时执行**等价检查**（不判失败）：核验项目基础文件
  （pipeline.yaml / tests 目录 / 检查脚本）齐全并返回 ``[SKIP]`` +
  ``[INFO]``；显式指定交付目录但缺失 → ``[FAIL]``（用户明确要验证的包
  不存在）。
"""

from __future__ import annotations

import re
import sys
import time
from pathlib import Path
from typing import Any

from ..context import ConversionContext
from ..spec import PluginSpec
from ._base import TestSuitePlugin

__all__ = ["QaPackagePlugin", "PLUGIN"]

#: 等价结构检查项（无交付目录时核验）。
_STRUCTURAL_CHECKS: tuple[tuple[str, str], ...] = (
    ("pipeline.yaml", "pipeline.yaml"),
    ("tests/unit", "tests/unit"),
    ("tests/e2e", "tests/e2e"),
    ("tests/integration", "tests/integration"),
    ("scripts/verify_phaseXXI_package.py", "scripts/verify_phaseXXI_package.py"),
)

#: 常见交付目录（项目根相对路径，按优先级）。
_COMMON_DELIVERY_DIRS: tuple[str, ...] = ("output_verify_final", "output")


class QaPackagePlugin(TestSuitePlugin):
    """QA 交付包检查（scripts/verify_phaseXXI_package.py 或等价检查）。"""

    name = "qa_package"
    description = "QA 交付包检查（scripts/verify_phaseXXI_package.py 或等价结构检查）"

    def _find_delivery_dir(self, ctx: ConversionContext) -> Path | None:
        """定位交付目录（ctx.output_dir → 构造参数 delivery_dir → 常见目录）。"""
        candidates: list[Path | None] = [
            ctx.output_dir if ctx and ctx.output_dir else None,
            Path(self.params["delivery_dir"]) if self.params.get("delivery_dir") else None,
        ]
        for rel in _COMMON_DELIVERY_DIRS:
            candidates.append(self.root_dir / rel)
        for cand in candidates:
            if cand is not None and cand.is_dir():
                return cand
        # 显式指定但不存在：返回 Path 以便上层报 [FAIL]（与"未指定"区分）。
        if self.params.get("delivery_dir"):
            return Path(str(self.params["delivery_dir"]))
        if ctx and ctx.output_dir:
            return Path(str(ctx.output_dir))
        return None

    def _run_checks(self, ctx: ConversionContext) -> list[str]:
        """运行 QA 检查并返回结果行（覆盖基类非 pytest 路径）。"""
        delivery = self._find_delivery_dir(ctx)
        script = self.root_dir / "scripts" / "verify_phaseXXI_package.py"
        if not script.exists():
            return [f"[FAIL] qa_package: 检查脚本缺失: {script}"]
        if delivery is None:
            return self._structural_check(None)
        if not delivery.is_dir():
            return [
                f"[FAIL] qa_package: 交付目录不存在: {delivery}",
                "[INFO] qa_package: 可先运行 convert 生成输出，或用 delivery_dir 参数指定交付目录",
            ]
        cmd = [sys.executable, str(script), str(delivery)]
        self.last_command = cmd
        start = time.monotonic()
        proc = self._subprocess_run(cmd, cwd=str(self.root_dir), timeout=self.timeout)
        self.last_elapsed = time.monotonic() - start
        output = (proc.stdout or "") + "\n" + (proc.stderr or "")
        n_pass = len(re.findall(r"\[PASS\]", output))
        n_fail = len(re.findall(r"\[FAIL\]", output))
        ok = proc.returncode == 0 and n_fail == 0
        status = "PASS" if ok else "FAIL"
        lines = [
            f"[{status}] qa_package: {script.name} {delivery} → "
            f"{n_pass} PASS / {n_fail} FAIL (rc={proc.returncode}, {self.last_elapsed:.1f}s)",
        ]
        # 附加失败明细（最多 10 行），便于用户定位。
        fail_lines = [ln for ln in output.splitlines() if ln.startswith("[FAIL]")]
        lines.extend(fail_lines[:10])
        if not ok and not fail_lines:
            lines.append(f"[ERROR] qa_package: 检查脚本异常退出: {proc.stderr.strip()[-500:]}")
        return lines

    def _structural_check(self, delivery: Path | None) -> list[str]:
        """等价检查：无交付目录时核验项目基础文件（不判失败）。"""
        missing = [
            label for label, rel in _STRUCTURAL_CHECKS if not (self.root_dir / rel).exists()
        ]
        if missing:
            return [f"[FAIL] qa_package: 等价结构检查缺失 {sorted(missing)}"]
        note = (
            "交付目录未指定（ctx.output_dir 为空、未发现 "
            "output_verify_final/output）"
            if delivery is None
            else f"交付目录不存在: {delivery}"
        )
        return [
            f"[SKIP] qa_package: 未运行 verify_phaseXXI_package.py（{note}）",
            "[INFO] qa_package: 等价结构检查通过（pipeline.yaml / tests/unit / "
            "tests/e2e / tests/integration / 检查脚本均在）",
        ]


PLUGIN = PluginSpec(
    name="qa_package",
    stage="test",
    description=QaPackagePlugin.description,
    cls=QaPackagePlugin,
    module=__name__,
    param_section="",
    param_fields=("suites",),
    writes_keys=(),
    requires=(),
    builtin=True,
)
