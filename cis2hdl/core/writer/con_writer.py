"""ConWriter — generates Cadence ``.con`` S-Expr connectivity files.

Phase XI P0-B (system_design.md A.1): the ``.con`` file uses Cadence
Lisp-style S-expressions:

    (
      (version 16.6)
      (tool (creator "conceptHDL") (last "conceptHDL"))
      (library "<lib>")
      (design "<cell>"
        (lastIds (lastInstanceId N) (lastNetId N) (lastInstTermId N))
        (cells ("S1" "capacitor" "hdl_lib" "sym_1" (terms ...)) ...)
        (nets   ("N1" "gnd_power" -1 -1 2) ...)
        (alias  ("N2" -1 -1 "N1" -1 -1) ...)
        (instances ("I1" "page1_i1" "S2" (pins ("M1" "T3" -1 -1 (conn ("0" -1 -1 "N7" -1 -1))) ...)) ...)
      )
    )

Power symbols (gnd_power / vcc_circle) never appear in cells/instances.
"""

from __future__ import annotations

import logging
from pathlib import Path

from .base import WriterBase
from .connectivity_model import DesignConnectivity
from .output_manager import OutputManager

logger = logging.getLogger(__name__)


class ConWriter(WriterBase):
    """Generate a ``<cell>.con`` file from a DesignConnectivity model.

    Usage::

        writer = ConWriter()
        writer.write(conn, output_dir)
    """

    FORMAT_NAME: str = "con"

    # ------------------------------------------------------------------
    #  Public API
    # ------------------------------------------------------------------

    def write(self, conn: "DesignConnectivity", output_dir: Path) -> list[Path]:
        """Generate and write the .con file.

        Args:
            conn: DesignConnectivity built by ConnectivityModelBuilder.
            output_dir: Output root directory.

        Returns:
            List containing the written .con path.
        """
        self._ensure_output_dir(output_dir)
        mgr = OutputManager(
            project_name=conn.cell_name,
            output_root=output_dir,
        )
        mgr.setup_directory_structure()
        content = self._build_con_content(conn)
        path = mgr.write_con_file(
            cell_name=conn.cell_name,
            library_alias=conn.library_alias,
            design_ir=None,
            match_map=None,
            content_override=content,
        )
        logger.info(
            "ConWriter: %d cells / %d nets / %d instances / %d pins → %s",
            conn.cell_count, conn.net_count,
            conn.instance_count, conn.pin_count, path,
        )
        return [path]

    def write_with_manager(
        self,
        conn: "DesignConnectivity",
        mgr: OutputManager,
    ) -> list[Path]:
        """Generate a .con file using an existing OutputManager."""
        content = self._build_con_content(conn)
        path = mgr.write_con_file(
            cell_name=conn.cell_name,
            library_alias=conn.library_alias,
            design_ir=None,
            match_map=None,
            content_override=content,
        )
        return [path]

    # ------------------------------------------------------------------
    #  Content builder
    # ------------------------------------------------------------------

    @staticmethod
    def _build_con_content(conn: "DesignConnectivity") -> str:
        """Build the complete .con S-Expr content."""
        lines: list[str] = []
        a = lines.append

        a("(")
        a("  (version 16.6)")
        a("  (tool")
        a('    (creator "conceptHDL")')
        a('    (last "conceptHDL")')
        a("  )")
        a(f'  (library "{conn.library_alias}")')
        a(f'  (design "{conn.cell_name}"')
        a("    (lastIds")
        a(f"      (lastInstanceId {conn.instance_count})")
        a(f"      (lastNetId {conn.net_count})")
        a(f"      (lastInstTermId {conn.pin_count})")
        a("    )")

        # ── cells ───────────────────────────────────────────────────
        a("    (cells")
        for cell in conn.cells:
            a(f'      ("{cell.cell_id}" "{cell.cell_name}" "{cell.library}" "{cell.sym}"')
            a("        (terms")
            for term in cell.terms:
                a(
                    f'          ("{term.term_id}" "{term.name}" -1 -1 {term.direction})'
                )
            a("        )")
            a("      )")
        a("    )")

        # ── nets ────────────────────────────────────────────────────
        a("    (nets")
        for net in conn.nets:
            a(f'      ("{net.net_id}" "{net.internal_name}" -1 -1 {net.scope} )')
        a("    )")

        # ── alias (local power net → global net) ────────────────────
        a("    (alias")
        for local_name, global_name in conn.aliases:
            local_rec = conn.net_by_internal.get(local_name)
            global_rec = conn.net_by_internal.get(global_name)
            if local_rec is None or global_rec is None:
                continue
            a(
                f'      ("{local_rec.net_id}" -1 -1 "{global_rec.net_id}" -1 -1)'
            )
        a("    )")

        # ── instances ───────────────────────────────────────────────
        a("    (instances")
        for irec in conn.instances:
            a(f'      ("{irec.inst_id}" "{irec.internal_name}" "{irec.cell_id}"')
            if irec.pins:
                a("        (pins")
                for pre in irec.pins:
                    a(
                        f'          ("{pre.pin_id}" "{pre.term_id}" -1 -1'
                        f'\n            (conn'
                        f'\n              ("0" -1 -1 "{pre.net_id}" -1 -1)'
                        f"\n            )"
                        f"\n          )"
                    )
                a("        )")
            a("      )")
        a("    )")

        a("  )")
        a(")")
        return "\n".join(lines) + "\n"
