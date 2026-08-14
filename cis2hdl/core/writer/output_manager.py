"""OutputManager — unified output directory management for Cadence DEHDL format.

Manages the creation of the standard Cadence DEHDL Project Manager
directory structure and provides convenience methods for writing
page files, placeholder files, and project-level files.

Reference directory structure:
    output_root/
    ├── <cell_name>.cpm              ← Project Manager file (output root)
    ├── cds.lib                       ← Library definitions (output root)
    ├── temp/                         ← Temp directory (.cpm references this)
    └── worklib/                      ← Working library
        └── <cell_name>/              ← Cell directory (short name)
            ├── sch_1/                ← Schematic view (fixed name)
            │   ├── page1.csa         ← CSA native page files (MACRO_DRAWING)
            │   ├── <cell_name>.con   ← Constraint file
            │   ├── module_order.dat  ← Module order list
            │   ├── master.tag        ← Contains "CDS_SYSTEM"
            │   └── page.map          ← Empty file
            ├── cfg_package/
            ├── cfg_pic/
            ├── physical/
            └── variant/
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..config import config as cfg

logger = logging.getLogger(__name__)


def _extract_page_number(page) -> int:
    """Extract the real physical sheet number from a PageIR.

    EDIF page blocks are named ``01-Cover_Page``, ``10-SOC_SerDes`` ... —
    the leading numeric prefix is the sheet number shown in the title
    block (and used by DEHDL's page.map).  Falls back to the internal
    page_id suffix ("1.5" → 5) and finally to 0.
    """
    name: str = getattr(page, "page_name", "") or ""
    m = re.match(r"(\d+)-", name)
    if m:
        return int(m.group(1))
    pid: str = getattr(page, "page_id", "") or ""
    m2 = re.match(r"(\d+)\.(\d+)", pid)
    if m2:
        return int(m2.group(2))
    return 0


class OutputManager:
    """Manages Cadence DEHDL output directory structure and file placement.

    Usage::

        mgr = OutputManager(project_name="RTL8367RB-VC-DEMO", output_root=Path("output"))
        mgr.setup_directory_structure()
        mgr.write_csa_page(1, csa_content)
        mgr.write_con_file()
        mgr.write_module_order()
        mgr.write_cpm()
        mgr.write_cdslib()
        mgr.write_placeholder_files()
    """

    def __init__(
        self,
        project_name: str,
        output_root: Path,
        library_alias: Optional[str] = None,
    ) -> None:
        """Initialize the output manager.

        Args:
            project_name: Full project name (used to derive cell_name).
            output_root: Root output directory.
            library_alias: Library alias for cds.lib DEFINE.
                           Defaults to ``{cell_name}_lib`` if not provided.
        """
        self.project_name: str = project_name
        self.output_root: Path = Path(output_root)

        # Derive cell name from project name
        self.cell_name: str = cfg.output.derive_cell_name(project_name)

        # Library alias: defaults to "{cell_name}_lib"
        if library_alias is None:
            self.library_alias: str = f"{self.cell_name}_lib"
        else:
            self.library_alias = library_alias

        # ── Derived paths ──────────────────────────────────────────
        self.worklib_root: Path = self.output_root / cfg.output.worklib_dir
        self.cell_dir: Path = self.worklib_root / self.cell_name
        self.sch_dir: Path = self.cell_dir / cfg.output.view_name
        self.temp_dir: Path = self.output_root / cfg.output.temp_dir

    # ------------------------------------------------------------------
    #  Directory setup
    # ------------------------------------------------------------------

    def setup_directory_structure(self) -> list[Path]:
        """Create the complete Cadence DEHDL directory structure.

        Creates:
            - output_root/temp/
            - output_root/worklib/<cell>/sch_1/
            - output_root/worklib/<cell>/cfg_package/
            - output_root/worklib/<cell>/cfg_pic/
            - output_root/worklib/<cell>/physical/
            - output_root/worklib/<cell>/variant/

        Returns:
            List of created directory paths.
        """
        created: list[Path] = []

        dirs_to_create: list[Path] = [
            self.temp_dir,
            self.sch_dir,
        ]

        # Cell subdirectories (cfg_package, cfg_pic, physical, variant)
        for subdir in cfg.output.cell_subdirs:
            dirs_to_create.append(self.cell_dir / subdir)

        for d in dirs_to_create:
            if not d.exists():
                d.mkdir(parents=True, exist_ok=True)
                created.append(d)
                logger.debug("Created directory: %s", d)

        logger.info(
            "OutputManager: %d directories created for cell '%s'",
            len(created),
            self.cell_name,
        )
        return created

    # ------------------------------------------------------------------
    #  Helper: write worklib files with CRLF line endings
    # ------------------------------------------------------------------

    @staticmethod
    def _write_worklib_file(filepath: Path, content: str, encoding: str = "ascii") -> None:
        """Write a worklib file with CRLF line endings (Cadence Windows requirement).

        Cadence DEHDL on Windows expects worklib files to use CRLF (\\r\\n)
        line endings.  Root-level files (.cpm, cds.lib) use LF and are
        written via the normal ``write_text`` path.

        Uses binary write to avoid Python's text-mode newline translation
        on Windows (which would turn ``\\r\\n`` into ``\\r\\r\\n``).

        Args:
            filepath: Destination path.
            content: Text content to write.
            encoding: Character encoding (default: "ascii").
        """
        crlf_content: str = content.replace("\n", "\r\n")
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_bytes(crlf_content.encode(encoding))

    @staticmethod
    def _write_root_file(filepath: Path, content: str, encoding: str = "ascii") -> None:
        """Write a root-level file with LF line endings (Cadence requirement).

        Root-level files (.cpm, cds.lib) must use LF line endings even on
        Windows.  Uses binary write to avoid Python text-mode translation.

        Args:
            filepath: Destination path.
            content: Text content to write.
            encoding: Character encoding (default: "ascii").
        """
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_bytes(content.encode(encoding))

    # ------------------------------------------------------------------
    #  CSA page file writing (DEHDL native format)
    # ------------------------------------------------------------------

    def write_csa_page(self, page_num: int, content: str) -> Path:
        """Write a single CSA page file to worklib/<cell>/sch_1/pageN.csa.

        The .csa format (FILE_TYPE = MACRO_DRAWING) is the native
        DEHDL format that Cadence Concept HDL reads directly.

        Args:
            page_num: Page number (1-based).
            content: Full .csa MACRO_DRAWING content.

        Returns:
            Path to the written file.
        """
        self.sch_dir.mkdir(parents=True, exist_ok=True)
        path: Path = self.sch_dir / f"page{page_num}.csa"
        self._write_worklib_file(path, content, encoding=cfg.app.output_encoding)
        logger.debug("Wrote CSA page %d: %s", page_num, path)
        return path

    # ------------------------------------------------------------------
    #  .con constraint file
    # ------------------------------------------------------------------

    def write_con_file(
        self,
        cell_name: Optional[str] = None,
        library_alias: Optional[str] = None,
        design_ir=None,
        match_map=None,
        content_override: Optional[str] = None,
    ) -> Path:
        """Generate and write the .con constraint file.

        Written to worklib/<cell>/sch_1/<cell_name>.con

        Reference format (from 8367.con) — Lisp-like S-expressions:
            (
              (version 16.6)
              (tool (creator "conceptHDL") (last "conceptHDL"))
              (library "8367_lib")
              (design "8367"
                (lastIds (lastInstanceId ...) (lastNetId ...) (lastInstTermId ...))
                ...
              )
            )

        When ``design_ir`` is provided, the nets and instances sections
        are populated from the DesignIR data, providing real connectivity
        and component placement information.  When ``content_override`` is
        provided (Phase XI P0-B: ConWriter), it is used verbatim and the
        legacy builder is skipped.

        Args:
            cell_name: Cell short name (defaults to self.cell_name).
            library_alias: Library alias (defaults to self.library_alias).
            design_ir: Optional DesignIR for populating nets/instances.
            match_map: Optional match map for HDL cell resolution.
            content_override: Optional pre-built .con content (ConWriter).

        Returns:
            Path to the written .con file.
        """
        if cell_name is None:
            cell_name = self.cell_name
        if library_alias is None:
            library_alias = self.library_alias

        if content_override is not None:
            content = content_override
        else:
            content = self._build_con_content(
                cell_name, library_alias, design_ir=design_ir, match_map=match_map,
            )
        self.sch_dir.mkdir(parents=True, exist_ok=True)
        con_path: Path = self.sch_dir / f"{cell_name}.con"
        self._write_worklib_file(con_path, content, encoding=cfg.app.output_encoding)
        logger.info("Wrote .con: %s", con_path)
        return con_path

    def _build_con_content(
        self,
        cell_name: str,
        library_alias: str,
        design_ir=None,
        match_map=None,
    ) -> str:
        """Build .con file content with populated nets and instances.

        When ``design_ir`` is provided, collects pin_connections from all
        ComponentInstanceIR objects across all pages and groups them by
        net_name to populate the (nets) section.  Also populates the
        (instances) section with refdes, cell, location, and rotation.

        Args:
            cell_name: Short cell name.
            library_alias: Library alias string.
            design_ir: Optional DesignIR with pages/instances data.
            match_map: Optional match map (reserved for future use).

        Returns:
            Complete .con file content as a string.
        """
        from collections import defaultdict

        lines: list[str] = []
        a = lines.append

        # ── Collect net→pins mapping from all instances ──────────────
        net_pins: dict[str, list[tuple[str, str]]] = defaultdict(list)

        if design_ir is not None:
            for page in design_ir.pages:
                for inst in page.instances:
                    refdes = getattr(inst, 'refdes', '')
                    pin_conns = getattr(inst, 'pin_connections', {}) or {}
                    for pin, net_name in pin_conns.items():
                        if net_name:
                            net_pins[net_name].append((refdes, pin))

        # ── Compute ID counters ─────────────────────────────────────
        total_instances: int = 0
        total_nets: int = 0
        total_inst_terms: int = 0
        if design_ir is not None:
            total_instances = sum(len(p.instances) for p in design_ir.pages)
            total_nets = len(net_pins)
            total_inst_terms = sum(len(pins) for pins in net_pins.values())

        a("(")
        a("  (version 16.6)")
        a("  (tool")
        a('    (creator "conceptHDL")')
        a('    (last "conceptHDL")')
        a("  )")
        a(f'  (library "{library_alias}")')
        a(f'  (design "{cell_name}"')
        a("    (lastIds")
        a(f"      (lastInstanceId {total_instances})")
        a(f"      (lastNetId {total_nets})")
        a(f"      (lastInstTermId {total_inst_terms})")
        a("    )")

        # ── Build lookup from source_library_id → target cell name ──
        match_cell_lookup: dict[str, str] = {}
        if match_map is not None:
            for m in match_map:
                sid = getattr(m, 'source_library_id', '')
                tid = getattr(m, 'target_library_id', '')
                if sid and tid:
                    cell = tid.rsplit('/', 1)[-1] if '/' in tid else tid
                    match_cell_lookup[sid] = cell

        # ── Cells section — referenced HDL cells ────────────────────
        a("    (cells")
        if design_ir is not None:
            cells_seen: set[str] = set()
            for page in design_ir.pages:
                for inst in page.instances:
                    lib_id = getattr(inst, 'library_id', '')
                    # Resolve actual cell name from match lookup
                    cell = match_cell_lookup.get(lib_id, '')
                    if not cell:
                        cell = lib_id.rsplit('/', 1)[-1] if '/' in lib_id else lib_id
                    if cell and cell not in cells_seen and len(cell) > 2:
                        cells_seen.add(cell)
                        a(f'      (cell "{cell}")')
        a("    )")

        # ── Nets section — connectivity from pin_connections ─────────
        a("    (nets")
        if design_ir is not None:
            for net_name, pins in sorted(net_pins.items()):
                a(f'      (net "{net_name}"')
                for refdes, pin in pins:
                    a(f'        (instTerm (refdes "{refdes}") (pin "{pin}"))')
                a("      )")
        a("    )")

        # ── Alias section ────────────────────────────────────────────
        a("    (alias")
        a("    )")

        # ── Instances section — component placement ──────────────────
        a("    (instances")
        if design_ir is not None:
            for page in design_ir.pages:
                for inst in page.instances:
                    refdes = getattr(inst, 'refdes', '?')
                    lib_id = getattr(inst, 'library_id', '')
                    # Resolve cell name from match lookup (same as cells)
                    cell = match_cell_lookup.get(lib_id, '')
                    if not cell:
                        cell = lib_id.rsplit('/', 1)[-1] if '/' in lib_id else lib_id
                    loc_x = getattr(inst, 'loc_x', 0)
                    loc_y = getattr(inst, 'loc_y', 0)
                    rotation_raw = getattr(inst, 'rotation', 0) or 0
                    rotation_str = f"R{rotation_raw}"
                    a(
                        f'      (instance (refdes "{refdes}")'
                        f' (cell "{cell}")'
                        f' (loc "{loc_x} {loc_y}")'
                        f' (rotation "{rotation_str}"))'
                    )
        a("    )")
        a("  )")
        a(")")
        return "\n".join(lines) + "\n"

    # ------------------------------------------------------------------
    #  module_order.dat
    # ------------------------------------------------------------------

    def write_module_order(
        self,
        library: Optional[str] = None,
        cell: Optional[str] = None,
        view: Optional[str] = None,
    ) -> Path:
        """Generate and write the module_order.dat file.

        Written to worklib/<cell>/sch_1/module_order.dat

        Reference format:
            Version 15.0
            START_MODULEORDER
            @\\<library>\\.\\<cell>\\(<view>)	0	1	1	3	0
            END_MODULEORDER

        Args:
            library: Library name (defaults to library_alias).
            cell: Cell name (defaults to cell_name).
            view: View name (defaults to "sch_1").

        Returns:
            Path to the written module_order.dat file.
        """
        if library is None:
            library = self.library_alias
        if cell is None:
            cell = self.cell_name
        if view is None:
            view = cfg.output.view_name

        content: str = self._build_module_order_content(library, cell, view)
        self.sch_dir.mkdir(parents=True, exist_ok=True)
        mo_path: Path = self.sch_dir / "module_order.dat"
        self._write_worklib_file(mo_path, content, encoding=cfg.app.output_encoding)
        logger.info("Wrote module_order.dat: %s", mo_path)
        return mo_path

    @staticmethod
    def _build_module_order_content(
        library: str, cell: str, view: str,
    ) -> str:
        """Build module_order.dat content.

        Reference format (C.4b, 04p4 evidence):
            Version 15.0
            START_MODULEORDER
            @\\<library>\\.\\<cell>\\(<view>)	0	1	1	3	0
            END_MODULEORDER

        The library/cell/view tokens are backslash-escaped with the DEHDL
        ``\\.\\`` separator and the final field is ``3`` (not ``2``).
        """
        lines: list[str] = [
            "Version 15.0",
            "START_MODULEORDER",
            f"@\\{library}\\.\\{cell}\\({view})\t0\t1\t1\t3\t0\t",
            "END_MODULEORDER",
        ]
        return "\n".join(lines) + "\n"

    # ------------------------------------------------------------------
    #  .dcf design constraint file
    # ------------------------------------------------------------------

    def write_dcf(
        self,
        cell_name: Optional[str] = None,
        dcf_version: str = "16.6",
    ) -> Path:
        """Generate and write the .dcf design constraint file.

        Written to worklib/<cell>/sch_1/<cell_name>.dcf

        The .dcf (Design Constraint File) uses S-expression format and is
        required by Cadence DEHDL Packager and Constraint Manager.

        Reference format (from out_hdl.dcf):
            ( ConstraintFile "out_hdl"
              ( constraintHeader
                ( objectKey ( logical ) )
                ( version ( 16.6 ) )
                ...
              )
              ( DictionaryExtensions ... )
              ( designConstraints ... )
            )

        Args:
            cell_name: Cell short name (defaults to self.cell_name).
            dcf_version: DCF version string (defaults to "16.6").

        Returns:
            Path to the written .dcf file.
        """
        if cell_name is None:
            cell_name = self.cell_name

        content: str = self._build_dcf_content(cell_name, dcf_version)
        self.sch_dir.mkdir(parents=True, exist_ok=True)
        dcf_path: Path = self.sch_dir / f"{cell_name}.dcf"
        self._write_worklib_file(dcf_path, content, encoding=cfg.app.output_encoding)
        logger.info("Wrote .dcf: %s", dcf_path)
        return dcf_path

    @staticmethod
    def _build_dcf_content(cell_name: str, dcf_version: str = "16.6") -> str:
        """Build .dcf file content in Cadence S-expression format."""
        lines: list[str] = []
        a = lines.append

        a(f'( ConstraintFile "{cell_name}"')
        a("  ( constraintHeader")
        a("    ( objectKey")
        a("      ( logical )")
        a("    )")
        a("    ( version")
        a(f"      ( {dcf_version} )")
        a("    )")
        a("    ( revisionNumber")
        a("      ( logicalViewRevNum 0 )")
        a("      ( physicalViewRevNum 0 )")
        a("      ( otherViewRevNum 0 )")
        a("    )")
        a("    ( contents")
        a("      ( dictionaryExtensions )")
        a("      ( worksheetCustomizations )")
        a("      ( electricalConstraints )")
        a("      ( netClasses )")
        a("      ( properties )")
        a("    )")
        a("    ( precision")
        a('      ( units mil )')
        a("      ( numberOfDecimalPlaces 2 )")
        a("    )")
        a("  )")
        a("  ( DictionaryExtensions )")
        a("  ( designConstraints")
        a("    ( ruleChanges")
        a("      ( allRules )")
        a(f'      ( design "{cell_name}" )')
        a("    )")
        a("  )")
        a(")")

        return "\n".join(lines) + "\n"

    # ------------------------------------------------------------------
    #  .xcon XML schema file
    # ------------------------------------------------------------------

    def write_xcon(
        self,
        cell_name: Optional[str] = None,
        library_alias: Optional[str] = None,
        num_pages: int = 1,
        content_override: Optional[str] = None,
    ) -> Path:
        """Generate and write the .xcon Cadence CS Schema XML file.

        Written to worklib/<cell>/sch_1/<cell_name>.xcon

        The .xcon file is required by Cadence Concept HDL to define the
        schematic structure — pages, nets, instances, etc.

        Args:
            cell_name: Cell short name (defaults to self.cell_name).
            library_alias: Library alias (defaults to self.library_alias).
            num_pages: Number of schematic pages.
            content_override: Pre-built .xcon content (XconWriter) —
                **Phase XXII D6/Q6: 强制必填**（XconWriter 是唯一内容源）。

        Returns:
            Path to the written .xcon file.

        Raises:
            ValueError: 当 ``content_override`` 为 None —— xcon 内容必须
                来自 XconWriter（单一内容源，Q6）；output_manager 只写文件。
        """
        if cell_name is None:
            cell_name = self.cell_name
        if library_alias is None:
            library_alias = self.library_alias

        if content_override is None:
            raise ValueError(
                "xcon content must come from XconWriter (single content source)"
            )
        content = content_override
        self.sch_dir.mkdir(parents=True, exist_ok=True)
        xcon_path: Path = self.sch_dir / f"{cell_name}.xcon"
        self._write_worklib_file(xcon_path, content, encoding=cfg.app.output_encoding)
        logger.info("Wrote .xcon: %s", xcon_path)
        return xcon_path

    # ------------------------------------------------------------------
    #  page.map — hierarchy viewer display names
    # ------------------------------------------------------------------

    def write_page_map(
        self,
        pages: Optional[list] = None,
        page_name: str = "DDR3",
        num_pages: int = 1,
    ) -> Path:
        """Write page.map for hierarchy viewer display names.

        Reference format (from worklib/out_hdl/sch_1/page.map)::

            1 1 DDR3

        Format: ``<page_number> <tab_index> <display_name>``

        When ``pages`` (list of PageIR) is provided, the page name comes
        from ``page.page_name`` (e.g. "01-Cover_Page").  If empty, falls
        back to the ``page_id``.

        Args:
            pages: Optional list of PageIR objects with page_name/page_id.
            page_name: Fallback page name (used when pages is None/empty).
            num_pages: Number of pages (used when pages is None).

        Returns:
            Path to the written page.map file.
        """
        self.sch_dir.mkdir(parents=True, exist_ok=True)

        if pages:
            # Collect (real_page_number, display_name) then sort by page
            # number so DEHDL's hierarchy viewer lists sheets in physical
            # order (01..24).  The tab index is the ordinal after sorting —
            # matching reference page.map files (zx279125).
            entries: list[tuple[int, str]] = []
            for page in pages:
                display_name: str = getattr(page, 'page_name', '') or "PAGE"
                # Real physical page number from the page name prefix
                # (e.g. "01-Cover_Page" → 1, "10-SOC_SerDes" → 10).
                # EDIF page blocks are ordered 01..24; page_id ("1.1"..)
                # is the internal index, NOT the sheet number shown in the
                # title block, so we extract it from the page name.
                page_num = _extract_page_number(page)
                entries.append((page_num, display_name))
            entries.sort(key=lambda e: e[0])
            lines = [f"{num} {tab} {name}" for tab, (num, name) in
                     enumerate(entries, start=1)]
            content: str = "\n".join(lines) + "\n"
        else:
            # Legacy fallback: single line
            content = f"1 {num_pages} {page_name}\n"

        page_map_path: Path = self.sch_dir / "page.map"
        self._write_worklib_file(page_map_path, content, encoding=cfg.app.output_encoding)
        logger.debug("Wrote page.map: %s", page_map_path)
        return page_map_path

    # ------------------------------------------------------------------
    #  .cpc — cell property files
    # ------------------------------------------------------------------

    def write_cpc_file(
        self, page_id: int, content: Optional[str] = None,
    ) -> Path:
        """Write a .cpc cell property file for a given page.

        Reference .cpc format (from worklib/out_hdl/sch_1/page1.cpc)::

            #ISCELL
              hdl_lib c#20size#20page *
              *

        The ``#20`` is the hex-encoded space character used in
        Cadence DEHDL property file format.

        Args:
            page_id: Page number (1-based).
            content: Optional pre-built .cpc content (CpcWriter).  When
                None, the legacy page-frame-only placeholder is written.

        Returns:
            Path to the written .cpc file.
        """
        self.sch_dir.mkdir(parents=True, exist_ok=True)
        if content is None:
            content = (
                "#ISCELL\n"
                "  hdl_lib c#20size#20page *\n"
                "  *\n"
            )
        cpc_path: Path = self.sch_dir / f"page{page_id}.cpc"
        self._write_worklib_file(cpc_path, content, encoding=cfg.app.output_encoding)
        logger.debug("Wrote .cpc: %s", cpc_path)
        return cpc_path

    # ------------------------------------------------------------------
    #  pageN.csv — DEHDL page connectivity files
    # ------------------------------------------------------------------

    def write_csv_page(self, page_num: int, content: str) -> Path:
        """Write a pageN.csv page connectivity file.

        Args:
            page_num: Page number (1-based).
            content: Full .csv CONNECTIVITY content (PageCsvWriter).

        Returns:
            Path to the written .csv file.
        """
        self.sch_dir.mkdir(parents=True, exist_ok=True)
        csv_path: Path = self.sch_dir / f"page{page_num}.csv"
        self._write_worklib_file(csv_path, content, encoding=cfg.app.output_encoding)
        logger.debug("Wrote .csv: %s", csv_path)
        return csv_path

    def write_all_cpc_files(self, num_pages: int) -> list[Path]:
        """Write .cpc files for all pages.

        Args:
            num_pages: Total number of pages.

        Returns:
            List of written .cpc file paths.
        """
        files: list[Path] = []
        for n in range(1, num_pages + 1):
            files.append(self.write_cpc_file(n))
        return files

    # ------------------------------------------------------------------
    #  Legacy API (backward compatibility)
    # ------------------------------------------------------------------

    def write_placeholder_files(
        self,
        page_name: str = "DDR3",
        num_pages: int = 1,
    ) -> list[Path]:
        """Create DEHDL-required placeholder files.

        **DEPRECATED** — use ``write_page_map()``, ``_write_master_tag()``,
        and ``write_all_cpc_files()`` directly.

        Creates:
            - worklib/<cell>/sch_1/master.tag
            - worklib/<cell>/sch_1/page.map

        Args:
            page_name: Page name for page.map (default: "DDR3").
            num_pages: Number of pages (default: 1).

        Returns:
            List of written file paths.
        """
        files: list[Path] = []
        files.append(self._write_master_tag(num_pages))
        files.append(self.write_page_map(page_name=page_name, num_pages=num_pages))
        return files

    # ------------------------------------------------------------------
    #  Project-level files
    # ------------------------------------------------------------------

    def write_cpm(self) -> Path:
        """Generate and write the .cpm Project Manager file.

        Written to output_root/<cell_name>.cpm

        Returns:
            Path to the .cpm file.
        """
        content: str = self._build_cpm_content()
        cpm_path: Path = self.output_root / f"{self.cell_name}.cpm"
        self.output_root.mkdir(parents=True, exist_ok=True)
        self._write_root_file(cpm_path, content, encoding=cfg.app.output_encoding)
        logger.info("Wrote .cpm: %s", cpm_path)
        return cpm_path

    def _build_cpm_content(self) -> str:
        """Build the .cpm file content matching Cadence DEHDL format.

        Reference format (from out_hdl.cpm):
            { Machine generated file created by SPI }
            { Last modified was 13:54:33 Saturday, July 04, 2026 }
            { NOTE: Do not modify the contents of this file. If this is regenerated by }
            {       SPI, your modifications will be overwritten. }

            START_GLOBAL
            design_name 'out_hdl'
            design_library 'out_hdl_lib'
            library 'hdl_lib' 'out_hdl_lib'
            temp_dir 'temp'
            cpm_version '16.6'
            session_name 'ProjectMgr3606'
            END_GLOBAL
        """
        lines: list[str] = []
        nl = lines.append

        now: datetime = datetime.now()
        timestamp: str = now.strftime("%H:%M:%S %A, %B %d, %Y")

        nl("{ Machine generated file created by SPI }")
        nl(f"{{ Last modified was {timestamp} }}")
        nl("{ NOTE: Do not modify the contents of this file. If this is regenerated by }")
        nl("{       SPI, your modifications will be overwritten. }")
        nl("")
        nl("")
        nl("START_GLOBAL")
        nl(f"design_name '{self.cell_name}'")
        nl(f"design_library '{self.library_alias}'")
        nl(f"library 'hdl_lib' '{self.library_alias}'")
        nl(f"temp_dir '{cfg.output.temp_dir}'")
        nl(f"cpm_version '{cfg.output.cpm_version}'")
        nl("session_name 'ProjectMgr3606'")
        nl("END_GLOBAL")
        nl("")
        nl("START_CONCEPTHDL")
        nl("PAGE_NAME_PROP 'EDIT PAGE NAME'")
        nl("END_CONCEPTHDL")
        nl("")
        nl("START_PKGRXL")
        nl("feedback 'ALLEGRO'")
        nl("electrical_constraints 'ON'")
        nl("b2f_overwrite_constraints 'OFF'")
        nl("import_constraints_only_feedback 'OFF'")
        nl("END_PKGRXL")
        nl("")
        nl("START_DESIGNSYNC")
        nl("last_board_file ''")
        nl("run_feedback 'YES'")
        nl("run_genfeedformat 'YES'")
        nl("backannotate_feedback 'YES'")
        nl("show_report 'NO'")
        nl("END_DESIGNSYNC")
        nl("")
        nl("START_CONSTRAINT_MGR")
        nl("EDIT_PHYSICAL_SPACING_CONSTRAINTS 'ON'")
        nl("END_CONSTRAINT_MGR")

        return "\n".join(lines) + "\n"

    def write_cdslib(self) -> Path:
        """Generate and write the cds.lib library definition file.

        Written to output_root/cds.lib

        Reference format (from 8367 cds.lib):
            DEFINE 8367_lib ./worklib
            INCLUDE $CONCEPT_INST_DIR/share/cdssetup/cds.lib
            DEFINE hdl_lib ./hdl_lib

        Returns:
            Path to the cds.lib file.
        """
        lines: list[str] = []
        nl = lines.append

        nl(f"DEFINE {self.library_alias} {cfg.output.worklib_dir}")
        nl("INCLUDE $CONCEPT_INST_DIR/share/cdssetup/cds.lib")
        nl(f"DEFINE hdl_lib {cfg.output.hdl_lib_dir}")
        # Phase XVIII R4 补丁（SPCOCN-515 ORIGIN.SYM.1.1 缺失）：Cadence
        # 打开带 part_table 的符号（如 CAPACITOR）时隐式解析 ORIGIN.SYM.1.1
        # （参考库 Standard 符号），用户环境缺该系统库 → 报 "parts missing:
        # ORIGIN.SYM.1.1"。输出包**自包含**：创建最小 origin 库并 DEFINE，
        # 使任何符号解析 ORIGIN.SYM.1.1 都能命中（不再依赖用户系统库）。
        nl("DEFINE origin origin")
        # Phase XVII M1 (QA P1-2 修复): mock 模拟图标写在独立
        # output/temp_lib/，其 CSA 块 CDS_LIB 指向 temp_lib —— 此处补
        # DEFINE 让 Cadence 解析到该库（相对路径不带 ./，与 hdl_lib
        # 行一致；e2e test_verify_fixes 断言 DEFINE 行无 ./）。
        # temp_lib 关闭时省略（无引用）。
        if getattr(getattr(cfg, "routing", None), "temp_lib", None) is not None:
            if cfg.routing.temp_lib.enabled:
                _tl = cfg.routing.temp_lib.lib_name
                nl(f"DEFINE {_tl} {_tl}")

        content: str = "\n".join(lines) + "\n"
        cdslib_path: Path = self.output_root / "cds.lib"
        self.output_root.mkdir(parents=True, exist_ok=True)
        self._write_root_file(cdslib_path, content, encoding=cfg.app.output_encoding)
        logger.info("Wrote cds.lib: %s", cdslib_path)
        return cdslib_path

    def write_hdldirect_dat(self, cell_name: Optional[str] = None) -> Path:
        """Generate and write the hdldirect.dat file.

        Written to output_root/hdldirect.dat

        Reference format (Lisp S-expression):
            (HDLDirect
              (Version 16.6)
              (Design "CELL_NAME")
            )

        Args:
            cell_name: Cell short name (defaults to self.cell_name).

        Returns:
            Path to the hdldirect.dat file.
        """
        if cell_name is None:
            cell_name = self.cell_name

        lines: list[str] = [
            "(HDLDirect",
            "  (Version 16.6)",
            f'  (Design "{cell_name}")',
            ")",
        ]
        content: str = "\n".join(lines) + "\n"
        hdldirect_path: Path = self.output_root / "hdldirect.dat"
        self.output_root.mkdir(parents=True, exist_ok=True)
        self._write_root_file(hdldirect_path, content, encoding=cfg.app.output_encoding)
        logger.info("Wrote hdldirect.dat: %s", hdldirect_path)
        return hdldirect_path

    # ------------------------------------------------------------------
    #  Convenience: generate everything
    # ------------------------------------------------------------------

    def generate_all_project_files(self) -> list[Path]:
        """Generate all project-level files (.cpm, cds.lib, hdldirect.dat).

        Returns:
            List of generated file paths.
        """
        files: list[Path] = []
        files.append(self.write_cpm())
        files.append(self.write_cdslib())
        files.append(self.write_hdldirect_dat())
        files.append(self.write_origin_lib())
        return files

    def write_origin_lib(self) -> Path:
        """Write a minimal self-contained ``origin`` library (SPCOCN-515).

        Cadence 打开带 part_table 的符号（CAPACITOR 等）时隐式解析
        ``ORIGIN.SYM.1.1``（参考库 Standard 符号）；用户环境缺该系统库
        时双击元件报 "parts missing: ORIGIN.SYM.1.1"。此处生成最小
        origin 符号（outline + PATH 属性，无引脚），配合 cds.lib
        ``DEFINE origin origin`` 使解析自包含。

        Returns:
            Path to the origin library sym_1/symbol.css.
        """
        origin_dir: Path = self.output_root / "origin" / "sym_1"
        origin_dir.mkdir(parents=True, exist_ok=True)
        css = (
            'P "CDS_LMAN_SYM_OUTLINE" "-25,25,25,-25" 0 0 0.00 0.00 22 0 0 0 0 0 0 0 0\n'
            "L -25 25 25 25 -1 0\n"
            "L 25 25 25 -25 -1 0\n"
            "L 25 -25 -25 -25 -1 0\n"
            "L -25 -25 -25 25 -1 0\n"
            'P "$LOCATION" "?" 0 -30 0 0 40 0 0 1 0 0 1 0 0\n'
            'P "PATH" "?" 0 0 0 0 48 0 0 0 0 0 0 0 32\n'
        )
        css_path = origin_dir / "symbol.css"
        css_path.write_text(css, encoding=cfg.app.output_encoding)
        (origin_dir / "master.tag").write_text(
            "sym_1=symbol.css\n", encoding=cfg.app.output_encoding)
        logger.info("Wrote self-contained origin library: %s", css_path)
        return css_path

    def generate_all_cell_files(
        self,
        cell_name: Optional[str] = None,
        library_alias: Optional[str] = None,
        page_name: str = "DDR3",
        num_pages: int = 1,
        design_ir=None,
        match_map=None,
    ) -> list[Path]:
        """Generate all cell-level support files.

        Creates: .con, .dcf, module_order.dat, master.tag, page.map,
        and per-page .cpc files.

        Phase XXII D6/Q6：**不再生成 .xcon** —— 真实管线 .xcon 由
        ``XconWriter.write_with_manager`` 产出（唯一内容源）；
        master.tag 仍列出 .xcon（由转换引擎随后写入，见
        ``_write_master_tag`` 注释）。本方法仅测试/兼容用，标记
        deprecation warning。

        Args:
            cell_name: Cell short name (defaults to self.cell_name).
            library_alias: Library alias (defaults to self.library_alias).
            page_name: Fallback page name for page.map.
            num_pages: Number of pages.
            design_ir: Optional DesignIR for populating .con nets/instances
                       and for generating per-page page.map entries.
            match_map: Optional match map for HDL cell resolution.

        Returns:
            List of generated file paths.
        """
        import warnings

        warnings.warn(
            "generate_all_cell_files is deprecated for .xcon: use "
            "XconWriter.write_with_manager (single content source, Q6)",
            DeprecationWarning,
            stacklevel=2,
        )
        files: list[Path] = []
        files.append(self.write_con_file(cell_name, library_alias,
                                         design_ir=design_ir,
                                         match_map=match_map))
        files.append(self.write_dcf(cell_name or self.cell_name))
        files.append(self.write_module_order(library_alias or self.library_alias,
                                              cell_name or self.cell_name))

        # ── page.map — use DesignIR pages for per-page entries ───────
        pages: Optional[list] = None
        if design_ir is not None:
            pages = getattr(design_ir, 'pages', None)
        files.append(self.write_page_map(
            pages=pages, page_name=page_name, num_pages=num_pages,
        ))

        # ── master.tag ───────────────────────────────────────────────
        files.append(self._write_master_tag(num_pages))

        # ── Per-page .cpc files ──────────────────────────────────────
        files.extend(self.write_all_cpc_files(num_pages))

        return files

    def _write_master_tag(self, num_pages: int = 1) -> Path:
        """Write master.tag — DEHDL file list.

        Format (C.4b, 04p4 evidence): one .csa per page, then .xcon and
        .dcf.  **.cpc files are NOT listed** (04p4 master.tag omits them).

        Args:
            num_pages: Number of schematic pages.

        Returns:
            Path to the written master.tag file.
        """
        self.sch_dir.mkdir(parents=True, exist_ok=True)
        master_tag_path: Path = self.sch_dir / "master.tag"
        tag_lines: list[str] = []
        for n in range(1, num_pages + 1):
            tag_lines.append(f"page{n}.csa")
        tag_lines.append(f"{self.cell_name}.xcon")
        tag_lines.append(f"{self.cell_name}.dcf")
        self._write_worklib_file(
            master_tag_path,
            "\n".join(tag_lines) + "\n",
            encoding=cfg.app.output_encoding,
        )
        logger.debug("Wrote master.tag: %s", master_tag_path)
        return master_tag_path
