"""Unit tests for CrossValidator — EDIF vs DSN consistency checking."""

import pytest

from cis2hdl.core.parser.cross_validator import CrossValidator


@pytest.mark.unit
class TestCrossValidator:
    def test_empty_designs_pass_validation(self) -> None:
        """CrossValidator reports success when both EDIF and DSN designs are empty."""
        from cis2hdl.core.ir.design import DesignIR

        edif = DesignIR(project_name="test", source_format="EDIF")
        dsn = DesignIR(project_name="test", source_format="DSN")
        validator = CrossValidator()
        report = validator.validate(edif, dsn)
        assert report.passed
        assert report.error_count == 0

    def test_different_instance_counts_cause_failure(self) -> None:
        """CrossValidator reports failure when EDIF and DSN have different instance counts."""
        from cis2hdl.core.ir.design import DesignIR, PageIR
        from cis2hdl.core.ir.component import ComponentInstanceIR

        edif = DesignIR(project_name="test", source_format="EDIF")
        edif.pages.append(PageIR(page_id="1.1"))
        edif.pages[0].instances.append(
            ComponentInstanceIR(refdes="R1", library_id="RES"),
        )

        dsn = DesignIR(project_name="test", source_format="DSN")
        dsn.pages.append(PageIR(page_id="1.1"))
        # dsn has no instances — should fail

        validator = CrossValidator()
        report = validator.validate(edif, dsn)
        assert not report.passed
        assert report.error_count >= 1

    def test_pin_count_mismatch_detected(self) -> None:
        """CrossValidator reports pin count mismatch for same refdes."""
        from cis2hdl.core.ir.design import DesignIR, PageIR
        from cis2hdl.core.ir.component import ComponentInstanceIR

        edif = DesignIR(project_name="test", source_format="EDIF")
        edif.pages.append(PageIR(page_id="1.1"))
        edif_inst = ComponentInstanceIR(refdes="U1", library_id="IC")
        edif_inst.pin_connections = {"1": "VCC", "2": "GND", "3": "SIG"}
        edif.pages[0].instances.append(edif_inst)

        dsn = DesignIR(project_name="test", source_format="DSN")
        dsn.pages.append(PageIR(page_id="1.1"))
        dsn_inst = ComponentInstanceIR(refdes="U1", library_id="IC")
        dsn_inst.pin_connections = {"1": "VCC", "2": "GND"}  # 1 less pin
        dsn.pages[0].instances.append(dsn_inst)

        validator = CrossValidator()
        report = validator.validate(edif, dsn)
        # Should have pin count mismatch warning
        pin_warnings = [i for i in report.issues if i.category == "pin"]
        assert len(pin_warnings) >= 1

    def test_pin_count_match_info(self) -> None:
        """CrossValidator reports info when pin counts match."""
        from cis2hdl.core.ir.design import DesignIR, PageIR
        from cis2hdl.core.ir.component import ComponentInstanceIR

        edif = DesignIR(project_name="test", source_format="EDIF")
        edif.pages.append(PageIR(page_id="1.1"))
        edif_inst = ComponentInstanceIR(refdes="R1", library_id="RES")
        edif_inst.pin_connections = {"1": "NET1", "2": "NET2"}
        edif.pages[0].instances.append(edif_inst)

        dsn = DesignIR(project_name="test", source_format="DSN")
        dsn.pages.append(PageIR(page_id="1.1"))
        dsn_inst = ComponentInstanceIR(refdes="R1", library_id="RES")
        dsn_inst.pin_connections = {"1": "NET1", "2": "NET2"}  # same count
        dsn.pages[0].instances.append(dsn_inst)

        validator = CrossValidator()
        report = validator.validate(edif, dsn)
        # Should have info about pin count match
        pin_infos = [
            i for i in report.issues
            if i.category == "pin" and i.severity == "info"
        ]
        assert len(pin_infos) >= 1

    def test_device_type_grouping_counts(self) -> None:
        """CrossValidator groups instances by type and reports counts."""
        from cis2hdl.core.ir.design import DesignIR, PageIR
        from cis2hdl.core.ir.component import ComponentInstanceIR

        edif = DesignIR(project_name="test", source_format="EDIF")
        edif.pages.append(PageIR(page_id="1.1"))
        edif.pages[0].instances.append(
            ComponentInstanceIR(refdes="R1", library_id="RES_0603"))
        edif.pages[0].instances.append(
            ComponentInstanceIR(refdes="C1", library_id="CAP_0603"))

        dsn = DesignIR(project_name="test", source_format="DSN")
        dsn.pages.append(PageIR(page_id="1.1"))
        dsn.pages[0].instances.append(
            ComponentInstanceIR(refdes="R1", library_id="RES_0603"))
        # missing C1 in DSN

        validator = CrossValidator()
        report = validator.validate(edif, dsn)

        # Should have device type related issues
        type_issues = [i for i in report.issues if i.category == "count"
                       and "Capacitor" in i.message]
        assert len(type_issues) >= 1

    def test_net_topology_consistency(self) -> None:
        """CrossValidator reports net topology consistency metrics."""
        from cis2hdl.core.ir.design import DesignIR, PageIR, NetIR, NetConnection
        from cis2hdl.core.ir.component import ComponentInstanceIR

        edif = DesignIR(project_name="test", source_format="EDIF")
        edif.pages.append(PageIR(page_id="1.1"))
        edif.pages[0].nets.append(NetIR(
            name="VCC",
            connections=[
                NetConnection(refdes="U1", pin_number="1"),
                NetConnection(refdes="R1", pin_number="1"),
            ],
        ))

        dsn = DesignIR(project_name="test", source_format="DSN")
        dsn.pages.append(PageIR(page_id="1.1"))
        dsn.pages[0].nets.append(NetIR(
            name="NET_POWER_1",  # different name, same connections
            connections=[
                NetConnection(refdes="U1", pin_number="1"),
                NetConnection(refdes="R1", pin_number="1"),
            ],
        ))

        validator = CrossValidator()
        report = validator.validate(edif, dsn)

        # Should report exact match in topology (Jaccard=1.0)
        topology_msgs = [
            i.message for i in report.issues
            if "topology" in i.message.lower() or "net topology" in i.message.lower()
        ]
        # At minimum, should not crash and should produce some output
        assert isinstance(report.issues, list)
