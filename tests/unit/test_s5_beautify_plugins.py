"""S5 — beautify 插件真实现单测：独立启停 + 顺序执行 + 参数生效（FR4/FR9）。

设计依据：``docs/developer-guide.md`` S5 章节 / ``cis2hdl/plugins/beautify/_base.py``。

覆盖：
  1. 6 个 beautify 插件（overlap_resolve/gnd_cluster/parallel_short/
     three_stage_stub/wire_simplify/text_layout）真实现：cls 非 None、
     stage="beautify"、writes_keys 契约、param_section/param_fields 声明。
  2. 默认 profile 注册 [overlap_resolve, gnd_cluster, parallel_short] +
     执行顺序（yaml 顺序）；wire_simplify/three_stage_stub/text_layout
     默认不注册（不在默认链）。
  3. 独立启停：单插件 profile（[text_layout] / [wire_simplify] /
     [gnd_cluster] 等）注册成功；空链（[]）→ 无 beautify 插件注册。
  4. 参数生效（配置编排）：enabled 插件把完整 ``beautify.params`` 应用到
     全局 ``config.routing``（writer 读取）；disabled 插件不应用。
  5. 顺序执行断言：order_trace + ctx.routed_nets.applied_plugins 均按
     yaml 顺序。
  6. max-beauty profile：完整 params 应用（routing.mode=detour /
     wire_simplify.enabled / text_layout.enabled 等非单插件字段也生效）。
  7. cleanup 复位 enabled（幂等）。
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from cis2hdl.core.config import Config, config as global_cfg
from cis2hdl.core.engine.conversion_engine import ConversionEngine
from cis2hdl.core.pipeline_config import PipelineConfig
from cis2hdl.core.profile_manager import ProfileManager
from cis2hdl.plugins.context import ConversionContext
from cis2hdl.plugins.manager import build_plugin_manager
from cis2hdl.plugins.ordering import assert_order
from cis2hdl.plugins.spec import PluginSpec

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _restore_global_config() -> None:
    """保存/恢复全局 Config 单例（防顺序依赖污染，同 S4 单测）。"""
    saved_instance = Config._instance
    saved_state = (
        copy.deepcopy(saved_instance.__dict__)
        if saved_instance is not None
        else None
    )
    yield
    if saved_instance is not None:
        Config._instance = saved_instance
        saved_instance.__dict__.clear()
        saved_instance.__dict__.update(saved_state)
    else:
        Config._instance = None


def _engine() -> ConversionEngine:
    return ConversionEngine()


def _pm_for(pc: PipelineConfig):
    engine = _engine()
    engine.set_pipeline(pc)
    return engine, engine._pm


def _ctx(pc: PipelineConfig) -> ConversionContext:
    return ConversionContext(cfg=pc)


# ─────────────────────────────────────────────────────────────────────────
# 1. 插件元数据与注册
# ─────────────────────────────────────────────────────────────────────────


class TestBeautifyPluginSpecs:
    """S5 插件元数据：真实现、writes_keys 契约、参数源声明。"""

    @pytest.mark.parametrize(
        "name,param_section,param_fields",
        [
            ("overlap_resolve", "overlap", ("check", "resolve", "avoid_margin")),
            ("gnd_cluster", "gnd_distribution", ("enabled", "cluster_radius")),
            ("parallel_short", "gnd_distribution", ("parallel_short", "parallel_short_dist")),
            ("wire_simplify", "wire_simplify", ("enabled",)),
            ("three_stage_stub", "", ("three_stage_stub",)),
            ("text_layout", "text_layout", ("enabled",)),
        ],
    )
    def test_beautify_plugin_real_spec(
        self,
        name: str,
        param_section: str,
        param_fields: tuple[str, ...],
    ) -> None:
        pm = build_plugin_manager(PipelineConfig())
        spec = next(s for s in pm.list_plugins("beautify") if s.name == name)
        assert spec.cls is not None, f"{name} 应为真实现"
        assert spec.stage == "beautify"
        assert spec.writes_keys == ("routed_nets",)
        assert spec.param_section == param_section
        assert spec.param_fields == param_fields
        assert spec.builtin is True

    def test_all_six_beautify_plugins_discovered(self) -> None:
        pm = build_plugin_manager(PipelineConfig())
        names = {s.name for s in pm.list_plugins("beautify")}
        assert names == {
            "overlap_resolve", "gnd_cluster", "parallel_short",
            "wire_simplify", "three_stage_stub", "text_layout",
        }

    def test_default_profile_registration(self) -> None:
        """默认链注册 [overlap_resolve, gnd_cluster, parallel_short]。"""
        pc = PipelineConfig()
        pm = build_plugin_manager(pc)
        assert_order(pm, "beautify", ["overlap_resolve", "gnd_cluster", "parallel_short"])
        assert pm.get_plugin("wire_simplify") is None
        assert pm.get_plugin("text_layout") is None
        assert pm.get_plugin("three_stage_stub") is None


# ─────────────────────────────────────────────────────────────────────────
# 2. enabled 门语义 + 参数生效（配置编排）
# ─────────────────────────────────────────────────────────────────────────


class TestBeautifyEnabledGates:
    """每插件 enabled 门来自自身 params（独立启停）。"""

    @pytest.mark.parametrize(
        "name,setter,expected_default,expected_on",
        [
            ("overlap_resolve", "overlap.resolve", True, True),
            ("gnd_cluster", "gnd_distribution.enabled", False, True),
            ("parallel_short", "gnd_distribution.parallel_short", True, True),
            ("three_stage_stub", "three_stage_stub", True, True),
            ("wire_simplify", "wire_simplify.enabled", False, True),
            ("text_layout", "text_layout.enabled", False, True),
        ],
    )
    def test_enabled_flag_from_params(
        self,
        name: str,
        setter: str,
        expected_default: bool,
        expected_on: bool,
    ) -> None:
        # 默认值
        pc = PipelineConfig()
        pc.beautify.plugins = [name]
        engine, pm = _pm_for(pc)
        plugin = pm.get_plugin(name)
        assert plugin.enabled is expected_default
        # 显式开启
        pc2 = PipelineConfig()
        pc2.beautify.plugins = [name]
        section, _, field = setter.partition(".")
        if section == "three_stage_stub":
            setattr(pc2.beautify.params, field, expected_on)
        else:
            setattr(getattr(pc2.beautify.params, section), field, expected_on)
        engine2, pm2 = _pm_for(pc2)
        assert pm2.get_plugin(name).enabled is expected_on

    def test_enabled_plugin_applies_full_params_to_global_config(self) -> None:
        """enabled 插件把完整 beautify.params 应用到全局 config.routing。"""
        pc = PipelineConfig()
        pc.beautify.plugins = ["text_layout"]
        pc.beautify.params.text_layout.enabled = True
        engine, pm = _pm_for(pc)
        # 重置全局 config（默认 RoutingConfig）
        Config.get().reset()
        ctx = _ctx(pc)
        results = pm.hook.beautify(ctx=ctx)
        assert results == [True]
        assert global_cfg.routing.text_layout.enabled is True
        # ctx 摘要
        assert ctx.routed_nets["applied_plugins"] == ["text_layout"]
        assert ctx.routed_nets["enabled"] is True

    def test_disabled_plugin_does_not_apply(self) -> None:
        """disabled 插件不应用 params（返回 False；全局 config 保持默认）。"""
        pc = PipelineConfig()
        pc.beautify.plugins = ["gnd_cluster"]  # gnd_distribution.enabled=False
        engine, pm = _pm_for(pc)
        Config.get().reset()
        ctx = _ctx(pc)
        results = pm.hook.beautify(ctx=ctx)
        assert results == [False]
        assert global_cfg.routing.gnd_distribution.enabled is False
        assert ctx.routed_nets["skipped_plugins"] == ["gnd_cluster"]
        assert ctx.routed_nets["applied_plugins"] == []

    def test_empty_chain_no_application(self) -> None:
        """空链 → 无人处理 → 全局 config 不应用（保持默认）。"""
        pc = PipelineConfig()
        pc.beautify.plugins = []
        engine, pm = _pm_for(pc)
        Config.get().reset()
        ctx = _ctx(pc)
        results = pm.hook.beautify(ctx=ctx)
        assert results == []
        assert ctx.routed_nets is None
        assert global_cfg.routing.text_layout.enabled is False

    def test_max_beauty_full_params_application(self) -> None:
        """max-beauty：完整 params 应用（routing.mode=detour 等非单插件
        param_fields 覆盖字段也生效，FR9 与 S1 CLI 全量应用等价）。"""
        pc = ProfileManager().get("max-beauty")
        engine, pm = _pm_for(pc)
        Config.get().reset()
        ctx = _ctx(pc)
        results = pm.hook.beautify(ctx=ctx)
        # 默认链 + wire_simplify + three_stage_stub + text_layout；
        # gnd_cluster 仍 disabled（max-beauty 未开 gnd_distribution.enabled）
        assert results == [True, False, True, True, True, True]
        assert global_cfg.routing.mode == "detour"
        assert global_cfg.routing.wire_simplify.enabled is True
        assert global_cfg.routing.text_layout.enabled is True
        assert global_cfg.routing.three_stage_stub is True
        assert global_cfg.routing.overlap.resolve is True
        applied = ctx.routed_nets["applied_plugins"]
        assert applied == [
            "overlap_resolve", "parallel_short", "wire_simplify",
            "three_stage_stub", "text_layout",
        ]
        assert ctx.routed_nets["skipped_plugins"] == ["gnd_cluster"]


# ─────────────────────────────────────────────────────────────────────────
# 3. 顺序执行断言
# ─────────────────────────────────────────────────────────────────────────


class TestBeautifyOrder:
    """美化链按 yaml 顺序执行（order_trace + ctx.routed_nets）。"""

    def test_default_order_trace(self) -> None:
        pc = PipelineConfig()
        engine, pm = _pm_for(pc)
        ctx = _ctx(pc)
        pm.hook.beautify(ctx=ctx)
        for name in ("overlap_resolve", "gnd_cluster", "parallel_short"):
            plugin = pm.get_plugin(name)
            assert plugin.order_trace == [name]
        assert ctx.routed_nets["applied_plugins"] == ["overlap_resolve", "parallel_short"]
        assert ctx.routed_nets["skipped_plugins"] == ["gnd_cluster"]

    def test_custom_order_trace(self) -> None:
        pc = PipelineConfig()
        pc.beautify.plugins = ["text_layout", "wire_simplify", "gnd_cluster"]
        engine, pm = _pm_for(pc)
        assert_order(pm, "beautify", ["text_layout", "wire_simplify", "gnd_cluster"])
        ctx = _ctx(pc)
        pm.hook.beautify(ctx=ctx)
        for name in ("text_layout", "wire_simplify", "gnd_cluster"):
            plugin = pm.get_plugin(name)
            assert plugin.order_trace == [name]


# ─────────────────────────────────────────────────────────────────────────
# 4. 独立启停
# ─────────────────────────────────────────────────────────────────────────


class TestBeautifyIndependentEnable:
    """每美化插件可独立启停（FR2）。"""

    @pytest.mark.parametrize(
        "name,setter",
        [
            ("overlap_resolve", "overlap.resolve"),
            ("gnd_cluster", "gnd_distribution.enabled"),
            ("parallel_short", "gnd_distribution.parallel_short"),
            ("three_stage_stub", "three_stage_stub"),
            ("wire_simplify", "wire_simplify.enabled"),
            ("text_layout", "text_layout.enabled"),
        ],
    )
    def test_single_plugin_registers(self, name: str, setter: str) -> None:
        pc = PipelineConfig()
        pc.beautify.plugins = [name]
        engine, pm = _pm_for(pc)
        assert pm.get_plugin(name) is not None
        assert_order(pm, "beautify", [name])
        # 其它插件不注册
        others = {
            "overlap_resolve", "gnd_cluster", "parallel_short",
            "wire_simplify", "three_stage_stub", "text_layout",
        } - {name}
        for other in others:
            assert pm.get_plugin(other) is None, f"{other} 不应注册"

    def test_single_enabled_plugin_runs(self) -> None:
        """单独启用 wire_simplify（enabled=True）→ 应用 params → 返回 True。"""
        pc = PipelineConfig()
        pc.beautify.plugins = ["wire_simplify"]
        pc.beautify.params.wire_simplify.enabled = True
        engine, pm = _pm_for(pc)
        Config.get().reset()
        ctx = _ctx(pc)
        results = pm.hook.beautify(ctx=ctx)
        assert results == [True]
        assert global_cfg.routing.wire_simplify.enabled is True


# ─────────────────────────────────────────────────────────────────────────
# 5. cleanup / 引擎入口
# ─────────────────────────────────────────────────────────────────────────


class TestBeautifyCleanup:
    def test_cleanup_resets_enabled(self) -> None:
        pc = PipelineConfig()
        pc.beautify.params.gnd_distribution.enabled = True
        pm = build_plugin_manager(pc)
        gnd = pm.get_plugin("gnd_cluster")
        assert gnd.enabled is True
        pm.cleanup()
        assert gnd.enabled is False

    def test_cleanup_idempotent(self) -> None:
        pm = build_plugin_manager(PipelineConfig())
        pm.cleanup()
        pm.cleanup()
        assert pm._registered_names == []
        assert len(pm.hook.beautify.get_hookimpls()) == 0

    def test_engine_apply_beautify_params_matches_to_routing_config(self) -> None:
        """engine.apply_beautify_params == S1 CLI to_routing_config 写回。"""
        pc = ProfileManager().get("max-beauty")
        engine = _engine()
        ctx = _ctx(pc)
        Config.get().reset()
        engine.apply_beautify_params(ctx)
        expected = pc.to_routing_config()
        assert global_cfg.routing.mode == expected.mode == "detour"
        assert global_cfg.routing.wire_simplify.enabled == expected.wire_simplify.enabled is True
        assert global_cfg.routing.text_layout.enabled == expected.text_layout.enabled is True
