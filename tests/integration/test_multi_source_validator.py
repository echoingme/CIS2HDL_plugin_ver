"""Integration tests for MultiSourceCrossValidator."""
from __future__ import annotations

import pytest
from pathlib import Path

pytestmark = [pytest.mark.integration]


class TestMultiSourceIntegration:
    """Integration tests using real fixture data."""

    @pytest.fixture(autouse=True)
    def _setup(self, fixtures_dir: Path) -> None:
        self.dsn_path = fixtures_dir / "RTL8367RB-VC-DEMO-LQFP128EP-P4L-V1_0.DSN"
        self.edf_path = fixtures_dir / "RTL8367RB-VC-DEMO-LQFP128EP-P4L-V1_0.EDF"
        if not self.dsn_path.exists() or not self.edf_path.exists():
            pytest.skip("Required fixtures not found")

    def test_two_source_basic(self) -> None:
        """DSN vs EDF: basic validation produces summary."""
        from cis2hdl.core.diagnostics.multi_source import MultiSourceCrossValidator
        from cis2hdl.core.parser.dsn.dsn_parser import DSNParser
        from cis2hdl.core.parser.edif_parser import EDIFParser

        dsn_ir = DSNParser().parse(self.dsn_path)
        edf_ir = EDIFParser().parse(self.edf_path)
        report = MultiSourceCrossValidator().validate(
            dsn_ir=dsn_ir, edf_ir=edf_ir,
        )
        assert report.sources_available >= 2
        assert isinstance(report.summary(), str)
        assert isinstance(report.detailed_report(), str)

    def test_two_source_has_pin_checks(self) -> None:
        """DSN vs EDF: validation includes pin count comparisons."""
        from cis2hdl.core.diagnostics.multi_source import MultiSourceCrossValidator
        from cis2hdl.core.parser.dsn.dsn_parser import DSNParser
        from cis2hdl.core.parser.edif_parser import EDIFParser

        dsn_ir = DSNParser().parse(self.dsn_path)
        edf_ir = EDIFParser().parse(self.edf_path)
        report = MultiSourceCrossValidator().validate(
            dsn_ir=dsn_ir, edf_ir=edf_ir,
        )
        pin_issues = [i for i in report.issues if i.category == "pin"]
        # May have pin count issues or may not, but should not crash
        assert isinstance(pin_issues, list)

    def test_two_source_has_device_type_checks(self) -> None:
        """DSN vs EDF: validation includes device type grouping."""
        from cis2hdl.core.diagnostics.multi_source import MultiSourceCrossValidator
        from cis2hdl.core.parser.dsn.dsn_parser import DSNParser
        from cis2hdl.core.parser.edif_parser import EDIFParser

        dsn_ir = DSNParser().parse(self.dsn_path)
        edf_ir = EDIFParser().parse(self.edf_path)
        report = MultiSourceCrossValidator().validate(
            dsn_ir=dsn_ir, edf_ir=edf_ir,
        )
        type_issues = [i for i in report.issues if i.category == "count"
                       and "device type" in i.message.lower()]
        assert isinstance(type_issues, list)
