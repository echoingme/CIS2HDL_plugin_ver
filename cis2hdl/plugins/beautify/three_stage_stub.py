"""three_stage_stub 美化插件（FR4 / Phase XV R5；S5 真实现）。

对应 writer 模块：``cis2hdl/core/writer/wire_layout.py``（布线器 stub 走
三段式 —— ``routing.three_stage_stub=true`` 时每条 stub 由引出段+垂直段+
接入段组成；``_stub_lead_cfg`` / ``_three_stage_enabled`` 读取路由配置）。
CSAWriter 布线时经 router 读取该配置，顺序由 writer 内部保证。

参数源 = RoutingConfig **顶层**（param_section=""，S1 K1 复用）。
S5 语义：``beautify.params.three_stage_stub`` 为 enabled 门（默认 True）。
启用 → 应用完整 ``beautify.params``（含顶层 ``routing.mode=detour`` 等
max-beauty 字段）到全局 ``config.routing``；返回 True。
"""

from __future__ import annotations

from ..spec import PluginSpec
from ._base import BeautifyPlugin

__all__ = ["ThreeStageStubPlugin", "PLUGIN"]


class ThreeStageStubPlugin(BeautifyPlugin):
    """三段式 stub（Phase XV R5 迁移；wire_layout 布线编排）。"""

    name = "three_stage_stub"
    description = (
        "三段式 stub（默认开）：writer wire_layout 布线器编排"
        "（引出段+垂直段+接入段三段式 stub，stub_lead 控制引出距离）"
    )

    def _enabled_from_params(self, params: dict) -> bool:
        """enabled 门 = 顶层 ``routing.three_stage_stub``（默认 True）。"""
        return bool(params.get("three_stage_stub", False))


PLUGIN = PluginSpec(
    name="three_stage_stub",
    stage="beautify",
    description=ThreeStageStubPlugin.description,
    cls=ThreeStageStubPlugin,
    module=__name__,
    param_section="",
    param_fields=("three_stage_stub",),
    writes_keys=("routed_nets",),
    requires=("ir", "matches"),
)
