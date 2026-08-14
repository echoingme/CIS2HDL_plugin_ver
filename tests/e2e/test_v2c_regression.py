"""v2c regression tests — real HG5015 HDL library integration.

Covers the two most important v2c fixes against REAL library data:

  - A.5 (0402C-S mystery): PassiveMatcher L1 must report the ACTUAL
    size-matched part.ptf row.  C1 (10UF + 0603) must enrich with
    hdl_package_type=C0603 — NOT the first value row (C0402).
  - A.6 (J10 wildcard): J10 (MJ8-M2, empty footprint) must rescue via
    the footprint-wildcard path → ACTIVE_WITHIN_TYPE with
    phase2_within_conf=0.85 and final conf >= 0.65 (with the persisted
    J→connector affinity this is 0.86×0.85 = 0.731 >= 0.70 per PRD).
  - A.2 (stats cards): HTML report contains the three card groups.

Uses ``HG5015_tests/output_v2b/hdl_lib`` (the real scanned library).
Skips gracefully when the library is unavailable.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_HDL_LIB = _PROJECT_ROOT / "HG5015_tests" / "output_v2b" / "hdl_lib"

# S0 排除项：HG5015_tests/（交付包，未复制进插件版仓库）。
# 数据目录存在时正常验证；缺失时整体跳过（插件版基线 929/6/0 全绿）。
pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(
        not _HDL_LIB.is_dir(),
        reason=f"数据目录未复制（S0 排除项）: {_HDL_LIB}",
    ),
]

from cis2hdl.core.diagnostics.report_gen import StructuredReportGenerator
from cis2hdl.core.engine.conversion_engine import ConversionReport
from cis2hdl.core.ir.component import ComponentDef, ElectricalType, PinDef
from cis2hdl.core.ir.match import MatchStrategy
from cis2hdl.core.matcher.pipeline import MatcherPipeline
from cis2hdl.core.parser.hdl_scanner import HDLLibScanner


def _make_cis_component(
    library_id: str,
    refdes: str,
    part_name: str,
    category: str,
    value: str,
    footprint: str,
    pin_count: int = 2,
    extra_data: dict | None = None,
) -> ComponentDef:
    """Build a CIS-side ComponentDef with refdes for the pipeline.

    NOTE: when ``pin_count=0`` (unknown), NO pins are created — otherwise
    ``ComponentDef.model_post_init`` would derive pin_count=1 from the
    single pin and defeat the wildcard pin-compatibility gate.
    """
    comp = ComponentDef(
        library_id=library_id,
        part_name=part_name,
        category=category,
        footprint=footprint,
        value=value,
        pin_count=pin_count,
        pins=[
            PinDef(number=str(i + 1), name=f"PIN{i + 1}", type=ElectricalType.PASSIVE)
            for i in range(max(pin_count, 0))
        ],
        extra_data=extra_data or {},
    )
    object.__setattr__(comp, "refdes", refdes)
    return comp


@pytest.fixture(scope="module")
def hdl_db():
    """Scan the real v2b HDL library once per module."""
    if not _HDL_LIB.exists() or not _HDL_LIB.is_dir():
        pytest.skip(f"HDL library not found: {_HDL_LIB}")
    db = HDLLibScanner().scan(_HDL_LIB)
    assert len(db) > 0, "scanned HDL library is empty"
    return db


class TestV2cMatchedRowLinkage:
    """A.5 — report follows the actual matched size row."""

    def test_c1_10uf_0603_reports_c0603(self, hdl_db) -> None:
        """C1 (10UF + 0603) → PASSIVE_EXACT with hdl_package_type=C0603."""
        c1 = _make_cis_component(
            library_id="C1",
            refdes="C1",
            part_name="CAP_10UF",
            category="capacitor",
            value="10UF",
            footprint="SC0603-TD",
            extra_data={"jedec_type": "CAPACITOR"},
        )
        pipeline = MatcherPipeline()
        results = pipeline.run_batch([c1], hdl_db)
        result = results[0]

        # L1 value+size double-exact is correct and must be preserved.
        assert result.strategy == MatchStrategy.PASSIVE_EXACT
        assert result.confidence == 1.0

        # v2c: enrichment must use the 0603 row, not the first value row (C0402).
        hdl_pkg = result.extra_data.get("hdl_package_type", "")
        hdl_fp = result.extra_data.get("hdl_footprint", "")
        assert hdl_pkg == "C0603", f"expected C0603, got {hdl_pkg!r}"
        assert hdl_fp == "C0603", f"expected C0603, got {hdl_fp!r}"
        # The matched-size marker must be 0603.
        assert result.extra_data.get("_matched_size") == "0603"


class TestV2cWildcardRescue:
    """A.6 — footprint wildcard rescue for J10."""

    def test_j10_wildcard_conf_improved(self, hdl_db) -> None:
        """J10 (catalog part_name='J10', value='MJ8-M2', empty fp) → within=0.85."""
        # Model the REAL catalog shape: part_name is a placeholder equal to
        # library_id; the meaningful part identity lives in the VALUE field.
        j10 = _make_cis_component(
            library_id="J10",
            refdes="J10",
            part_name="J10",
            category="connector",
            value="MJ8-M2",
            footprint="connector",
            pin_count=0,
            extra_data={"jedec_type": "MJ8-R-P"},
        )
        pipeline = MatcherPipeline()
        results = pipeline.run_batch([j10], hdl_db)
        result = results[0]

        assert result.strategy == MatchStrategy.ACTIVE_WITHIN_TYPE
        assert result.target_library_id == "rj45_2x2_led", (
            f"expected rj45_2x2_led, got {result.target_library_id!r}"
        )
        # The wildcard rescue itself is deterministic (within=0.85).
        assert result.phase2_within_conf >= 0.85
        # final = prior × 0.85.  Cold start prior=0.80 → 0.68;
        # with persisted J→connector affinity (1.0 → blended 0.86) → 0.731.
        assert result.confidence >= 0.65, (
            f"expected conf >= 0.65, got {result.confidence:.3f}"
        )
        assert "wildcard" in result.phase2_strategy_detail


class TestV2cReportStats:
    """A.2 — summary card groups present in the HTML report."""

    def test_html_has_three_card_groups(self, hdl_db) -> None:
        """The HTML report renders CIS/HDL/Output card groups."""
        report = ConversionReport(
            project_name="v2c_e2e",
            pages=6,
            instances=2,
            nets=4,
            output_files=["out/sch_1/page1.csa", "out/HG5015.cpm"],
        )
        c1 = _make_cis_component(
            library_id="C1", refdes="C1", part_name="CAP_10UF",
            category="capacitor", value="10UF", footprint="SC0603-TD",
            extra_data={"jedec_type": "CAPACITOR"},
        )
        j10 = _make_cis_component(
            library_id="J10", refdes="J10", part_name="MJ8-M2",
            category="connector", value="MJ8-M2", footprint="",
            pin_count=0, extra_data={"jedec_type": "MJ8-R-P"},
        )
        pipeline = MatcherPipeline()
        report.match_results = pipeline.run_batch([c1, j10], hdl_db)

        html = StructuredReportGenerator().generate_html(report)
        assert "CIS 解析" in html
        assert "HDL 输出" in html
        assert "Matched Instances" in html
        assert "Matched Nets" in html
        assert "Output Files" in html
        assert "HDL PACKAGE_TYPE" in html
        assert "Type (phase1)" in html

    def test_report_json_derived_stats(self, hdl_db) -> None:
        """_report_to_dict computes hdl_pages/matched_instances/matched_nets."""
        report = ConversionReport(
            project_name="v2c_e2e",
            pages=6,
            instances=2,
            nets=4,
            output_files=["out/sch_1/page1.csa", "out/HG5015.cpm"],
        )
        c1 = _make_cis_component(
            library_id="C1", refdes="C1", part_name="CAP_10UF",
            category="capacitor", value="10UF", footprint="SC0603-TD",
            extra_data={"jedec_type": "CAPACITOR"},
        )
        pipeline = MatcherPipeline()
        report.match_results = pipeline.run_batch([c1], hdl_db)

        data = StructuredReportGenerator()._report_to_dict(report)
        assert data["hdl_pages"] == 1  # only *.csa
        assert data["matched_instances"] == 1
        assert data["matched_nets"] == 4  # 1:1 copy
