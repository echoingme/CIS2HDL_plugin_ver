"""DSNParser — Binary DSN 顶层调度器（B1.14）。

完整的 Binary DSN 解析管道：
    OleReader → Page流 + Cache流 + Library流 → DesignIR（含坐标）

参考：
    - openOrCadParser: DsnParser.cpp
    - universal-netlist: dsn-parser.ts
    - BACKEND_DESIGN.md §3.1
"""

from __future__ import annotations

import logging
import re
from copy import copy
from pathlib import Path

from ..base import ParserBase
from ...ir.design import DesignIR, PageIR, NetIR, NetConnection, WireSegment as IRWireSegment
from ...ir.component import ComponentInstanceIR
from ...db.component_db import ComponentDB
from ...config import config as cfg
from cis2hdl.core.net_utils import classify_net

from .ole_reader import OleReader, OlePathEntry
from .page_parser import parse_page, PageData
from .structures import PlacedInstance
from .library_parser import parse_strlst
from .cache_parser import parse_cache_stream

logger = logging.getLogger(__name__)


class DSNParser(ParserBase):
    """Binary DSN 解析器 — 将 .dsn 文件解析为完整 DesignIR（含坐标）。

    Usage:
        parser = DSNParser()
        ir = parser.parse(Path("project.dsn"))
    """

    FORMAT_NAME = "CIS_DSN"
    FILE_EXTENSIONS = [".dsn"]

    def parse(self, dsn_path: Path) -> DesignIR:
        """解析 DSN 二进制文件为 DesignIR。

        Args:
            dsn_path: .dsn 文件路径。

        Returns:
            包含坐标和逻辑数据的完整 DesignIR。

        Raises:
            ParseError: 解析过程中的任何错误。
        """
        logger.info("Parsing Binary DSN: %s", dsn_path)
        ole = OleReader(dsn_path)
        entries = ole.list_all_entries()

        project_name = dsn_path.stem

        # ── 0. Load strLst from Library stream ───────────────────────
        strlst: list[str] | None = None
        try:
            lib_bytes = ole.read_stream("Library")
            strlst = parse_strlst(lib_bytes)
            logger.info("Loaded strLst: %d entries", len(strlst))
        except Exception as exc:
            logger.warning("Failed to load strLst from Library stream: %s", exc)

        # ── 0.5. Parse Cache stream for component definitions ────────
        component_db = ComponentDB()
        try:
            cache_bytes = ole.read_stream("Cache")
            cache_data = parse_cache_stream(cache_bytes)
            for comp in cache_data.components:
                component_db.add(comp)
            logger.info(
                "Loaded %d components from Cache stream",
                cache_data.component_count,
            )
        except Exception as exc:
            logger.warning("Failed to parse Cache stream: %s", exc)

        # ── 1. Discover Page streams ─────────────────────────────────
        pages_data: list[PageData] = self._read_all_pages(ole, entries, strlst)
        logger.info(
            "Found %d pages: %s",
            len(pages_data),
            ", ".join(p.page_id for p in pages_data),
        )

        # ── 1.5. Resolve hierarchical DrawnInst → sub-page traversal ─
        pages_data = self._resolve_hierarchy(
            ole, pages_data, project_name, strlst, max_depth=2,
        )

        # ── 2. Build DesignIR ────────────────────────────────────────
        design = DesignIR(project_name=project_name, source_format="CIS_DSN")

        # component_db was created in step 0.5 (Cache parsing)

        for idx, page_data in enumerate(pages_data):
            page = self._build_page_ir(page_data, f"1.{idx + 1}", component_db, strlst)
            design.pages.append(page)

            # Collect global nets
            for g in page_data.globals_:
                if g.name and g.name not in design.global_nets:
                    design.global_nets.append(g.name)

        # ── 2.5. Extract info page graphics ─────────────────────────
        info_page_graphics = self._extract_info_page_graphics(ole, strlst)
        if info_page_graphics:
            for page in design.pages:
                if page.page_name in info_page_graphics:
                    page.graphic_elements = info_page_graphics[page.page_name]
                    logger.info(
                        "Page '%s': attached %d graphic elements",
                        page.page_name, len(page.graphic_elements),
                    )

        design.component_db = component_db

        # ── 3. Metadata ──────────────────────────────────────────────
        design.metadata["page_count"] = len(pages_data)
        design.metadata["total_instances"] = sum(
            len(p.instances) for p in pages_data
        )
        design.metadata["total_wires"] = sum(len(p.wires) for p in pages_data)
        design.metadata["total_ports"] = sum(len(p.ports) for p in pages_data)

        logger.info(
            "DSN parse complete: %d pages, %d instances, %d wires",
            len(pages_data),
            design.metadata["total_instances"],
            design.metadata["total_wires"],
        )

        return design

    # ── Page stream discovery ────────────────────────────────────────

    def _read_all_pages(
        self, ole: OleReader, entries: list,
        strlst: list[str] | None = None,
    ) -> list[PageData]:
        """从 OLE 容器中发现并解析所有页面流。

        采用两层策略：
        1. **主路径**：通过 CFB 目录树查找 ``Pages/`` 路径下的流条目。
        2. **回退路径**：当目录树条目损坏（OrCAD CFB 已知问题）导致
           页面流未被正确链入 Pages hierarchy 时，绕过目录树，
           直接从原始目录条目中按名称模式匹配页面流。

        Args:
            ole: OLE 容器读取器。
            entries: 条目列表。

        Returns:
            解析完成的 PageData 列表。
        """
        # ── 主路径：通过目录树查找 Pages/* 流 ─────────────────
        page_entries = [
            e for e in entries
            if "Pages" in e.full_path and e.dir_type == 2  # 2 = stream
        ]

        pages: list[PageData] = []
        seen_names: set[str] = set()

        for entry in page_entries:
            try:
                buffer = ole.read_stream_by_path(entry.full_path)
                page_id = entry.full_path.split("/")[-1]
                page_data = parse_page(buffer, page_id, strlst=strlst)
                page_data.page_name = entry.name
                pages.append(page_data)
                seen_names.add(entry.name)
            except Exception as exc:
                logger.error(
                    "Failed to parse page stream '%s': %s",
                    entry.full_path,
                    exc,
                )

        # ── 回退路径：绕过损坏的目录树，直接扫描原始条目 ──────
        # 当 raw entries 中的页面候选数多于 tree traversal 返回的页面数时，
        # 说明部分页面流因 CFB 目录树 sibling/child 指针损坏而未被遍历到。
        raw_candidate_count = ole.count_page_candidates()
        if len(pages) < raw_candidate_count:
            logger.warning(
                "Found %d pages via tree but %d candidates in raw entries; "
                "falling back to raw directory entry scan for missing pages",
                len(pages), raw_candidate_count,
            )
            raw_entries = ole.list_raw_dir_entries()
            for entry in raw_entries:
                if entry.dir_type != 2:
                    continue
                if entry.name in seen_names:
                    continue

                name_upper = entry.name.upper()
                is_page_candidate = (
                    name_upper.startswith("PAGE")
                    or "PAGE" in name_upper
                    or "VRTL" in name_upper
                    or "Pages" in entry.full_path
                    or bool(re.match(r'^\d{2,3}-', entry.name))
                )
                if not is_page_candidate:
                    continue

                try:
                    buffer = ole.read_stream_from_entry(entry)
                    page_data = parse_page(buffer, entry.name, strlst=strlst)
                    page_data.page_name = entry.name
                    pages.append(page_data)
                    seen_names.add(entry.name)
                    logger.info(
                        "Recovered page stream via raw entry: '%s' (%d bytes)",
                        entry.name,
                        len(buffer),
                    )
                except Exception as exc:
                    logger.error(
                        "Failed to parse raw page stream '%s': %s",
                        entry.name,
                        exc,
                    )

        return pages

    # ── Hierarchical DrawnInst traversal ────────────────────────────

    def _resolve_hierarchy(
        self,
        ole: OleReader,
        pages: list[PageData],
        project_name: str,
        strlst: list[str] | None = None,
        max_depth: int = 2,
    ) -> list[PageData]:
        """递归遍历层次块（DrawnInst），提取子页面中的叶子器件。

        RTL8367RB DSN 为层次化设计：顶层页面包含 DrawnInst（层次块实例），
        块内部的子页面中包含电阻/电容等叶子器件。此方法在解析完所有页面后，
        递归进入 DrawnInst 指向的子页面提取这些叶子器件。

        DrawnInst 识别：
            - pkg_name 在 CFB 原始目录条目中存在对应流条目
            - pkg_name 不同于当前页面名称（避免循环引用）
            - 对应流条目可成功解析为 PageData

        Args:
            ole: OLE 容器读取器（用于读取子页面流）。
            pages: 已解析的页面列表。
            project_name: 设计名（用于日志）。
            max_depth: 最大递归深度（RTL8367RB 只有 1 层嵌套）。

        Returns:
            合并后的页面列表（原地修改并返回）。
        """
        # 1. 构建所有原始流条目的名称映射
        raw_entries = ole.list_raw_dir_entries()
        stream_map: dict[str, OlePathEntry] = {}
        for entry in raw_entries:
            if entry.dir_type == 2 and entry.stream_size > 0:  # stream
                stream_map[entry.name] = entry

        # 2. 记录已解析的页面名称（用于子页面缓存和循环检测）
        parsed_page_cache: dict[str, PageData] = {}
        seen_names: set[str] = set()
        for page in pages:
            if page.page_name:
                seen_names.add(page.page_name)
                parsed_page_cache[page.page_name] = page

        # 3. 对每个页面递归解析层次块
        for page in pages:
            self._resolve_page_hierarchy(
                ole, page, stream_map, parsed_page_cache,
                seen_names, project_name, strlst, depth=0, max_depth=max_depth,
            )

        # 4. 汇总日志
        total_instances = sum(len(p.instances) for p in pages)
        logger.info(
            "Hierarchy resolved: %d pages, %d total instances",
            len(pages), total_instances,
        )

        return pages

    def _resolve_page_hierarchy(
        self,
        ole: OleReader,
        page: PageData,
        stream_map: dict[str, OlePathEntry],
        parsed_page_cache: dict[str, PageData],
        seen_names: set[str],
        project_name: str,
        strlst: list[str] | None,
        depth: int,
        max_depth: int,
    ) -> None:
        """递归解析单个页面中的层次块（DrawnInst）。

        遍历页面中的所有实例，识别 DrawnInst（其 pkg_name 指向 CFB 中
        的子页面流），解析子页面并将叶子器件合并到当前页面中。

        合并规则：
            - 子页面实例的坐标加上 DrawnInst 的偏移量（loc_x, loc_y）
            - DrawnInst 本身保留（包含其在顶层页面中的引脚连接数据）
            - 子页面中的 DrawnInst 继续递归解析（直到达到 max_depth）

        Args:
            ole: OLE 容器读取器。
            page: 当前页面数据。
            stream_map: CFB 流条目名称 → 条目映射。
            parsed_page_cache: 已解析的子页面缓存。
            seen_names: 已见过的页面名称集合（用于循环检测）。
            project_name: 设计名。
            depth: 当前递归深度。
            max_depth: 最大递归深度。
        """
        if depth >= max_depth:
            return

        new_instances: list[PlacedInstance] = []
        resolved_count = 0
        # Track sub-page usage within this page to offset shared sub-pages
        _sub_page_usage: dict[str, int] = {}

        for inst in page.instances:
            pkg_name = inst.pkg_name

            # 检测是否为 DrawnInst
            if not self._is_drawn_inst(pkg_name, page.page_name,
                                        stream_map, seen_names):
                new_instances.append(inst)
                continue

            # 解析子页面（使用缓存避免重复解析）
            sub_page = parsed_page_cache.get(pkg_name)
            if sub_page is None:
                sub_entry = stream_map[pkg_name]
                try:
                    buffer = ole.read_stream_from_entry(sub_entry)
                    sub_page = parse_page(buffer, pkg_name, strlst=strlst)
                    sub_page.page_name = pkg_name
                    parsed_page_cache[pkg_name] = sub_page
                    seen_names.add(pkg_name)
                    logger.debug(
                        "Parsed sub-page '%s' (%d bytes, %d instances)",
                        pkg_name, len(buffer), len(sub_page.instances),
                    )
                except Exception as exc:
                    logger.warning(
                        "Failed to parse sub-page '%s' for DrawnInst "
                        "'%s' (page '%s'): %s",
                        pkg_name, inst.reference, page.page_name, exc,
                    )
                    new_instances.append(inst)
                    continue

            # 递归解析子页面中的层次块（深度+1）
            self._resolve_page_hierarchy(
                ole, sub_page, stream_map, parsed_page_cache,
                seen_names, project_name, strlst, depth=depth + 1,
                max_depth=max_depth,
            )

            # 保留原始 DrawnInst（包含其顶层引脚连接数据）
            new_instances.append(inst)

            # Track sub-page usage — apply progressive offset for shared sub-pages
            usage_idx = _sub_page_usage.get(pkg_name, 0)
            _sub_page_usage[pkg_name] = usage_idx + 1
            extra_offset = usage_idx * 100  # 100 mil progressive offset

            # 合并子页面的叶子实例（浅拷贝 + 坐标偏移，避免污染缓存）
            for child_inst in sub_page.instances:
                cloned = copy(child_inst)
                cloned.loc_x += inst.loc_x + extra_offset
                cloned.loc_y += inst.loc_y + extra_offset
                new_instances.append(cloned)

            resolved_count += 1
            logger.info(
                "Resolved DrawnInst '%s' → sub-page '%s': "
                "merged %d child instances (depth=%d)",
                inst.reference, pkg_name,
                len(sub_page.instances), depth + 1,
            )

        if resolved_count > 0:
            page.instances = new_instances

    @staticmethod
    def _is_drawn_inst(
        pkg_name: str,
        current_page_name: str,
        stream_map: dict[str, OlePathEntry],
        seen_names: set[str],
    ) -> bool:
        """判断一个 PlacedInstance 是否为 DrawnInst（层次块）。

        DrawnInst 与普通 PlacedInstance 共享相同的 RTL 二进制格式，
        区别在于 DrawnInst 的 pkg_name 指向 CFB 中的子页面流。

        判断条件：
            1. pkg_name 非空
            2. pkg_name 与当前页面名不同（避免循环引用）
            3. pkg_name 在 stream_map 中存在对应的流条目
            4. pkg_name 尚未被解析为页面（或作为子页面解析过）

        Args:
            pkg_name: 实例的包名。
            current_page_name: 当前页面名称。
            stream_map: CFB 流条目映射。
            seen_names: 已见过的页面名称集合。

        Returns:
            True 如果该实例是 DrawnInst。
        """
        if not pkg_name:
            return False
        # 避免循环引用：DrawnInst 不能指向自身所在的页面
        if pkg_name == current_page_name:
            return False
        # 检查 CFB 中是否存在对应子页面流
        if pkg_name not in stream_map:
            return False
        # 额外检查：pkg_name 不应是已知的顶层页面名（避免已解析页面的重复处理）
        # 此项检查较宽松：允许 pkg_name 在 seen_names 中（作为子页面缓存）
        return True

    # ── IR construction ──────────────────────────────────────────────

    _INFO_PAGE_NAMES: set[str] = {
        '01-Cover_Page', '02-Block_Diagram',
        '03-Clock_Tree', '04-Power_Tree',
    }
    """信息页名称集合 — 这些页面包含 TitleBlock/GraphicInst 结构，
    其文本不会通过普通的 page_parser 提取，需要单独扫描。"""

    def _extract_info_page_graphics(
        self, ole: OleReader, strlst: list[str] | None = None,
    ) -> dict[str, list[dict]]:
        """从信息页提取图形和文本元素。

        信息页（Cover_Page, Block_Diagram, Clock_Tree, Power_Tree）
        的页面流中可能包含 TitleBlock 和 GraphicInst 结构。
        通过搜索拉丁-1 可打印字符串模式来提取文本注释。

        Args:
            ole: OLE 容器读取器（用于读取原始页面流）。
            strlst: 字符串表，可选。

        Returns:
            页面名称 → 图形元素列表的映射。每个元素包含：
            {type: 'text', text: str, position: int}
        """
        result: dict[str, list[dict]] = {}
        raw_entries = ole.list_raw_dir_entries()

        for entry in raw_entries:
            if entry.dir_type != 2:  # 2 = stream
                continue
            if entry.name not in self._INFO_PAGE_NAMES:
                continue
            try:
                buf = ole.read_stream_from_entry(entry)
                graphics: list[dict] = []
                self._scan_for_text_strings(buf, graphics, strlst)
                if graphics:
                    result[entry.name] = graphics
                    logger.info(
                        "Info page '%s': extracted %d text element(s)",
                        entry.name, len(graphics),
                    )
            except Exception as exc:
                logger.warning(
                    "Failed to extract info page graphics for '%s': %s",
                    entry.name, exc,
                )

        return result

    @staticmethod
    def _scan_for_text_strings(
        buf: bytes, graphics: list[dict], strlst: list[str] | None = None,
    ) -> None:
        """扫描二进制缓冲区寻找可打印文本字符串。

        使用正则表达式查找连续的可打印 Latin-1 字符序列（至少 4 个字符），
        并过滤掉明显的十六进制垃圾和空白填充。

        Args:
            buf: 原始字节缓冲区。
            graphics: 输出列表，每个元素为 {type, text, position}。
            strlst: 字符串表（未使用，保留接口兼容）。
        """
        # 寻找连续的可打印 Latin-1 字符序列（至少 4 个字符）
        text_pattern = re.compile(rb'[\x20-\x7E\xA0-\xFF]{4,}')
        for match in text_pattern.finditer(buf):
            text = match.group().decode('latin-1', errors='replace')
            # 过滤明显的垃圾
            if len(text) < 4:
                continue
            # 过滤纯空格序列
            if text.count(' ') > len(text) * 0.5:
                continue
            # 过滤可能的十六进制字符串
            if all(c in '0123456789abcdefABCDEF' for c in text):
                continue
            # 过滤纯标点/特殊字符
            if sum(1 for c in text if c.isalnum()) < len(text) * 0.3:
                continue
            # 过滤乱码文本：非可打印字符占比超过40%
            non_printable = sum(
                1 for c in text if not c.isprintable() and c not in '\t\n\r'
            )
            if non_printable > len(text) * 0.4:
                continue
            # 过滤明显为二进制数据的文本（控制字符占比超过50%）
            if sum(1 for c in text if ord(c) < 32) > len(text) * 0.5:
                continue
            # 过滤乱码：扩展 Latin-1 字符（0xA0-0xFF）占比超过40%
            # 原理图文本注释通常为 ASCII，高比例扩展字符表明是二进制数据
            high_bytes = sum(1 for c in text if ord(c) >= 0xA0)
            if high_bytes > len(text) * 0.4:
                continue

            graphics.append({
                'type': 'text',
                'text': text,
                'position': match.start(),
            })

    def _build_page_ir(
        self,
        page_data: PageData,
        page_id: str,
        component_db: ComponentDB,
        strlst: list[str] | None = None,
    ) -> PageIR:
        """将 PageData 转换为 PageIR。

        Args:
            page_data: 解析后的页面数据。
            page_id: 页面编号（如 '1.1'）。
            component_db: 器件数据库（用于注册新器件）。
            strlst: 字符串表（用于解析索引引用），可选。

        Returns:
            PageIR 对象。
        """
        # ── Build net alias map ──────────────────────────────────
        net_alias_map: dict[int, str] = {}
        aliases = page_data.aliases if page_data.aliases else None
        if aliases:
            for a in aliases:
                net_alias_map[a.alias_id] = a.name
            logger.debug(
                "Page %s: loaded %d net aliases",
                page_id, len(net_alias_map),
            )

        # ── Instances ────────────────────────────────────────────
        instances: list[ComponentInstanceIR] = []
        seen_refdes_lib: set[tuple[str, str]] = set()  # for coordinate dedup
        for pi in page_data.instances:
            # ── Filter fake PlacedInstances ─────────────────────────
            # strLst entries and other parsing artifacts produce fake
            # PlacedInstances with db_id=0 (no real database entry).
            # These have garbled attributes and no valid pin connections.
            # Real instances always have non-zero db_id.
            if pi.db_id == 0:
                continue

            # Coordinate dedup: if same refdes+library_id appears multiple
            # times, keep the one with non-zero coordinates.
            key = (pi.reference, pi.pkg_name)
            if key in seen_refdes_lib:
                # Check if existing has zero coords and this one doesn't
                if pi.loc_x != 0 or pi.loc_y != 0:
                    for existing in instances:
                        if existing.refdes == pi.reference and existing.library_id == pi.pkg_name:
                            if existing.loc_x == 0 and existing.loc_y == 0:
                                existing.loc_x = pi.loc_x
                                existing.loc_y = pi.loc_y
                            break
                continue
            seen_refdes_lib.add(key)

            inst = ComponentInstanceIR(
                refdes=pi.reference,
                library_id=pi.pkg_name,
                loc_x=pi.loc_x,
                loc_y=pi.loc_y,
                section=1,
            )
            # Pin connections from T0x10
            for t0 in pi.t0x10_list:
                pin_num = str(t0.pin_index)
                net_name = net_alias_map.get(t0.net_id, f"NET_{t0.net_id}")
                inst.pin_connections[pin_num] = net_name

            # Properties from prefix — resolve strLst indices
            for pp in pi.prefix_props:
                if pp.name.isdigit() and strlst and 0 <= int(pp.name) < len(strlst):
                    pp_name = strlst[int(pp.name)]
                else:
                    pp_name = pp.name
                if pp.value.isdigit() and strlst and 0 <= int(pp.value) < len(strlst):
                    pp_value = strlst[int(pp.value)]
                else:
                    pp_value = pp.value
                inst.properties[pp_name] = pp_value

            instances.append(inst)

        # ── Nets ─────────────────────────────────────────────────
        nets: list[NetIR] = []
        net_map: dict[int, list[tuple[str, str]]] = {}
        for pi in page_data.instances:
            for t0 in pi.t0x10_list:
                net_map.setdefault(t0.net_id, []).append(
                    (pi.reference, str(t0.pin_index))
                )

        for net_id, connections in net_map.items():
            real_name = net_alias_map.get(net_id, f"NET_{net_id}")
            net = NetIR(
                name=real_name,
                category=classify_net(real_name),
                connections=[
                    NetConnection(refdes=refdes, pin_number=pin)
                    for refdes, pin in connections
                ],
            )
            nets.append(net)

        # ── Build wire_net_map from Wire segments ────────────────
        # Always build this map so wire segments can resolve their
        # net names regardless of whether net_map from instances exists.
        wire_net_map: dict[int, str] = {}
        if page_data.wires:
            for ws in page_data.wires:
                wire_id = ws.wire_id
                if wire_id in wire_net_map:
                    continue
                # Prefer alias-resolved name over synthetic NET_xxx
                net_name = net_alias_map.get(wire_id, "")
                if not net_name and ws.aliases:
                    for a_id in ws.aliases:
                        if a_id in net_alias_map:
                            net_name = net_alias_map[a_id]
                            break
                if not net_name:
                    net_name = f"NET_{wire_id}"
                wire_net_map[wire_id] = net_name

        # ── Path B: Build nets from Wire segments when instances
        #    are empty (v0.5.0 CrossRef-driven mode).  Wire segments
        #    carry wire_id and alias references that let us reconstruct
        #    net topology even without PlacedInstance t0x10 data.
        if not net_map:
            seen_net_names: set[str] = set()
            for wire_id, net_name in wire_net_map.items():
                if net_name not in seen_net_names:
                    seen_net_names.add(net_name)
                    nets.append(NetIR(
                        name=net_name,
                        category=classify_net(net_name),
                        connections=[],
                    ))

        # ── Ports / Globals as additional net nodes ──────────────
        # Port and Global symbols on a page represent named
        # connection points that should appear in the netlist.
        _existing_nets: set[str] = {n.name for n in nets}
        for port in page_data.ports:
            if port.name and port.name not in _existing_nets:
                _existing_nets.add(port.name)
                nets.append(NetIR(
                    name=port.name,
                    category=classify_net(port.name),
                    connections=[],
                ))
        for g in page_data.globals_:
            if g.name and g.name not in _existing_nets:
                _existing_nets.add(g.name)
                nets.append(NetIR(
                    name=g.name,
                    category=classify_net(g.name),
                    connections=[],
                ))

        # ── Wires ────────────────────────────────────────────────
        wires: list[IRWireSegment] = []
        for ws in page_data.wires:
            net_name = wire_net_map.get(ws.wire_id, "")
            wires.append(
                IRWireSegment(
                    start_x=ws.start_x,
                    start_y=ws.start_y,
                    end_x=ws.end_x,
                    end_y=ws.end_y,
                    net_name=net_name,
                )
            )

        # ── Ports ────────────────────────────────────────────────
        ports: list[dict] = []
        for port in page_data.ports:
            ports.append({
                "name": port.name,
                "loc_x": port.loc_x,
                "loc_y": port.loc_y,
                "type": "PORT",
            })
        for g in page_data.globals_:
            ports.append({
                "name": g.name,
                "loc_x": g.loc_x,
                "loc_y": g.loc_y,
                "type": "GLOBAL",
            })

        # ── v0.5.1: Transfer title_blocks to graphic_elements ────
        # Info pages (Cover, Clock, Power, Block) produce TitleBlockText
        # entries via sequential fallback parsing.  Convert them to the
        # dict format expected by CSAWriter._build_csa_graphic_elements.
        graphic_elems: list[dict] = []
        for tb in page_data.title_blocks:
            if tb.text and tb.text.strip():
                graphic_elems.append({
                    "type": "text",
                    "text": tb.text,
                    "position": tb.loc_x if tb.loc_x else 0,
                })

        return PageIR(
            page_id=page_id,
            page_name=page_data.page_name or page_id,
            width=page_data.width,
            height=page_data.height,
            instances=instances,
            nets=nets,
            wires=wires,
            ports=ports,
            graphic_elements=graphic_elems,
        )
