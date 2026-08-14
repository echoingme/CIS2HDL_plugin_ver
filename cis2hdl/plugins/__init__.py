"""CIS2HDL 插件基座包（S2）。

T01 导出：PROJECT_NAME / PipelineHooks / ConversionContext / ReadOnlyViolation。
T02 起追加：PluginSpec / PluginManager / build_plugin_manager。
"""

from __future__ import annotations

from .context import ConversionContext, ReadOnlyViolation
from .hookspecs import PROJECT_NAME, PipelineHooks, hookimpl, hookspec

__all__ = [
    "PROJECT_NAME",
    "PipelineHooks",
    "ConversionContext",
    "ReadOnlyViolation",
    "hookspec",
    "hookimpl",
]
