"""ScrWriter — generate DEHDL console interaction scripts (.scr).

Generates ``.scr`` files that can be sourced in the DEHDL console to
place parts, set properties, and configure symbol attributes.  These
scripts are used for automated schematic population and debugging.

Reference format (from CIStoHDL_standard/generate_hdl_scr.py)::

    add <hdl_lib>capacitor
    :%Value:PART_NAME=CAPACITOR_0201
    :%Value:VALUE=100nF
    :%Value:REFDES=C460
    :%Value:LOCATION=-7348,6308

Output path: ``worklib/<cell>/sch_1/place_parts.scr``

Usage::

    writer = ScrWriter()
    writer.write_scr(page, output_path=Path("worklib/cell/sch_1/place_parts.scr"))
    # Or per-page:
    writer.write_scr_page(page, sch_dir=Path("worklib/cell/sch_1"))
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from cis2hdl.core.ir.component import ComponentInstanceIR
from cis2hdl.core.ir.design import PageIR

logger = logging.getLogger(__name__)


class ScrWriter:
    """Generate DEHDL console interaction scripts (.scr).

    Produces ``.scr`` files that automate part placement and property
    assignment in Cadence DEHDL schematic views.
    """

    def __init__(self, encoding: str = "utf-8") -> None:
        """Initialize the .scr writer.

        Args:
            encoding: Output file encoding.
        """
        self._encoding: str = encoding

    # ------------------------------------------------------------------
    #  Public API
    # ------------------------------------------------------------------

    def write_scr(
        self,
        page: PageIR,
        output_path: Path,
        match_lookup: Optional[dict[str, str]] = None,
    ) -> Path:
        """Generate a .scr script for a single schematic page.

        Each component instance on the page gets a ``add <hdl_lib>cell``
        command followed by property assignment lines.

        Args:
            page: The PageIR containing component instances.
            output_path: Where to write the .scr file.
            match_lookup: Optional dict mapping source_library_id →
                          (target_library_id, part_name) for resolving
                          the correct HDL cell and part name.

        Returns:
            Path to the written .scr file.
        """
        lines: list[str] = self._build_scr_content(page, match_lookup)
        content: str = "\n".join(lines) + "\n"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding=self._encoding)
        logger.info("Wrote .scr: %s (%d instances)", output_path, len(page.instances))
        return output_path

    def write_scr_page(
        self,
        page: PageIR,
        sch_dir: Path,
        page_num: int = 1,
        match_lookup: Optional[dict[str, str]] = None,
    ) -> Path:
        """Write a per-page .scr file to worklib/<cell>/sch_1/place_parts_pageN.scr.

        Args:
            page: The PageIR containing component instances.
            sch_dir: The sch_1 output directory.
            page_num: Page number (1-based).
            match_lookup: Optional match lookup for HDL cell resolution.

        Returns:
            Path to the written file.
        """
        path: Path = sch_dir / f"place_parts_page{page_num}.scr"
        return self.write_scr(page, path, match_lookup)

    def write_all(
        self,
        pages: list[PageIR],
        sch_dir: Path,
        match_lookup: Optional[dict[str, str]] = None,
    ) -> list[Path]:
        """Generate .scr files for all pages and a combined master file.

        Args:
            pages: List of PageIR objects.
            sch_dir: The sch_1 output directory.
            match_lookup: Optional match lookup for HDL cell resolution.

        Returns:
            List of all written .scr file paths.
        """
        files: list[Path] = []
        all_lines: list[str] = []

        for idx, page in enumerate(pages, start=1):
            page_file: Path = self.write_scr_page(page, sch_dir, idx, match_lookup)
            files.append(page_file)

            # Collect for master file
            all_lines.extend(self._build_scr_content(page, match_lookup))
            if page.instances:
                all_lines.append("")

        # Write master place_parts.scr (combined)
        master_path: Path = sch_dir / "place_parts.scr"
        master_content: str = "\n".join(all_lines) + "\n"
        sch_dir.mkdir(parents=True, exist_ok=True)
        master_path.write_text(master_content, encoding=self._encoding)
        files.append(master_path)
        logger.info("Wrote master .scr: %s", master_path)

        return files

    # ------------------------------------------------------------------
    #  Content generation
    # ------------------------------------------------------------------

    def _build_scr_content(
        self,
        page: PageIR,
        match_lookup: Optional[dict[str, str]] = None,
    ) -> list[str]:
        """Build .scr content lines for a page.

        Args:
            page: The PageIR with component instances.
            match_lookup: Optional match lookup for HDL cell resolution.

        Returns:
            List of .scr content lines.
        """
        lines: list[str] = []
        if match_lookup is None:
            match_lookup = {}

        for inst in page.instances:
            refdes: str = getattr(inst, 'refdes', '?')

            # Resolve HDL cell name from match_lookup or library_id
            lib_id: str = getattr(inst, 'library_id', 'unknown')
            match_info = match_lookup.get(lib_id)
            if match_info is not None:
                # match_info could be a tuple (target_library_id, part_name) or a
                # MatchResult object
                if isinstance(match_info, tuple):
                    target_lib_id, part_name = match_info
                elif hasattr(match_info, 'target_library_id'):
                    target_lib_id = match_info.target_library_id
                    part_name = getattr(match_info, 'target_part_name', '')
                else:
                    target_lib_id = lib_id
                    part_name = ''
            else:
                target_lib_id = lib_id
                part_name = ''

            # Extract cell name from target_library_id (last path component)
            cell: str = target_lib_id.rsplit('/', 1)[-1] if target_lib_id else 'unknown'

            # Use part_name from match or derive from instance
            if not part_name:
                part_name = getattr(inst, 'value_override', '') or cell.upper()

            value: str = getattr(inst, 'value_override', '') or ''
            loc_x: int = getattr(inst, 'loc_x', 0)
            loc_y: int = getattr(inst, 'loc_y', 0)

            lines.append(f"add <hdl_lib>{cell}")
            lines.append(f":%Value:PART_NAME={part_name}")
            if value:
                lines.append(f":%Value:VALUE={value}")
            lines.append(f":%Value:REFDES={refdes}")
            lines.append(f":%Value:LOCATION={loc_x},{loc_y}")
            lines.append("")

        return lines
