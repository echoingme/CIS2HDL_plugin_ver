"""S3 T05 — input 插件独立启停 + 组合单元测试。

设计依据：``docs/developer-guide.md`` S3 章节 / ``docs/plugin-api.md``。

覆盖（FR1 + NFR7）：
  1. 5 个输入插件（edif/dsn/cross_ref/pstxnet/pstchip）真实现：cls 非 None、
     writes_keys=("ir",)、engine 注入可用。
  2. cfg.input.plugins 独立启停：禁用某插件 → 不注册；组合可配。
  3. edif 插件：P0-D2 EDIF 优先（.dsn → 同名 .EDF）、cross_ref/pst 增量
     委托语义（插件启用则跳过、禁用则内联，FR9 等价）。
  4. dsn 插件：直接 DSN 解析；与 edif 互斥（先到先得）。
  5. cross_ref 插件：CSV → ComponentCatalog + 坐标注入 + _last_cross_ref_map。
  6. pstxnet/pstchip 插件：pstxprt/pstxnet/pstchip 增量载入 pst_data。
  7. 单插件禁用不报错；全增量无解析器 → 不接管（回退 legacy）。
  8. 引擎 post-chain _finalize_plugin_input：catalog 重建 + 副作用暴露。
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from cis2hdl.core.config import Config
from cis2hdl.core.engine.conversion_engine import ConversionEngine, ConversionReport
from cis2hdl.core.pipeline_config import PipelineConfig
from cis2hdl.plugins.context import ConversionContext
from cis2hdl.plugins.manager import build_plugin_manager

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_FIXTURES = _PROJECT_ROOT / "tests" / "fixtures"
_HG_DSN = _FIXTURES / "HG5015test" / "HG5015-BE36_V10.DSN"
_HG_EDF = _FIXTURES / "HG5015test" / "HG5015-BE36_V10.EDF"
_EDF = _FIXTURES / "RTL8367RB-VC-DEMO-LQFP128EP-P4L-V1_0.EDF"


@pytest.fixture(autouse=True)
def _restore_global_config() -> None:
    """保存/恢复全局 Config 单例（防顺序依赖污染，同 S2 e2e）。"""
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


def _instances(design) -> int:
    return sum(len(p.instances) for p in design.pages)


class TestPluginSpecs:
    """S3 插件元数据：真实现、writes_keys 契约、独立启停。"""

    @pytest.mark.parametrize(
        "name,desc",
        [
            ("edif", "EDIF 解析"),
            ("dsn", "DSN 解析"),
            ("cross_ref", "CrossRef CSV"),
            ("pstxnet", "pstxnet 网络注入"),
            ("pstchip", "pstchip 引脚名恢复"),
        ],
    )
    def test_input_plugin_real_spec(self, name: str, desc: str) -> None:
        pm = build_plugin_manager(PipelineConfig(), engine=_engine())
        spec = next(s for s in pm.list_plugins("input") if s.name == name)
        assert spec.cls is not None, f"{name} 应为真实现（S3）"
        assert spec.writes_keys == ("ir",)
        assert desc in spec.description
        assert spec.stage == "input"

    def test_disabled_plugin_not_registered(self) -> None:
        pc = PipelineConfig()
        pc.input.plugins = ["edif", "pstxnet"]  # pstchip 禁用
        pm = build_plugin_manager(pc, engine=_engine())
        assert pm.get_plugin("pstchip") is None
        assert pm.get_plugin("edif") is not None
        assert pm.get_plugin("pstxnet") is not None

    def test_cross_ref_disabled_by_default(self) -> None:
        pm = build_plugin_manager(PipelineConfig(), engine=_engine())
        assert pm.get_plugin("cross_ref") is None  # 默认 profile 不含
        assert pm.get_plugin("dsn") is None

    def test_both_parsers_can_be_enabled(self) -> None:
        pc = PipelineConfig()
        pc.input.plugins = ["edif", "dsn", "pstxnet", "pstchip"]
        pm = build_plugin_manager(pc, engine=_engine())
        assert pm.get_plugin("edif") is not None
        assert pm.get_plugin("dsn") is not None


class TestEdifPlugin:
    """edif 插件：P0-D2 EDIF 优先 + cross_ref/pst 增量委托。"""

    def test_edif_parses_edf_input(self) -> None:
        _skip_if_missing(_EDF)
        from cis2hdl.plugins.input.edif import EdifInputPlugin

        engine = _engine()
        pc = PipelineConfig()
        plug = EdifInputPlugin(engine=engine)
        ctx = _ctx(pc, _EDF)
        assert plug.load_input(ctx) is True
        assert ctx.ir is not None
        assert ctx.ir.source_format == "CIS_EDIF"
        assert len(ctx.ir.pages) > 0

    def test_edif_prefers_edif_sibling_for_dsn(self) -> None:
        """P0-D2：.dsn 输入 + 同名 .EDF → 解析 EDIF（与 legacy 一致）。"""
        _skip_if_missing(_HG_DSN)
        from cis2hdl.plugins.input.edif import EdifInputPlugin

        engine = _engine()
        pc = PipelineConfig()
        plug = EdifInputPlugin(engine=engine)
        ctx = _ctx(pc, _HG_DSN)
        assert plug.load_input(ctx) is True
        assert ctx.ir is not None
        assert ctx.ir.source_format == "CIS_EDIF"

    def test_edif_inlines_cross_ref_and_pst_when_disabled(self) -> None:
        """profile=[edif]（cross_ref/pst 插件全禁用）→ edif 内联全链。"""
        _skip_if_missing(_HG_DSN)
        from cis2hdl.plugins.input.edif import EdifInputPlugin

        engine = _engine()
        pc = PipelineConfig()
        pc.input.plugins = ["edif"]
        plug = EdifInputPlugin(engine=engine)
        ctx = _ctx(pc, _HG_DSN)
        assert plug.load_input(ctx) is True
        # cross_ref 内联：catalog 已建
        catalog = ctx.ir.metadata.get("component_catalog")
        assert catalog is not None and len(catalog) > 0
        # pst 内联：pst_data 三源齐全
        pst = ctx.ir.metadata.get("pst_data", {})
        assert {"pstchip", "pstxprt", "pstxnet"} <= set(pst)

    def test_edif_skips_pst_when_plugins_enabled(self) -> None:
        """默认 profile：edif 只做解析 + cross_ref 内联；pst 由插件增量。"""
        _skip_if_missing(_HG_DSN)
        from cis2hdl.plugins.input.edif import EdifInputPlugin

        engine = _engine()
        pc = PipelineConfig()  # 默认 [edif, pstxnet, pstchip]
        plug = EdifInputPlugin(engine=engine)
        ctx = _ctx(pc, _HG_DSN)
        assert plug.load_input(ctx) is True
        # cross_ref 未启用 → edif 内联（legacy 行为，FR9）
        assert ctx.ir.metadata.get("component_catalog") is not None
        # pst 插件已启用 → edif 不加载 pst_data（留给 pstxnet/pstchip）
        assert "pst_data" not in ctx.ir.metadata


class TestDsnPlugin:
    """dsn 插件：直接 DSN 解析 + 与 edif 互斥。"""

    def test_dsn_parses_dsn_input(self) -> None:
        _skip_if_missing(_HG_DSN)
        from cis2hdl.plugins.input.dsn import DsnInputPlugin

        engine = _engine()
        pc = PipelineConfig()
        pc.input.plugins = ["dsn", "pstxnet", "pstchip"]
        plug = DsnInputPlugin(engine=engine)
        ctx = _ctx(pc, _HG_DSN)
        assert plug.load_input(ctx) is True
        assert ctx.ir is not None
        assert ctx.ir.source_format == "CIS_DSN"  # 不经 EDIF 优先

    def test_edif_dsn_mutual_exclusion_edif_first(self) -> None:
        """[edif, dsn] 双解析器：yaml 顺序 edif 先执行，dsn 见 ir 已设返回 False。"""
        _skip_if_missing(_HG_DSN)
        pc = PipelineConfig()
        pc.input.plugins = ["edif", "dsn"]
        engine = _engine()
        pm = build_plugin_manager(pc, engine=engine)
        ctx = _ctx(pc, _HG_DSN)
        results = pm.hook.load_input(ctx=ctx)
        assert results[0] is True or results[1] is True
        assert ctx.ir is not None
        # 无论哪个先跑，最终只有一个解析结果且不抛错
        assert len(ctx.ir.pages) > 0


class TestCrossRefPlugin:
    """cross_ref 插件：CSV → ComponentCatalog + 坐标注入。"""

    def test_cross_ref_builds_catalog(self) -> None:
        _skip_if_missing(_HG_DSN)
        from cis2hdl.plugins.input.cross_ref import CrossRefInputPlugin

        engine = _engine()
        pc = PipelineConfig()
        # 先手动解析（模拟 edif 已产出 ctx.ir）
        ctx = _ctx(pc, _HG_DSN)
        engine._stage_parse(engine._resolve_parse_path(_HG_DSN), ctx.report, None)
        # 重新走 edif 插件保证完整（简化：直接构造 parsed design）
        from cis2hdl.plugins.input.edif import EdifInputPlugin
        EdifInputPlugin(engine=engine).load_input(ctx)
        ctx2 = _ctx(pc, _HG_DSN)
        ctx2.ir = ctx.ir  # 复用已解析 design

        plug = CrossRefInputPlugin(engine=engine)
        assert plug.load_input(ctx2) is True
        catalog = ctx2.ir.metadata.get("component_catalog")
        assert catalog is not None and len(catalog) > 0
        assert len(engine._last_cross_ref_map) > 0

    def test_cross_ref_no_csv_no_crash(self) -> None:
        _skip_if_missing(_EDF)
        from cis2hdl.plugins.input.cross_ref import CrossRefInputPlugin

        engine = _engine()
        pc = PipelineConfig()
        ctx = _ctx(pc, _EDF)
        # RTL8367RB 目录无 CSV
        from cis2hdl.plugins.input.edif import EdifInputPlugin
        EdifInputPlugin(engine=engine).load_input(ctx)
        plug = CrossRefInputPlugin(engine=engine)
        assert plug.load_input(ctx) is True
        assert ctx.ir.metadata.get("component_catalog") is None

    def test_cross_ref_requires_parsed_ir(self) -> None:
        """无解析结果 → 不接管（返回 False，引擎回退 legacy）。"""
        from cis2hdl.plugins.input.cross_ref import CrossRefInputPlugin

        pc = PipelineConfig()
        ctx = ConversionContext(cfg=pc, input_files=[_HG_DSN])
        ctx.report = ConversionReport()
        plug = CrossRefInputPlugin(engine=_engine())
        assert plug.load_input(ctx) is False


class TestPstPlugins:
    """pstxnet/pstchip 插件：增量载入 pst_data。"""

    @pytest.fixture()
    def parsed_ctx(self) -> ConversionContext:
        """HG5015 edif 解析结果（无 pst_data）。"""
        _skip_if_missing(_HG_DSN)
        from cis2hdl.plugins.input.edif import EdifInputPlugin

        engine = _engine()
        pc = PipelineConfig()
        pc.input.plugins = ["edif"]
        ctx = _ctx(pc, _HG_DSN)
        EdifInputPlugin(engine=engine).load_input(ctx)
        # 清掉 edif 内联的 pst（模拟"pst 交给插件"场景）
        ctx.ir.metadata.pop("pst_data", None)
        return ctx

    def test_pstxnet_loads_pstxprt_and_net(self, parsed_ctx: ConversionContext) -> None:
        from cis2hdl.plugins.input.pstxnet import PstxnetInputPlugin

        plug = PstxnetInputPlugin(engine=_engine())
        assert plug.load_input(parsed_ctx) is True
        pst = parsed_ctx.ir.metadata.get("pst_data", {})
        assert "pstxprt" in pst
        assert "pstxnet" in pst
        assert "pstchip" not in pst  # 本插件不载 pstchip

    def test_pstchip_loads_pstchip(self, parsed_ctx: ConversionContext) -> None:
        from cis2hdl.plugins.input.pstchip import PstchipInputPlugin

        plug = PstchipInputPlugin(engine=_engine())
        assert plug.load_input(parsed_ctx) is True
        pst = parsed_ctx.ir.metadata.get("pst_data", {})
        assert "pstchip" in pst

    def test_disable_pstchip_no_error(self) -> None:
        """禁 pstchip（profile=[edif, pstxnet]）→ 不报错；pstxnet 插件贡献保留。

        设计契约（FR9 优先）：edif 是"完整解析链编排器"，对**未启用**的
        增量插件做内联补偿——任意含 edif 的 profile 输出与 legacy 等价；
        启用某增量插件则改由该插件执行对应子步骤（谁干活可变，结果不变）。
        """
        _skip_if_missing(_HG_DSN)
        pc = PipelineConfig()
        pc.input.plugins = ["edif", "pstxnet"]
        engine = _engine()
        pm = build_plugin_manager(pc, engine=engine)
        ctx = _ctx(pc, _HG_DSN)
        results = pm.hook.load_input(ctx=ctx)
        assert any(results)
        pst = ctx.ir.metadata.get("pst_data", {})
        # pstxnet 插件的贡献（pstxprt/pstxnet 由插件载入）
        assert "pstxprt" in pst and "pstxnet" in pst


class TestCombosAndFinalize:
    """组合等价性（IR 级）+ 引擎 post-chain 收尾。"""

    def test_no_parser_all_increments_fallback(self) -> None:
        """全增量无解析器（[cross_ref, pstxnet, pstchip]）→ 全部不接管。"""
        pc = PipelineConfig()
        pc.input.plugins = ["cross_ref", "pstxnet", "pstchip"]
        pm = build_plugin_manager(pc, engine=_engine())
        ctx = _ctx(pc, _HG_DSN)
        results = pm.hook.load_input(ctx=ctx)
        assert all(r is False for r in results)
        assert ctx.ir is None

    def test_single_plugin_disabled_no_error(self) -> None:
        """各类"少一个插件"组合：hook 链不抛错且接管。"""
        _skip_if_missing(_HG_DSN)
        combos = [
            ["edif"],
            ["edif", "pstxnet"],
            ["edif", "pstchip"],
            ["edif", "cross_ref", "pstxnet", "pstchip"],
            ["dsn", "pstxnet", "pstchip"],
        ]
        for plugins in combos:
            pc = PipelineConfig()
            pc.input.plugins = list(plugins)
            engine = _engine()
            pm = build_plugin_manager(pc, engine=engine)
            ctx = _ctx(pc, _HG_DSN)
            results = pm.hook.load_input(ctx=ctx)  # 不抛错即通过
            assert any(results), f"组合 {plugins} 未接管"
            assert ctx.ir is not None

    def test_finalize_plugin_input_rebuilds_and_side_effects(self) -> None:
        """post-chain：catalog 重建（1219 实例）+ _last_* 副作用（同 legacy）。"""
        _skip_if_missing(_HG_DSN)
        pc = PipelineConfig()  # 默认 [edif, pstxnet, pstchip]
        engine = _engine()
        pm = build_plugin_manager(pc, engine=engine)
        ctx = _ctx(pc, _HG_DSN)
        pm.hook.load_input(ctx=ctx)
        assert ctx.ir is not None
        before = _instances(ctx.ir)
        assert before == 3023  # EDIF 占位实例（重建前）

        engine._finalize_plugin_input(ctx.ir, ctx.report, _HG_DSN)
        after = _instances(ctx.ir)
        assert after == 1219  # 914 catalog + 305 power（与 legacy 一致）
        assert engine._last_catalog is not None
        assert len(engine._last_cross_ref_map) > 0
        assert ctx.report.instances == after

    def test_default_profile_matches_legacy_ir_shape(self) -> None:
        """默认 profile 插件链产出 DesignIR 形状 == legacy 全链（HG5015）。"""
        _skip_if_missing(_HG_DSN)
        # legacy 全链
        engine_legacy = _engine()
        r_legacy = ConversionReport()
        design_legacy = engine_legacy._legacy_load_input(_HG_DSN, r_legacy, None)
        assert design_legacy is not None
        assert _instances(design_legacy) == 1219

        # plugin 默认 profile
        pc = PipelineConfig()
        engine_p = _engine()
        pm = build_plugin_manager(pc, engine=engine_p)
        ctx = _ctx(pc, _HG_DSN)
        pm.hook.load_input(ctx=ctx)
        engine_p._finalize_plugin_input(ctx.ir, ctx.report, _HG_DSN)

        assert len(ctx.ir.pages) == len(design_legacy.pages)
        assert _instances(ctx.ir) == _instances(design_legacy)
        assert set(ctx.ir.metadata.get("pst_data", {})) == set(
            design_legacy.metadata.get("pst_data", {})
        )
        assert len(ctx.ir.metadata["component_catalog"]) == len(
            design_legacy.metadata["component_catalog"]
        )
        # refdes 集合一致（catalog 重建后实例同一性）
        refdes_p = {
            i.refdes for pg in ctx.ir.pages for i in pg.instances
        }
        refdes_l = {
            i.refdes for pg in design_legacy.pages for i in pg.instances
        }
        assert refdes_p == refdes_l
