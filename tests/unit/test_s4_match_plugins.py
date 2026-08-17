"""S4 — match 插件独立启停 + 权重/prefix/阈值配置生效 + manual_overrides 单测。

设计依据：``docs/developer-guide.md`` S4 章节 / ``docs/plugin-api.md``。

覆盖（FR2/FR3/NFR5/FR9）：
  1. 6 个 match 插件（matcher_pipeline/exact/fuzzy/passive/fallback/
     manual_overrides）真实现：cls 非 None、stage="match"、writes_keys 契约。
  2. 默认 profile 注册 [exact, fuzzy, passive, fallback] + 执行顺序
     （exact→fuzzy→passive→fallback）；matcher_pipeline/manual_overrides
     默认不注册（不在默认链）。
  3. 独立启停：单插件 profile（[exact] / [fuzzy] / [matcher_pipeline]）注册
     成功；全禁（[]）→ 无 match 插件注册（引擎回退 legacy）。
  4. 配置生效（NFR5）：
     - thresholds → ComponentMatchingConfig（默认值对齐；显式修改生效）。
     - weights → ActiveMatcher.WITHIN_TYPE_WEIGHTS（默认对齐；应用+恢复）。
     - MatchSection.weights 默认 == ActiveMatcher.WITHIN_TYPE_WEIGHTS。
     - prefix_scope helper：默认空 → 不过滤；显式配置 → 候选库收窄。
  5. 编排等价（HG5015）：plugin match_components 产出 == legacy
     _stage_match + _append_power_symbol_matches（长度/策略分布/映射一致）。
  6. manual_overrides 插件（FR3）：启用后委托 _apply_phase14_matching，
     写 ctx.manual_overrides；chip_config 同步到全局 Config。
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from cis2hdl.core.config import Config
from cis2hdl.core.engine.conversion_engine import ConversionEngine, ConversionReport
from cis2hdl.core.ir.component import ComponentDef
from cis2hdl.core.ir.match import MatchStrategy
from cis2hdl.core.matcher.active_matcher import ActiveMatcher
from cis2hdl.core.pipeline_config import PipelineConfig
from cis2hdl.plugins.context import ConversionContext
from cis2hdl.plugins.manager import build_plugin_manager
from cis2hdl.plugins.ordering import assert_order

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_FIXTURES = _PROJECT_ROOT / "tests" / "fixtures"
_HG_DSN = _FIXTURES / "HG5015test" / "HG5015-BE36_V10.DSN"
_HDL = _FIXTURES / "hdl_lib"


@pytest.fixture(autouse=True)
def _restore_global_config() -> None:
    """保存/恢复全局 Config 单例（防顺序依赖污染，同 S3 单测）。"""
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


def _skip_if_missing(path: Path) -> None:
    if not path.exists():
        pytest.skip(f"fixture 缺失: {path}")


def _engine() -> ConversionEngine:
    return ConversionEngine()


def _ctx(pc: PipelineConfig, input_path: Path) -> ConversionContext:
    ctx = ConversionContext(cfg=pc, input_files=[input_path])
    ctx.report = ConversionReport()
    return ctx


def _make_candidate(
    library_id: str = "hdl_lib/capacitor",
    part_name: str = "CAPACITOR",
    category: str = "capacitor",
    footprint: str = "HSC0402-HDTB",
    value: str = "",
) -> ComponentDef:
    """最小 ComponentDef（测试用；ptf_rows 可选）。"""
    from cis2hdl.core.ir.component import PinDef, ElectricalType

    return ComponentDef(
        library_id=library_id,
        part_name=part_name,
        category=category,
        footprint=footprint,
        value=value,
        pins=[PinDef(number="1", name="P1", type=ElectricalType.PASSIVE)],
        extra_data={"ptf_rows": []},
    )


# ─────────────────────────────────────────────────────────────────────────
# 1. 插件元数据与注册
# ─────────────────────────────────────────────────────────────────────────


class TestMatchPluginSpecs:
    """S4 插件元数据：真实现、writes_keys 契约、独立启停。"""

    @pytest.mark.parametrize(
        "name,desc",
        [
            ("matcher_pipeline", "匹配阶段编排"),
            ("exact", "exact 匹配"),
            ("fuzzy", "fuzzy 匹配"),
            ("passive", "passive 匹配"),
            ("fallback", "fallback 匹配"),
            ("manual_overrides", "手动干预"),
        ],
    )
    def test_match_plugin_real_spec(self, name: str, desc: str) -> None:
        pm = build_plugin_manager(PipelineConfig(), engine=_engine())
        spec = next(s for s in pm.list_plugins("match") if s.name == name)
        assert spec.cls is not None, f"{name} 应为真实现（S4）"
        assert spec.stage == "match"
        assert desc in spec.description
        if name == "manual_overrides":
            assert "manual_overrides" in spec.writes_keys
        else:
            assert spec.writes_keys == ("matches",)

    def test_default_profile_registers_four(self) -> None:
        pc = PipelineConfig()
        pm = build_plugin_manager(pc, engine=_engine())
        for name in ("exact", "fuzzy", "passive", "fallback"):
            assert pm.get_plugin(name) is not None, f"{name} 默认应注册"
        # 默认链不含显式编排器与手动干预
        assert pm.get_plugin("matcher_pipeline") is None
        assert pm.get_plugin("manual_overrides") is None

    def test_default_match_chain_order(self) -> None:
        pc = PipelineConfig()
        pm = build_plugin_manager(pc, engine=_engine())
        assert_order(pm, "match", ["exact", "fuzzy", "passive", "fallback"])

    def test_single_plugin_enabled(self) -> None:
        for name in ("exact", "fuzzy", "passive", "fallback", "matcher_pipeline"):
            pc = PipelineConfig()
            pc.match.plugins = [name]
            pm = build_plugin_manager(pc, engine=_engine())
            assert pm.get_plugin(name) is not None, f"{name} 单独启用应注册"
            assert_order(pm, "match", [name])

    def test_all_disabled_falls_back(self) -> None:
        pc = PipelineConfig()
        pc.match.plugins = []
        pm = build_plugin_manager(pc, engine=_engine())
        assert pm.get_plugin("exact") is None
        assert pm.get_plugin("fuzzy") is None
        assert pm.get_plugin("manual_overrides") is None
        # match_components 钩子无 handler → PluginHost 回退 legacy
        engine = _engine()
        engine.set_pipeline(pc)
        ctx = _ctx(pc, _HG_DSN)
        handled, _ = engine._host.call(ctx, "match_components", fallback=lambda: None)
        assert handled is False


# ─────────────────────────────────────────────────────────────────────────
# 2. 配置生效（NFR5：权重/prefix/阈值全进 yaml）
# ─────────────────────────────────────────────────────────────────────────


class TestMatchParams:
    """yaml match 段参数应用：thresholds/weights/prefix_scope。"""

    def test_weights_default_aligned_with_active_matcher(self) -> None:
        cfg = PipelineConfig()
        assert cfg.match.weights == ActiveMatcher.WITHIN_TYPE_WEIGHTS, (
            "S4 对齐：yaml 默认权重必须等于 ActiveMatcher.WITHIN_TYPE_WEIGHTS"
            "（否则默认应用会破坏 FR9 等价）"
        )

    def test_thresholds_default_aligned_with_component_matching(self) -> None:
        from cis2hdl.core.config import ComponentMatchingConfig

        cfg = PipelineConfig()
        cmc = ComponentMatchingConfig()
        assert cfg.match.thresholds["exact"] == cmc.exact_threshold
        assert cfg.match.thresholds["fuzzy"] == cmc.fuzzy_threshold
        assert cfg.match.thresholds["feature"] == cmc.feature_threshold
        assert cfg.match.thresholds["fallback"] == cmc.fallback_threshold

    def test_prefix_scope_default_empty(self) -> None:
        assert PipelineConfig().match.prefix_scope == {}

    def test_plugin_receives_yaml_params(self) -> None:
        pc = PipelineConfig()
        pc.match.weights = {"part_name": 0.9, "footprint": 0.05}
        pc.match.thresholds = {"exact": 0.99, "fuzzy": 0.8}
        pc.match.prefix_scope = {"R": ["1206"]}
        pm = build_plugin_manager(pc, engine=_engine())
        plug = pm.get_plugin("exact")
        assert plug is not None
        assert plug.weights == pc.match.weights
        assert plug.thresholds["exact"] == 0.99
        assert plug.prefix_scope == {"R": ["1206"]}

    def test_apply_thresholds_and_restore(self) -> None:
        from cis2hdl.plugins.match._match_params import (
            apply_match_params,
            restore_match_params,
        )

        mc = Config.get().matching
        orig_exact = mc.exact_threshold
        applied = apply_match_params(thresholds={"exact": 0.999})
        assert mc.exact_threshold == 0.999  # 生效
        restore_match_params(applied)
        assert mc.exact_threshold == orig_exact  # 恢复

    def test_apply_weights_and_restore(self) -> None:
        from cis2hdl.plugins.match._match_params import (
            apply_match_params,
            restore_match_params,
        )

        orig = dict(ActiveMatcher.WITHIN_TYPE_WEIGHTS)
        applied = apply_match_params(weights={"part_name": 0.9})
        assert ActiveMatcher.WITHIN_TYPE_WEIGHTS["part_name"] == 0.9
        assert ActiveMatcher.WITHIN_TYPE_WEIGHTS["footprint"] == orig["footprint"]
        restore_match_params(applied)
        assert ActiveMatcher.WITHIN_TYPE_WEIGHTS == orig

    def test_apply_weights_jedec_type_alias(self) -> None:
        from cis2hdl.plugins.match._match_params import (
            apply_match_params,
            restore_match_params,
        )

        orig = dict(ActiveMatcher.WITHIN_TYPE_WEIGHTS)
        applied = apply_match_params(weights={"jedec_type": 0.5})
        assert ActiveMatcher.WITHIN_TYPE_WEIGHTS["jedec"] == 0.5  # 别名映射
        restore_match_params(applied)
        assert ActiveMatcher.WITHIN_TYPE_WEIGHTS == orig

    def test_apply_unknown_weight_ignored(self) -> None:
        from cis2hdl.plugins.match._match_params import (
            apply_match_params,
            restore_match_params,
        )

        orig = dict(ActiveMatcher.WITHIN_TYPE_WEIGHTS)
        applied = apply_match_params(weights={"bogus": 1.0})
        assert ActiveMatcher.WITHIN_TYPE_WEIGHTS == orig  # 无变化
        restore_match_params(applied)


class TestPrefixScope:
    """prefix_scope 过滤 helper（默认空 = 不过滤；显式配置收窄）。"""

    def test_is_scope_effective_default_false(self) -> None:
        from cis2hdl.plugins.match._prefix_scope import is_scope_effective

        assert is_scope_effective(None) is False
        assert is_scope_effective({}) is False
        assert is_scope_effective({"R": []}) is False
        assert is_scope_effective({"IC": ["any"]}) is False
        assert is_scope_effective({"R": ["0603"]}) is True

    def test_candidate_in_scope(self) -> None:
        from cis2hdl.plugins.match._prefix_scope import candidate_in_scope

        c1 = _make_candidate(footprint="HSC0603-HDTB")
        c2 = _make_candidate(footprint="HSC2512-HDTB")
        assert candidate_in_scope(c1, ["0603"]) is True
        assert candidate_in_scope(c2, ["0603"]) is False
        # package_type / jedec_type 也参与
        c3 = _make_candidate(part_name="CAPACITOR")
        c3.extra_data = {"ptf_rows": [{"package_type": "C0402", "jedec_type": "CAPACITOR"}]}
        assert candidate_in_scope(c3, ["0402"]) is True
        assert candidate_in_scope(c3, ["sot223"]) is False

    def test_apply_prefix_scope_filters_db(self) -> None:
        from cis2hdl.core.db.component_db import ComponentDB
        from cis2hdl.plugins.match._prefix_scope import apply_prefix_scope

        db = ComponentDB()
        db.add(_make_candidate(library_id="hdl_lib/resistor_0603", footprint="HSC0603-HDTB"))
        db.add(_make_candidate(library_id="hdl_lib/resistor_2512", footprint="HSC2512-HDTB"))
        db.add(_make_candidate(library_id="hdl_lib/capacitor_0402", footprint="HSC0402-HDTB"))

        # 默认空 → 原引用不变（FR9）
        assert apply_prefix_scope({}, db) is db
        assert apply_prefix_scope(None, db) is db

        # 显式 {R: [0603, 0402]} → 收窄（并集语义）
        filtered = apply_prefix_scope({"R": ["0603", "0402"]}, db)
        ids = {c.library_id for c in filtered.list_all()}
        assert ids == {
            "hdl_lib/resistor_0603",
            "hdl_lib/capacitor_0402",
        }
        assert len(db.list_all()) == 3  # 原始 DB 不变


# ─────────────────────────────────────────────────────────────────────────
# 3. 编排等价（HG5015 real fixture）
# ─────────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="class")
def hg5015_legacy_match() -> list:
    """legacy 匹配阶段产物（_stage_match + _append_power_symbol_matches）。"""
    _skip_if_missing(_HG_DSN)
    engine = _engine()
    report = ConversionReport()
    design = engine._legacy_load_input(_HG_DSN, report, None)
    hdl_db = engine._stage_scan(_HDL, report, None) if _HDL.exists() else None
    results = engine._stage_match(
        design, hdl_db, report, None,
        getattr(engine, "_last_cross_ref_map", None),
    )
    engine._append_power_symbol_matches(design, results)
    return results


@pytest.fixture(scope="class")
def hg5015_plugin_ctx(hg5015_legacy_match) -> ConversionContext:
    """plugin 模式匹配阶段产物（match_components 钩子链）。"""
    _skip_if_missing(_HG_DSN)
    pc = PipelineConfig()  # 默认 [exact, fuzzy, passive, fallback]
    engine = _engine()
    ctx = _ctx(pc, _HG_DSN)
    report = ctx.report
    design = engine._legacy_load_input(_HG_DSN, report, None)
    ctx.ir = design
    ctx.hdl_db = engine._stage_scan(_HDL, report, None) if _HDL.exists() else None
    pm = build_plugin_manager(pc, engine=engine)
    results = pm.hook.match_components(ctx=ctx)
    assert any(results), "match 插件链应接管匹配阶段"
    return ctx


class TestMatchOrchestrationEquivalence:
    """默认 profile 插件匹配 == legacy 匹配阶段（HG5015）。"""

    def test_match_count_and_strategy_distribution(
        self,
        hg5015_legacy_match: list,
        hg5015_plugin_ctx: ConversionContext,
    ) -> None:
        legacy = hg5015_legacy_match
        plugin = hg5015_plugin_ctx.matches
        assert len(plugin) == len(legacy)
        from collections import Counter

        assert Counter(m.strategy for m in plugin) == Counter(
            m.strategy for m in legacy
        )

    def test_match_mapping_identical(
        self,
        hg5015_legacy_match: list,
        hg5015_plugin_ctx: ConversionContext,
    ) -> None:
        legacy = {
            m.source_library_id: m.target_library_id for m in hg5015_legacy_match
        }
        plugin = {
            m.source_library_id: m.target_library_id
            for m in hg5015_plugin_ctx.matches
        }
        assert plugin == legacy

    def test_second_plugin_skips_when_handled(self) -> None:
        """链首 exact 编排后，fuzzy/passive/fallback 跳过（不重复匹配）。"""
        _skip_if_missing(_HG_DSN)
        pc = PipelineConfig()
        engine = _engine()
        ctx = _ctx(pc, _HG_DSN)
        design = engine._legacy_load_input(_HG_DSN, ctx.report, None)
        ctx.ir = design
        ctx.hdl_db = engine._stage_scan(_HDL, ctx.report, None) if _HDL.exists() else None
        pm = build_plugin_manager(pc, engine=engine)
        results = pm.hook.match_components(ctx=ctx)
        # 4 插件：exact True，其余 False（跳过）
        assert results[0] is True
        assert all(r is False for r in results[1:])

    def test_single_plugin_profile_equivalent(self) -> None:
        """单插件 profile（[fuzzy] 等）也应产出与 legacy 相同的匹配。"""
        _skip_if_missing(_HG_DSN)
        for name in ("exact", "fuzzy", "passive", "fallback", "matcher_pipeline"):
            pc = PipelineConfig()
            pc.match.plugins = [name]
            engine = _engine()
            ctx = _ctx(pc, _HG_DSN)
            report = ctx.report
            design = engine._legacy_load_input(_HG_DSN, report, None)
            ctx.ir = design
            ctx.hdl_db = (
                engine._stage_scan(_HDL, report, None) if _HDL.exists() else None
            )
            pm = build_plugin_manager(pc, engine=engine)
            results = pm.hook.match_components(ctx=ctx)
            assert any(results), f"profile [{name}] 应接管匹配"
            # 与 legacy 长度一致（映射等价由上面 test 覆盖；此处防回归）
            legacy = engine._stage_match(
                design, ctx.hdl_db, ConversionReport(), None,
                getattr(engine, "_last_cross_ref_map", None),
            )
            engine._append_power_symbol_matches(design, legacy)
            assert len(ctx.matches) == len(legacy), f"profile [{name}] 长度不一致"


# ─────────────────────────────────────────────────────────────────────────
# 4. manual_overrides 插件（FR3）
# ─────────────────────────────────────────────────────────────────────────


class TestManualOverridesPlugin:
    """manual_overrides 插件：委托 + ctx 契约 + chip_config 同步。"""

    def test_requires_matches(self) -> None:
        from cis2hdl.plugins.match.manual_overrides import ManualOverridesPlugin

        pc = PipelineConfig()
        ctx = _ctx(pc, _HG_DSN)
        plug = ManualOverridesPlugin(engine=_engine())
        assert plug.apply_manual_overrides(ctx) is False  # 无 ir/hdl_db/matches

    def test_applies_chip_config_and_writes_summary(self, tmp_path: Path) -> None:
        """启用 manual_overrides 插件 + chip_config → 覆盖应用 + ctx 摘要。"""
        _skip_if_missing(_HG_DSN)
        # 构造匹配阶段（legacy 直调，保证前置产物完整）
        engine = _engine()
        pc = PipelineConfig()
        ctx = _ctx(pc, _HG_DSN)
        report = ctx.report
        design = engine._legacy_load_input(_HG_DSN, report, None)
        ctx.ir = design
        ctx.hdl_db = engine._stage_scan(_HDL, report, None) if _HDL.exists() else None
        match_results = engine._stage_match(
            design, ctx.hdl_db, report, None,
            getattr(engine, "_last_cross_ref_map", None),
        )
        engine._append_power_symbol_matches(design, match_results)
        ctx.matches = match_results

        # 选一个已匹配源 → 覆盖到其自身 target（幂等但证明应用路径）
        target = ""
        for m in match_results:
            if m.target_library_id:
                target = m.target_library_id
                break
        assert target, "HG5015 应有已匹配结果"
        src = next(
            m.source_library_id for m in match_results if m.target_library_id
        )
        chip = tmp_path / "chip_config.yaml"
        chip.write_text(
            "version: '2.0'\nmatches:\n"
            f"  - refdes: '{src}'\n"
            f"    library_id: '{target}'\n"
            "    section: 1\n",
            encoding="utf-8",
        )

        pc.match.manual_overrides.file = str(chip)
        pc.match.plugins.append("manual_overrides")
        pm = build_plugin_manager(pc, engine=engine)
        ctx.cfg = pc
        results = pm.hook.apply_manual_overrides(ctx=ctx)
        assert any(results), "manual_overrides 插件应接管"
        assert ctx.manual_overrides["applied"] is True
        assert ctx.manual_overrides["chip_config"] == str(chip)
        # 覆盖后该源 strategy=MANUAL
        for m in ctx.matches:
            if m.source_library_id == src:
                assert m.strategy == MatchStrategy.MANUAL
                assert m.target_library_id == target
                break
        else:
            pytest.fail(f"{src} 未出现在匹配结果中")

    def test_disabled_by_default_no_registration(self) -> None:
        pc = PipelineConfig()
        pm = build_plugin_manager(pc, engine=_engine())
        assert pm.get_plugin("manual_overrides") is None

    def test_cleanup_releases_engine(self) -> None:
        from cis2hdl.plugins.match.manual_overrides import ManualOverridesPlugin

        plug = ManualOverridesPlugin(engine=_engine())
        plug.cleanup()
        assert plug.engine is None
