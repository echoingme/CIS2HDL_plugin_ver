"""内置插件 stub 工厂（S3 起仅 beautify 占位；S5 替换为真实现）。

设计依据：``docs/S2-plugin-base-design.md`` §4.3 示例（GndClusterPlugin）。

- input：S2 占位 stub 已由 S3 真实现替换（edif/dsn/cross_ref/pstxnet/pstchip
  编排调用引擎子步骤，见 ``cis2hdl/plugins/input/*.py``），``make_input_stub``
  已移除。
- beautify stub：``beautify`` 记录执行顺序 + enabled 感知，返回 False
  （现有美化逻辑仍在 writer 内部，S5 迁入）。

工厂产出的类会被 pluggy 直接实例化/注册（hookimpl 在类体内装饰）。
"""

from __future__ import annotations

from typing import Any

from .hookspecs import hookimpl
from .context import ConversionContext


def make_beautify_stub(name: str) -> type:
    """构造 beautify 阶段占位插件类（beautify → 顺序记录 + enabled 感知 → False）。"""

    class _BeautifyStub:
        def __init__(self, enabled: bool = False, **kwargs: Any) -> None:
            self.name = name
            self.enabled = bool(enabled)
            self.params = kwargs
            self.order_trace: list[str] = []

        @hookimpl
        def beautify(self, ctx: ConversionContext) -> bool | None:  # noqa: ARG002
            self.order_trace.append(self.name)
            if not self.enabled:
                return False
            return False  # S2 占位：不迁移逻辑；S5 改为 True + 真实调用

        def cleanup(self) -> None:
            self.enabled = False

    _BeautifyStub.__name__ = f"{name.title().replace('_', '')}Plugin"
    return _BeautifyStub
