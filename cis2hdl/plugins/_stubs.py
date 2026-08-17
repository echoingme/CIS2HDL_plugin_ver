"""内置插件 stub 工厂（S3/S5 起全部真实现，无占位 stub）。

历史：
- input：S2 占位 stub 已由 S3 真实现替换（edif/dsn/cross_ref/pstxnet/pstchip
  编排调用引擎子步骤，见 ``cis2hdl/plugins/input/*.py``）。
- beautify：S2 占位 stub（``make_beautify_stub``）已由 S5 真实现替换
  （``cis2hdl/plugins/beautify/_base.py`` + 6 个插件，配置编排委托）。

本模块保留为空壳以兼容历史 import 路径（``cis2hdl.plugins._stubs``）；
不注册任何 hookimpl。
"""

from __future__ import annotations

__all__: list[str] = []
