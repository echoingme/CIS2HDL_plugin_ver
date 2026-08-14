"""Phase XVIII R4 — 元件库统一 hdl_lib + CSA 属性注入（CrossRef）。

Covers:
  * `_inject_crossref_props` 从 CrossRef CSV 注入四字段（golden CAPACITOR
    块格式：FORCEPROP 1 LAST <KEY> <value> + J 0 + DISPLAY 1.021277）
  * 缺失字段跳过、禁止 "?" 默认值注入
  * `audit_origin_refs` 全量扫描返回 []（无 ORIGIN 引用）
  * `CandidatePoolBuilder` hdl_lib_only 过滤（Q1）
  * CrossRefParser 四属性解析（头行列名驱动）
"""

from __future__ import annotations

from pathlib import Path

_FIXTURES_HDL_LIB = Path(__file__).parent.parent / "fixtures" / "hdl_lib"


def _entry(**kw):
    from cis2hdl.core.parser.cross_ref_parser import CrossRefEntry

    defaults = dict(
        refdes="C1", value="100NF", schematic_name="T/05-P", sheet="0",
        library="LIB.OLB", x=1.0, y=2.0,
    )
    defaults.update(kw)
    return CrossRefEntry(**defaults)


class TestCrossRefAttrParse:
    def test_header_driven_attrs(self):
        """真实项目 CSV 头行含 DESCRIPTION/JEDEC_TYPE/PACKAGE_TYPE/SN_NUM。"""
        from cis2hdl.core.parser.cross_ref_parser import CrossRefParser

        csv_text = (
            "Item,Part,Reference,SchematicName,Sheet,Library,X,Y,"
            "DESCRIPTION,JEDEC_TYPE,PACKAGE_TYPE,SN_NUM\n"
            "____________________________________________________________________________\n"
            "1,100NF*,C1,T/05-P,0,C:/LIB.OLB, 1.00, 2.00, "
            "CAP 100NF 10V,0402R-S,R0402,M02.010176\n"
        )
        entries = CrossRefParser().parse(csv_text, "test")
        e = entries["C1"]
        assert e.description == "CAP 100NF 10V"
        assert e.jedec_type == "0402R-S"
        assert e.package_type == "R0402"
        assert e.sn_num == "M02.010176"

    def test_absent_columns_empty(self):
        """无四属性列的 CSV → 字段保持空串（向后兼容）。"""
        from cis2hdl.core.parser.cross_ref_parser import CrossRefParser

        csv_text = (
            "Item,Part,Reference,SchematicName,Sheet,Library,X,Y\n"
            "____________________________________________________________________________\n"
            "1,100NF*,C1,T/05-P,0,C:/LIB.OLB, 1.00, 2.00\n"
        )
        entries = CrossRefParser().parse(csv_text, "test")
        e = entries["C1"]
        assert e.description == "" and e.jedec_type == ""

    def test_catalog_entry_carries_attrs(self):
        from cis2hdl.core.parser.component_catalog import ComponentCatalog

        csv_text = (
            "Item,Part,Reference,SchematicName,Sheet,Library,X,Y,"
            "DESCRIPTION,JEDEC_TYPE,PACKAGE_TYPE,SN_NUM\n"
            "____________________________________________________________________________\n"
            "1,100NF*,C1,T/05-P,0,C:/LIB.OLB, 1.00, 2.00, "
            "CAP 100NF 10V,0402R-S,R0402,M02.010176\n"
        )
        path = Path(__import__("tempfile").mkdtemp()) / "design.CSV"
        path.write_text(csv_text, encoding="utf-8")
        catalog = ComponentCatalog.from_cross_ref(path)
        entry = catalog.get_by_refdes("C1")
        assert entry is not None
        assert entry.jedec_type == "0402R-S"
        assert entry.sn_num == "M02.010176"


class TestInjectCrossrefProps:
    def _writer(self, crossref=None):
        from cis2hdl.core.config import RoutingConfig
        from cis2hdl.core.writer.csa_writer import CSAWriter

        w = CSAWriter(routing_cfg=RoutingConfig())
        w.set_crossref_map(crossref or {})
        return w

    def _irec(self, refdes="C1", props=None):
        return type(
            "IRec", (), {
                "refdes": refdes,
                "properties": props or {},
            },
        )()

    def test_four_fields_injected(self):
        w = self._writer({"C1": _entry(
            description="CAP 100NF 10V",
            jedec_type="0402R-S",
            package_type="R0402",
            sn_num="M02.010176",
        )})
        lines = w._inject_crossref_props(self._irec(), {}, 100, 200)
        text = "\n".join(lines)
        assert "FORCEPROP 1 LAST JEDEC_TYPE 0402R-S" in text
        assert "FORCEPROP 1 LAST SN_NUM M02.010176" in text
        assert "FORCEPROP 1 LAST PACKAGE_TYPE R0402" in text
        assert "FORCEPROP 1 LAST DESCRIPTION CAP 100NF 10V" in text
        # golden 格式：J 0 + (x y); + DISPLAY 1.021277 + DISPLAY INVISIBLE
        assert "J 0" in text
        assert "(100 200);" in text
        assert "DISPLAY 1.021277 (100 200);" in text
        assert "DISPLAY INVISIBLE (100 200);" in text

    def test_missing_field_skipped_no_question(self):
        w = self._writer({"C1": _entry(description="", jedec_type="?")})
        lines = w._inject_crossref_props(self._irec(), {}, 0, 0)
        text = "\n".join(lines)
        assert "DESCRIPTION" not in text, "缺失字段禁止注入"
        assert "JEDEC_TYPE" not in text, "? 默认值禁止注入"
        assert "SN_NUM" not in text

    def test_props_fallback(self):
        """CrossRef 缺失时回退 irec.properties（非 "?" 值）。"""
        w = self._writer({})
        lines = w._inject_crossref_props(
            self._irec(props={"JEDEC_TYPE": "0402R-S", "SN_NUM": "?"}),
            {"JEDEC_TYPE": "0402R-S", "SN_NUM": "?"},
            0, 0,
        )
        text = "\n".join(lines)
        assert "JEDEC_TYPE 0402R-S" in text
        assert "SN_NUM" not in text, "? 值跳过"

    def test_disabled_by_config(self):
        from cis2hdl.core.config import RoutingConfig

        cfg = RoutingConfig()
        cfg.attribute.inject_crossref = False
        from cis2hdl.core.writer.csa_writer import CSAWriter

        w = CSAWriter(routing_cfg=cfg)
        w.set_crossref_map({"C1": _entry(jedec_type="0402R-S")})
        assert w._inject_crossref_props(self._irec(), {}, 0, 0) == []

    def test_conn_block_contains_crossref_attrs(self):
        """集成：CSA 实例块含 CrossRef 四字段（golden 字段级比对）。"""
        from cis2hdl.core.ir.component import ComponentInstanceIR
        from cis2hdl.core.ir.design import DesignIR, PageIR
        from cis2hdl.core.writer.connectivity_model import ConnectivityModelBuilder
        from cis2hdl.core.config import RoutingConfig
        from cis2hdl.core.writer.csa_writer import CSAWriter

        p1 = PageIR(page_id="1.1", page_name="05-Power_Supply1")
        p1.instances = [
            ComponentInstanceIR(
                refdes="C1", library_id="CAPACITOR", loc_x=4500, loc_y=12000,
                rotation=0, mirror=0,
                pin_connections={"1": "NET_A", "2": "NET_B"},
            ),
        ]
        design = DesignIR(project_name="T", pages=[p1])
        conn = ConnectivityModelBuilder(design, matches=[]).build()
        w = CSAWriter(routing_cfg=RoutingConfig(), hdl_lib_path=_FIXTURES_HDL_LIB)
        w.set_crossref_map({"C1": _entry(
            description="CAP 100NF 10V",
            jedec_type="0201-RF",
            package_type="C0201",
            sn_num="M01.090002",
        )})
        content = w._build_csa_content_conn(conn, conn.pages[0])
        for key, val in (
            ("JEDEC_TYPE", "0201-RF"),
            ("SN_NUM", "M01.090002"),
            ("PACKAGE_TYPE", "C0201"),
            ("DESCRIPTION", "CAP 100NF 10V"),
        ):
            assert f"FORCEPROP 1 LAST {key} {val}" in content, key


class TestAuditOriginRefs:
    def test_fixtures_hdl_lib_clean(self):
        """hdl_lib fixtures 无 ORIGIN 引用 → 返回 []。"""
        from cis2hdl.core.writer.audit_origin_refs import audit_origin_refs

        violations = audit_origin_refs(_FIXTURES_HDL_LIB, [])
        assert violations == []

    def test_clean_csa_pages(self, tmp_path):
        from cis2hdl.core.writer.audit_origin_refs import audit_origin_refs

        page = tmp_path / "page1.csa"
        page.write_text(
            "FILE_TYPE = MACRO_DRAWING;\n"
            "FORCEADD CAPACITOR..1\n"
            "(-100 200);\n"
            "FORCEPROP 2 LAST CDS_LIB hdl_lib\n"
            "J 0\n"
            "(-100 200);\n"
            "DISPLAY INVISIBLE (-100 200);\n",
            encoding="utf-8",
        )
        assert audit_origin_refs(_FIXTURES_HDL_LIB, [page]) == []

    def test_origin_in_csa_detected(self, tmp_path):
        from cis2hdl.core.writer.audit_origin_refs import audit_origin_refs

        page = tmp_path / "page1.csa"
        page.write_text(
            "FORCEADD CAPACITOR..1\n"
            "FORCEPROP 2 LAST CDS_LIB ORIGIN\n",
            encoding="utf-8",
        )
        violations = audit_origin_refs(_FIXTURES_HDL_LIB, [page])
        assert any("ORIGIN" in v for v in violations)

    def test_foreign_cds_lib_detected(self, tmp_path):
        from cis2hdl.core.writer.audit_origin_refs import audit_origin_refs

        page = tmp_path / "page1.csa"
        page.write_text(
            "FORCEPROP 2 LAST CDS_LIB standard\n",
            encoding="utf-8",
        )
        violations = audit_origin_refs(_FIXTURES_HDL_LIB, [page])
        assert any("CDS_LIB standard" in v for v in violations)

    def test_origin_in_hdl_lib_detected(self, tmp_path):
        from cis2hdl.core.writer.audit_origin_refs import audit_origin_refs

        lib = tmp_path / "hdl_lib"
        (lib / "capacitor" / "sym_1").mkdir(parents=True)
        (lib / "capacitor" / "sym_1" / "symbol.css").write_text(
            'P "CDS_LIB" "ORIGIN"\n', encoding="utf-8",
        )
        violations = audit_origin_refs(lib, [])
        assert any("ORIGIN" in v for v in violations)


class TestHdlLibOnly:
    def _fake_db(self, candidates):
        class DB:
            def list_all(self):
                return list(candidates)

        return DB()

    def _comp(self, library_id, source_format="HDL", source_file=""):
        from cis2hdl.core.ir.component import ComponentDef

        return ComponentDef(
            library_id=library_id, part_name=library_id, category="ic",
            source_format=source_format, source_file=source_file,
        )

    def test_filters_system_lib(self):
        from cis2hdl.core.matcher.candidate_pool import CandidatePoolBuilder

        db = self._fake_db([
            self._comp("capacitor"),
            self._comp("ORIGIN", source_format="HDL"),
            self._comp("standard/foo", source_format="system"),
        ])
        builder = CandidatePoolBuilder(db, hdl_lib_only=True)
        pool = builder.build([])
        # 无 type hypotheses → type_sets 空；直接检查内部候选集。
        assert builder._all_candidates is not None
        ids = [c.library_id for c in builder._all_candidates]
        assert "capacitor" in ids
        assert "ORIGIN" not in ids
        assert "standard/foo" not in ids

    def test_disabled_keeps_all(self):
        from cis2hdl.core.matcher.candidate_pool import CandidatePoolBuilder

        db = self._fake_db([
            self._comp("capacitor"),
            self._comp("standard/foo", source_format="system"),
        ])
        builder = CandidatePoolBuilder(db, hdl_lib_only=False)
        builder.build([])
        assert len(builder._all_candidates) == 2


class TestEntireCsvFormat:
    """Phase XVIII R4：OrCAD "Entire" 导出（tab 分隔）解析支持。

    真实项目（HG5015-BE36_V10/entire.csv）是 tab 分隔 + ``"HEADER"``
    头行 + ``"PARTINST:..."`` 数据行格式，与简化版（逗号分隔
    ``Item,Part,...``）不同。R4 修复使解析器同时支持两种格式。
    """

    _ENTIRE = (
        '"DESIGN"\t"C:\\DSN\\HG5015.DSN"\n'
        '"HEADER"\t"ID"\t"Part Reference"\t"Value"\t"DESCRIPTION"\t'
        '"JEDEC_TYPE"\t"PACKAGE_TYPE"\t"SN_NUM"\t"CATEGORY_NAME"\n'
        '"PARTINST:TG1:05-P:1"\t"C1"\t"C1"\t"100nF"\t"CIS 100NF"\t'
        '"0402R-S"\t"R0402"\t"M02.010176"\t"CAPACITOR"\n'
        '"PININST:TG1:05-P:1:0"\t"C1:A"\t"<null>"\t"<null>"\t"<null>"\t'
        '"<null>"\t"<null>"\t"<null>"\t"<null>"\n'
    )

    def test_entire_format_parses(self):
        from cis2hdl.core.parser.cross_ref_parser import CrossRefParser

        entries = CrossRefParser().parse(self._ENTIRE, "entire.csv")
        assert "C1" in entries
        e = entries["C1"]
        assert e.value == "100nF"
        assert e.package_type == "R0402"
        assert e.jedec_type == "0402R-S"
        assert e.sn_num == "M02.010176"
        assert e.description == "CIS 100NF"

    def test_entire_pininst_skipped(self):
        """PININST 行不产生条目（仅 PARTINST 是元件）。"""
        from cis2hdl.core.parser.cross_ref_parser import CrossRefParser

        entries = CrossRefParser().parse(self._ENTIRE, "entire.csv")
        assert len(entries) == 1  # 只有 C1

    def test_entire_null_placeholders_filtered(self):
        """OrCAD 空值占位符（<null>/NULL/?）不注入。"""
        from cis2hdl.core.parser.cross_ref_parser import CrossRefParser

        csv_text = (
            '"HEADER"\t"ID"\t"Part Reference"\t"Value"\t"PACKAGE_TYPE"\t"SN_NUM"\n'
            '"PARTINST:T:1"\t"R1"\t"R1"\t"4.7K"\t"<null>"\t"?"\n'
        )
        entries = CrossRefParser().parse(csv_text, "entire.csv")
        e = entries["R1"]
        assert e.package_type == ""
        assert e.sn_num == ""

    def test_simplified_format_regression(self):
        """简化版（逗号分隔 Item,Part,...）回归不受影响。"""
        from cis2hdl.core.parser.cross_ref_parser import CrossRefParser

        csv_text = (
            "Item,Part,Reference,SchematicName,Sheet,Library,X,Y,"
            "DESCRIPTION,JEDEC_TYPE,PACKAGE_TYPE,SN_NUM\n"
            "____________________________________________________________________________\n"
            "1,100NF*,C1,T/05-P,0,C:/LIB.OLB, 1.00, 2.00, "
            "CAP 100NF,0402R-S,R0402,M02.010176\n"
        )
        entries = CrossRefParser().parse(csv_text, "simplified.csv")
        assert entries["C1"].package_type == "R0402"

    def test_entire_detect_delimiter(self):
        from cis2hdl.core.parser.cross_ref_parser import CrossRefParser

        assert CrossRefParser._detect_delimiter("a\tb\tc") == "\t"
        assert CrossRefParser._detect_delimiter("a,b,c") == ","


class TestEntirePageAttribution:
    """Phase XVIII R4-修复：OrCAD "Entire" 导出的页面归属与坐标提取。

    用户真实数据（HG5015test/entire.csv）的 PARTINST 行 ID 列编码页面路径
    ``"PARTINST:<设计>:<页面>:<序号>"``，且坐标在 Location X/Y 列。修复前
    schematic_name 为空 → 转换引擎 fuzzy 匹配 ``'' in page_id`` 恒真，
    全部实例被塞进 page1（P0-D2 页面归属错乱，915 元件挤 1 页）。
    """

    _ENTIRE = (
        '"DESIGN"\t"C:\\\\DSN\\\\HG.DSN"\n'
        '"HEADER"\t"ID"\t"Part Reference"\t"Value"\t"DESCRIPTION"\t'
        '"PACKAGE_TYPE"\t"Location X-Coordinate"\t"Location Y-Coordinate"\n'
        '"PARTINST:TG1C0D8_VB:10-SOC_SerDes:265"\t"C96"\t"C96"\t"100nF"\t'
        '"CIS 100NF"\t"R0402"\t"1050"\t"410"\n'
        '"PARTINST:TG1C0D8_VB:19-WIFI5G_FEM_C0:12"\t"R7"\t"R7"\t"4.7K"\t'
        '"R 4.7K"\t"SR0402"\t"2000"\t"300"\n'
    )

    def test_page_name_from_id_column(self):
        from cis2hdl.core.parser.cross_ref_parser import CrossRefParser

        entries = CrossRefParser().parse(self._ENTIRE, "entire.csv")
        assert entries["C96"].page_name() == "10-SOC_SerDes"
        assert entries["R7"].page_name() == "19-WIFI5G_FEM_C0"

    def test_schematic_name_matches_simplified_format(self):
        """页面名与简化版 SchematicName 列（``设计/页面``）同构。"""
        from cis2hdl.core.parser.cross_ref_parser import CrossRefParser

        entries = CrossRefParser().parse(self._ENTIRE, "entire.csv")
        assert entries["C96"].schematic_name == "TG1C0D8_VB/10-SOC_SerDes"

    def test_location_coordinates_extracted(self):
        from cis2hdl.core.parser.cross_ref_parser import CrossRefParser

        entries = CrossRefParser().parse(self._ENTIRE, "entire.csv")
        assert entries["C96"].x == 1050.0
        assert entries["C96"].y == 410.0

    def test_no_empty_page_attribution(self):
        """所有 PARTINST 行都必须有页面名（不得为空 → 防 page1 挤爆）。"""
        from pathlib import Path
        from cis2hdl.core.parser.cross_ref_parser import CrossRefParser

        m = CrossRefParser().parse_file(
            Path("tests/fixtures/HG5015test/entire.csv"))
        empty = [k for k, v in m.items() if not v.page_name()]
        assert not empty, f"空页面归属: {empty[:5]}"
        # 页面覆盖 ≥ 简化版（20 页），无空页
        pages = {v.page_name() for v in m.values()}
        assert len(pages) >= 15 and "" not in pages
