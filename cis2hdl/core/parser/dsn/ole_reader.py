"""OleReader — MS-CFB 复合文件容器读取器（Binary DSN Parser Layer 1）。

基于 openOrCadParser / universal-netlist 的 OleReader 实现移植。
CFB（Compound File Binary）格式是 Microsoft OLE 结构化存储标准，
OrCAD Capture .dsn 文件即以此格式存储。

CFB 内部结构：
    Header (512B) → FAT 扇区分配表 → Directory Tree (128B/entry) → MiniFAT → MiniStream

参考：
    - openOrCadParser C++ implementation: Database.hpp
    - universal-netlist TypeScript: OleReader.ts
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from struct import unpack_from

logger = logging.getLogger(__name__)

# ── CFB 常量 ────────────────────────────────────────────────────────────

OLE_MAGIC = bytes([0xD0, 0xCF, 0x11, 0xE0, 0xA1, 0xB1, 0x1A, 0xE1])
HEADER_SIZE = 512
DIR_ENTRY_SIZE = 128
ENDOFCHAIN = 0xFFFFFFFE
FREESECT = 0xFFFFFFFF
NOSTREAM = 0xFFFFFFFF
MINI_STREAM_SECTOR_SIZE = 64
MINI_STREAM_CUTOFF_SIZE = 4096

# FAT 扇区大小
FAT_SECTOR_SIZE = 512

# Directory entry types
DIR_TYPE_EMPTY = 0
DIR_TYPE_STORAGE = 1
DIR_TYPE_STREAM = 2
DIR_TYPE_ROOT = 5

# ---------------------------------------------------------------------------


class CFBError(Exception):
    """CFB 格式解析错误。"""

    def __init__(self, message: str) -> None:
        super().__init__(f"CFB parse error: {message}")


@dataclass
class OlePathEntry:
    """OLE 容器路径条目。

    Attributes:
        name: Entry name (UTF-16LE decoded).
        full_path: Hierarchical path (e.g. 'Views/SCHEMATIC1/Pages/PAGE1').
        dir_type: CFB directory type (1=storage, 2=stream, 5=root).
        start_sector: First sector of data.
        stream_size: Stream data size in bytes.
    """

    name: str
    full_path: str
    dir_type: int
    start_sector: int
    stream_size: int


@dataclass
class _DirEntry:
    """Internal CFB directory entry (128 bytes)."""

    name: str
    dir_type: int
    start_sector: int
    stream_size: int
    left_sibling: int
    right_sibling: int
    child_id: int


class OleReader:
    """MS-CFB 复合文件读取器。

    构造时自动完成完整解析：头部→FAT→目录树→miniFAT→miniStream。

    使用方式:
        ole = OleReader(Path("project.dsn"))
        entries = ole.list_all_entries()
        data = ole.read_stream_by_path("Views/SCHEMATIC1/Pages/PAGE1")
    """

    def __init__(self, file_path: Path) -> None:
        self._buffer = file_path.read_bytes()
        self._validate_magic()
        self._parse_header()
        self._build_fat()
        self._read_directories()
        self._build_mini_fat()
        self._read_mini_stream()

    # ── Initialization ─────────────────────────────────────────────────

    def _validate_magic(self) -> None:
        """验证 CFB 文件魔数。"""
        if len(self._buffer) < 8:
            raise CFBError("File too small")
        if self._buffer[:8] != OLE_MAGIC:
            raise CFBError(
                f"Invalid OLE magic; expected {OLE_MAGIC.hex()}, "
                f"got {self._buffer[:8].hex()}"
            )

    def _parse_header(self) -> None:
        """解析 512 字节 CFB 头部。

        关键字段：
            0x18-0x1B: minor_version (2 bytes)
            0x1A-0x1B: dll_version (2 bytes) — byte order marker
            0x1C-0x1D: byte_order (0xFFFE = little-endian)
            0x1E-0x1F: sector_size_power
            0x20-0x21: mini_sector_size_power
            0x2C-0x2F: num_dir_sectors
            0x30-0x33: num_fat_sectors
            0x34-0x37: first_dir_sector
            0x38-0x3B: transaction_signature
            0x3C-0x3F: mini_stream_cutoff
            0x40-0x43: first_mini_fat_sector
            0x44-0x47: num_mini_fat_sectors
            0x48-0x4B: first_difat_sector
            0x4C-0x4F: num_difat_sectors
            0x4C-0x1FF: DIFAT[109] — initial FAT sector chain
        """
        self._sector_size = 1 << unpack_from("<H", self._buffer, 0x1E)[0]
        self._mini_sector_size = 1 << unpack_from("<H", self._buffer, 0x20)[0]
        self._num_dir_sectors = unpack_from("<I", self._buffer, 0x2C)[0]
        self._num_fat_sectors = unpack_from("<I", self._buffer, 0x30)[0]
        self._first_dir_sector = unpack_from("<I", self._buffer, 0x34)[0]
        self._mini_stream_cutoff = unpack_from("<I", self._buffer, 0x3C)[0]
        self._first_mini_fat_sector = unpack_from("<I", self._buffer, 0x40)[0]
        self._num_mini_fat_sectors = unpack_from("<I", self._buffer, 0x44)[0]
        self._first_difat_sector = unpack_from("<I", self._buffer, 0x48)[0]
        self._num_difat_sectors = unpack_from("<I", self._buffer, 0x4C)[0]

        # Read initial 109 DIFAT entries from header
        self._difat = list(
            unpack_from(f"<109I", self._buffer, 0x4C)
        )

        # Read additional DIFAT sectors if any
        if self._num_difat_sectors > 0:
            self._read_difat_sectors()

        # Build FAT sector chain — use actual DIFAT count, not header num_fat_sectors
        self._fat_chain: list[int] = []
        for sect in self._difat:
            if sect != FREESECT:
                self._fat_chain.append(int(sect))
        # Override num_fat_sectors with actual count (some DSN files have header mismatch)
        self._num_fat_sectors = len(self._fat_chain)

    def _read_difat_sectors(self) -> None:
        """读取额外的 DIFAT 扇区。

        DIFAT 扇区的最后 4 字节指向下一个 DIFAT 扇区。
        """
        current = self._first_difat_sector
        for _ in range(self._num_difat_sectors):
            if current == ENDOFCHAIN or current == FREESECT:
                break
            offset = (current + 1) * self._sector_size  # +1 for header sector
            entries_per_sector = self._sector_size // 4 - 1  # last entry is chain pointer
            for i in range(entries_per_sector):
                self._difat.append(
                    unpack_from("<I", self._buffer, offset + i * 4)[0]
                )
            # Last 4 bytes → next DIFAT sector
            current = unpack_from(
                "<I", self._buffer, offset + entries_per_sector * 4
            )[0]

    def _build_fat(self) -> None:
        """构建完整 FAT（文件分配表）。

        FAT 是 int32 数组，每个条目指向下一个扇区或结束标记。
        """
        fat_size = self._num_fat_sectors * (self._sector_size // 4)
        self._fat = [FREESECT] * fat_size

        idx: int = 0
        for fat_sector in self._fat_chain:
            offset = (fat_sector + 1) * self._sector_size
            entries = self._sector_size // 4
            for i in range(entries):
                if idx < fat_size:
                    val = unpack_from("<I", self._buffer, offset + i * 4)[0]
                    self._fat[idx] = int(val)
                idx += 1

    def _read_directories(self) -> None:
        """读取并解析 CFB 目录树。

        Handles OrCAD's CFB variant where the directory sector numbering
        may differ from standard (directory offset shifted by one sector).
        """
        # Try standard offset chain
        chain = self._get_sector_chain(self._first_dir_sector)
        dir_data = bytearray()
        for sect in chain:
            offset = (sect + 1) * self._sector_size
            dir_data.extend(self._buffer[offset : offset + self._sector_size])

        # Check if first entry looks like a valid Root Entry
        if not self._is_valid_root_entry(dir_data):
            # Try with +1 sector offset (OrCAD CFB variant)
            logger.debug("Directory not at standard offset; trying +1 sector")
            dir_data = bytearray()
            for sect in chain:
                offset = (sect + 2) * self._sector_size
                if offset + self._sector_size <= len(self._buffer):
                    dir_data.extend(self._buffer[offset : offset + self._sector_size])

            if not self._is_valid_root_entry(dir_data):
                raise CFBError(
                    "Cannot locate directory entries in CFB container — "
                    "unsupported CFB variant."
                )

        self._parse_dir_entries(dir_data)

    def _is_valid_root_entry(self, dir_data: bytes) -> bool:
        """Check if the first 128 bytes look like a valid Root Entry (type=5)."""
        if len(dir_data) < 128:
            return False
        # Root Entry has type=5 at offset 0x42
        dir_type = dir_data[0x42]
        if dir_type != 5:  # DIR_TYPE_ROOT
            # Also check if first byte is valid (might have minor offset)
            if dir_type not in (0, 1, 2, 5):
                return False
        # Name at offset 0 should be readable UTF-16LE
        name_len = int.from_bytes(dir_data[0x40:0x42], "little")
        if name_len == 0 or name_len > 64:
            return False
        try:
            name = dir_data[0:name_len].decode("utf-16-le", errors="strict")
            return len(name) > 0
        except UnicodeDecodeError:
            return False

    def _parse_dir_entries(self, dir_data: bytes) -> None:
        """Parse raw directory data into _DirEntry list.

        Args:
            dir_data: Raw directory sector data.
        """
        num_entries = len(dir_data) // DIR_ENTRY_SIZE
        entries: list[_DirEntry] = []
        for i in range(num_entries):
            pos = i * DIR_ENTRY_SIZE
            entry = self._parse_dir_entry(
                bytes(dir_data[pos : pos + DIR_ENTRY_SIZE])
            )
            entries.append(entry)

        self._dir_entries = entries

        # Build hierarchical paths (in-order RB tree traversal)
        self._entry_paths: list[OlePathEntry] = []
        self._visiting: set[int] = set()
        self._visit_depth = 0
        self._visit_dir(entries, 0, "", self._entry_paths)

    def _parse_dir_entry(self, raw: bytes) -> _DirEntry:
        """解析单个 128 字节目录条目。"""
        name_len = unpack_from("<H", raw, 0x40)[0]
        # Name is UTF-16LE encoded, up to 32 characters (64 bytes).
        # But in CFB, the name length is given in bytes, and
        # the field is padded to 0.
        name_raw = raw[0:name_len]
        name = name_raw.decode("utf-16-le", errors="replace").rstrip("\x00")

        dir_type = raw[0x42]
        start_sector = unpack_from("<I", raw, 0x74)[0]
        stream_size_low = unpack_from("<I", raw, 0x78)[0]
        # stream_size_high at 0x7C — unused for sizes < 4GB
        left_sibling = unpack_from("<i", raw, 0x44)[0]
        right_sibling = unpack_from("<i", raw, 0x48)[0]
        child_id = unpack_from("<i", raw, 0x4C)[0]

        return _DirEntry(
            name=name,
            dir_type=dir_type,
            start_sector=start_sector,
            stream_size=stream_size_low,
            left_sibling=left_sibling,
            right_sibling=right_sibling,
            child_id=child_id,
        )

    def _visit_dir(
        self,
        entries: list[_DirEntry],
        entry_id: int,
        parent_path: str,
        result: list[OlePathEntry],
    ) -> None:
        """递归访问目录树（Red-Black Tree 中序遍历）。

        CFB 的兄弟关系存储为 Red-Black Tree：
            left_sibling = 左子节点 (较小的)
            right_sibling = 右子节点 (较大的)
            child = 该节点的子节点树的根
        
        中序遍历: 左子树 → 当前节点 → 右子树
        """
        _visiting: set[int] = getattr(self, "_visiting", set())
        _depth: int = getattr(self, "_visit_depth", 0)

        if entry_id < 0 or entry_id >= len(entries):
            return
        if entry_id in _visiting or _depth > 500:
            return
        entry = entries[entry_id]
        if entry.dir_type == DIR_TYPE_EMPTY:
            return

        _visiting.add(entry_id)
        self._visit_depth = _depth + 1

        try:
            # If this entry has a left sibling (left child in RB tree), visit it first (inorder)
            self._visit_dir(entries, entry.left_sibling, parent_path, result)

            # Then visit this entry itself
            full_path = (
                parent_path + "/" + entry.name
                if parent_path
                else entry.name
            )
            result.append(
                OlePathEntry(
                    name=entry.name,
                    full_path=full_path,
                    dir_type=entry.dir_type,
                    start_sector=entry.start_sector,
                    stream_size=entry.stream_size,
                )
            )

            # Visit children of this entry
            child_path = full_path if entry.dir_type == DIR_TYPE_ROOT else full_path
            self._visit_dir(entries, entry.child_id, child_path, result)

            # Then visit right sibling (right child in RB tree)
            self._visit_dir(entries, entry.right_sibling, parent_path, result)
        finally:
            _visiting.discard(entry_id)
            self._visit_depth = _depth
        # Save visiting set for next call
        self._visiting = _visiting

    def _build_mini_fat(self) -> None:
        """构建 miniFAT（迷你扇区分配表）。"""
        if self._first_mini_fat_sector == FREESECT or self._first_mini_fat_sector == ENDOFCHAIN:
            self._mini_fat = []
            return
        chain = self._get_sector_chain(self._first_mini_fat_sector)
        mini_fat_data = bytearray()
        for sect in chain:
            offset = (sect + 1) * self._sector_size
            mini_fat_data.extend(
                self._buffer[offset : offset + self._sector_size]
            )

        num_entries = len(mini_fat_data) // 4
        self._mini_fat = list(
            unpack_from(f"<{num_entries}I", bytes(mini_fat_data))
        )

    def _read_mini_stream(self) -> None:
        """读取 mini stream 数据。

        Mini stream 位于根存储的常规流中，使用 miniFAT 扇区。
        """
        root_entry = self._dir_entries[0]
        chain = self._get_sector_chain(root_entry.start_sector)
        self._mini_stream = bytearray()
        for sect in chain:
            offset = (sect + 1) * self._sector_size
            self._mini_stream.extend(
                self._buffer[offset : offset + self._sector_size]
            )

    # ── Sector chains ──────────────────────────────────────────────────

    def _get_sector_chain(self, start_sector: int) -> list[int]:
        """从起始扇区遍历 FAT 链，返回所有扇区号。

        Handles OrCAD CFB variants:
        - 0xFFFFFFFD: contiguous sector marker (→ current + 1)
        - 0xFFFFFFFE: ENDOFCHAIN
        - 0xFFFFFFFF: FREESECT

        Args:
            start_sector: 起始扇区号。

        Returns:
            排序后的扇区号列表。
        """
        chain: list[int] = []
        current: int = start_sector
        seen: set[int] = set()
        max_iter = 10000  # safety limit

        for _ in range(max_iter):
            if current == ENDOFCHAIN or current == FREESECT:
                break
            if current < 0 or current >= len(self._fat):
                break
            if current in seen:
                break
            seen.add(current)
            chain.append(current)
            next_val = self._fat[current]
            if next_val == 0xFFFFFFFD:
                # OrCAD CFB variant: contiguous chain marker → next sector
                current += 1
            elif next_val >= 0xFFFFFFFE:
                current = ENDOFCHAIN
            else:
                current = next_val
        return chain

    def _get_mini_sector_chain(self, start_sector: int) -> list[int]:
        """遍历 miniFAT 链。"""
        chain: list[int] = []
        current: int = start_sector
        seen: set[int] = set()

        for _ in range(10000):
            if current == ENDOFCHAIN or current == FREESECT:
                break
            if current < 0 or current >= len(self._mini_fat):
                break
            if current in seen:
                break
            seen.add(current)
            chain.append(current)
            next_val = self._mini_fat[current]
            if next_val == 0xFFFFFFFD:
                current += 1
            elif next_val >= 0xFFFFFFFE:
                current = ENDOFCHAIN
            else:
                current = next_val
        return chain

    # ── Public API ─────────────────────────────────────────────────────

    def list_all_entries(self) -> list[OlePathEntry]:
        """返回容器中所有条目的完整层级路径列表。"""
        return list(self._entry_paths)

    def find_entries_by_name(self, name: str) -> list[OlePathEntry]:
        """按名称查找条目（扁平匹配，不区分大小写）。

        Args:
            name: 条目名称（如 'PAGE1'）。

        Returns:
            匹配的条目列表。
        """
        return [
            e for e in self._entry_paths
            if e.name.upper() == name.upper()
        ]

    def find_entries_by_path_pattern(self, pattern: str) -> list[OlePathEntry]:
        """按路径模式匹配条目。

        Args:
            pattern: 路径包含的模式（如 'Pages'）。

        Returns:
            匹配的条目列表。
        """
        return [
            e for e in self._entry_paths
            if pattern in e.full_path
        ]

    def list_raw_dir_entries(self) -> list[OlePathEntry]:
        """返回所有非空目录条目的原始数据，绕过 RB-tree 遍历。

        CFB 目录条目以 Red-Black Tree 结构组织。当部分条目的
        sibling/child 指针损坏时（OrCAD 已知问题），通过 RB-tree
        遍历会遗漏这些条目。本方法直接从原始目录数据中提取所有
        非空条目，不依赖树结构。

        Returns:
            所有非空目录条目的 OlePathEntry 列表。注意 full_path
            仅设置为条目名称本身（无法重建层级路径）。
        """
        result: list[OlePathEntry] = []
        for entry in self._dir_entries:
            if entry.dir_type == DIR_TYPE_EMPTY:
                continue
            if not entry.name:
                continue
            result.append(
                OlePathEntry(
                    name=entry.name,
                    full_path=entry.name,
                    dir_type=entry.dir_type,
                    start_sector=entry.start_sector,
                    stream_size=entry.stream_size,
                )
            )
        return result

    def count_page_candidates(self) -> int:
        """统计 raw entries 中潜在的页面流条目数。

        匹配规则（按优先级）：
        1. 以 "PAGE" 开头的流
        2. 名称包含 "VRTL" 的流（RTL8367RB 层次块页面命名模式）
        3. 以数字开头后跟连字符的流（如 "01-Cover_Page"、"02-Block_Diagram"）
           这是 OrCAD 页面命名惯例：页号-页面名
        4. 大小 > 2000 字节且不在已知系统流中的流

        Returns:
            潜在页面流条目数。
        """
        import re

        SYSTEM_NAMES: set[str] = {
            'Cache', 'Library', 'AdminData', 'DsnStream', 'HSObjects',
            'NetBundleMapData', 'Cells Directory', 'Parts Directory',
            'Views Directory', 'Symbols Directory', 'Graphics Directory',
            'Packages Directory', 'ExportBlocks Directory',
        }

        count: int = 0
        for entry in self._dir_entries:
            if entry.dir_type != DIR_TYPE_STREAM:
                continue
            if not entry.name:
                continue
            name_upper: str = entry.name.upper()

            # Rule 1: PAGE prefix
            if name_upper.startswith("PAGE"):
                count += 1
                continue
            # Rule 2: VRTL
            if "VRTL" in name_upper:
                count += 1
                continue
            # Rule 3: numbered prefix (e.g., "01-Cover_Page")
            if re.match(r'^\d{2,3}-', entry.name):
                count += 1
                continue
            # Rule 4: large stream (>2000 bytes) not in system names
            if (entry.stream_size > 2000
                    and entry.name not in SYSTEM_NAMES
                    and entry.name.upper() not in SYSTEM_NAMES):
                count += 1

        return count

    def read_stream_by_path(self, path: str) -> bytes:
        """按层级路径读取流数据。

        Args:
            path: 层级路径，如 'Views/SCHEMATIC1/Pages/PAGE1'。

        Returns:
            流数据字节。

        Raises:
            CFBError: 路径不存在或目标不是流。
        """
        for entry in self._entry_paths:
            if entry.full_path == path:
                return self._read_stream_data(entry)
        raise CFBError(f"Stream not found: {path}")

    def read_stream(self, name: str) -> bytes:
        """按名称读取流数据（扁平查找）。"""
        entries = self.find_entries_by_name(name)
        for entry in entries:
            if entry.dir_type == DIR_TYPE_STREAM:
                return self._read_stream_data(entry)
        raise CFBError(f"Stream not found: {name}")

    def read_stream_from_entry(self, entry: OlePathEntry) -> bytes:
        """读取由 OlePathEntry 指定的流数据。

        接受来自 ``list_all_entries()`` 或 ``list_raw_dir_entries()``
        的条目，直接读取其数据。适用于绕过损坏的目录树直接访问
        原始条目。

        Args:
            entry: 包含有效 start_sector 和 stream_size 的路径条目。

        Returns:
            流数据字节。

        Raises:
            CFBError: 如果 entry 的 dir_type 不是 stream。
        """
        if entry.dir_type != DIR_TYPE_STREAM:
            raise CFBError(
                f"Entry '{entry.name}' is not a stream (type={entry.dir_type})"
            )
        return self._read_stream_data(entry)

    def _read_stream_data(self, entry: OlePathEntry) -> bytes:
        """读取条目的原始数据，根据大小选择常规扇区或 mini 扇区。

        Args:
            entry: 流条目。

        Returns:
            流数据字节。
        """
        if entry.stream_size == 0:
            return b""

        if entry.stream_size >= self._mini_stream_cutoff:
            # Regular stream
            chain = self._get_sector_chain(entry.start_sector)
            data = bytearray()
            for sect in chain:
                offset = (sect + 1) * self._sector_size
                data.extend(
                    self._buffer[offset : offset + self._sector_size]
                )
            return bytes(data[: entry.stream_size])
        else:
            # Mini stream
            chain = self._get_mini_sector_chain(entry.start_sector)
            data = bytearray()
            for mini_sect in chain:
                offset = mini_sect * MINI_STREAM_SECTOR_SIZE
                data.extend(
                    self._mini_stream[offset : offset + MINI_STREAM_SECTOR_SIZE]
                )
            return bytes(data[: entry.stream_size])

    @property
    def sector_size(self) -> int:
        """CFB 扇区大小。"""
        return self._sector_size
