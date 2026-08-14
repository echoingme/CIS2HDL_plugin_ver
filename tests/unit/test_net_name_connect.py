"""Phase XVII M5 — net_name_connect（用户 D2：IOPORT→网络名）。

Covers:
  * cross_page_bare_names（跨页网判定，数据源 = DesignConnectivity）
  * ioport_skip_plan（use_net_name=true 时全部 IOPORT 跳过）
  * net_name_labels（跨页网缺失 source-pin 标签时补 SIG_NAME）
  * ioport_net_mapping（off_page → 网络名映射）
"""

from __future__ import annotations


class _Net:
    def __init__(self, net_id, bare_name, pages):
        self.net_id = net_id
        self.bare_name = bare_name
        self.pages = pages


class _Conn:
    def __init__(self, nets):
        self.nets = nets


class TestCrossPageBareNames:
    def test_detects_multi_page_nets(self):
        from cis2hdl.core.writer.net_name_connect import cross_page_bare_names

        conn = _Conn([
            _Net("N1", "NET_A", [1, 2]),
            _Net("N2", "NET_B", [1]),
            _Net("N3", "12V0", [1, 2, 3]),
        ])
        assert cross_page_bare_names(conn) == {"net_a", "12v0"}

    def test_empty(self):
        from cis2hdl.core.writer.net_name_connect import cross_page_bare_names

        assert cross_page_bare_names(_Conn([])) == set()


class TestIoportSkipPlan:
    def test_use_net_name_skips_all(self):
        from cis2hdl.core.writer.net_name_connect import ioport_skip_plan

        ops = [{"name": "OP0", "net_name": "NET_A"}]
        assert ioport_skip_plan(ops, True) == ops

    def test_default_keeps_ioport(self):
        from cis2hdl.core.writer.net_name_connect import ioport_skip_plan

        ops = [{"name": "OP0", "net_name": "NET_A"}]
        assert ioport_skip_plan(ops, False) == []


class TestNetNameLabels:
    def test_cross_page_missing_source_label_gets_label(self):
        from cis2hdl.core.writer.net_name_connect import net_name_labels

        net_pin_map = {
            "NET_A": [{"refdes": "U1", "pin": "1", "coord": (100, 100)}],
        }
        labels = net_name_labels(
            net_pin_map, set(), {"net_a"}, True,
        )
        assert labels == [((100, 100), "NET_A")]

    def test_cross_page_with_source_label_no_extra(self):
        from cis2hdl.core.writer.net_name_connect import net_name_labels

        net_pin_map = {
            "NET_A": [{"refdes": "U1", "pin": "1", "coord": (100, 100)}],
        }
        labels = net_name_labels(
            net_pin_map, {("U1", "1")}, {"net_a"}, True,
        )
        assert labels == []

    def test_disabled_returns_empty(self):
        from cis2hdl.core.writer.net_name_connect import net_name_labels

        net_pin_map = {
            "NET_A": [{"refdes": "U1", "pin": "1", "coord": (100, 100)}],
        }
        assert net_name_labels(net_pin_map, set(), {"net_a"}, False) == []


class TestIoportNetMapping:
    def test_mapping(self):
        from cis2hdl.core.writer.net_name_connect import ioport_net_mapping

        mapping = ioport_net_mapping([
            {"name": "OP0", "net_name": "NET_A"},
            {"name": "OP1", "net_name": "NET_A"},
            {"name": "OP2"},
        ])
        assert mapping == {"OP0": "NET_A", "OP1": "NET_A", "OP2": "OP2"}
