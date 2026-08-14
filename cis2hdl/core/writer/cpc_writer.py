"""CpcWriter — generates DEHDL ``pageN.cpc`` page instance files.

Phase XI P0-B (system_design.md A.4)::

    #ISCELL
      hdl_lib c#20size#20page *
      *
    #ISCELL
      hdl_lib gnd_power *
      page15_i1
    #CELL
      hdl_lib capacitor *
      page15_i10
    ...

Rules:
  * ``#ISCELL`` for the page frame (``c#20size#20page``, instance ``*``)
    and for power symbols (gnd_power / vcc_circle);
  * ``#CELL`` for every regular component;
  * instance names ``pageN_i<k>`` use the shared page-local k — identical
    to the con instance internal names and the csv ``I<k>`` references.
"""

from __future__ import annotations

import logging
from pathlib import Path

from .base import WriterBase
from .connectivity_model import DesignConnectivity
from .output_manager import OutputManager

logger = logging.getLogger(__name__)


class CpcWriter(WriterBase):
    """Generate pageN.cpc files from a DesignConnectivity model."""

    FORMAT_NAME: str = "cpc"

    def write(self, conn: "DesignConnectivity", output_dir: Path) -> list[Path]:
        """Write all page cpc files (WriterBase interface)."""
        return self.write_all(conn, output_dir)

    def write_all(
        self,
        conn: "DesignConnectivity",
        output_dir: Path,
    ) -> list[Path]:
        """Write one pageN.cpc per page.

        Args:
            conn: DesignConnectivity built by ConnectivityModelBuilder.
            output_dir: Output root directory.

        Returns:
            List of written .cpc paths.
        """
        self._ensure_output_dir(output_dir)
        mgr = OutputManager(
            project_name=conn.cell_name,
            output_root=output_dir,
        )
        mgr.setup_directory_structure()
        files: list[Path] = []
        for page_conn in conn.pages:
            content = self._build_cpc_content(conn, page_conn)
            files.append(mgr.write_cpc_file(page_conn.page_num, content))
        logger.info("CpcWriter: %d page(s) written", len(files))
        return files

    def write_all_with_manager(
        self,
        conn: "DesignConnectivity",
        mgr: OutputManager,
    ) -> list[Path]:
        """Write all page cpc files using an existing OutputManager."""
        files: list[Path] = []
        for page_conn in conn.pages:
            content = self._build_cpc_content(conn, page_conn)
            files.append(mgr.write_cpc_file(page_conn.page_num, content))
        return files

    # ------------------------------------------------------------------
    #  Content builder
    # ------------------------------------------------------------------

    def _build_cpc_content(
        self,
        conn: "DesignConnectivity",
        page_conn,
    ) -> str:
        """Build the complete pageN.cpc content.

        Entries are ordered by page-local k ascending (8367 evidence).
        """
        lines: list[str] = []

        # ── Page frame (always #ISCELL, instance *) ─────────────────
        lines.append("#ISCELL")
        lines.append(f"  {conn.hdl_lib_name} c#20size#20page *")
        lines.append("  *")

        # ── Instances in k order ────────────────────────────────────
        ordered = sorted(page_conn.instances, key=lambda i: i.page_local_k)
        for irec in ordered:
            # Phase XI P0-遗留#2: power symbols have no con cell record, so
            # their HDL cell name comes from InstanceRecord.cell_name
            # (gnd_power / vcc_circle); regular cells resolve via conn.cells.
            cell_label = irec.cell_name or self._cell_label(conn, irec.cell_id)
            is_iscell = irec.is_power_symbol or cell_label.lower() in _ISCELL_CELLS
            lines.append("#ISCELL" if is_iscell else "#CELL")
            lines.append(f"  {conn.hdl_lib_name} {cell_label} *")
            lines.append(f"  {irec.internal_name}")

        return "\n".join(lines) + "\n"

    # ------------------------------------------------------------------
    #  Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _cell_label(conn: "DesignConnectivity", cell_id: str) -> str:
        if not cell_id:
            return "unknown"
        for cell in conn.cells:
            if cell.cell_id == cell_id:
                return cell.cell_name
        return "unknown"


#: Cells emitted as #ISCELL (beyond power symbols handled via the flag).
_ISCELL_CELLS: frozenset[str] = frozenset(
    {
        "c#20size#20page", "a#20size#20page", "b#20size#20page",
        "d#20size#20page", "e#20size#20page",
        "vcc_circle", "vcc_bar", "vcc_arrow",
        "gnd_power", "gnd_earth", "gnd_signal", "gnd_chassis",
        "off_page", "offpage_l", "offpage_r",
        "nc", "test_point", "tp",
        # P1-5: "mark" was removed — reference engineering (8367 page1.cpc,
        # 04p4 page9.cpc) emits mark as a regular #CELL, not #ISCELL.
    }
)
