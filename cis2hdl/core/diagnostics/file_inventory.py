"""FileInventory and DSNInternalInventoryBuilder (D1.1 + D1.2).

FileInventory: scans user-supplied files, classifies them by type, validates magic bytes.
DSNInternalInventoryBuilder: opens a .dsn CFB container and extracts internal structure.
"""

from __future__ import annotations

import logging
from pathlib import Path

from .diagnostic_report import (
    FileState,
    FileStatus,
    ProjectInventory,
    DSNInternalInventory,
    DiagnosisError,
    Severity,
    ActionItem,
    ActionVerb,
)

logger = logging.getLogger(__name__)

# ── Known file types and their magic bytes ─────────────────────────────────

# OLE/CFB magic
OLE_MAGIC = bytes([0xD0, 0xCF, 0x11, 0xE0, 0xA1, 0xB1, 0x1A, 0xE1])

# EDIF magic (first line should contain "edif")
EDIF_MAGIC_HINT = b"(edif"

FILE_TYPE_MAP: dict[str, str] = {
    ".dsn": "DSN",
    ".olb": "OLB",
    ".opj": "OPJ",
    ".edf": "EDF",
    ".dbk": "DBK",
    ".dat": "UNKNOWN",  # pstx files have .dat extension
    ".sim": "SIM",
    ".cir": "CIR",
    ".net": "NET",
}


def _classify_file(path: Path) -> str:
    """Determine file type from extension or content."""
    suffix = path.suffix.lower()
    if suffix in FILE_TYPE_MAP:
        return FILE_TYPE_MAP[suffix]

    # Special detection for pstx files by filename pattern
    name = path.name.lower()
    if "pstxnet" in name:
        return "PSTXNET"
    if "pstxprt" in name:
        return "PSTXPRT"
    if "pstchip" in name:
        return "PSTCHIP"

    return "UNKNOWN"


def _is_cfb_file(path: Path) -> bool:
    """Check if file starts with OLE/CFB magic bytes."""
    try:
        with open(path, "rb") as f:
            head = f.read(8)
        return head == OLE_MAGIC
    except (OSError, PermissionError):
        return False


def _is_edif_file(path: Path) -> bool:
    """Check if file looks like EDIF (text starting with (edif)."""
    try:
        with open(path, "rb") as f:
            head = f.read(256)
        return EDIF_MAGIC_HINT in head.lower()
    except (OSError, PermissionError):
        return False


# ── FileInventory (D1.1) ───────────────────────────────────────────────────


class FileInventory:
    """Scan a set of user-provided files and build ProjectInventory.

    Usage:
        inventory_builder = FileInventory()
        inventory = inventory_builder.scan([Path("project.dsn"), Path("lib.olb")])
    """

    def scan(self, files: list[Path], project_root: Path | None = None) -> ProjectInventory:
        """Scan all provided files and classify them.

        Args:
            files: List of file paths provided by user.
            project_root: Optional project root directory for relative path display.

        Returns:
            Populated ProjectInventory with per-file status.
        """
        root = project_root or Path(".")
        inventory = ProjectInventory(project_root=root)

        # ── Classify each file ─────────────────────────────────────
        for fpath in files:
            # Skip directories
            if fpath.is_dir():
                continue

            if not fpath.exists():
                status = FileStatus(
                    path=fpath,
                    file_type=_classify_file(fpath),
                    state=FileState.MISSING,
                    summary=f"文件不存在: {fpath}",
                )
                inventory.files[str(fpath)] = status
                continue

            size = fpath.stat().st_size if fpath.is_file() else 0

            if size == 0:
                inventory.files[str(fpath)] = FileStatus(
                    path=fpath,
                    file_type=_classify_file(fpath),
                    state=FileState.CORRUPTED,
                    size=0,
                    summary="文件为空 (0 bytes)",
                )
                continue

            # Validate format
            file_type = _classify_file(fpath)

            if file_type in ("DSN", "OLB", "DBK"):
                # Must be CFB
                if _is_cfb_file(fpath):
                    inventory.files[str(fpath)] = FileStatus(
                        path=fpath,
                        file_type=file_type,
                        state=FileState.FOUND_OK,
                        size=size,
                        summary=f"{file_type} CFB container, {size:,} bytes",
                        data_quality=0.9,  # Will be refined by DSN parser
                    )
                else:
                    inventory.files[str(fpath)] = FileStatus(
                        path=fpath,
                        file_type=file_type,
                        state=FileState.BAD_FORMAT,
                        size=size,
                        summary=f"不是有效的 {file_type} CFB 文件（无效魔数）",
                        detail=f"期望: {OLE_MAGIC.hex(' ')}",
                    )
                    inventory.errors.append(
                        DiagnosisError(
                            code=2,
                            severity=Severity.ERROR,
                            category="FILE",
                            message=f"{file_type} 文件头损坏（无效魔数）",
                            source_file=str(fpath),
                            suggestion="文件可能已损坏，请尝试从 .dbk 备份恢复",
                            can_ignore=False,
                        )
                    )

            elif file_type in ("EDF",):
                if _is_edif_file(fpath) or fpath.suffix.lower() == ".edf":
                    inventory.files[str(fpath)] = FileStatus(
                        path=fpath,
                        file_type=file_type,
                        state=FileState.FOUND_OK,
                        size=size,
                        summary=f"EDIF text file, {size:,} bytes",
                        data_quality=0.95,
                    )
                else:
                    inventory.files[str(fpath)] = FileStatus(
                        path=fpath,
                        file_type=file_type,
                        state=FileState.BAD_FORMAT,
                        size=size,
                        summary="不是有效的 EDIF 文件",
                    )

            elif file_type in ("PSTXNET", "PSTXPRT", "PSTCHIP"):
                # Text netlist files — validate by content
                inventory.files[str(fpath)] = FileStatus(
                    path=fpath,
                    file_type=file_type,
                    state=FileState.FOUND_OK,
                    size=size,
                    summary=f"{file_type} netlist, {size:,} bytes",
                    data_quality=0.8,
                )

            else:
                # Unknown/other — accept as-is
                inventory.files[str(fpath)] = FileStatus(
                    path=fpath,
                    file_type=file_type,
                    state=FileState.FOUND_OK,
                    size=size,
                    summary=f"{file_type} file, {size:,} bytes",
                    data_quality=0.5,
                )

        # ── Generate actions ────────────────────────────────────────
        self._generate_actions(inventory)
        return inventory

    def _generate_actions(self, inventory: ProjectInventory) -> None:
        """Generate user-actionable suggestions from file inventory."""
        has_dsn = any(
            f.file_type == "DSN" and f.state == FileState.FOUND_OK
            for f in inventory.files.values()
        )
        has_edf = any(
            f.file_type == "EDF" and f.state == FileState.FOUND_OK
            for f in inventory.files.values()
        )
        has_olb = any(
            f.file_type == "OLB" and f.state == FileState.FOUND_OK
            for f in inventory.files.values()
        )

        if not has_dsn:
            inventory.actions.append(
                ActionItem(
                    verb=ActionVerb.PROVIDE,
                    target="*.dsn 文件",
                    reason="DSN 是原理图主文件，转换的必要输入",
                    priority=0,
                )
            )

        if not has_edf:
            inventory.actions.append(
                ActionItem(
                    verb=ActionVerb.UPLOAD,
                    target="*.edf 文件",
                    reason="EDIF 可用于交叉验证 DSN 解析结果的正确性",
                    priority=1,
                )
            )

        if not has_olb:
            inventory.actions.append(
                ActionItem(
                    verb=ActionVerb.UPLOAD,
                    target="*.olb 器件库文件",
                    reason="OLB 库提供引脚名称和器件属性，可大幅提升匹配准确率",
                    priority=1,
                )
            )

        inventory.actions.append(
            ActionItem(
                verb=ActionVerb.UPLOAD,
                target="pstxnet.dat / pstxprt.dat / pstchip.dat",
                reason="PCB 网表文件可用于三路交叉验证",
                priority=2,
            )
        )


# ── DSNInternalInventoryBuilder (D1.2) ─────────────────────────────────────


class DSNInternalInventoryBuilder:
    """Open a DSN file and extract its internal structure inventory.

    Uses OleReader to inspect the CFB container and report on stream health.
    """

    def build(self, dsn_path: Path) -> DSNInternalInventory:
        """Build DSNInternalInventory from a .dsn file.

        Args:
            dsn_path: Path to the .dsn file.

        Returns:
            Populated DSNInternalInventory.
        """
        inv = DSNInternalInventory(dsn_path=str(dsn_path))

        try:
            from ..parser.dsn.ole_reader import OleReader, OlePathEntry
            from ..parser.dsn.page_parser import parse_page

            ole = OleReader(dsn_path)
            entries = ole.list_all_entries()

            # ── Stream presence ─────────────────────────────────
            entry_paths = [e.full_path for e in entries]
            inv.has_root = any("Root Entry" in p for p in entry_paths)
            inv.has_views = any("Views" in p for p in entry_paths)
            inv.has_pages = any("Pages" in p for p in entry_paths)
            inv.has_cache = any("Cache" in p for p in entry_paths)
            inv.has_library = any("Library" in p for p in entry_paths)
            inv.has_hierarchy = any("Hierarchy" in p for p in entry_paths)

            # ── Page stats ──────────────────────────────────────
            # v0.8.0: Filter to actual schematic pages (match \d{2}- naming
            # pattern like "05-Power_Supply1").  Internal CFB sub-streams
            # (PAGE1, VRTL, etc.) are NOT actual pages and should be excluded.
            import re as _re
            _PAGE_NAME_PATTERN = _re.compile(r'^\d{2}-')
            _all_streams = [
                e for e in entries
                if "Pages" in e.full_path and e.dir_type == 2
            ]
            page_entries = [
                e for e in _all_streams
                if _PAGE_NAME_PATTERN.match(e.name)
            ]
            # Fallback: if no entries match the pattern, use all streams
            # (compatible with DSN files using different naming conventions)
            if not page_entries:
                page_entries = _all_streams
            inv.total_pages = len(page_entries)

            for entry in page_entries:
                page_name = entry.full_path.split("/")[-1]
                try:
                    buffer = ole.read_stream_by_path(entry.full_path)
                    parse_page(buffer, page_name)
                    inv.page_details[page_name] = True
                except Exception:
                    inv.page_details[page_name] = False

            inv.pages_parsed = sum(1 for v in inv.page_details.values() if v)

            # ── Raw fallback for corrupted directory trees ──────
            # When the CFB directory tree has broken sibling/child pointers
            # (known OrCAD issue), list_all_entries() may miss page streams.
            # Here we fall back to scanning raw directory entries and matching
            # pages by common naming patterns — the same strategy used by
            # DSNParser._read_all_pages().
            if inv.total_pages == 0:
                logger.warning(
                    "No pages found via directory tree; "
                    "falling back to raw directory entry scan"
                )
                raw_entries = ole.list_raw_dir_entries()
                for raw_entry in raw_entries:
                    if raw_entry.dir_type != 2:  # stream only
                        continue

                    name_upper = raw_entry.name.upper()
                    # v0.8.0: Prefer \d{2}- naming pattern for schematic pages
                    # Phase XI T05: VRTL chip-package view streams
                    # (vRTL8367RB-...) carry no \d{2}- prefix — accept them
                    # as page candidates directly.
                    is_page_candidate = (
                        (name_upper.startswith("PAGE")
                         or "VRTL" in name_upper
                         or "Pages" in raw_entry.full_path)
                        and (
                            _PAGE_NAME_PATTERN.match(raw_entry.name)
                            or name_upper.startswith("VRTL")
                        )
                    )
                    # Fallback: if no pattern-matched candidates found, use
                    # all page-like streams
                    if not is_page_candidate:
                        continue

                    try:
                        buffer = ole.read_stream_from_entry(raw_entry)
                        parse_page(buffer, raw_entry.name)
                        inv.page_details[raw_entry.name] = True
                        inv.total_pages += 1
                        logger.info(
                            "Recovered page stream via raw entry: '%s' (%d bytes)",
                            raw_entry.name,
                            len(buffer),
                        )
                    except Exception:
                        inv.page_details[raw_entry.name] = False

                inv.pages_parsed = sum(1 for v in inv.page_details.values() if v)

            # ── Cache entries ───────────────────────────────────
            cache_entries = [e for e in entries if "Cache" in e.full_path and e.dir_type == 2]
            inv.cache_entries = len(cache_entries)

            # ── strLst entries ──────────────────────────────────
            try:
                if inv.has_library:
                    for e in entries:
                        if "strLst" in e.name or "Library" in e.full_path:
                            buf = ole.read_stream_by_path(e.full_path)
                            # Count string entries: each is a length-prefixed + NULL-terminated string
                            # Rough estimate: count NULL bytes as separator
                            inv.strlst_entries = buf.count(b"\x00") + 1
                            break
            except Exception:
                inv.strlst_entries = 0

        except Exception as exc:
            logger.warning("DSN internal inventory failed for %s: %s", dsn_path, exc)
            inv.strlst_entries = 0

        return inv
