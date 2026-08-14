"""OLBOleReader — OLB CFB 容器读取器。

基于 OleReader 为 OLB 文件提供便利的访问方法。
OLB 文件与 DSN 文件同样使用 Microsoft CFB (Compound File Binary) 格式。

OLB 内部流结构:
    MyLib.olb (CFB)
    ├── Packages/{PkgName}           ← Type 31 Package 结构体流
    ├── Packages/{PkgName}/Devices   ← Type 32 Device 定义流(含 pinMap)
    ├── Library/strLst               ← 全局字符串表
    └── Symbols/{LibPart}/NormalView ← 符号图形数据(Line/Ellipse/Arc...)

参考:
    - openOrCadParser: OlbParser.cpp, OlbReader.hpp
    - docs/ORCAD_SOURCE_ANALYSIS.md §1.2
    - BACKEND_DESIGN.md §3.1
"""

from __future__ import annotations

import logging
from pathlib import Path

from ..dsn.ole_reader import (
    OleReader, OlePathEntry, CFBError,
    DIR_TYPE_STREAM, DIR_TYPE_STORAGE,
    MINI_STREAM_SECTOR_SIZE,
)

logger = logging.getLogger(__name__)


class OLBOleReader(OleReader):
    """OLB CFB 容器读取器 — 提供 OLB 特定的流访问方法。

    继承自 OleReader，自动完成 CFB 解析。
    提供按 OLB 逻辑结构分组的流访问 API。

    注意：某些 OLB 文件的 CFB 容器在 miniFAT 处理上存在变体，
    导致部分 stream 的 mini-sector 读取返回空数据。
    本类在读取时会回退到常规扇区读取以处理这种情况。

    Usage:
        reader = OLBOleReader(Path("mylib.olb"))
        pkgs = reader.list_packages()
        device_data = reader.read_device_stream("PackageName")
        sym_data = reader.read_normal_view("SYM_CAP_NP")
    """

    def __init__(self, file_path: Path) -> None:
        """初始化 OLB 读取器。

        Args:
            file_path: .olb 文件路径。
        """
        super().__init__(file_path)
        self._all_entries: list[OlePathEntry] = self.list_all_entries()

    # ── Override stream reading to handle OLB CFB variants ──────────

    def _read_stream_data(self, entry: OlePathEntry) -> bytes:
        """读取条目数据，处理 OLB CFB 的 FAT 变体。

        某些 OLB 文件中，目录条目引用的扇区号超出 FAT 范围
        （例如 sector 473 而 FAT 只有 256 条目）。
        此时回退到 mini-stream 扇区读取。

        Args:
            entry: 流条目。

        Returns:
            流数据字节。
        """
        if entry.stream_size == 0:
            return b""

        # Try regular FAT path (stream_size >= cutoff)
        if entry.stream_size >= self._mini_stream_cutoff:
            chain = self._get_sector_chain(entry.start_sector)
            if chain:
                data = bytearray()
                for sect in chain:
                    offset = (sect + 1) * self._sector_size
                    if offset + self._sector_size <= len(self._buffer):
                        data.extend(self._buffer[offset : offset + self._sector_size])
                result = bytes(data[: entry.stream_size])
                if len(result) > 0:
                    return result
            # FAT returned empty/zero → fall through to mini-stream path

        # Mini stream path (default for small streams, fallback for FREESECT FAT)
        chain = self._get_mini_sector_chain(entry.start_sector)
        if not chain:
            return b""
        data = bytearray()
        for mini_sect in chain:
            offset = mini_sect * MINI_STREAM_SECTOR_SIZE
            if offset + MINI_STREAM_SECTOR_SIZE <= len(self._mini_stream):
                data.extend(self._mini_stream[offset : offset + MINI_STREAM_SECTOR_SIZE])
        return bytes(data[: entry.stream_size])

    # ── Package 列表 ───────────────────────────────────────────────────

    def list_packages(self) -> list[str]:
        """列出 OLB 中所有 Package 名称。

        遍历 ``Packages/`` 路径下的所有 stream 条目，提取 Package 名称。
        OLB 中的 Package 数据存储为 stream（非 storage），位于 Packages 子目录下。

        Returns:
            Package 名称列表（按发现顺序）。
        """
        packages: list[str] = []
        seen: set[str] = set()

        for entry in self._all_entries:
            if entry.dir_type != DIR_TYPE_STREAM:
                continue
            path = entry.full_path
            # Match paths like "Root Entry/Packages/8P4R_0" or "Packages/8P4R_0"
            if self._is_package_entry(path):
                pkg_name = path.split("/")[-1]
                # Skip known non-package entries
                if pkg_name in ("$Types$", "Cache", "strLst", ""):
                    continue
                if pkg_name and pkg_name not in seen:
                    packages.append(pkg_name)
                    seen.add(pkg_name)

        logger.info("Found %d package(s) in OLB", len(packages))
        return packages

    @staticmethod
    def _is_package_entry(path: str) -> bool:
        """检查路径是否为 Package 流条目。

        Matches patterns:
        - ``Packages/{Name}``  (no further children)
        - ``Root Entry/Packages/{Name}``
        """
        parts = path.split("/")
        # Find "Packages" segment
        for i, part in enumerate(parts):
            if part == "Packages" and i + 1 < len(parts):
                # Has a direct child after "Packages/" — that's the package
                # Ensure no grandchild (e.g. Packages/PKG/Devices would be 3 deep)
                remaining = parts[i + 1:]
                if len(remaining) == 1:
                    return True
        return False

    def list_package_entries(self) -> list[OlePathEntry]:
        """列出所有 Package stream 条目。

        Returns:
            Packages/ 下的 stream 条目列表。
        """
        return [
            e for e in self._all_entries
            if e.dir_type == DIR_TYPE_STREAM
            and self._is_package_entry(e.full_path)
        ]

    # ── Device 流 ──────────────────────────────────────────────────────

    @staticmethod
    def _match_stream_path(entries: list[OlePathEntry], path_suffix: str) -> OlePathEntry | None:
        """在条目列表中按路径后缀匹配 stream 条目。

        支持两种路径格式:
        - ``Root Entry/Packages/8P4R_0`` (带 Root Entry 前缀)
        - ``Packages/8P4R_0`` (无前缀)

        Args:
            entries: CFB 条目列表。
            path_suffix: 路径后缀（如 "Packages/8P4R_0"）。

        Returns:
            匹配的条目或 None。
        """
        leaf = path_suffix.split("/")[-1]
        parent = "/".join(path_suffix.split("/")[:-1])
        for entry in entries:
            if entry.dir_type != DIR_TYPE_STREAM:
                continue
            fp = entry.full_path
            # Exact match
            if fp == path_suffix:
                return entry
            # Match with "Root Entry/" prefix
            if fp == f"Root Entry/{path_suffix}":
                return entry
            # Match ending with leaf name in correct parent context
            if fp.endswith(f"/{leaf}") and parent and fp.endswith(path_suffix):
                return entry
            # Lenient: match by leaf name if parent context appears
            if fp.endswith(f"/{leaf}") and parent.split("/")[-1] in fp:
                # Verify it's the right parent by checking the path
                fp_parts = fp.split("/")
                if parent.split("/")[-1] in fp_parts:
                    return entry
        return None

    def read_device_stream(self, package_name: str) -> bytes:
        """读取指定 Package 的 Device 定义流。

        路径模式: ``Packages/{package_name}/Devices``

        Args:
            package_name: Package 名称。

        Returns:
            Device 流的原始字节数据。

        Raises:
            CFBError: 流不存在或无法读取。
        """
        path = f"Packages/{package_name}/Devices"
        entry = self._match_stream_path(self._all_entries, path)
        if entry is not None:
            return self.read_stream_from_entry(entry)
        raise CFBError(f"Device stream not found for package '{package_name}'")

    def read_package_stream(self, package_name: str) -> bytes:
        """读取指定 Package 的结构体数据流。

        路径模式: ``Packages/{package_name}``

        Args:
            package_name: Package 名称。

        Returns:
            Package 流的原始字节数据。

        Raises:
            CFBError: 流不存在或无法读取。
        """
        path = f"Packages/{package_name}"
        entry = self._match_stream_path(self._all_entries, path)
        if entry is not None:
            return self.read_stream_from_entry(entry)
        raise CFBError(f"Package stream not found for '{package_name}'")

    # ── Library 流 ─────────────────────────────────────────────────────

    def read_library_stream(self, stream_name: str = "strLst") -> bytes:
        """读取 Library 目录下的流数据。

        路径模式: ``Library/{stream_name}``

        Args:
            stream_name: 流名称（默认 "strLst"）。

        Returns:
            流的原始字节数据。

        Raises:
            CFBError: 流不存在或无法读取。
        """
        path = f"Library/{stream_name}"
        entry = self._match_stream_path(self._all_entries, path)
        if entry is not None:
            return self.read_stream_from_entry(entry)
        raise CFBError(f"Library stream not found: '{stream_name}'")

    # ── Symbol/NormalView 流 ───────────────────────────────────────────

    def read_normal_view(self, lib_part_name: str) -> bytes:
        """读取指定 LibPart 的 NormalView 符号图形流。

        路径模式: ``Symbols/{lib_part_name}/NormalView``

        Args:
            lib_part_name: LibPart 名称（符号部件名）。

        Returns:
            NormalView 流的原始字节数据。

        Raises:
            CFBError: 流不存在或无法读取。
        """
        # Try NormalView sub-path first
        path = f"Symbols/{lib_part_name}/NormalView"
        entry = self._match_stream_path(self._all_entries, path)
        if entry is not None:
            return self.read_stream_from_entry(entry)
        # Fallback: the symbol itself is the stream (no NormalView sub-path)
        path_direct = f"Symbols/{lib_part_name}"
        entry = self._match_stream_path(self._all_entries, path_direct)
        if entry is not None:
            return self.read_stream_from_entry(entry)
        raise CFBError(f"NormalView stream not found for '{lib_part_name}'")

    def list_symbols(self) -> list[str]:
        """列出 OLB 中所有 LibPart 符号名称。

        遍历 ``Symbols/`` 路径下的 stream 条目。

        Returns:
            LibPart 名称列表。
        """
        symbols: list[str] = []
        seen: set[str] = set()

        for entry in self._all_entries:
            if entry.dir_type != DIR_TYPE_STREAM:
                continue
            path = entry.full_path
            if self._is_symbol_entry(path):
                sym_name = path.split("/")[-1]
                if sym_name in ("$Types$", ""):
                    continue
                if sym_name and sym_name not in seen:
                    symbols.append(sym_name)
                    seen.add(sym_name)

        logger.info("Found %d symbol(s) in OLB", len(symbols))
        return symbols

    @staticmethod
    def _is_symbol_entry(path: str) -> bool:
        """检查路径是否为 Symbol 流条目。

        Matches patterns:
        - ``Symbols/{Name}`` (direct child, no NormalView sub-path)
        - ``Root Entry/Symbols/{Name}``
        """
        parts = path.split("/")
        for i, part in enumerate(parts):
            if part == "Symbols" and i + 1 < len(parts):
                remaining = parts[i + 1:]
                if len(remaining) == 1:
                    return True
        return False

    def read_symbol_stream(self, lib_part_name: str) -> bytes | None:
        """读取指定 LibPart 的符号数据流（NormalView）。

        等同于 ``read_normal_view()``，提供别名以匹配设计文档 API。

        Args:
            lib_part_name: LibPart 名称。

        Returns:
            NormalView 流数据，或 None 如果不存在。
        """
        try:
            return self.read_normal_view(lib_part_name)
        except CFBError:
            logger.debug("Symbol stream not found for '%s'", lib_part_name)
            return None
