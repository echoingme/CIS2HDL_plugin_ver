"""resolve_params — 从 PipelineConfig 提取插件构造参数（S2 §3.2 / 决策 D5）。

设计依据：``docs/S2-plugin-base-design.md`` §3.2。

规则：
- beautify: base = ``cfg.beautify.params``（RoutingConfig，S1 K1 复用）
- input:    base = ``cfg.input``
- match:    base = ``cfg.match``
- output:   base = ``cfg.output``
- test:     base = ``cfg.test``
- ``spec.param_section`` 非空 → ``base = getattr(base, param_section)``
- ``spec.param_fields`` → ``{f: getattr(base, f) for f in param_fields if hasattr(base, f)}``
- engine 注入：构造签名含 ``engine`` 的插件（matcher_pipeline 等）由调用方
  传入 ``engine`` 对象（Shared Knowledge：插件无法从 ctx 反向取 engine）。
"""

from __future__ import annotations

import inspect
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..core.pipeline_config import PipelineConfig
    from .spec import PluginSpec

__all__ = ["resolve_params"]


def _stage_base(cfg: "PipelineConfig", stage: str) -> Any:
    """返回阶段参数源对象。"""
    if stage == "input":
        return cfg.input
    if stage == "match":
        return cfg.match
    if stage == "beautify":
        return cfg.beautify.params  # RoutingConfig（S1 K1）
    if stage == "output":
        return cfg.output
    if stage == "test":
        return cfg.test
    return None


def _cls_accepts_engine(cls: type | None) -> bool:
    """插件类构造签名是否含 ``engine`` 参数（Shared Knowledge 注入规则）。"""
    if cls is None:
        return False
    try:
        sig = inspect.signature(cls.__init__)
    except (TypeError, ValueError):
        return False
    return "engine" in sig.parameters


def resolve_params(
    cfg: "PipelineConfig",
    spec: "PluginSpec",
    engine: Any = None,
) -> dict:
    """从 PipelineConfig 提取插件构造参数。

    Args:
        cfg: S1 PipelineConfig（参数源）。
        spec: 插件元数据（param_section/param_fields 声明）。
        engine: 引擎引用（仅注入构造签名含 ``engine`` 的插件）。

    Returns:
        构造 kwargs dict（缺失字段忽略；插件无参构造时可能为空 dict）。
    """
    base = _stage_base(cfg, spec.stage)
    if spec.param_section and base is not None:
        base = getattr(base, spec.param_section, None)

    params: dict[str, Any] = {}
    if base is not None:
        for f in spec.param_fields:
            if hasattr(base, f):
                params[f] = getattr(base, f)

    if engine is not None and _cls_accepts_engine(spec.cls):
        params["engine"] = engine
    return params
