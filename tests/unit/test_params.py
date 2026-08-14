"""S2 T02 — resolve_params 参数注入单元测试。

Covers（docs/S2-plugin-base-design.md T02）：
  * beautify: gnd_cluster 从 params.gnd_distribution 提取 enabled/cluster_radius
  * parallel_short 同节不同字段
  * three_stage_stub 顶层 RoutingConfig（param_section=""）
  * input/match/output/test 各阶段 base
  * engine 注入（构造签名含 engine 的插件）
  * 缺失字段忽略
"""

from __future__ import annotations

import pytest

from cis2hdl.core.pipeline_config import PipelineConfig
from cis2hdl.plugins.params import resolve_params
from cis2hdl.plugins.spec import PluginSpec


def _spec(**kw) -> PluginSpec:
    defaults = {"name": "x", "stage": "beautify", "cls": None}
    defaults.update(kw)
    return PluginSpec(**defaults)


class TestBeautifyParams:
    def test_gnd_cluster_from_gnd_distribution(self):
        cfg = PipelineConfig()
        cfg.beautify.params.gnd_distribution.enabled = True
        cfg.beautify.params.gnd_distribution.cluster_radius = 700
        params = resolve_params(cfg, _spec(
            name="gnd_cluster", param_section="gnd_distribution",
            param_fields=("enabled", "cluster_radius"),
        ))
        assert params["enabled"] is True
        assert params["cluster_radius"] == 700

    def test_parallel_short_same_section_diff_fields(self):
        cfg = PipelineConfig()
        cfg.beautify.params.gnd_distribution.parallel_short = False
        cfg.beautify.params.gnd_distribution.parallel_short_dist = 900
        params = resolve_params(cfg, _spec(
            name="parallel_short", param_section="gnd_distribution",
            param_fields=("parallel_short", "parallel_short_dist"),
        ))
        assert params["parallel_short"] is False
        assert params["parallel_short_dist"] == 900

    def test_three_stage_stub_top_level_routing(self):
        """param_section="" → 顶层 RoutingConfig。"""
        cfg = PipelineConfig()
        cfg.beautify.params.three_stage_stub = False
        params = resolve_params(cfg, _spec(
            name="three_stage_stub", param_section="",
            param_fields=("three_stage_stub",),
        ))
        assert params["three_stage_stub"] is False

    def test_defaults_injected(self):
        """默认值（未覆盖）也被注入。"""
        cfg = PipelineConfig()
        params = resolve_params(cfg, _spec(
            name="gnd_cluster", param_section="gnd_distribution",
            param_fields=("enabled", "cluster_radius"),
        ))
        assert params["enabled"] is False
        assert params["cluster_radius"] == 2000


class TestStageBases:
    def test_input_base(self):
        cfg = PipelineConfig()
        cfg.input.hdl_lib = "/lib"
        params = resolve_params(cfg, _spec(
            name="edif", stage="input", param_section="",
            param_fields=("hdl_lib",),
        ))
        assert params["hdl_lib"] == "/lib"

    def test_match_base(self):
        cfg = PipelineConfig()
        params = resolve_params(cfg, _spec(
            name="matcher_pipeline", stage="match", param_section="",
            param_fields=("plugins",),
        ))
        assert params["plugins"] == ["exact", "fuzzy", "passive", "fallback"]

    def test_output_base(self):
        cfg = PipelineConfig()
        cfg.output.files = ["csa"]
        params = resolve_params(cfg, _spec(
            name="default_writer", stage="output", param_section="",
            param_fields=("files",),
        ))
        assert params["files"] == ["csa"]

    def test_test_base(self):
        cfg = PipelineConfig()
        cfg.test.suites = ["unit"]
        params = resolve_params(cfg, _spec(
            name="unit", stage="test", param_section="",
            param_fields=("suites",),
        ))
        assert params["suites"] == ["unit"]

    def test_missing_field_ignored(self):
        cfg = PipelineConfig()
        params = resolve_params(cfg, _spec(
            name="x", param_section="gnd_distribution",
            param_fields=("no_such_field", "enabled"),
        ))
        assert "no_such_field" not in params
        assert params["enabled"] is False


class TestEngineInjection:
    def test_engine_injected_when_signature_accepts(self):
        class NeedsEngine:
            def __init__(self, engine):
                self.engine = engine

        cfg = PipelineConfig()
        params = resolve_params(cfg, _spec(name="m", cls=NeedsEngine), engine="ENGINE")
        assert params["engine"] == "ENGINE"

    def test_engine_not_injected_when_not_accepted(self):
        class NoEngine:
            def __init__(self, enabled: bool = False):
                self.enabled = enabled

        cfg = PipelineConfig()
        params = resolve_params(cfg, _spec(name="m", cls=NoEngine), engine="ENGINE")
        assert "engine" not in params

    def test_engine_none_no_injection(self):
        cfg = PipelineConfig()
        params = resolve_params(cfg, _spec(name="m", cls=None), engine=None)
        assert "engine" not in params
