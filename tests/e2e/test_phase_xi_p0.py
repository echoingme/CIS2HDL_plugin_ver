"""Phase XI P0-B/P0-C/P0-D2 end-to-end acceptance — HG5015.

Runs the full conversion pipeline on the HG5015 fixture (DSN input, EDIF
component source under P0-D2) and asserts the system_design.md C.4
acceptance criteria A1-A9 against the generated con/xcon/csv/cpc/csa files.

Honest measurements (2026-08 run, after P0-遗留#1 ROUTE jumpers + #2 power
symbols + #3 UN$ auto-nets):
  * con nets: 590 unique raw nets (== pstxnet NET_NAME count); net records
    in the con file are 687 because power nets also carry one page-local
    record per page (8367 evidence: gnd_power global + pageN_gnd_power
    locals, each aliased).
  * con instances: 914 — CrossRef catalog INCLUDING the 25 ROUTE jumpers
    (issue #1 fix; the pre-fix 889 figure is obsolete).  Power symbols
    never appear in con cells/instances (C.5 convention).
  * con pin connections: 2360 — actual value in the working tree
    (catalog + pstxnet injection).  Earlier 2771/2821 estimates included
    pstxnet-only refdes (U6, extra pins) absent from the CrossRef catalog
    and are not reproduced by the current pipeline.
  * power symbols: 20 pages get 1 GND_POWER symbol each, page6 additionally
    1 VCC_CIRCLE — present in csv (%"GND_POWER" / %"VCC_CIRCLE" blocks),
    cpc (#ISCELL), csa (FORCEADD + LASTPIN SIG_NAME + HDL_POWER) but NOT in
    con (issue #2 fix).
"""

from __future__ import annotations

import re
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.slow]

from cis2hdl.core.engine.conversion_engine import ConversionEngine


def _hg5015_fixture(fixtures_dir: Path) -> Path | None:
    """Return the HG5015 test fixture dir or None (skip)."""
    base = fixtures_dir / "HG5015test"
    if not (base / "HG5015-BE36_V10.DSN").exists():
        return None
    return base


@pytest.fixture(scope="module")
def hg5015_dir(fixtures_dir: Path) -> Path:
    base = _hg5015_fixture(fixtures_dir)
    if base is None:
        pytest.skip("HG5015 fixtures not available")
    return base


@pytest.fixture(scope="module")
def converted(hg5015_dir: Path, tmp_path_factory):
    """Run the full pipeline once per module and expose the output dir."""
    out_dir = tmp_path_factory.mktemp("phase_xi_p0")
    engine = ConversionEngine()
    hdl = Path(__file__).parent.parent / "fixtures" / "hdl_lib"
    report = engine.convert(
        hg5015_dir / "HG5015-BE36_V10.DSN",
        out_dir,
        hdl_lib_path=hdl if hdl.exists() else None,
    )
    return report, out_dir


class TestPhaseXiP0Acceptance:
    # ------------------------------------------------------------------
    #  Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _sch_dir(out_dir: Path) -> Path:
        worklib = out_dir / "worklib"
        cells = [d for d in worklib.iterdir() if d.is_dir()]
        assert cells, "no cell directory under worklib"
        return cells[0] / "sch_1"

    def _con_path(self, out_dir: Path) -> Path:
        sch = self._sch_dir(out_dir)
        cons = list(sch.glob("*.con"))
        assert cons, "no .con file"
        return cons[0]

    def _xcon_path(self, out_dir: Path) -> Path:
        sch = self._sch_dir(out_dir)
        xcons = list(sch.glob("*.xcon"))
        assert xcons, "no .xcon file"
        return xcons[0]

    # ------------------------------------------------------------------
    #  A8: parseability (S-Expr / XML)
    # ------------------------------------------------------------------

    def test_a8_con_sexpr_and_xcon_xml_parseable(self, converted):
        from sexpdata import loads
        report, out_dir = converted
        assert report.errors == [], f"pipeline errors: {report.errors[:3]}"
        tree = loads(self._con_path(out_dir).read_text())
        assert len(tree) == 4  # version tool library design
        root = ET.fromstring(self._xcon_path(out_dir).read_text())
        assert root.tag.endswith("schema")

    # ------------------------------------------------------------------
    #  A1/A2/A3: con counts
    # ------------------------------------------------------------------

    def test_a1_con_nets_590_unique(self, converted):
        _, out_dir = converted
        text = self._con_path(out_dir).read_text()
        nets = re.findall(r'\("N\d+" "([^"]+)" -1 -1 (\d) \)', text)
        assert len(nets) > 0
        # every record is well-formed: id/name/-1/-1/scope
        for name, scope in nets:
            assert name
            assert scope in ("0", "2")
        # unique raw nets (dedup by bare name) == pstxnet NET_NAME count
        bare = set(re.sub(r"^page\d+_", "", n) for n, _s in nets)
        assert len(bare) == 590, (
            f"expected 590 unique nets, got {len(bare)}"
        )
        # lastNetId == number of net records (8367 pattern)
        last_net = re.search(r"lastNetId (\d+)", text)
        assert last_net is not None
        assert int(last_net.group(1)) == len(nets)

    def test_a2_con_pin_conns(self, converted):
        _, out_dir = converted
        text = self._con_path(out_dir).read_text()
        pins = re.findall(r'\("M\d+"', text)
        last_term = re.search(r"lastInstTermId (\d+)", text)
        assert last_term is not None
        assert int(last_term.group(1)) == len(pins)
        # 2821 == pstxnet NODE_NAME 连接数（Phase XI P0-遗留#3 修复后恢复；
        # 此前 2360 是 net_by_raw 缺失导致 $ 网引脚被丢弃的 bug 状态）
        assert len(pins) == 2821

    def test_a3_con_instances(self, converted):
        _, out_dir = converted
        text = self._con_path(out_dir).read_text()
        insts = re.findall(r'\("I\d+" "page\d+_i\d+" "S\d+"', text)
        last_inst = re.search(r"lastInstanceId (\d+)", text)
        assert last_inst is not None
        assert int(last_inst.group(1)) == len(insts)
        # 914 = CrossRef catalog INCLUDING the 25 ROUTE jumpers (issue #1)
        assert len(insts) == 914

    def test_a3_no_power_symbols_in_con(self, converted):
        _, out_dir = converted
        text = self._con_path(out_dir).read_text()
        assert "gnd_power" not in re.sub(r'\("N\d+" "(\w+)" -1 -1 2 \)', r"\1", text) \
            or "gnd_power" not in text  # power nets ARE allowed in con nets
        # but power SYMBOLS must not appear as cells/instances
        assert '"gnd_power" "hdl_lib"' not in text
        assert '"vcc_circle" "hdl_lib"' not in text

    # ------------------------------------------------------------------
    #  A4: csv
    # ------------------------------------------------------------------

    def test_a4_csv_format(self, converted):
        _, out_dir = converted
        sch = self._sch_dir(out_dir)
        csvs = sorted(sch.glob("page*.csv"))
        assert len(csvs) == 24
        saw_pn = False
        for csv in csvs:
            content = csv.read_text()
            assert content.startswith("FILE_TYPE = CONNECTIVITY;")
            assert '0"NC";' in content
            assert content.rstrip().endswith("END.")
            if "$PN" in content:
                saw_pn = True
        assert saw_pn, "no page csv contains $PN pin mappings"

    # ------------------------------------------------------------------
    #  A5: csa
    # ------------------------------------------------------------------

    def test_a5_csa_wire_lastpin_quit(self, converted):
        _, out_dir = converted
        sch = self._sch_dir(out_dir)
        csas = sorted(sch.glob("page*.csa"))
        assert len(csas) == 24
        saw_wire = False
        for csa in csas:
            content = csa.read_text()
            assert content.rstrip().endswith("QUIT")
            if "WIRE 16 -1" in content:
                saw_wire = True
                assert "LASTPIN" in content
                assert "SIG_NAME" in content
        assert saw_wire, "no csa contains WIRE 16 -1"

    def test_a5_wire_endpoints_cover_pins(self, converted):
        """Pins of multi-pin nets must be WIRE endpoints (connection rule).

        Rebuilds the connectivity model to know which pins belong to nets
        with >= 2 pins on a page — only those must appear as endpoints.
        Single-pin nets carry no wire (they only get a SIG_NAME label).
        """
        from cis2hdl.core.ir.component import ComponentInstanceIR
        from cis2hdl.core.parser.component_catalog import ComponentCatalog
        from cis2hdl.core.parser.edif_parser import EDIFParser
        from cis2hdl.core.parser.pstxnet_netlist_parser import PstxnetNetlistParser
        from cis2hdl.core.writer.connectivity_model import ConnectivityModelBuilder

        report, out_dir = converted
        sch = self._sch_dir(out_dir)
        hg = Path(__file__).parent.parent / "fixtures" / "HG5015test"

        design = EDIFParser().parse(hg / "HG5015-BE36_V10.EDF")
        catalog = ComponentCatalog.from_cross_ref(hg / "HG5015-BE36_V10.CSV")
        pages_by_name = {p.page_name: p for p in design.pages}
        for p in design.pages:
            p.instances = []
        for entry in catalog.all_entries():
            target = pages_by_name.get(entry.page_name)
            if target is None:
                continue
            target.instances.append(ComponentInstanceIR(
                refdes=entry.refdes, library_id=entry.refdes,
                loc_x=entry.loc_x, loc_y=entry.loc_y,
                value_override=entry.value,
            ))
        netlist = PstxnetNetlistParser().parse(hg / "pstxnet.dat")
        for p in design.pages:
            for inst in p.instances:
                pins = netlist.get(inst.refdes)
                if pins:
                    inst.pin_connections = dict(pins)
        conn = ConnectivityModelBuilder(design, matches=[]).build()

        for page_conn in conn.pages:
            csa = sch / f"page{page_conn.page_num}.csa"
            content = csa.read_text()
            if "WIRE 16 -1" not in content:
                continue
            wires = re.findall(
                r"WIRE 16 -1 \((-?\d+) (-?\d+)\)\((-?\d+) (-?\d+)\);", content
            )
            endpoints = set()
            for w in wires:
                endpoints.add((int(w[0]), int(w[1])))
                endpoints.add((int(w[2]), int(w[3])))
            # pins of nets with >= 2 pins on this page must be endpoints
            multi = {
                pnr.bare_name for pnr in page_conn.nets if len(pnr.connections) >= 2
            }
            for pnr in page_conn.nets:
                if pnr.bare_name not in multi:
                    continue
                # the source pin of this net carries SIG_NAME; every other
                # connected pin carries $PN — both must be wire endpoints
                sig_match = re.search(
                    rf"LASTPIN \((-?\d+) (-?\d+)\) SIG_NAME {re.escape(pnr.display_name)}\b",
                    content,
                )
                if sig_match:
                    coord = (int(sig_match.group(1)), int(sig_match.group(2)))
                    assert coord in endpoints, (
                        f"page{page_conn.page_num}: SIG_NAME pin of "
                        f"{pnr.display_name} not a wire endpoint"
                    )
            for irec in page_conn.instances:
                for pre in irec.pins:
                    net_display = next(
                        (pnr.display_name for pnr in page_conn.nets
                         if pnr.pin_net_id == pre.net_id), ""
                    )
                    if not net_display:
                        continue
                    bare = net_display.replace("\\g", "").lower()
                    # Phase XI P2-2: NC pins carry no net — they keep a
                    # LASTPIN $PN but no SIG_NAME/WIRE, so they are not
                    # required to be wire endpoints.
                    if bare == "nc":
                        continue
                    if bare not in multi:
                        continue
                    lastpin_match = re.search(
                        rf"LASTPIN \((-?\d+) (-?\d+)\) \$PN {re.escape(pre.pin_number)}",
                        content,
                    )
                    if lastpin_match:
                        coord = (int(lastpin_match.group(1)), int(lastpin_match.group(2)))
                        assert coord in endpoints, (
                            f"page{page_conn.page_num}: pin "
                            f"{irec.refdes}.{pre.pin_number} not a wire endpoint"
                        )

    def test_a5_one_sig_name_per_net(self, converted):
        _, out_dir = converted
        sch = self._sch_dir(out_dir)
        for csa in sorted(sch.glob("page*.csa")):
            content = csa.read_text()
            sigs = re.findall(r"SIG_NAME (\S+)", content)
            assert len(sigs) == len(set(sigs)), (
                f"{csa.name}: duplicate SIG_NAME labels"
            )

    # ------------------------------------------------------------------
    #  A6: xcon <-> con consistency
    # ------------------------------------------------------------------

    def test_a6_xcon_con_consistency(self, converted):
        _, out_dir = converted
        con_text = self._con_path(out_dir).read_text()
        xcon_text = self._xcon_path(out_dir).read_text()
        # xcon nets ids == con net ids
        con_net_ids = set(re.findall(r'\("(N\d+)" "[^"]+" -1 -1 \d \)', con_text))
        xcon_net_ids = set(re.findall(r"<id>(N\d+)</id>", xcon_text))
        assert con_net_ids == xcon_net_ids
        # xcon instance ids == con instance ids
        con_inst_ids = set(re.findall(r'\("(I\d+)" "page\d+_i\d+" "S\d+"', con_text))
        xcon_inst_ids = set(re.findall(r"<id>(I\d+)</id>", xcon_text))
        assert con_inst_ids == xcon_inst_ids
        # aliases present for power nets
        aliases = re.findall(r'<alias net1="(N\d+)"', xcon_text)
        assert len(aliases) > 0

    # ------------------------------------------------------------------
    #  A7: cpc <-> con <-> csv instance names
    # ------------------------------------------------------------------

    def test_a7_cpc_names_consistent(self, converted):
        _, out_dir = converted
        sch = self._sch_dir(out_dir)
        con_text = self._con_path(out_dir).read_text()
        con_internal = set(
            m.replace('"', "") for m in re.findall(r'"page\d+_i\d+"', con_text)
        )
        for cpc in sorted(sch.glob("page*.cpc")):
            content = cpc.read_text()
            names = set(re.findall(r"page\d+_i\d+", content))
            # skip the page frame entry (*); component instances must match
            # con internal names (shared page-local k)
            names.discard("page0_i0")
            # Phase XI P0-遗留#2: power symbols (#ISCELL gnd_power /
            # vcc_circle) intentionally appear in cpc but NOT in con (C.5
            # convention) — exclude their instance names from the check.
            power_names = set(
                m.group(3)
                for m in re.finditer(
                    r"#ISCELL\s*\n\s+(\S+) (gnd_power|vcc_circle|gnd_earth"
                    r"|gnd_signal|vcc_bar|vcc_arrow) \*\s*\n\s+(page\d+_i\d+)",
                    content,
                )
            )
            assert names - power_names <= con_internal, (
                f"{cpc.name}: {names - power_names - con_internal} not in "
                f"con instances"
            )

    # ------------------------------------------------------------------
    #  A9: file inventory + no fatal
    # ------------------------------------------------------------------

    def test_a9_file_inventory(self, converted):
        report, out_dir = converted
        sch = self._sch_dir(out_dir)
        assert not report.has_fatal
        assert len(list(sch.glob("*.con"))) == 1
        assert len(list(sch.glob("*.xcon"))) == 1
        assert len(list(sch.glob("page*.csv"))) == 24
        assert len(list(sch.glob("page*.cpc"))) == 24
        assert len(list(sch.glob("page*.csa"))) == 24
        assert (sch / "master.tag").exists()
        assert (sch / "module_order.dat").exists()

    def test_no_3717_fake_nets(self, converted):
        """DSN RTL garbage nets ($17N..., 3717 fake nets) must not appear."""
        _, out_dir = converted
        text = self._con_path(out_dir).read_text()
        fake = re.findall(r'"\$17N\d+"', text)
        assert len(fake) == 0, f"DSN fake nets leaked into con: {fake[:5]}"


class TestPhaseXiP0PowerSymbols:
    """P0-遗留#2 acceptance — power symbols reach csv/cpc/csa, not con.

    Design assertions (phaseXI_P0_fix_design.md §2.5):
      * every page csa has ``FORCEADD GND_POWER..1`` / ``VCC_CIRCLE..1`` +
        ``LASTPIN ... SIG_NAME <net>\\g`` + ``HDL_POWER <net>`` +
        ``BODY_TYPE PLUMBING``;
      * csv has ``%"GND_POWER"`` / ``%"VCC_CIRCLE"`` blocks + ``HDL_POWER``
        + single-pin row ``"GND"<id>;`` / ``"G<SIZE-1..0> \\B"<id>;``;
      * cpc has ``#ISCELL hdl_lib gnd_power/vcc_circle * pageN_i<k>``;
      * con has NO power symbol cells/instances (C.5).
    """

    @staticmethod
    def _sch_dir(out_dir: Path) -> Path:
        worklib = out_dir / "worklib"
        cells = [d for d in worklib.iterdir() if d.is_dir()]
        return cells[0] / "sch_1"

    def _con_path(self, out_dir: Path) -> Path:
        sch = self._sch_dir(out_dir)
        cons = list(sch.glob("*.con"))
        assert cons, "no .con file"
        return cons[0]

    def test_power_symbols_in_csa(self, converted):
        _, out_dir = converted
        sch = self._sch_dir(out_dir)
        saw_gnd = saw_vcc = False
        for csa in sorted(sch.glob("page*.csa")):
            content = csa.read_text()
            for block in re.findall(
                r"FORCEADD (GND_POWER|VCC_CIRCLE)\.\.1\n"
                r"\((-?\d+) (-?\d+)\);.*?FORCEPROP 1 LAST PATH I\d+",
                content,
                flags=re.S,
            ):
                body, x, y = block
                if body == "GND_POWER":
                    saw_gnd = True
                else:
                    saw_vcc = True
                # LASTPIN SIG_NAME <net>\g at pin coord (body + pin offset)
                assert re.search(
                    rf"FORCEPROP 3 LASTPIN \(-?\d+ -?\d+\) SIG_NAME \S+\\g",
                    content,
                ), f"{csa.name}: {body} block missing LASTPIN SIG_NAME"
                assert f"HDL_POWER " in content, (
                    f"{csa.name}: {body} block missing HDL_POWER"
                )
                assert "FORCEPROP 1 LAST BODY_TYPE PLUMBING" in content, (
                    f"{csa.name}: {body} block missing BODY_TYPE PLUMBING"
                )
                assert int(x) != 0 or int(y) != 0
        assert saw_gnd, "no GND_POWER FORCEADD block found in any csa"
        assert saw_vcc, "no VCC_CIRCLE FORCEADD block found in any csa"

    def test_power_symbols_in_csv(self, converted):
        _, out_dir = converted
        sch = self._sch_dir(out_dir)
        saw_gnd = saw_vcc = False
        for csv in sorted(sch.glob("page*.csv")):
            content = csv.read_text()
            if '%"GND_POWER"' in content:
                saw_gnd = True
                assert 'HDL_POWER"GND"' in content, (
                    f"{csv.name}: GND_POWER block missing HDL_POWER"
                )
                assert 'BODY_TYPE"PLUMBING";' in content, (
                    f"{csv.name}: GND_POWER block missing BODY_TYPE"
                )
                assert re.search(r'"GND"\d+;', content), (
                    f"{csv.name}: GND_POWER block missing single-pin row"
                )
            if '%"VCC_CIRCLE"' in content:
                saw_vcc = True
                assert re.search(r'HDL_POWER"\S+"', content), (
                    f"{csv.name}: VCC_CIRCLE block missing HDL_POWER"
                )
                assert 'SIZE"1B"' in content, (
                    f"{csv.name}: VCC_CIRCLE block missing SIZE"
                )
                assert re.search(r'"G<SIZE-1\.\.0> \\B"\d+;', content), (
                    f"{csv.name}: VCC_CIRCLE block missing single-pin row"
                )
        assert saw_gnd, "no %\"GND_POWER\" block found in any csv"
        assert saw_vcc, "no %\"VCC_CIRCLE\" block found in any csv"

    def test_power_symbols_in_cpc(self, converted):
        _, out_dir = converted
        sch = self._sch_dir(out_dir)
        saw_gnd = saw_vcc = False
        for cpc in sorted(sch.glob("page*.cpc")):
            content = cpc.read_text()
            for cell in re.findall(
                r"#ISCELL\s*\n\s+\S+ (gnd_power|vcc_circle) \*\s*\n\s+(page\d+_i\d+)",
                content,
            ):
                if cell[0] == "gnd_power":
                    saw_gnd = True
                else:
                    saw_vcc = True
                assert cell[1].startswith("page"), (
                    f"{cpc.name}: bad #ISCELL instance name {cell[1]}"
                )
        assert saw_gnd, "no #ISCELL gnd_power entry in any cpc"
        assert saw_vcc, "no #ISCELL vcc_circle entry in any cpc"

    def test_power_symbols_not_in_con(self, converted):
        _, out_dir = converted
        text = self._con_path(out_dir).read_text()
        assert '"gnd_power" "hdl_lib"' not in text
        assert '"vcc_circle" "hdl_lib"' not in text
        # no instance references a power symbol cell id
        assert re.search(r'"I\d+" "page\d+_i\d+" "S\d+"', text)  # sanity
        insts = re.findall(r'\("I\d+" "page\d+_i\d+" "S\d+"', text)
        assert len(insts) == 914  # power symbols excluded from con instances
