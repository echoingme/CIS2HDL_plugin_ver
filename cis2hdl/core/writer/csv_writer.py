"""PageCsvWriter — generates DEHDL ``pageN.csv`` connectivity files.

Phase XI P0-B (system_design.md A.3)::

    FILE_TYPE = CONNECTIVITY;
    {Allegro Design Entry HDL 16.6-p007 (v16-6-112F) 10/10/2012}
    "PAGE_NUMBER" = 1;
    0"NC";
    1"VCC_12\\g";
    ...
    %"DC_DC"
    "1","(-5350,6675)","0","hdl_lib","I1";
    ;
    VALUE"SY8113BADC"
    ...
    "BST"
    $PN"1"12;
    ...
    END.

Notes:
  * page-local net ids (0 = NC placeholder) are distinct from con design
    net ids; they are bridged by the bare net name.
  * power symbols (gnd_power / vcc_circle) DO appear here as single-pin
    blocks (they are excluded from con cells/instances).
"""

from __future__ import annotations

import logging
from pathlib import Path

from .base import WriterBase
from .connectivity_model import DesignConnectivity, PageConnectivity
from .output_manager import OutputManager

logger = logging.getLogger(__name__)

#: DEHDL render version string (second line of every csv).
_VERSION_LINE = "{Allegro Design Entry HDL 16.6-p007 (v16-6-112F) 10/10/2012}"


class PageCsvWriter(WriterBase):
    """Generate pageN.csv files from PageConnectivity + instance details.

    Usage::

        writer = PageCsvWriter()
        writer.write_all(conn, output_dir)
    """

    FORMAT_NAME: str = "csv"

    def write(self, conn: "DesignConnectivity", output_dir: Path) -> list[Path]:
        """Write all page csv files (WriterBase interface)."""
        return self.write_all(conn, output_dir)

    def write_all(
        self,
        conn: "DesignConnectivity",
        output_dir: Path,
    ) -> list[Path]:
        """Write one pageN.csv per page.

        Args:
            conn: DesignConnectivity built by ConnectivityModelBuilder.
            output_dir: Output root directory.

        Returns:
            List of written .csv paths.
        """
        self._ensure_output_dir(output_dir)
        mgr = OutputManager(
            project_name=conn.cell_name,
            output_root=output_dir,
        )
        mgr.setup_directory_structure()
        files: list[Path] = []
        for page_conn in conn.pages:
            content = self._build_csv_content(conn, page_conn)
            files.append(mgr.write_csv_page(page_conn.page_num, content))
        logger.info(
            "PageCsvWriter: %d page(s) written", len(files),
        )
        return files

    def write_all_with_manager(
        self,
        conn: "DesignConnectivity",
        mgr: OutputManager,
    ) -> list[Path]:
        """Write all page csv files using an existing OutputManager."""
        files: list[Path] = []
        for page_conn in conn.pages:
            content = self._build_csv_content(conn, page_conn)
            files.append(mgr.write_csv_page(page_conn.page_num, content))
        return files

    # ------------------------------------------------------------------
    #  Content builder
    # ------------------------------------------------------------------

    def _build_csv_content(
        self,
        conn: "DesignConnectivity",
        page_conn: "PageConnectivity",
    ) -> str:
        """Build the complete pageN.csv content for a page."""
        page_num = page_conn.page_num
        lines: list[str] = []
        a = lines.append

        a("FILE_TYPE = CONNECTIVITY;")
        a(_VERSION_LINE)
        a(f'"PAGE_NUMBER" = {page_num};')

        # ── Network list (0 = NC placeholder, then page-local nets) ──
        a('0"NC";')
        for pnr in page_conn.nets:
            a(f'{pnr.local_id}"{pnr.display_name}";')

        # ── Instance blocks ─────────────────────────────────────────
        for irec in page_conn.instances:
            cell_label = irec.cell_name or self._cell_label(conn, irec.cell_id)
            lines.extend(self._build_instance_block(
                conn, page_conn, irec, cell_label,
            ))

        a("END.")
        return "\n".join(lines) + "\n"

    # ------------------------------------------------------------------
    #  Instance block
    # ------------------------------------------------------------------

    def _build_instance_block(
        self,
        conn: "DesignConnectivity",
        page_conn: "PageConnectivity",
        irec,
        cell_label: str,
    ) -> list[str]:
        """Build one instance block (header + attributes + pins)."""
        lines: list[str] = []
        a = lines.append

        refdes = irec.refdes
        section = irec.section
        props = irec.properties or {}
        value = irec.value or props.get("VALUE", "") or refdes
        x, y = self._instance_coords(conn, page_conn, irec)

        # Phase XI P0-遗留#2: power symbols use the dedicated single-pin
        # block (8367 page1.csv L360-376) — no VALUE / PART_NAME / LOCATION.
        if irec.is_power_symbol:
            return self._build_power_symbol_block(
                conn, page_conn, irec, cell_label, x, y,
            )

        # ── Header ──────────────────────────────────────────────────
        a(f'%"{cell_label.upper()}"')
        a(f'"{section}","({x},{y})","0","{conn.hdl_lib_name}","I{irec.page_local_k}";')
        a(";")

        # ── Attributes ──────────────────────────────────────────────
        outline = self._outline_for(conn, irec.cell_id)
        a(f'VALUE"{value}"')
        a(f'CDS_LMAN_SYM_OUTLINE"{outline}"')
        a(f'CDS_LIB"{conn.hdl_lib_name}"')
        a(f'PART_NAME"{cell_label.upper()}"')
        a(f'LOCATION"{refdes}"')
        a(f'$SEC"{section}"')
        a(f'CDS_SEC"{section}";')

        # ── Pins ────────────────────────────────────────────────────
        for pre in irec.pins:
            pnr = self._page_net_for_pin(page_conn, pre.net_id)
            if pnr is None:
                continue
            a(f'"{pre.pin_name}"')
            a(f'$PN"{pre.pin_number}"{pnr.local_id};')

        return lines

    def _build_power_symbol_block(
        self,
        conn: "DesignConnectivity",
        page_conn: "PageConnectivity",
        irec,
        cell_label: str,
        x: int,
        y: int,
    ) -> list[str]:
        """Power symbol single-pin block (8367 page1.csv L360-376).

        Format::

            %"GND_POWER"
            "1","(-5600,4275)","0","hdl_lib","I27";
            ;
            CDS_LMAN_SYM_OUTLINE"-50,0,50,-50"
            CDS_LIB"hdl_lib"
            HDL_POWER"GND_POWER"
            BODY_TYPE"PLUMBING";
            "GND"2;

        The symbol has no VALUE / PART_NAME / LOCATION; ``HDL_POWER`` holds
        the power net name (no ``\\g``); VCC_CIRCLE additionally carries
        ``SIZE"1B"``.  The single-pin row is ``"<pinName>"<netId>;``.
        """
        lines: list[str] = []
        a = lines.append
        cell_lower = (cell_label or "").lower()
        net_display = (irec.power_nets[0] if irec.power_nets else "GND").rstrip("\\g")
        outline = self._outline_for_name(cell_label)
        net_id = self._power_net_id(page_conn, irec)

        a(f'%"{cell_label.upper()}"')
        a(f'"1","({x},{y})","0","{conn.hdl_lib_name}","I{irec.page_local_k}";')
        a(";")
        if cell_lower == "vcc_circle":
            a(f'HDL_POWER"{net_display}"')
            a(f'CDS_LIB"{conn.hdl_lib_name}"')
            a('SIZE"1B"')
            a('BODY_TYPE"PLUMBING"')
            a(f'CDS_LMAN_SYM_OUTLINE"{outline}";')
            pin_name = "G<SIZE-1..0> \\B"
        else:  # gnd / dgnd / gnd_power / gnd_earth / gnd_signal
            a(f'CDS_LMAN_SYM_OUTLINE"{outline}"')
            a(f'CDS_LIB"{conn.hdl_lib_name}"')
            a(f'HDL_POWER"{net_display}"')
            a('BODY_TYPE"PLUMBING";')
            pin_name = "GND"
        a(f'"{pin_name}"{net_id};')
        return lines

    @staticmethod
    def _power_net_id(page_conn, irec) -> int:
        """Page-local net id for a power symbol's single pin.

        Power symbols have no PinRecord, so the net id is resolved through
        the page net whose bare name matches the symbol's power net
        (e.g. GND → the page's ``gnd`` record).  Falls back to 0 (NC) when
        the net is absent from the page.
        """
        from ..net_utils import con_name
        if not irec.power_nets:
            return 0
        bare = con_name(irec.power_nets[0])
        pnr = page_conn.net_by_bare.get(bare)
        return pnr.local_id if pnr is not None else 0

    # ------------------------------------------------------------------
    #  Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _cell_label(conn: "DesignConnectivity", cell_id: str) -> str:
        if not cell_id:
            return "UNKNOWN"
        for cell in conn.cells:
            if cell.cell_id == cell_id:
                return cell.cell_name
        return "UNKNOWN"

    @staticmethod
    def _instance_coords(conn, page_conn, irec) -> tuple[int, int]:
        """Return (x, y) DEHDL coords for the instance header.

        Uses the page's CoordTransform so csv coordinates agree with the
        csa FORCEADD coordinates (single coordinate source rule).

        Phase XI P0-遗留#2: power symbols are excluded from the
        regular-component bounding box (EDIF ``portImplementation`` origins
        live in a different coordinate space); their own origin is mapped
        with the same affine transform, and symbols without usable placement
        fall back to the page corner region (``power_symbol_position``).
        """
        from .coord_transform import CoordTransform
        coords = getattr(page_conn, "_coord_map", None)
        if coords is None:
            coords = CoordTransform.map_page_instances(page_conn.instances)
            page_conn._coord_map = coords  # type: ignore[attr-defined]
        if irec.refdes in coords:
            return coords[irec.refdes]
        if irec.is_power_symbol:
            return CoordTransform.power_symbol_position(irec.page_local_k)
        return CoordTransform.grid_position(irec.page_local_k - 1)

    @staticmethod
    def _outline_for_name(cell_name: str) -> str:
        """Default CDS_LMAN_SYM_OUTLINE by HDL cell name."""
        n = (cell_name or "").lower()
        if n in ("capacitor", "resistor", "inductor", "diode", "led"):
            return "-25,50,25,-50"
        if n in ("gnd_power", "gnd", "dgnd", "gnd_earth", "gnd_signal"):
            return "-50,0,50,-50"
        if n == "vcc_circle":
            return "-75,75,75,-75"
        return "-50,0,50,-25"

    @staticmethod
    def _outline_for(conn, cell_id: str) -> str:
        """Default CDS_LMAN_SYM_OUTLINE for a cell (best-effort)."""
        if cell_id:
            for cell in conn.cells:
                if cell.cell_id == cell_id:
                    return PageCsvWriter._outline_for_name(cell.cell_name)
        return PageCsvWriter._outline_for_name("")

    @staticmethod
    def _page_net_for_pin(page_conn, design_net_id: str):
        """Find the page net record whose pin_net_id matches a pin's net."""
        for pnr in page_conn.nets:
            if pnr.pin_net_id == design_net_id:
                return pnr
        # fallback: match by net_id (flat nets where both coincide)
        for pnr in page_conn.nets:
            if pnr.net_id == design_net_id:
                return pnr
        return None
