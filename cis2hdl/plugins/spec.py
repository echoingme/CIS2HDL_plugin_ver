"""PluginSpec — 插件元数据（S2 §3.2）。

设计依据：``docs/S2-plugin-base-design.md`` §3.2。

约定：
- ``name`` = 模块名（beautify: "gnd_cluster"；与 S1 白名单对齐，
  注意与 yaml params key ``gnd_distribution`` 区分）。
- ``cls`` = 可实例化插件类；``None`` = 占位/未实现（仅白名单声明）。
- ``param_section``/``param_fields``：参数注入声明（见 params.resolve_params）。
- ``writes_keys``：声明的 ctx 可写字段（只读守卫）。
- ``requires``：依赖的阶段产物（S2 仅声明不强制）。
- ``builtin``：True=目录扫描（包内）；False=外部 entry points。
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["STAGES", "PluginSpec"]

#: 插件组合比较/发现的 5 个阶段（对齐 S1 STAGES）。
STAGES: tuple[str, ...] = ("input", "match", "beautify", "output", "test")


@dataclass(frozen=True)
class PluginSpec:
    """插件元数据（不可变）。"""

    name: str
    """插件名（= 模块名）。"""
    stage: str
    """input | match | beautify | output | test。"""
    description: str = ""
    cls: type | None = None
    """插件类（可实例化）；None = 占位/未实现。"""
    module: str = ""
    """import path（诊断用）。"""
    param_section: str = ""
    """参数子节名（beautify: "gnd_distribution"；"" = 顶层）。"""
    param_fields: tuple[str, ...] = ()
    """提取并作为构造 kwargs 的字段。"""
    writes_keys: tuple[str, ...] = ()
    """声明的 ctx 可写字段（只读守卫）。"""
    requires: tuple[str, ...] = ()
    """依赖的阶段产物（S2 仅声明不强制）。"""
    builtin: bool = True
    """内置（目录扫描）还是外部（entry points）。"""
