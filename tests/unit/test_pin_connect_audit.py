"""Phase XVII M6 — pin_connect_audit（引脚连接审计，数据源铁律）。

Covers:
  * 已接/悬空/网名不匹配/引脚名不匹配四状态
  * [PIN_AUDIT] / [HANGING] 报告格式
  * report_hanging 开关
"""

from __future__ import annotations


class _Pin:
    def __init__(self, pin_number, pin_name, net_id):
        self.pin_number = pin_number
        self.pin_name = pin_name
        self.net_id = net_id


class _Irec:
    def __init__(self, refdes, cell_id, pins):
        self.refdes = refdes
        self.cell_id = cell_id
        self.pins = pins


class _Page:
    def __init__(self, page_num, instances):
        self.page_num = page_num
        self.instances = instances


class _Net:
    def __init__(self, net_id, internal_name, connections):
        self.net_id = net_id
        self.internal_name = internal_name
        self.connections = connections


class _Cell:
    def __init__(self, cell_id, pin_names):
        self.cell_id = cell_id
        self.pin_names = pin_names


class _Conn:
    def __init__(self, nets, cells, pages):
        self.nets = nets
        self.cells = cells
        self.pages = pages


def _make_conn():
    """U1: pin1 NET_A (2 conns, connected), pin2 single-net (hanging),
    pin3 bad net_id (net_mismatch), pin4 pin_mismatch (not in cell)."""
    net_a = _Net("N1", "NET_A", [("U1", "1"), ("U2", "1")])
    net_solo = _Net("N2", "SOLO", [("U1", "2")])
    cells = [_Cell("C1", {"1": "A0", "2": "A1", "3": "A2"})]
    u1 = _Irec(
        "U1", "C1",
        [
            _Pin("1", "A0", "N1"),
            _Pin("2", "A1", "N2"),
            _Pin("3", "A2", "N99"),   # net not in conn.nets
            _Pin("4", "ZZZ", "N1"),   # pin 4 not in cell pin defs
        ],
    )
    page = _Page(5, [u1])
    return _Conn([net_a, net_solo], cells, [page])


class TestPinConnectAudit:
    def test_status_classification(self):
        from cis2hdl.core.writer.pin_connect_audit import PinConnectAuditor

        result = PinConnectAuditor().audit(_make_conn())
        by_pin = {e.pin_number: e.status for e in result.entries}
        assert by_pin["1"] == "connected"
        assert by_pin["2"] == "hanging"
        assert by_pin["3"] == "net_mismatch"
        assert by_pin["4"] == "pin_mismatch"
        assert result.total == 4
        assert result.connected == 1
        assert result.hanging == 1
        assert result.net_mismatch == 1
        assert result.pin_mismatch == 1

    def test_hanging_entries(self):
        from cis2hdl.core.writer.pin_connect_audit import PinConnectAuditor

        result = PinConnectAuditor().audit(_make_conn())
        hanging = result.hanging_entries
        assert len(hanging) == 1
        assert hanging[0].refdes == "U1"
        assert hanging[0].pin_number == "2"

    def test_disabled_returns_empty(self):
        from cis2hdl.core.writer.pin_connect_audit import PinConnectAuditor

        result = PinConnectAuditor(enabled=False).audit(_make_conn())
        assert result.total == 0

    def test_report_format(self):
        from cis2hdl.core.writer.pin_connect_audit import PinConnectAuditor

        auditor = PinConnectAuditor(report_hanging=False)
        result = auditor.audit(_make_conn())
        report = auditor.format_report(result)
        assert "[PIN_AUDIT]" in report
        assert "[HANGING]" in report
        assert "待 Allegro 布线" in report

    def test_write_report(self, tmp_path):
        from cis2hdl.core.writer.pin_connect_audit import PinConnectAuditor

        auditor = PinConnectAuditor()
        result = auditor.audit(_make_conn())
        out = auditor.write(result, tmp_path)
        assert out is not None
        assert out.exists()
        assert "PIN CONNECT AUDIT REPORT" in out.read_text(encoding="utf-8")
