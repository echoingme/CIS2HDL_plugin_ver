"""Phase XIV T4 — D1 文本/标签去冲突 + 对齐（text_layout.py）。

Covers:
  * bbox 估算（保守宽度/最小宽度）
  * 碰撞检测（O(n²)）
  * SIG_NAME 优先移动 / PIN_TEXT 禁动 / VALUE 就近微调
  * 25 网格
  * 网络名 x = snap25(trunk_min_x + 375) 对齐
  * 差分对 _P/_N → P 上 N 下
  * csa 输出标签坐标偏移（LASTPIN/WIRE 不动）
"""

from __future__ import annotations


def _item(**kw):
    from cis2hdl.core.writer.text_layout import TextItem

    defaults = dict(
        key="x", kind="VALUE", text="TXT", anchor=(0, 0),
        font_size=40, scale=0.851064, movable=True, priority=1,
    )
    defaults.update(kw)
    return TextItem(**defaults)


class TestBBoxEstimate:
    def test_min_width(self):
        from cis2hdl.core.writer.text_layout import TextLayoutOptimizer

        bbox = TextLayoutOptimizer.estimate_bbox("1", (100, 100), 24, 0.808511)
        assert bbox[2] - bbox[0] >= TextLayoutOptimizer.MIN_TEXT_W

    def test_long_text_wider(self):
        from cis2hdl.core.writer.text_layout import TextLayoutOptimizer

        short = TextLayoutOptimizer.estimate_bbox("A", (0, 0), 40, 0.851064)
        long = TextLayoutOptimizer.estimate_bbox("ABCDEFGHIJ", (0, 0), 40, 0.851064)
        assert long[2] - long[0] > short[2] - short[0]

    def test_bbox_anchor_lower_left(self):
        from cis2hdl.core.writer.text_layout import TextLayoutOptimizer

        bbox = TextLayoutOptimizer.estimate_bbox("TXT", (100, 100), 40, 1.0)
        assert bbox[0] < 100 < bbox[2]
        assert bbox[1] < 100 < bbox[3]


class TestCollisionDetection:
    def test_detect_overlap(self):
        from cis2hdl.core.writer.text_layout import TextLayoutOptimizer

        a = _item(key="a.VALUE", anchor=(100, 100), text="RESISTOR_0402")
        b = _item(key="b.VALUE", anchor=(140, 110), text="CAPACITOR_0603")
        opt = TextLayoutOptimizer()
        collisions = opt.detect_collisions([a, b])
        assert len(collisions) == 1

    def test_detect_no_overlap(self):
        from cis2hdl.core.writer.text_layout import TextLayoutOptimizer

        a = _item(key="a.VALUE", anchor=(100, 100), text="R")
        b = _item(key="b.VALUE", anchor=(1000, 1000), text="C")
        opt = TextLayoutOptimizer()
        assert opt.detect_collisions([a, b]) == []


class TestResolve:
    def test_pin_text_never_moves(self):
        from cis2hdl.core.writer.text_layout import TextLayoutOptimizer

        pin = _item(
            key="U1.1.PIN_TEXT", kind="PIN_TEXT", text="1",
            anchor=(100, 100), movable=False, priority=3,
            font_size=24, scale=0.808511,
        )
        value = _item(key="U1.VALUE", text="MP147X", anchor=(95, 60))
        opt = TextLayoutOptimizer()
        collisions = opt.detect_collisions([pin, value])
        result = opt.resolve([pin, value], collisions)
        # PIN_TEXT 禁动
        assert pin.anchor == (100, 100)
        # VALUE 可动（有偏移或碰撞已解决）
        assert "U1.VALUE" in result.offsets or result.collisions_after == 0

    def test_sig_name_moves_before_value(self):
        from cis2hdl.core.writer.text_layout import TextLayoutOptimizer

        sig = _item(
            key="NET_A.SIG_NAME", kind="SIG_NAME", text="NET_A",
            anchor=(200, 200), movable=True, priority=0,
            font_size=24, scale=0.659574,
        )
        value = _item(key="U1.VALUE", text="LONG_VALUE_123", anchor=(210, 210))
        opt = TextLayoutOptimizer()
        collisions = opt.detect_collisions([sig, value])
        result = opt.resolve([sig, value], collisions)
        assert result.collisions_after == 0
        # SIG_NAME 动了（低优先级先动）
        assert sig.anchor != (200, 200)

    def test_all_offsets_on_grid(self):
        from cis2hdl.core.writer.text_layout import TextLayoutOptimizer

        items = [
            _item(key="a.VALUE", text="VALUE_A", anchor=(100, 100)),
            _item(key="b.VALUE", text="VALUE_B", anchor=(130, 110)),
            _item(key="c.VALUE", text="VALUE_C", anchor=(160, 120)),
        ]
        opt = TextLayoutOptimizer()
        collisions = opt.detect_collisions(items)
        result = opt.resolve(items, collisions)
        for key, (dx, dy) in result.offsets.items():
            it = next(i for i in items if i.key == key)
            nx = it.origin[0] + dx
            ny = it.origin[1] + dy
            assert nx % 25 == 0 and ny % 25 == 0, f"{key} off-grid"


class TestAlignment:
    def test_align_net_names_x(self):
        from cis2hdl.core.writer.text_layout import TextLayoutOptimizer

        # 线上 SIG_NAME：wire_min_x=100 → x = snap25(100+375)=475
        sig = _item(
            key="NET_A.SIG_NAME", kind="SIG_NAME", text="NET_A",
            anchor=(0, 200), movable=True, priority=0,
            font_size=24, scale=0.659574, net_key="NET_A", wire_min_x=100,
        )
        opt = TextLayoutOptimizer()
        opt.align_net_names([sig])
        assert sig.anchor[0] == 475

    def test_align_net_names_skips_fixed(self):
        from cis2hdl.core.writer.text_layout import TextLayoutOptimizer

        sig = _item(
            key="NET_B.SIG_NAME", kind="SIG_NAME", text="NET_B",
            anchor=(0, 200), movable=False, priority=0,
            net_key="NET_B", wire_min_x=100,
        )
        opt = TextLayoutOptimizer()
        opt.align_net_names([sig])
        assert sig.anchor == (0, 200)  # 禁动标签不被对齐挪走

    def test_diff_pair_p_above_n(self):
        from cis2hdl.core.writer.text_layout import TextLayoutOptimizer

        p = _item(
            key="CLK_P.SIG_NAME", kind="SIG_NAME", text="CLK_P",
            anchor=(100, 100), movable=True, priority=0,
            net_key="CLK_P",
        )
        n = _item(
            key="CLK_N.SIG_NAME", kind="SIG_NAME", text="CLK_N",
            anchor=(100, 300), movable=True, priority=0,
            net_key="CLK_N",
        )
        opt = TextLayoutOptimizer()
        ok, total = opt.enforce_diff_pairs([p, n], ["CLK_P", "CLK_N"])
        assert total == 1
        assert ok == 1
        assert p.anchor[1] > n.anchor[1], "P 必须在 N 上方"


class TestOptimizeEndToEnd:
    def _make_page(self):
        from cis2hdl.core.ir.component import ComponentInstanceIR
        from cis2hdl.core.writer.connectivity_model import (
            ConnectivityModelBuilder,
        )
        from cis2hdl.core.ir.design import DesignIR, PageIR

        p1 = PageIR(page_id="1.1", page_name="05-Power_Supply1")
        p1.instances = [
            ComponentInstanceIR(
                refdes="U1", library_id="U1", loc_x=4500, loc_y=12000,
                pin_connections={"1": "NET_A", "2": "NET_B"},
            ),
        ]
        design = DesignIR(project_name="T", pages=[p1])
        conn = ConnectivityModelBuilder(design, matches=[]).build()
        return conn, conn.pages[0]

    def test_optimize_no_wire_change(self):
        """text_layout 只返回标签 offsets —— WIRE 段与 LASTPIN 坐标不变。"""
        from cis2hdl.core.config import TextLayoutCfg
        from cis2hdl.core.writer.csa_writer import CSAWriter
        from cis2hdl.core.writer.text_layout import TextLayoutOptimizer

        conn, page_conn = self._make_page()
        # 开启 text_layout 与关闭时，WIRE 段必须一致
        writer_off = CSAWriter(routing_cfg=__import__(
            "cis2hdl.core.config", fromlist=["RoutingConfig"]
        ).RoutingConfig())
        content_off = writer_off._build_csa_content_conn(conn, page_conn)

        from cis2hdl.core.config import RoutingConfig
        cfg = RoutingConfig(text_layout=TextLayoutCfg(enabled=True))
        writer_on = CSAWriter(routing_cfg=cfg)
        content_on = writer_on._build_csa_content_conn(conn, page_conn)

        import re

        def wires(text):
            return re.findall(
                r"WIRE 16 -1 \((-?\d+) (-?\d+)\)\((-?\d+) (-?\d+)\);", text,
            )

        def lastpins(text):
            return re.findall(
                r"FORCEPROP [0-3] LASTPIN \((-?\d+) (-?\d+)\)", text,
            )

        assert wires(content_on) == wires(content_off)
        assert lastpins(content_on) == lastpins(content_off)

    def test_optimize_labels_on_grid(self):
        """开启 text_layout 后 VALUE/$LOCATION 标签坐标全部 25 网格。"""
        from cis2hdl.core.config import RoutingConfig, TextLayoutCfg
        from cis2hdl.core.writer.csa_writer import CSAWriter

        conn, page_conn = self._make_page()
        cfg = RoutingConfig(text_layout=TextLayoutCfg(enabled=True))
        content = CSAWriter(routing_cfg=cfg)._build_csa_content_conn(conn, page_conn)

        import re
        # VALUE / $LOCATION 块：FORCEPROP 后首个 "(x y);" 坐标行
        # （Phase XXII D7：orient=0 时标签块不输出 R 行，坐标行位置可变）。
        coords: list[tuple[int, int]] = []
        lines = content.splitlines()
        for i, line in enumerate(lines):
            if re.match(r"^FORCEPROP 1 LAST (VALUE|\$LOCATION) ", line):
                for j in range(i + 1, min(i + 4, len(lines))):
                    m = re.match(r"^\((-?\d+) (-?\d+)\);", lines[j])
                    if m:
                        coords.append((int(m.group(1)), int(m.group(2))))
                        break
        assert coords, "no VALUE/$LOCATION labels found"
        for x, y in coords:
            assert x % 25 == 0, f"VALUE/LOCATION off-grid x={x}"
            assert y % 25 == 0, f"VALUE/LOCATION off-grid y={y}"


class TestLabelOrientD7:
    """Phase XXII D7 — 标签方向随元件（text_layout.enabled 时）。"""

    def _make_rotated_page(self, rotation: int = 180):
        from cis2hdl.core.ir.component import ComponentInstanceIR
        from cis2hdl.core.writer.connectivity_model import ConnectivityModelBuilder
        from cis2hdl.core.ir.design import DesignIR, PageIR

        p1 = PageIR(page_id="1.1", page_name="05-Power_Supply1")
        p1.instances = [
            ComponentInstanceIR(
                refdes="U1", library_id="U1", loc_x=4500, loc_y=12000,
                rotation=rotation,
                pin_connections={"1": "NET_A", "2": "NET_B"},
            ),
        ]
        design = DesignIR(project_name="T", pages=[p1])
        conn = ConnectivityModelBuilder(design, matches=[]).build()
        return conn, conn.pages[0]

    def test_collect_text_items_orient_matches_rotation(self):
        """旋转元件 VALUE/$LOCATION 的 orient == dehdl R 行角（180→2）。"""
        from cis2hdl.core.writer.text_layout import (
            KIND_LOCATION, KIND_VALUE, TextLayoutOptimizer,
        )

        conn, page_conn = self._make_rotated_page(rotation=180)
        opt = TextLayoutOptimizer()
        items = opt.collect_text_items(
            page_conn, {}, {}, {}, {}, ioport_positions=[],
        )
        orient = {
            it.key: it.orient for it in items
            if it.kind in (KIND_VALUE, KIND_LOCATION)
        }
        assert orient == {"U1.VALUE": 180, "U1.LOCATION": 180}, orient

    def test_enabled_emits_r_line_for_rotated_component(self):
        """text_layout 开启：旋转元件（180°）的 VALUE 块携带 R 2。"""
        from cis2hdl.core.config import RoutingConfig, TextLayoutCfg
        from cis2hdl.core.writer.csa_writer import CSAWriter

        conn, page_conn = self._make_rotated_page(rotation=180)
        cfg = RoutingConfig(text_layout=TextLayoutCfg(enabled=True))
        content = CSAWriter(routing_cfg=cfg)._build_csa_content_conn(
            conn, page_conn,
        )
        # VALUE 块：FORCEPROP VALUE 后跟 R 2（180° 标签方向随元件）。
        lines = content.splitlines()
        idx = next(
            i for i, ln in enumerate(lines)
            if ln.startswith("FORCEPROP 1 LAST VALUE ")
        )
        assert lines[idx + 1] == "R 2", (
            f"VALUE block R line: {lines[idx:idx + 3]}"
        )

    def test_disabled_no_orient_change(self):
        """text_layout 关闭：VALUE 块保持现状 `R 1`（回归零影响）。"""
        from cis2hdl.core.config import RoutingConfig
        from cis2hdl.core.writer.csa_writer import CSAWriter

        conn, page_conn = self._make_rotated_page(rotation=180)
        cfg = RoutingConfig()  # text_layout.enabled=False 默认
        content = CSAWriter(routing_cfg=cfg)._build_csa_content_conn(
            conn, page_conn,
        )
        lines = content.splitlines()
        idx = next(
            i for i, ln in enumerate(lines)
            if ln.startswith("FORCEPROP 1 LAST VALUE ")
        )
        assert lines[idx + 1] == "R 1", (
            f"disabled must keep R 1: {lines[idx:idx + 3]}"
        )
