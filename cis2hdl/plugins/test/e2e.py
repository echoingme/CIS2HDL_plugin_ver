"""e2e 测试插件（FR6 / S8）：pytest 运行 ``tests/e2e/`` + ``tests/integration/``。

设计依据：``docs/developer-guide.md`` S8 章节。套件语义（S8 决策）：

- ``e2e`` = 端到端 + 集成测试套件（``pytest tests/e2e/ tests/integration/``，
  当前 82 + 27 = 109 用例），覆盖全链路转换（真实 DSN/EDF fixture）、
  插件 vs legacy 字节等价、多模块交互——均含 e2e/slow/integration 标记，
  运行较慢（真实解析 + 完整管线）。
- 纯单元测试（``tests/unit/``）归 ``unit`` 套件。
"""

from __future__ import annotations

from ..spec import PluginSpec
from ._base import TestSuitePlugin

__all__ = ["E2EPlugin", "PLUGIN"]


class E2EPlugin(TestSuitePlugin):
    """端到端 + 集成测试套件（pytest tests/e2e/ tests/integration/）。"""

    name = "e2e"
    description = "端到端 + 集成测试套件（pytest tests/e2e/ tests/integration/）"

    def _build_command(self) -> list[str]:
        return [
            str(self.root_dir / "tests" / "e2e"),
            str(self.root_dir / "tests" / "integration"),
        ]


PLUGIN = PluginSpec(
    name="e2e",
    stage="test",
    description=E2EPlugin.description,
    cls=E2EPlugin,
    module=__name__,
    param_section="",
    param_fields=("suites",),
    writes_keys=(),
    requires=(),
    builtin=True,
)
