"""S6 — 输出插件真实现单测：独立启停 + 顺序执行 + 文件集合断言（FR5/FR9）。

设计依据：``docs/developer-guide.md`` S6 章节 / ``cis2hdl/plugins/output/_base.py``。

覆盖：
  1. 11 个 output 插件（csa/con/xcon/csv/cpc/cpm/cds_lib + aesthetic/
     ioport/mapping/error）真实现：cls 非 None、stage="output"、
     writes_keys 契约、独立文件模块。
  2. 默认 profile 注册 7 文件 + 4 报告；write_output/write_report 执行
     顺序 = yaml 顺序（csa,con,xcon,csv,cpc,cpm,cds_lib / aesthetic,
     ioport,mapping,error）。
  3. 独立启停：output.files/reports 精确控制注册（禁 csv → csv 插件不
     注册；禁 mapping → mapping 插件不注册）。
  4. 文件插件 _write 真调用：最小 DesignConnectivity + OutputManager →
     断言写出文件集合（con/xcon/csv/cpc/cpm/cds_lib）。
  5. 报告插件 _write_report 真调用：mapping/error 写出报告文件；
     aesthetic/ioport no-op 返回空。
  6. 引擎聚合：_apply_plugin_output_files 按 legacy generate() 顺序
     重排（cpm → cds_lib → con → xcon → csv → cpc → csa → infra）。
  7. cleanup 复位（幂等）。
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from cis2hdl.core.config import Config
from cis2hdl.core.engine.conversion_engine import ConversionEngine
from cis2hdl.core.pipeline_config import PipelineConfig
from cis2hdl.plugins.context import ConversionContext
from cis2hdl.plugins.manager import build_plugin_manager
from cis2hdl.plugins.ordering import assert_order

_PROJECT_ROOT = Path(__file__).resolve().parents[2]

#: 11 个输出插件名。
_FILE_PLUGINS = ("csa", "con", "xcon", "csv", "cpc", "cpm", "cds_lib")
_REPORT_PLUGINS = ("aesthetic", "ioport", "mapping", "error")
_ALL_PLUGINS = _FILE_PLUGINS + _REPORT_PLUGINS


@pytest.fixture(autouse=True)
def _restore_global_config() -> None:
    """保存/恢复全局 Config 单例（防顺序依赖污染，同 S5 单测）。"""
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


def _ctx(pc: PipelineConfig, **kw) -> ConversionContext:
    return ConversionContext(cfg=pc, **kw)


# ─────────────────────────────────────────────────────────────────────────
# 1. 插件元数据与注册
# ─────────────────────────────────────────────────────────────────────────


class TestOutputPluginSpecs:
    """S6 插件元数据：真实现、writes_keys 契约、独立文件模块。"""

    @pytest.mark.parametrize("name", _ALL_PLUGINS)
    def test_output_plugin_real_spec(self, name: str) -> None:
        pm = build_plugin_manager(PipelineConfig())
        spec = next(s for s in pm.list_plugins("output") if s.name == name)
        assert spec.cls is not None, f"{name} 应为真实现"
        assert spec.stage == "output"
        assert spec.writes_keys == ()
        assert spec.builtin is True
        # 独立文件模块（模块名 = 插件名）
        assert spec.module.endswith(f"output.{name}")

    def test_all_eleven_output_plugins_discovered(self) -> None:
        pm = build_plugin_manager(PipelineConfig())
        names = {s.name for s in pm.list_plugins("output")}
        assert names == set(_ALL_PLUGINS)

    def test_default_profile_registration(self) -> None:
        """默认 profile 注册 7 文件 + 4 报告插件（= legacy 全文件）。"""
        pc = PipelineConfig()
        pm = build_plugin_manager(pc)
        for name in _FILE_PLUGINS:
            assert pm.get_plugin(name) is not None, f"{name} 应注册"
        for name in _REPORT_PLUGINS:
            assert pm.get_plugin(name) is not None, f"{name} 应注册"

    def test_output_execution_order_matches_yaml(self) -> None:
        """write_output/write_report 执行顺序 = yaml 顺序（S2 逆序注册）。"""
        pc = PipelineConfig()
        engine, pm = _pm_for(pc)
        # 文件链（yaml files 顺序）
        assert pm.hook_execution_order("write_output") == list(_FILE_PLUGINS)
        # 报告链（yaml reports 顺序）
        assert pm.hook_execution_order("write_report") == list(_REPORT_PLUGINS)
        # 传统断言接口同样成立（get_hookimpls 逆序）
        assert_order(pm, "beautify", ["overlap_resolve", "gnd_cluster", "parallel_short"])


# ─────────────────────────────────────────────────────────────────────────
# 2. 独立启停
# ─────────────────────────────────────────────────────────────────────────


class TestOutputIndependentEnable:
    """每输出插件可独立启停（FR2；output.files/reports 控制）。"""

    @pytest.mark.parametrize("name", _FILE_PLUGINS)
    def test_single_file_plugin_registers(self, name: str) -> None:
        pc = PipelineConfig()
        pc.output.files = [name]
        pc.output.reports = []
        engine, pm = _pm_for(pc)
        assert pm.get_plugin(name) is not None
        assert pm.hook_execution_order("write_output") == [name]
        others = set(_FILE_PLUGINS) - {name}
        for other in others:
            assert pm.get_plugin(other) is None, f"{other} 不应注册"
        # 报告插件全部不注册
        for other in _REPORT_PLUGINS:
            assert pm.get_plugin(other) is None, f"{other} 不应注册"

    @pytest.mark.parametrize("name", _REPORT_PLUGINS)
    def test_single_report_plugin_registers(self, name: str) -> None:
        pc = PipelineConfig()
        pc.output.files = []
        pc.output.reports = [name]
        engine, pm = _pm_for(pc)
        assert pm.get_plugin(name) is not None
        assert pm.hook_execution_order("write_report") == [name]
        for other in set(_REPORT_PLUGINS) - {name}:
            assert pm.get_plugin(other) is None, f"{other} 不应注册"
        for other in _FILE_PLUGINS:
            assert pm.get_plugin(other) is None, f"{other} 不应注册"

    def test_empty_output_no_plugins(self) -> None:
        """files=[] 且 reports=[] → 无输出插件注册（链空 → legacy fallback）。"""
        pc = PipelineConfig()
        pc.output.files = []
        pc.output.reports = []
        engine, pm = _pm_for(pc)
        assert pm.hook_execution_order("write_output") == []
        assert pm.hook_execution_order("write_report") == []

    def test_partial_combination(self) -> None:
        """部分组合：[csa, con] + [mapping] → 只注册这三个 + 顺序正确。"""
        pc = PipelineConfig()
        pc.output.files = ["csa", "con"]
        pc.output.reports = ["mapping"]
        engine, pm = _pm_for(pc)
        assert pm.hook_execution_order("write_output") == ["csa", "con"]
        assert pm.hook_execution_order("write_report") == ["mapping"]
        for name in ("xcon", "csv", "cpc", "cpm", "cds_lib"):
            assert pm.get_plugin(name) is None
        for name in ("aesthetic", "ioport", "error"):
            assert pm.get_plugin(name) is None


# ─────────────────────────────────────────────────────────────────────────
# 3. 文件插件 _write 真调用（最小 conn + OutputManager 文件集合断言）
# ─────────────────────────────────────────────────────────────────────────


class TestOutputFileWriters:
    """文件插件编排 writer 子步骤 → 写出对应文件（不重写逻辑）。"""

    def _conn(self, sample_design, sample_component_db):
        from cis2hdl.core.writer.connectivity_model import ConnectivityModelBuilder
        return ConnectivityModelBuilder(
            sample_design,
            matches=[],
            hdl_db=sample_component_db,
            hdl_lib_name="hdl_lib",
        ).build()

    def _mgr(self, tmp_path: Path, sample_design):
        from cis2hdl.core.writer.output_manager import OutputManager
        mgr = OutputManager(
            project_name=sample_design.project_name,
            output_root=tmp_path,
        )
        mgr.setup_directory_structure()
        return mgr

    def test_con_writer_plugin(self, tmp_path, sample_design, sample_component_db) -> None:
        from cis2hdl.plugins.output.con import ConOutputPlugin
        conn = self._conn(sample_design, sample_component_db)
        mgr = self._mgr(tmp_path, sample_design)
        plugin = ConOutputPlugin(engine=_engine())
        ctx = _ctx(PipelineConfig())
        paths = plugin._write(ctx, mgr, conn)
        assert len(paths) == 1
        assert paths[0].name == f"{conn.cell_name}.con"
        assert paths[0].exists()

    def test_xcon_writer_plugin(self, tmp_path, sample_design, sample_component_db) -> None:
        from cis2hdl.plugins.output.xcon import XconOutputPlugin
        conn = self._conn(sample_design, sample_component_db)
        mgr = self._mgr(tmp_path, sample_design)
        plugin = XconOutputPlugin(engine=_engine())
        paths = plugin._write(_ctx(PipelineConfig()), mgr, conn)
        assert len(paths) == 1
        assert paths[0].name == f"{conn.cell_name}.xcon"
        assert paths[0].exists()

    def test_csv_writer_plugin(self, tmp_path, sample_design, sample_component_db) -> None:
        from cis2hdl.plugins.output.csv import CsvOutputPlugin
        conn = self._conn(sample_design, sample_component_db)
        mgr = self._mgr(tmp_path, sample_design)
        plugin = CsvOutputPlugin(engine=_engine())
        paths = plugin._write(_ctx(PipelineConfig()), mgr, conn)
        assert paths, "应写出页级 csv"
        assert all(p.name.endswith(".csv") for p in paths)
        assert all(p.exists() for p in paths)

    def test_cpc_writer_plugin(self, tmp_path, sample_design, sample_component_db) -> None:
        from cis2hdl.plugins.output.cpc import CpcOutputPlugin
        conn = self._conn(sample_design, sample_component_db)
        mgr = self._mgr(tmp_path, sample_design)
        plugin = CpcOutputPlugin(engine=_engine())
        paths = plugin._write(_ctx(PipelineConfig()), mgr, conn)
        assert paths, "应写出页级 cpc"
        assert all(p.name.endswith(".cpc") for p in paths)

    def test_cpm_writer_plugin(self, tmp_path, sample_design, sample_component_db) -> None:
        from cis2hdl.plugins.output.cpm import CpmOutputPlugin
        conn = self._conn(sample_design, sample_component_db)
        mgr = self._mgr(tmp_path, sample_design)
        plugin = CpmOutputPlugin(engine=_engine())
        paths = plugin._write(_ctx(PipelineConfig()), mgr, conn)
        assert len(paths) == 1
        assert paths[0].name == f"{mgr.cell_name}.cpm"
        assert paths[0].exists()

    def test_cds_lib_writer_plugin(self, tmp_path, sample_design, sample_component_db) -> None:
        from cis2hdl.plugins.output.cds_lib import CdsLibOutputPlugin
        conn = self._conn(sample_design, sample_component_db)
        mgr = self._mgr(tmp_path, sample_design)
        plugin = CdsLibOutputPlugin(engine=_engine())
        paths = plugin._write(_ctx(PipelineConfig()), mgr, conn)
        names = {p.name for p in paths}
        assert "cds.lib" in names
        assert "hdldirect.dat" in names
        assert all(p.exists() for p in paths)


# ─────────────────────────────────────────────────────────────────────────
# 4. 报告插件 _write_report 真调用
# ─────────────────────────────────────────────────────────────────────────


class TestOutputReportWriters:
    """报告插件编排 writer → 写出报告文件（mapping/error 真委托）。"""

    def _ctx_with(self, pc: PipelineConfig, sample_design, tmp_path: Path) -> ConversionContext:
        return ConversionContext(
            cfg=pc,
            input_files=[Path("dummy.dsn")],
            output_dir=tmp_path,
            ir=sample_design,
            matches=[],
        )

    def test_mapping_report_plugin(self, tmp_path, sample_design, sample_component_db) -> None:
        from cis2hdl.plugins.output.mapping import MappingReportPlugin
        pc = PipelineConfig()
        ctx = self._ctx_with(pc, sample_design, tmp_path)
        ctx.report.project_name = sample_design.project_name
        plugin = MappingReportPlugin(engine=_engine())
        paths = plugin._write_report(ctx)
        assert len(paths) == 2
        assert paths[0].name == f"{sample_design.project_name}_mapping.csv"
        assert paths[1].name == f"{sample_design.project_name}_top3.txt"
        assert all(p.exists() for p in paths)

    def test_error_report_plugin(self, tmp_path, sample_design) -> None:
        from cis2hdl.plugins.output.error import ErrorReportPlugin
        pc = PipelineConfig()
        ctx = self._ctx_with(pc, sample_design, tmp_path)
        ctx.report.project_name = sample_design.project_name
        plugin = ErrorReportPlugin(engine=_engine())
        paths = plugin._write_report(ctx)
        assert len(paths) == 2
        assert all(p.exists() for p in paths)

    def test_aesthetic_report_noop(self, tmp_path, sample_design) -> None:
        from cis2hdl.plugins.output.aesthetic import AestheticReportPlugin
        pc = PipelineConfig()
        ctx = self._ctx_with(pc, sample_design, tmp_path)
        plugin = AestheticReportPlugin(engine=_engine())
        assert plugin._write_report(ctx) == []

    def test_ioport_report_noop(self, tmp_path, sample_design) -> None:
        from cis2hdl.plugins.output.ioport import IoportReportPlugin
        pc = PipelineConfig()
        ctx = self._ctx_with(pc, sample_design, tmp_path)
        plugin = IoportReportPlugin(engine=_engine())
        assert plugin._write_report(ctx) == []


# ─────────────────────────────────────────────────────────────────────────
# 5. 引擎聚合：_apply_plugin_output_files 顺序（FR9 report.html 渲染）
# ─────────────────────────────────────────────────────────────────────────


class TestEngineOutputAggregation:
    """write_output 产出按 legacy generate() 顺序重排追加 output_files。"""

    def test_apply_plugin_output_files_reorder(self) -> None:
        pc = PipelineConfig()
        engine, pm = _pm_for(pc)
        ctx = _ctx(pc, output_dir=Path("/out"), ir=object(), matches=[])
        results = [
            [Path("/out/worklib/cell/sch_1/page1.csa")],       # csa（执行序 1）
            [Path("/out/worklib/cell/sch_1/cell.con")],        # con
            [Path("/out/worklib/cell/sch_1/cell.xcon")],       # xcon
            [Path("/out/worklib/cell/sch_1/page1.csv")],       # csv
            [Path("/out/worklib/cell/sch_1/page1.cpc")],       # cpc
            [Path("/out/cell.cpm")],                           # cpm
            [Path("/out/cds.lib")],                            # cds_lib
        ]
        # 用 stub 共享状态避免真实构建（顺序断言只关心重排逻辑）。
        engine._output_shared[Path("/out")] = (None, None, [
            Path("/out/worklib/cell/sch_1/cell.dcf"),
            Path("/out/worklib/cell/sch_1/module_order.dat"),
            Path("/out/worklib/cell/sch_1/page.map"),
            Path("/out/worklib/cell/sch_1/master.tag"),
        ])
        engine._apply_plugin_output_files(ctx, results)
        appended = [Path(p) for p in ctx.report.output_files]
        # legacy generate() 顺序：cpm → cds.lib → con → xcon → csv → cpc
        # → csa → cell 支撑（dcf/module_order/page.map/master.tag）
        assert appended == [
            Path("/out/cell.cpm"),
            Path("/out/cds.lib"),
            Path("/out/worklib/cell/sch_1/cell.con"),
            Path("/out/worklib/cell/sch_1/cell.xcon"),
            Path("/out/worklib/cell/sch_1/page1.csv"),
            Path("/out/worklib/cell/sch_1/page1.cpc"),
            Path("/out/worklib/cell/sch_1/page1.csa"),
            Path("/out/worklib/cell/sch_1/cell.dcf"),
            Path("/out/worklib/cell/sch_1/module_order.dat"),
            Path("/out/worklib/cell/sch_1/page.map"),
            Path("/out/worklib/cell/sch_1/master.tag"),
        ]

    def test_apply_plugin_output_files_dedupes(self) -> None:
        pc = PipelineConfig()
        engine, pm = _pm_for(pc)
        ctx = _ctx(pc, output_dir=Path("/out"), ir=object(), matches=[])
        results = [
            [Path("/out/page1.csa"), Path("/out/page1.csa")],
        ]
        engine._output_shared[Path("/out")] = (None, None, [])
        engine._apply_plugin_output_files(ctx, results)
        assert ctx.report.output_files == [str(Path("/out/page1.csa"))]

    def test_apply_plugin_report_files_order(self) -> None:
        pc = PipelineConfig()
        engine, pm = _pm_for(pc)
        ctx = _ctx(pc, output_dir=Path("/out"), ir=object(), matches=[])
        # 执行序 = yaml reports：aesthetic([]) ioport([]) mapping mapping.csv
        # error err.html → 追加顺序与 legacy _legacy_reports 一致
        results = [
            [],
            [],
            [Path("/out/p_mapping.csv"), Path("/out/p_top3.txt")],
            [Path("/out/p_errors.html"), Path("/out/p_errors.log")],
        ]
        engine._apply_plugin_report_files(ctx, results)
        assert ctx.report.output_files == [
            str(Path("/out/p_mapping.csv")),
            str(Path("/out/p_top3.txt")),
            str(Path("/out/p_errors.html")),
            str(Path("/out/p_errors.log")),
        ]


# ─────────────────────────────────────────────────────────────────────────
# 6. cleanup / 钩子执行
# ─────────────────────────────────────────────────────────────────────────


class TestOutputCleanup:
    def test_cleanup_resets_engine(self) -> None:
        pc = PipelineConfig()
        engine = _engine()
        pm = build_plugin_manager(pc, engine=engine)
        csa = pm.get_plugin("csa")
        assert csa.engine is engine
        pm.cleanup()
        assert csa.engine is None

    def test_cleanup_idempotent(self) -> None:
        pm = build_plugin_manager(PipelineConfig())
        pm.cleanup()
        pm.cleanup()
        assert pm._registered_names == []
        assert len(pm.hook.write_output.get_hookimpls()) == 0
        assert len(pm.hook.write_report.get_hookimpls()) == 0

    def test_file_plugin_hook_returns_paths(self) -> None:
        """write_output 链（默认 profile）返回各插件路径列表（可空）。"""
        pc = PipelineConfig()
        pc.output.files = ["con"]
        pc.output.reports = []
        engine, pm = _pm_for(pc)
        ctx = _ctx(pc, output_dir=None)  # 无 output_dir → 各插件返回 None
        results = pm.hook.write_output(ctx=ctx)
        assert len(results) == 1
