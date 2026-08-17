"""manual_overrides 手动干预插件（FR3；S4 真委托）。

委托 ``engine.run_manual_overrides()``（= ``_apply_phase14_matching``：
D4 电源 IC 自动匹配 + D3 chip_config/manual_matches 手动匹配覆盖 +
export_unmatched 导出），与 legacy 行为等价（FR9）。

ctx 契约：
- 写 ``ctx.manual_overrides``（dict 摘要：本次应用了什么）。
- 原地更新 ``ctx.matches``（match_results 列表项被覆盖/增强——只读守卫只
  保护字段赋值，不保护可变对象内部修改，合法）。

配置源（NFR5 yaml 权威）：
- ``ctx.cfg.match.manual_overrides.file`` → 全局 ``Config.routing`` 的
  ``chip_config`` / ``manual_matches``（仅非空覆盖；空 = 保持现状）。
- ``ctx.cfg.match.manual_overrides.export_unmatched`` → ``export_unmatched``。
- power_ic 开关/配置在 ``beautify.params.power_ic``（``to_routing_config()``
  已携带，无需额外同步）。

默认 profile **不启用**本插件（``match.plugins`` 不含 manual_overrides）→
``apply_manual_overrides`` 钩子无人处理 → 引擎回退 legacy
``_apply_phase14_matching``（行为一致）；用户启用后由本插件接管。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from cis2hdl.core.config import config as _global_config

from ..hookspecs import hookimpl
from ..context import ConversionContext
from ..spec import PluginSpec

logger = logging.getLogger(__name__)

__all__ = ["ManualOverridesPlugin", "PLUGIN"]


class ManualOverridesPlugin:
    """手动干预插件：chip_config/manual_matches 应用 + power_ic 规则（FR3）。"""

    name = "manual_overrides"
    description = (
        "手动干预（FR3）：应用 chip_config/manual_matches 手动匹配 + "
        "D4 power_ic 自动匹配 + export_unmatched 导出（委托 "
        "engine._apply_phase14_matching，与 legacy 等价）"
    )

    def __init__(self, engine: Any = None, **kwargs: Any) -> None:
        self.engine = engine
        self.params = kwargs

    @hookimpl
    def apply_manual_overrides(self, ctx: ConversionContext) -> bool | None:
        """手动干预钩子：前置产物就绪后委托 legacy 阶段，写 ctx.manual_overrides。"""
        if ctx is None:
            return False
        if ctx.ir is None or ctx.hdl_db is None:
            return False
        if not ctx.matches:
            return False  # 匹配阶段未产出 → 无覆盖对象
        if self.engine is None:
            return False
        input_path: Path = ctx.input_files[0] if ctx.input_files else Path(".")
        self._sync_config(ctx)
        self.engine.run_manual_overrides(
            ctx.ir, ctx.hdl_db, ctx.matches, ctx.report, input_path,
        )
        ctx.manual_overrides = self._summary()
        return True

    def _sync_config(self, ctx: ConversionContext) -> None:
        """yaml manual_overrides → 全局 Config（仅非空覆盖；NFR5 yaml 权威）。"""
        mo = ctx.cfg.match.manual_overrides
        rc = _global_config.routing
        if mo.file:
            rc.chip_config = mo.file
            rc.manual_matches = mo.file
        if mo.export_unmatched:
            rc.export_unmatched = mo.export_unmatched

    def _summary(self) -> dict[str, Any]:
        rc = _global_config.routing
        return {
            "applied": True,
            "chip_config": rc.chip_config,
            "manual_matches": rc.manual_matches,
            "export_unmatched": rc.export_unmatched,
            "power_ic_enabled": bool(rc.power_ic.enabled),
        }

    def cleanup(self) -> None:
        self.engine = None
        self.params = {}


PLUGIN = PluginSpec(
    name="manual_overrides",
    stage="match",
    description=ManualOverridesPlugin.description,
    cls=ManualOverridesPlugin,
    module=__name__,
    param_fields=(),
    writes_keys=("matches", "manual_overrides"),
    requires=("ir", "hdl_db", "matches"),
    builtin=True,
)
