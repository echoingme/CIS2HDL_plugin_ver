"""test 阶段插件包（FR6）。

S2：仅白名单 spec（``cls=None``，不注册 hookimpl）；S8 接入
run_verification。``_SPECS`` 汇总（供 discover 读取）。
"""

from __future__ import annotations

from ..spec import PluginSpec

_SPECS: list[PluginSpec] = [
    PluginSpec(
        name="unit",
        stage="test",
        description="单元测试套件（S8 接入）",
        cls=None,
        module="cis2hdl.plugins.test",
    ),
    PluginSpec(
        name="e2e",
        stage="test",
        description="端到端测试套件（S8 接入）",
        cls=None,
        module="cis2hdl.plugins.test",
    ),
    PluginSpec(
        name="qa_package",
        stage="test",
        description="QA 交付包测试套件（S8 接入）",
        cls=None,
        module="cis2hdl.plugins.test",
    ),
]

__all__ = ["_SPECS"]
