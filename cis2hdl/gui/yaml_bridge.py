"""yaml 双通道（S9 §4）— 表单状态 ↔ PipelineConfig ↔ yaml 文本。

设计依据：``docs/gui-design.md`` §4（yaml 双通道映射 + 原子写）。
纯逻辑模块（**不依赖 PySide6**），可单测。UI 层（YamlEditor/ParamForm）
只依赖本模块的：

- :class:`FormState` —— 表单状态（profile + 各阶段插件顺序 + 扁平参数）
- :func:`form_state_from_cfg` / :func:`cfg_from_form_state` —— 双向映射
- :func:`cfg_to_yaml_text` / :func:`yaml_text_to_cfg` —— yaml 文本通道
- :func:`save_pipeline_atomic` —— 原子写（临时文件 + os.replace）
- :func:`is_text_in_sync` —— 表单与 yaml 冲突检测
- :func:`diff_lines` —— 行级差异（高亮用）

参数路径约定（dotted path，对应 yaml 路径）::

    beautify.routing.mode            → beautify.params.routing.mode
    beautify.text_layout.enabled     → beautify.params.text_layout.enabled
    match.weights.footprint          → match.weights.footprint
    match.prefix_scope.R             → match.prefix_scope.R
    match.mock.prefixes              → match.mock.prefixes
    match.manual_overrides.file      → match.manual_overrides.file
    output.reports                   → output.reports
    input.hdl_lib                    → input.hdl_lib
    test.suites                      → test.suites
    engine.output_dir                → engine.output_dir
"""

from __future__ import annotations

import copy
import dataclasses
import difflib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from ..core.pipeline_config import (
    ROUTING_SCALAR_KEYS,
    ROUTING_SUBSECTION_KEYS,
    PipelineConfig,
)

__all__ = [
    "FormState",
    "YamlValidationError",
    "form_state_from_cfg",
    "cfg_from_form_state",
    "cfg_to_yaml_text",
    "yaml_text_to_cfg",
    "save_pipeline_atomic",
    "is_text_in_sync",
    "diff_lines",
    "stage_plugins",
    "set_stage_plugins",
    "plugin_param_paths",
    "apply_param_path",
    "param_paths_from_cfg",
]

#: FormState.plugins 的阶段键（顺序 = 展示顺序；output 用 output.files）。
STAGES: tuple[str, ...] = ("input", "match", "beautify", "output", "test")


class YamlValidationError(ValueError):
    """yaml 文本解析/校验失败（YamlEditor 红框提示，不刷新表单）。"""


@dataclass
class FormState:
    """表单状态快照（GUI 表单 ↔ PipelineConfig 的中介）。"""

    profile: str = "default"
    plugins: dict[str, list[str]] = field(default_factory=dict)
    """``{stage: [插件名, ...]}``（有序 = 执行顺序）。"""
    params: dict[str, Any] = field(default_factory=dict)
    """``{dotted_path: value}`` 扁平参数（含 beautify/match/input/output/test/engine）。"""


# ── cfg ↔ FormState ─────────────────────────────────────────────────────────


def form_state_from_cfg(cfg: PipelineConfig) -> FormState:
    """PipelineConfig → FormState（插件顺序 + 全量扁平参数）。"""
    state = FormState(profile=cfg.profile)
    state.plugins = {
        "input": list(cfg.input.plugins),
        "match": list(cfg.match.plugins),
        "beautify": list(cfg.beautify.plugins),
        "output": list(cfg.output.files),
        "test": list(cfg.test.suites),
    }
    state.params = param_paths_from_cfg(cfg)
    return state


def cfg_from_form_state(
    state: FormState, base_cfg: PipelineConfig | None = None,
) -> PipelineConfig:
    """FormState → PipelineConfig（深拷贝 base；缺省全新默认）。

    插件列表直接替换；参数逐个 ``apply_param_path`` 应用。
    """
    cfg = copy.deepcopy(base_cfg) if base_cfg is not None else PipelineConfig()
    if state.profile:
        cfg.profile = state.profile
    for stage in STAGES:
        names = state.plugins.get(stage)
        if names is None:
            continue
        set_stage_plugins(cfg, stage, [str(x) for x in names])
    for path, value in (state.params or {}).items():
        apply_param_path(cfg, str(path), value)
    return cfg


# ── 插件列表辅助 ────────────────────────────────────────────────────────────


def stage_plugins(cfg: PipelineConfig, stage: str) -> list[str]:
    """读取某阶段插件列表（output → output.files）。"""
    if stage == "input":
        return list(cfg.input.plugins)
    if stage == "match":
        return list(cfg.match.plugins)
    if stage == "beautify":
        return list(cfg.beautify.plugins)
    if stage == "output":
        return list(cfg.output.files)
    if stage == "test":
        return list(cfg.test.suites)
    raise KeyError(f"未知阶段: {stage!r}")


def set_stage_plugins(cfg: PipelineConfig, stage: str, names: list[str]) -> None:
    """写某阶段插件列表（output → output.files；与 ProfileManager 对齐）。"""
    if stage == "input":
        cfg.input.plugins = list(names)
    elif stage == "match":
        cfg.match.plugins = list(names)
    elif stage == "beautify":
        cfg.beautify.plugins = list(names)
    elif stage == "output":
        cfg.output.files = list(names)
    elif stage == "test":
        cfg.test.suites = list(names)
    else:
        raise KeyError(f"未知阶段: {stage!r}")


# ── 参数 dotted path ────────────────────────────────────────────────────────


def param_paths_from_cfg(cfg: PipelineConfig) -> dict[str, Any]:
    """cfg → 全量扁平参数（``{dotted_path: value}``）。"""
    paths: dict[str, Any] = {}
    rc = cfg.beautify.params

    for key in ROUTING_SCALAR_KEYS:
        if hasattr(rc, key):
            paths[f"beautify.routing.{key}"] = getattr(rc, key)
    for key in ROUTING_SUBSECTION_KEYS:
        sub = getattr(rc, key, None)
        if sub is None:
            continue
        if isinstance(sub, dict):
            paths[f"beautify.{key}"] = copy.deepcopy(sub)
        else:
            for f in dataclasses.fields(sub):
                paths[f"beautify.{key}.{f.name}"] = getattr(sub, f.name)

    paths.update({
        **{f"match.weights.{k}": v for k, v in cfg.match.weights.items()},
        **{f"match.thresholds.{k}": v for k, v in cfg.match.thresholds.items()},
        **{f"match.prefix_scope.{k}": list(v) for k, v in cfg.match.prefix_scope.items()},
        "match.mock.prefixes": list(cfg.match.mock.prefixes),
        "match.mock.auto_icon": cfg.match.mock.auto_icon,
        "match.manual_overrides.file": cfg.match.manual_overrides.file,
        "match.manual_overrides.export_unmatched": cfg.match.manual_overrides.export_unmatched,
        "output.reports": list(cfg.output.reports),
        "input.hdl_lib": cfg.input.hdl_lib,
        "input.extra_hdl_libs": list(cfg.input.extra_hdl_libs),
        "test.suites": list(cfg.test.suites),
        "engine.output_dir": cfg.engine.output_dir,
        "engine.max_workers": cfg.engine.max_workers,
        "engine.benchmark": cfg.engine.benchmark,
    })
    return paths


def plugin_param_paths(spec: Any, cfg: PipelineConfig) -> dict[str, Any]:
    """某插件声明的 param_fields → dotted path 与当前值（ParamForm 数据源）。

    beautify：``param_section`` 非空 → ``beautify.<section>.<field>``；
    顶层 → ``beautify.routing.<field>``。match/test/input/output → 直接
    ``<stage>.<field>``（weights/thresholds/prefix_scope 整体 dict）。
    """
    paths: dict[str, Any] = {}
    stage = getattr(spec, "stage", "")
    fields = tuple(getattr(spec, "param_fields", ()) or ())
    if stage == "beautify":
        section = getattr(spec, "param_section", "") or ""
        if section:
            sub = getattr(cfg.beautify.params, section, None)
            for f in fields:
                paths[f"beautify.{section}.{f}"] = (
                    getattr(sub, f) if sub is not None else None
                )
        else:
            for f in fields:
                paths[f"beautify.routing.{f}"] = getattr(cfg.beautify.params, f, None)
    elif stage == "match":
        for f in fields:
            paths[f"match.{f}"] = getattr(cfg.match, f, None)
    elif stage == "test":
        for f in fields:
            paths[f"test.{f}"] = getattr(cfg.test, f, None)
    elif stage == "input":
        for f in fields:
            paths[f"input.{f}"] = getattr(cfg.input, f, None)
    elif stage == "output":
        for f in fields:
            paths[f"output.{f}"] = getattr(cfg.output, f, None)
    return paths


def apply_param_path(cfg: PipelineConfig, path: str, value: Any) -> None:
    """就地应用参数 dotted path（嵌套 dataclass 用 ``dataclasses.replace``）。"""
    parts = path.split(".")
    if not parts:
        return

    if parts[0] == "beautify":
        rc = cfg.beautify.params
        if len(parts) == 2 and parts[1] in ROUTING_SCALAR_KEYS:
            setattr(rc, parts[1], value)
        elif len(parts) == 3 and parts[1] == "routing":
            setattr(rc, parts[2], value)
        elif len(parts) == 3 and parts[1] in ROUTING_SUBSECTION_KEYS:
            sub = getattr(rc, parts[1])
            if isinstance(sub, dict):
                sub[parts[2]] = value
            else:
                setattr(rc, parts[1], dataclasses.replace(sub, **{parts[2]: value}))
        elif len(parts) == 2 and parts[1] in ROUTING_SUBSECTION_KEYS:
            setattr(rc, parts[1], _to_dataclass(getattr(rc, parts[1]), value))
        return

    if parts[0] == "match":
        _apply_match_path(cfg, parts, value)
        return

    if parts[0] == "input":
        if len(parts) == 2 and hasattr(cfg.input, parts[1]):
            setattr(cfg.input, parts[1], value)
        return

    if parts[0] == "output":
        if len(parts) == 2 and hasattr(cfg.output, parts[1]):
            setattr(cfg.output, parts[1], value)
        return

    if parts[0] == "test":
        if len(parts) == 2 and hasattr(cfg.test, parts[1]):
            setattr(cfg.test, parts[1], value)
        return

    if parts[0] == "engine":
        if len(parts) == 2 and hasattr(cfg.engine, parts[1]):
            setattr(cfg.engine, parts[1], value)
        return


def _apply_match_path(cfg: PipelineConfig, parts: list[str], value: Any) -> None:
    if len(parts) == 2:
        if hasattr(cfg.match, parts[1]):
            setattr(cfg.match, parts[1], value)
        return
    if len(parts) == 3:
        if parts[1] == "weights" and parts[2] in cfg.match.weights:
            cfg.match.weights[parts[2]] = value
        elif parts[1] == "thresholds" and parts[2] in cfg.match.thresholds:
            cfg.match.thresholds[parts[2]] = value
        elif parts[1] == "prefix_scope":
            cfg.match.prefix_scope[parts[2]] = value
        elif parts[1] == "mock" and hasattr(cfg.match.mock, parts[2]):
            setattr(cfg.match.mock, parts[2], value)
        elif (
            parts[1] == "manual_overrides"
            and hasattr(cfg.match.manual_overrides, parts[2])
        ):
            setattr(cfg.match.manual_overrides, parts[2], value)


def _to_dataclass(target: Any, value: Any) -> Any:
    """dict → dataclass（未知字段忽略，保持与 RoutingConfig.from_dict 一致）。"""
    if not dataclasses.is_dataclass(target) or not isinstance(value, dict):
        return value
    allowed = {f.name for f in dataclasses.fields(target)}
    kwargs = {k: v for k, v in value.items() if k in allowed}
    return dataclasses.replace(target, **kwargs)


# ── yaml 文本通道 ───────────────────────────────────────────────────────────


def cfg_to_yaml_text(cfg: PipelineConfig) -> str:
    """PipelineConfig → yaml 文本（与 ``PipelineConfig.to_yaml`` 同序列化）。"""
    return yaml.safe_dump(
        cfg.to_dict(), allow_unicode=True, sort_keys=False, default_flow_style=None,
    )


def yaml_text_to_cfg(text: str) -> PipelineConfig:
    """yaml 文本 → PipelineConfig；非法 → :class:`YamlValidationError`。"""
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise YamlValidationError(f"yaml 解析失败: {exc}") from exc
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise YamlValidationError("yaml 顶层必须是 mapping")
    try:
        return PipelineConfig.from_dict(data)
    except Exception as exc:  # noqa: BLE001 — 结构错误统一包装
        raise YamlValidationError(f"yaml 结构非法: {exc}") from exc


def save_pipeline_atomic(path: Path, cfg: PipelineConfig) -> None:
    """原子写 pipeline.yaml（临时文件 + os.replace；继承 to_yaml 原子语义）。"""
    cfg.to_yaml(Path(path))


def is_text_in_sync(text: str, cfg: PipelineConfig) -> bool:
    """yaml 文本与表单配置是否同步（解析比较有效配置；注释忽略）。"""
    try:
        parsed = yaml_text_to_cfg(text)
    except YamlValidationError:
        return False
    return parsed.to_dict() == cfg.to_dict()


# ── 行级差异（高亮用） ─────────────────────────────────────────────────────


def diff_lines(old_text: str, new_text: str) -> list[tuple[str, str, str]]:
    """行级差异（difflib.SequenceMatcher）。

    Returns:
        ``[(tag, old_line, new_line)]``；``tag`` ∈
        ``equal`` / ``delete``（旧独有） / ``insert``（新独有） /
        ``replace``（内容不同）。
    """
    matcher = difflib.SequenceMatcher(
        a=old_text.splitlines(keepends=True),
        b=new_text.splitlines(keepends=True),
        autojunk=False,
    )
    result: list[tuple[str, str, str]] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        old_block = "".join(matcher.a[i1:i2])
        new_block = "".join(matcher.b[j1:j2])
        if tag == "equal":
            result.append(("equal", old_block, new_block))
        elif tag == "delete":
            result.append(("delete", old_block, ""))
        elif tag == "insert":
            result.append(("insert", "", new_block))
        elif tag == "replace":
            result.append(("replace", old_block, new_block))
    return result
