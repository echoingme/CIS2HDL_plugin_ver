"""Unit tests for StructuredReportGenerator v2c HTML/JSON changes.

Covers (PRD A.1–A.5):
  - A.1: Type column shows phase1_type (not hdl_category)
  - A.2: three summary card groups, value-above-label, derived stats
  - A.3: Top-1 main row dark, Top-3 header/rank rows light
  - A.4: candidate rows carry value/jedec/package_type/pin_count
  - A.5: three JEDEC columns + hdl_package_type in JSON/CSV contract
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cis2hdl.core.diagnostics.report_gen import StructuredReportGenerator
from cis2hdl.core.engine.conversion_engine import ConversionReport
from cis2hdl.core.ir.match import MatchResult, MatchStrategy


def _make_match(
    src: str,
    tgt: str,
    strategy: MatchStrategy,
    confidence: float,
    phase1_type: str = "",
    hdl_category: str = "",
    hdl_package_type: str = "",
    hdl_footprint: str = "",
    hdl_jedec: str = "",
    cis_jedec: str = "",
    top3: list[dict] | None = None,
) -> MatchResult:
    """Build a MatchResult with v2c extra_data for reporting tests."""
    return MatchResult(
        confidence=confidence,
        strategy=strategy,
        source_library_id=src,
        target_library_id=tgt,
        phase1_type=phase1_type,
        jedec_type=cis_jedec,
        extra_data={
            "hdl_category": hdl_category,
            "hdl_package_type": hdl_package_type,
            "hdl_footprint": hdl_footprint,
            "hdl_jedec": hdl_jedec,
        },
        top3_candidates=top3 or [],
    )


def _make_report() -> ConversionReport:
    """Build a ConversionReport with representative matches and outputs."""
    report = ConversionReport(
        project_name="v2c_test",
        pages=6,
        instances=10,
        nets=4,
        output_files=[
            "out/sch_1/page1.csa",
            "out/sch_1/page2.csa",
            "out/sch_1/page3.csa",
            "out/HG5015.cpm",
            "out/cds.lib",
        ],
    )
    report.match_results = [
        _make_match(
            "C1", "hdl_lib/capacitor", MatchStrategy.PASSIVE_EXACT, 1.0,
            phase1_type="capacitor", hdl_category="DISCRETE",
            hdl_package_type="C0603", hdl_footprint="C0603",
            hdl_jedec="CAPACITOR", cis_jedec="CAPACITOR",
            top3=[
                {
                    "type": "capacitor",
                    "library_id": "hdl_lib/capacitor",
                    "part_name": "CAPACITOR",
                    "primitive": "CAPACITOR_0603",
                    "value": "10UF",
                    "jedec": "CAPACITOR",
                    "package_type": "C0603",
                    "pin_count": 2,
                    "final_conf": 1.0,
                    "match_dims": "value✅ footprint✅",
                },
                {
                    "type": "capacitor",
                    "library_id": "hdl_lib/capacitor_2",
                    "part_name": "CAPACITOR_2",
                    "primitive": "CAPACITOR_0402",
                    "value": "10UF",
                    "jedec": "CAPACITOR",
                    "package_type": "C0402",
                    "pin_count": 2,
                    "final_conf": 0.8,
                    "match_dims": "value✅ footprint⚠️",
                },
            ],
        ),
        _make_match(
            "J10", "hdl_lib/rj45_2x2_led", MatchStrategy.ACTIVE_WITHIN_TYPE, 0.73,
            phase1_type="connector", hdl_category="connector",
            hdl_package_type="", hdl_footprint="",
            hdl_jedec="RJ45", cis_jedec="MJ8-R-P",
        ),
        _make_match(
            "U3", "", MatchStrategy.NEEDS_REVIEW, 0.2,
            phase1_type="IC", hdl_category="IC",
        ),
    ]
    return report


class TestReportJson:
    """JSON contract — v2c derived stats and hdl_package_type."""

    def test_report_to_dict_adds_hdl_package_type(self) -> None:
        """Each match dict carries hdl_package_type (A.5)."""
        gen = StructuredReportGenerator()
        data = gen._report_to_dict(_make_report())
        c1 = next(m for m in data["match_results"] if m["source_library_id"] == "C1")
        assert c1["hdl_package_type"] == "C0603"

    def test_report_to_dict_adds_derived_stats(self) -> None:
        """hdl_pages / matched_instances / matched_nets are computed (A.2)."""
        gen = StructuredReportGenerator()
        data = gen._report_to_dict(_make_report())
        assert data["hdl_pages"] == 3  # *.csa files only
        # C1 (PASSIVE_EXACT) + J10 (ACTIVE_WITHIN_TYPE) → 2; U3 excluded
        assert data["matched_instances"] == 2
        assert data["matched_nets"] == 4  # 1:1 copy of nets


class TestReportHtml:
    """HTML rendering — A.1–A.5."""

    def test_summary_cards_three_groups_value_above_label(self) -> None:
        """Three card groups with value-above-label order (A.2)."""
        html = StructuredReportGenerator().generate_html(_make_report())
        assert "CIS 解析" in html
        assert "HDL 输出" in html
        assert "Matched Instances" in html
        assert "Matched Nets" in html
        # Value-above-label: find a card's value then label order
        value_pos = html.find('class="card-value">10<')
        label_pos = html.find("Instances")
        assert value_pos != -1 and label_pos != -1
        assert value_pos < label_pos

    def test_summary_stats_values(self) -> None:
        """Derived stats render with correct numbers (A.2)."""
        html = StructuredReportGenerator().generate_html(_make_report())
        assert "Matched Instances" in html
        # The matched_instances value '2' appears in the HDL group
        assert '<div class="card-value">2</div>' in html
        assert '<div class="card-value">3</div>' in html  # hdl_pages

    def test_type_column_uses_phase1_type(self) -> None:
        """Type (phase1) column shows phase1_type, not DISCRETE (A.1)."""
        html = StructuredReportGenerator().generate_html(_make_report())
        assert "Type (phase1)" in html
        # C1: hdl_category=DISCRETE but phase1_type=capacitor
        assert ">capacitor</td>" in html
        assert "DISCRETE" not in html

    def test_jedec_three_columns(self) -> None:
        """CIS JEDEC / HDL JEDEC / HDL PACKAGE_TYPE headers present (A.5)."""
        html = StructuredReportGenerator().generate_html(_make_report())
        assert "CIS JEDEC" in html
        assert "HDL JEDEC" in html
        assert "HDL PACKAGE_TYPE" in html
        assert "HDL Footprint" not in html

    def test_match_main_row_dark(self) -> None:
        """Top-1 main row has match-main class with light-gray bg (R7).

        Phase XII R7: the main row was changed from medium-gray #6B6860 to
        a light gray #E5E2D8 (slightly darker than the top-3 candidate rows
        rgba(108,104,96,0.04)) with dark text, so confidence colors remain
        distinguishable.  The old #A8C58A !important override is removed.
        """
        html = StructuredReportGenerator().generate_html(_make_report())
        assert 'class="match-main"' in html
        assert "#E5E2D8" in html  # light-gray main-row background (R7)
        assert "#A8C58A" not in html  # old conf !important override removed
        assert ".match-main td.conf-cell" not in html

    def test_top3_header_and_rank_rows_light(self) -> None:
        """Top-3 header + rank rows remain light (A.3)."""
        html = StructuredReportGenerator().generate_html(_make_report())
        assert "▼ Top-2 Candidates" in html
        assert 'class="top3-header"' in html
        assert 'class="top3-row"' in html

    def test_candidate_row_enriched_fields(self) -> None:
        """Candidate rows show value/jedec/package_type/pin_count (A.4)."""
        html = StructuredReportGenerator().generate_html(_make_report())
        assert "CAPACITOR_0603" in html
        assert "C0603" in html
        assert "CAPACITOR_0402" in html
        assert "C0402" in html

    def test_html_is_single_file_no_external_fonts(self) -> None:
        """HTML is a single file with inline CSS; no external font links."""
        html = StructuredReportGenerator().generate_html(_make_report())
        assert "<style>" in html
        assert "http" not in html.split("<style>")[1].split("</style>")[0]
        assert "@import" not in html
