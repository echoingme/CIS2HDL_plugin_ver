"""S2 T02 — 插件注册顺序单元测试（决策 D1：逆序注册 + LIFO 反转）。

Covers（docs/S2-plugin-base-design.md T02）：
  * beautify 链按 yaml 顺序执行（[overlap_resolve, gnd_cluster, parallel_short]）
  * 自定义顺序（max-beauty 组合）仍按 yaml 顺序
  * registration_order 工具：外部先、内置逆 yaml 序
  * assert_order 断言工具
  * 未启用插件不参与顺序
"""

from __future__ import annotations

import pytest

from cis2hdl.core.pipeline_config import PipelineConfig
from cis2hdl.plugins.context import ConversionContext
from cis2hdl.plugins.manager import build_plugin_manager
from cis2hdl.plugins.ordering import assert_order, registration_order


class TestBeautifyOrder:
    def test_default_yaml_order(self):
        """默认 beautify.plugins = [overlap_resolve, gnd_cluster, parallel_short]。"""
        pm = build_plugin_manager(PipelineConfig())
        assert_order(pm, "beautify", ["overlap_resolve", "gnd_cluster", "parallel_short"])

    def test_execution_trace_matches_yaml(self):
        pm = build_plugin_manager(PipelineConfig())
        ctx = ConversionContext(cfg=PipelineConfig())
        pm.hook.beautify(ctx=ctx)
        traces = [pm.get_plugin(n).order_trace for n in
                  ("overlap_resolve", "gnd_cluster", "parallel_short")]
        # 每个插件的 order_trace 记录自己被调用的时刻
        assert traces[0][0] == "overlap_resolve"
        assert traces[1][0] == "gnd_cluster"
        assert traces[2][0] == "parallel_short"

    def test_custom_yaml_order(self):
        """自定义 beautify 顺序仍按 yaml 声明执行。"""
        cfg = PipelineConfig()
        cfg.beautify.plugins = ["text_layout", "wire_simplify", "gnd_cluster"]
        pm = build_plugin_manager(cfg)
        assert_order(pm, "beautify", ["text_layout", "wire_simplify", "gnd_cluster"])

    def test_hook_results_false_for_stubs(self):
        """S2 占位：beautify 全部返回 False（逻辑仍在 writer，S5 迁入）。"""
        pm = build_plugin_manager(PipelineConfig())
        ctx = ConversionContext(cfg=PipelineConfig())
        results = pm.hook.beautify(ctx=ctx)
        assert all(r is False for r in results)


class TestRegistrationOrder:
    def test_reversed_yaml_for_builtin(self):
        cfg = PipelineConfig()
        pm = build_plugin_manager(cfg)
        # 只传**已启用**的 beautify specs（未启用插件不参与顺序）
        enabled_specs = [s for s in pm._enabled if s.stage == "beautify"]
        order = registration_order(enabled_specs, cfg)
        beautify_order = [s.name for s in order if s.stage == "beautify"]
        assert beautify_order == list(reversed(["overlap_resolve", "gnd_cluster", "parallel_short"]))

    def test_external_first(self):
        """外部插件（builtin=False）先注册 → LIFO 最后执行。"""
        from cis2hdl.plugins.spec import PluginSpec

        cfg = PipelineConfig()
        external = PluginSpec(
            name="ext_plugin", stage="beautify", cls=None, builtin=False,
        )
        order = registration_order([external], cfg)
        assert order[0].name == "ext_plugin"
        assert order[0].builtin is False

    def test_assert_order_mismatch_raises(self):
        pm = build_plugin_manager(PipelineConfig())
        with pytest.raises(AssertionError):
            assert_order(pm, "beautify", ["gnd_cluster", "overlap_resolve", "parallel_short"])

    def test_disabled_plugin_not_in_order(self):
        cfg = PipelineConfig()
        cfg.beautify.plugins = ["gnd_cluster"]
        pm = build_plugin_manager(cfg)
        assert_order(pm, "beautify", ["gnd_cluster"])
        assert pm.get_plugin("overlap_resolve") is None
