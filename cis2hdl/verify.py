"""S8 verify 编排器（FR6）— 运行 ``test.suites`` 指定的验证套件。

设计依据：``docs/developer-guide.md`` S8 章节 / 方案 v2 §3.3 run_verification
hook / §3.6 test 段。铁律：

- **独立入口**：``run_verification`` 只在 ``cis2hdl verify`` 触发，
  ``convert()`` 主流程内不调用（S2 设计）。
- **套件选择**：``suites=None`` → ``cfg.test.suites`` 全部；否则仅运行
  指定套件（深拷贝 cfg 后覆盖 ``test.suites``，不污染调用方配置）。
- **ctx 契约**：``ConversionContext(cfg=cfg)`` 传入钩子链；测试插件只读
  ``ctx.cfg``（``writes_keys=()``，不写 ctx）。
- **失败判定**：任一结果行以 ``[FAIL]`` / ``[ERROR]`` 开头 → 整体失败
  （``VerificationReport.failed=True``）；``[SKIP]``/``[INFO]``/``[PASS]``
  不判失败。
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TYPE_CHECKING

from .plugins.context import ConversionContext
from .plugins.manager import PluginManager, build_plugin_manager

if TYPE_CHECKING:
    from .core.pipeline_config import PipelineConfig

__all__ = ["VerificationRunner", "VerificationReport", "list_test_suites"]


@dataclass
class VerificationReport:
    """验证结果：报告行 + 是否失败。"""

    lines: list[str] = field(default_factory=list)
    """报告行（[PASS]/[FAIL]/[ERROR]/[SKIP]/[INFO] 前缀）。"""
    failed: bool = False
    """整体是否失败（任一 [FAIL]/[ERROR] 行或插件降级）。"""

    @property
    def ok(self) -> bool:
        return not self.failed


def list_test_suites() -> list[str]:
    """返回已发现 test 插件名（``cis2hdl verify --suite`` 候选）。"""
    pm = PluginManager()
    return sorted(s.name for s in pm.list_plugins("test"))


class VerificationRunner:
    """S8 验证编排器：构建 test 插件链并执行 ``run_verification``。"""

    def __init__(
        self,
        cfg: "PipelineConfig",
        *,
        plugins_dir: Path | None = None,
        engine: Any = None,
    ) -> None:
        """构造。

        Args:
            cfg: S1 PipelineConfig（``test.suites`` 控制套件选择）。
            plugins_dir: 插件扫描根（默认包内；测试可注入）。
            engine: 引擎引用（test 插件当前不使用；预留）。
        """
        self.cfg = cfg
        self.plugins_dir = plugins_dir
        self.engine = engine
        self.pm: PluginManager | None = None
        """最近一次构建的 PluginManager（诊断/测试用）。"""

    def run(self, suites: list[str] | None = None) -> VerificationReport:
        """执行验证，返回 :class:`VerificationReport`。

        Args:
            suites: 仅运行指定套件（``unit``/``e2e``/``qa_package``）；
                ``None`` → ``cfg.test.suites`` 全部。未知套件 → 失败报告。
        """
        run_cfg = self._effective_cfg(suites)
        self.pm = build_plugin_manager(
            run_cfg, plugins_dir=self.plugins_dir, engine=self.engine,
        )

        # 未知套件校验（针对 --suite 显式请求；缺省不校验）。
        if suites is not None:
            known = {s.name for s in self.pm.list_plugins("test")}
            unknown = sorted(set(suites) - known)
            if unknown:
                return VerificationReport(
                    lines=[f"[ERROR] verify: 未知测试套件: {unknown} "
                           f"（可选: {sorted(known)}）"],
                    failed=True,
                )

        ctx = ConversionContext(cfg=run_cfg)
        raw = self.pm.hook.run_verification(ctx=ctx) or []
        lines: list[str] = []
        for group in raw:
            if group:
                lines.extend(group)
        if not lines:
            lines.append(
                "[INFO] verify: 没有启用的测试套件（pipeline.yaml test.suites 为空）"
            )

        failed = any(
            line.startswith("[FAIL]") or line.startswith("[ERROR]")
            for line in lines
        )
        for name, err in self.pm.degraded:
            lines.append(f"[ERROR] 插件降级 {name}: {err}")
            failed = True
        return VerificationReport(lines=lines, failed=failed)

    def _effective_cfg(self, suites: list[str] | None) -> "PipelineConfig":
        """返回实际执行的配置（深拷贝，避免污染调用方）。"""
        if suites is None:
            return self.cfg
        run_cfg = copy.deepcopy(self.cfg)
        run_cfg.test.suites = list(suites)
        return run_cfg
