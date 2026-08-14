"""CIS2HDL 插件基座包（S2）。

导出：PROJECT_NAME / PipelineHooks / ConversionContext / PluginSpec /
PluginManager / build_plugin_manager。
S2 范围：hookspec 契约 + ConversionContext + PluginManager + 内置插件骨架
（input/beautify 占位、output/test 白名单）；S3-S6 逐个填充真实现。
"""

from __future__ import annotations

from .context import ConversionContext, ReadOnlyViolation
from .hookspecs import PROJECT_NAME, PipelineHooks, hookimpl, hookspec
from .manager import PluginManager, build_plugin_manager
from .spec import PluginSpec

__all__ = [
    "PROJECT_NAME",
    "PipelineHooks",
    "ConversionContext",
    "ReadOnlyViolation",
    "PluginSpec",
    "PluginManager",
    "build_plugin_manager",
    "hookspec",
    "hookimpl",
]
