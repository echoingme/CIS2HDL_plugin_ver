"""test 阶段插件包（FR6）。

S2：仅白名单 spec（``cls=None``，不注册 hookimpl）；S8 真实现——
``unit.py`` / ``e2e.py`` / ``qa_package.py`` 三个独立模块各声明 ``PLUGIN``
（cls=真实现类），由 discover 逐模块扫描；本包 ``_SPECS`` 保持空（白名单
占位已退役，避免与模块 PLUGIN 去重冲突）。
"""

from __future__ import annotations

from ..spec import PluginSpec

#: 白名单占位已退役（S8 真实现入独立模块）；保留空列表以兼容读取约定。
_SPECS: list[PluginSpec] = []

__all__ = ["_SPECS"]
