"""Integration tests for the full end-to-end CIS2HDL conversion pipeline.

Converted from phase2_e2e_pipeline.py standalone script to pytest.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

from cis2hdl.core.engine.conversion_engine import ConversionEngine
from cis2hdl.core.diagnostics.report_gen import StructuredReportGenerator


class TestFullE2EPipeline:
    """End-to-end pipeline integration tests using real RTL8367RB DSN."""

    def test_pipeline_converts_real_dsn(self, real_dsn_path: Path, real_edf_path: Path) -> None:
        """Full pipeline converts real DSN+EDF project successfully."""
        if not real_dsn_path.exists():
            pytest.skip(f"DSN fixture not found: {real_dsn_path}")
        if not real_edf_path.exists():
            pytest.skip(f"EDF fixture not found: {real_edf_path}")

        engine = ConversionEngine()
        stages: list[str] = []

        def progress_cb(stage: str, pct: int, msg: str) -> None:
            stages.append(f"[{stage}] {pct}%: {msg}")

        with tempfile.TemporaryDirectory(prefix="cis2hdl_e2e_") as tmp:
            out = Path(tmp)
            report = engine.convert(real_dsn_path, out, progress_callback=progress_cb)

            # Basic report assertions
            assert report.project_name, "project_name should not be empty"
            assert report.pages > 0, f"pages={report.pages}"
            assert report.instances > 0, f"instances={report.instances}"
            assert report.nets > 0, f"nets={report.nets}"

            # Stage execution
            stage_pcts = [s for s in stages if '%' in s]
            assert len(stage_pcts) > 0, "Should have executed at least one stage"

            # Quality metrics
            if hasattr(report, 'quality') and report.quality:
                q = report.quality
                if hasattr(q, 'logic_score'):
                    assert 0 <= q.logic_score <= 1

    def test_pipeline_generates_reports(self, real_dsn_path: Path, real_edf_path: Path) -> None:
        """Pipeline generates valid JSON and HTML reports."""
        if not real_dsn_path.exists():
            pytest.skip(f"DSN fixture not found: {real_dsn_path}")
        if not real_edf_path.exists():
            pytest.skip(f"EDF fixture not found: {real_edf_path}")

        engine = ConversionEngine()
        with tempfile.TemporaryDirectory(prefix="cis2hdl_report_") as tmp:
            out = Path(tmp)
            report = engine.convert(real_dsn_path, out)

            gen = StructuredReportGenerator()
            json_str = gen.generate_json(report)
            html_str = gen.generate_html(report)

            assert len(json_str) > 100, f"JSON too short: {len(json_str)} bytes"
            assert len(html_str) > 500, f"HTML too short: {len(html_str)} bytes"
            assert "<!DOCTYPE html>" in html_str
            assert "<body" in html_str
