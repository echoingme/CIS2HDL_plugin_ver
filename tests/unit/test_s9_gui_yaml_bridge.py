"""S9 GUI 测试 — yaml 双通道（§4）：FormState 映射 / 参数路径 / 原子写 / 冲突 / diff。

纯逻辑模块测试（无 PySide6）。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cis2hdl.core.pipeline_config import PipelineConfig
from cis2hdl.gui.yaml_bridge import (
    FormState,
    YamlValidationError,
    apply_param_path,
    cfg_from_form_state,
    cfg_to_yaml_text,
    diff_lines,
    form_state_from_cfg,
    is_text_in_sync,
    param_paths_from_cfg,
    plugin_param_paths,
    save_pipeline_atomic,
    set_stage_plugins,
    stage_plugins,
    yaml_text_to_cfg,
)


def make_cfg() -> PipelineConfig:
    return PipelineConfig()


# ── FormState 双向映射 ────────────────────────────────────────────────────


def test_form_state_roundtrip() -> None:
    cfg = make_cfg()
    state = form_state_from_cfg(cfg)
    assert state.plugins["input"] == ["edif", "pstxnet", "pstchip"]
    assert state.plugins["beautify"] == ["overlap_resolve", "gnd_cluster", "parallel_short"]
    restored = cfg_from_form_state(state)
    assert restored.to_dict() == cfg.to_dict()


def test_form_state_plugins_replace() -> None:
    state = FormState(profile="default")
    state.plugins = {"input": ["edif"], "match": [], "beautify": [], "output": [], "test": []}
    cfg = cfg_from_form_state(state)
    assert cfg.input.plugins == ["edif"]
    assert cfg.match.plugins == []


def test_stage_plugins_get_set() -> None:
    cfg = make_cfg()
    assert stage_plugins(cfg, "output") == cfg.output.files
    set_stage_plugins(cfg, "output", ["csa", "con"])
    assert cfg.output.files == ["csa", "con"]
    with pytest.raises(KeyError):
        stage_plugins(cfg, "nope")


# ── 参数路径 ──────────────────────────────────────────────────────────────


def test_param_paths_from_cfg_contains_all() -> None:
    cfg = make_cfg()
    paths = param_paths_from_cfg(cfg)
    assert paths["beautify.routing.mode"] == "p0"
    assert paths["beautify.text_layout.enabled"] is False
    assert paths["match.weights.footprint"] == pytest.approx(0.30)
    assert paths["match.mock.prefixes"] == ["J", "T"]
    assert paths["output.reports"] == ["aesthetic", "ioport", "mapping", "error"]


def test_apply_param_path_nested_dataclass() -> None:
    cfg = make_cfg()
    apply_param_path(cfg, "beautify.text_layout.enabled", True)
    assert cfg.beautify.params.text_layout.enabled is True
    apply_param_path(cfg, "beautify.overlap.avoid_margin", 99)
    assert cfg.beautify.params.overlap.avoid_margin == 99


def test_apply_param_path_scalar_and_match() -> None:
    cfg = make_cfg()
    apply_param_path(cfg, "beautify.routing.mode", "detour")
    assert cfg.beautify.params.mode == "detour"
    apply_param_path(cfg, "match.weights.footprint", 0.5)
    assert cfg.match.weights["footprint"] == pytest.approx(0.5)
    apply_param_path(cfg, "match.mock.prefixes", ["J", "T", "U"])
    assert cfg.match.mock.prefixes == ["J", "T", "U"]


def test_apply_param_path_unknown_ignored() -> None:
    cfg = make_cfg()
    before = cfg.to_dict()
    apply_param_path(cfg, "beautify.nope.field", 1)
    apply_param_path(cfg, "unknown.path", 1)
    assert cfg.to_dict() == before


def test_plugin_param_paths_stage_variants() -> None:
    from cis2hdl.plugins.spec import PluginSpec

    cfg = make_cfg()
    beautify = PluginSpec(name="overlap_resolve", stage="beautify",
                          param_section="overlap", param_fields=("resolve", "avoid_margin"))
    paths = plugin_param_paths(beautify, cfg)
    assert "beautify.overlap.resolve" in paths

    top = PluginSpec(name="three_stage_stub", stage="beautify",
                     param_section="", param_fields=("three_stage_stub",))
    paths = plugin_param_paths(top, cfg)
    assert "beautify.routing.three_stage_stub" in paths

    match = PluginSpec(name="exact", stage="match", param_fields=("weights",))
    paths = plugin_param_paths(match, cfg)
    assert "match.weights" in paths

    test = PluginSpec(name="unit", stage="test", param_fields=("suites",))
    paths = plugin_param_paths(test, cfg)
    assert "test.suites" in paths


# ── yaml 文本通道 ─────────────────────────────────────────────────────────


def test_yaml_roundtrip() -> None:
    cfg = make_cfg()
    cfg.beautify.params.text_layout.enabled = True
    text = cfg_to_yaml_text(cfg)
    assert "text_layout" in text
    restored = yaml_text_to_cfg(text)
    assert restored.to_dict() == cfg.to_dict()


def test_yaml_invalid_raises() -> None:
    with pytest.raises(YamlValidationError):
        yaml_text_to_cfg(":\n  - broken: [")
    with pytest.raises(YamlValidationError):
        yaml_text_to_cfg("- just a list\n")


def test_is_text_in_sync() -> None:
    cfg = make_cfg()
    assert is_text_in_sync(cfg_to_yaml_text(cfg), cfg) is True
    assert is_text_in_sync("profile: other\n", cfg) is False
    assert is_text_in_sync(": bad yaml", cfg) is False


def test_save_pipeline_atomic(tmp_path: Path) -> None:
    target = tmp_path / "sub" / "pipeline.yaml"
    cfg = make_cfg()
    save_pipeline_atomic(target, cfg)
    assert target.exists()
    assert PipelineConfig.from_yaml(target).to_dict() == cfg.to_dict()
    # 覆盖写（原子替换）
    cfg.profile = "max-beauty"
    save_pipeline_atomic(target, cfg)
    assert PipelineConfig.from_yaml(target).profile == "max-beauty"


# ── 行级 diff ─────────────────────────────────────────────────────────────


def test_diff_lines_detects_change() -> None:
    old = "profile: default\nmode: p0\n"
    new = "profile: default\nmode: detour\n"
    result = diff_lines(old, new)
    tags = {tag for tag, _, _ in result}
    assert "equal" in tags
    assert "replace" in tags


def test_diff_lines_insert_delete() -> None:
    result = diff_lines("a\n", "a\nb\n")
    assert any(tag == "insert" for tag, _, _ in result)
    result = diff_lines("a\nb\n", "a\n")
    assert any(tag == "delete" for tag, _, _ in result)


def test_diff_lines_empty() -> None:
    assert diff_lines("", "") == []
