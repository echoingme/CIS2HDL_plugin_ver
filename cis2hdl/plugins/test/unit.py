"""unit 测试插件（FR6 / S8）：pytest 运行 ``tests/unit/``。

设计依据：``docs/developer-guide.md`` S8 章节。套件语义（S8 决策）：

- ``unit`` = 单元测试套件（``pytest tests/unit/``，当前 1146 用例），
  快速、确定性，无 e2e/slow 标记。
- 集成测试（``tests/integration/``）归 ``e2e`` 套件（多模块交互/真实管线
  验证，见 ``cis2hdl/plugins/test/e2e.py``）。
"""

from __future__ import annotations

from ..spec import PluginSpec
from ._base import TestSuitePlugin

__all__ = ["UnitPlugin", "PLUGIN"]


class UnitPlugin(TestSuitePlugin):
    """单元测试套件（pytest tests/unit/）。"""

    name = "unit"
    description = "单元测试套件（pytest tests/unit/，快速确定性）"

    def _build_command(self) -> list[str]:
        return [str(self.root_dir / "tests" / "unit")]


PLUGIN = PluginSpec(
    name="unit",
    stage="test",
    description=UnitPlugin.description,
    cls=UnitPlugin,
    module=__name__,
    param_section="",
    param_fields=("suites",),
    writes_keys=(),
    requires=(),
    builtin=True,
)
