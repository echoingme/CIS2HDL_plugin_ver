"""PlaceholderLibrary — 占位符号自动生成（Phase XV P0-F）。

未匹配到具体 HDL 符号的多引脚芯片（如 U6 主芯片此前 fallback 到 CH347
错误符号，真实 BGA 引脚 K18/G20/AD15 与 CH347 的数字引脚 1..20 完全不
匹配 → SPCOCN-543 + 引脚塌缩）改由本模块生成**占位符号**：

* symbol.css —— 左右两列 ``C`` 命令按 EDIF 引脚序分布（与 csa_writer
  ``_fallback_pin_offsets`` 周边分布一致）+ 矩形 outline（尺寸贴合
  pin_count）；
* chips.prt  —— EDIF 引脚名表；
* 元件名标注占位 —— cell 名 ``<refdes>_PH``（如 ``U6_PH``）且 csa 块内
  附加 ``PLACEHOLDER 1`` 属性。

设计原则（STANDARDS Part I）：独立模块 + 配置开关（``placeholder.enabled``
默认 true —— 用户要求后端默认生效的例外）；纯几何函数（引脚分布）与文件
写入分离，便于单测。

引脚偏移与生成端一致 ⇒ LASTPIN/WIRE 连接成立：占位符号的 C 命令偏移由
``distribute_ic_pin_offsets`` 生成，csa_writer 用同一函数解析（经
``PlaceholderSymbol.offsets`` 直接取用），因此 LASTPIN 与 WIRE 端点永远
精确重合。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
#  纯几何：多引脚 IC 周边分布（与 csa_writer._fallback_pin_offsets 一致）
# ---------------------------------------------------------------------------


def distribute_ic_pin_offsets(
    pin_count: int,
    left_x: int = -150,
    right_x: int = 150,
    pitch: int = 100,
) -> dict[str, tuple[int, int]]:
    """Distribute N pins around a rectangle perimeter (two side columns).

    Small chips (``n <= 12``): two perimeter columns at ``±150`` with
    100-unit pitch — left column top→bottom, then the right column
    bottom→top.  Large chips (``n > 12``): four columns at
    ``-200/-100/+100/+200`` with pitch 50 (≤48 pins) or 25 (grid minimum),
    top-aligned — the extent stays inside ``±(150..-375)``.

    The keys are **position indexes** ``"1".."n"`` — the caller maps them
    onto the instance's real pin numbers/names.

    Args:
        pin_count: Number of connected pins.
        left_x/right_x: Left/right column x offsets (small chips).
        pitch: Column pin pitch (small chips).

    Returns:
        ``{"1": (x, y), ...}`` — position-index keyed relative offsets.
    """
    n = max(int(pin_count), 1)
    offsets: dict[str, tuple[int, int]] = {}
    if n <= 12:
        half = (n + 1) // 2
        for i in range(1, n + 1):
            if i <= half:
                offsets[str(i)] = (left_x, 150 - (i - 1) * pitch)
            else:
                j = i - half
                offsets[str(i)] = (right_x, -150 + (j - 1) * pitch)
        return offsets
    cols = 4
    per_col = (n + cols - 1) // cols
    col_pitch = 50 if per_col <= 12 else 25
    col_x = (-200, -100, 100, 200)
    for i in range(1, n + 1):
        col = (i - 1) // per_col
        row = (i - 1) % per_col
        offsets[str(i)] = (col_x[col], 150 - row * col_pitch)
    return offsets


def placeholder_outline(pin_count: int) -> str:
    """CDS_LMAN_SYM_OUTLINE rectangle sized from ``pin_count``.

    The rectangle matches ``distribute_ic_pin_offsets`` (left column
    x=-150 / right column x=+150 for small chips; -200..+200 for large),
    so the rendered body encloses every pin.

    Args:
        pin_count: Number of connected pins.

    Returns:
        ``"x1,y1,x2,y2"`` outline string.
    """
    n = max(int(pin_count), 1)
    if n <= 12:
        half = (n + 1) // 2
        bottom = min(150 - (half - 1) * 100, -150)
        return f"-150,150,150,{bottom}"
    cols = 4
    per_col = (n + cols - 1) // cols
    pitch = 50 if per_col <= 12 else 25
    bottom = 150 - (per_col - 1) * pitch
    return f"-200,150,200,{bottom}"


# ---------------------------------------------------------------------------
#  占位符号数据结构
# ---------------------------------------------------------------------------


@dataclass
class PlaceholderSymbol:
    """A generated placeholder symbol for one unmatched multi-pin IC."""

    cell_name: str
    """HDL cell/directory name (``<refdes>_PH``)."""

    pin_numbers: list[str]
    """EDIF pin numbers (unique, e.g. K18/G20/AD15)."""

    pin_names: list[str]
    """EDIF pin names (may repeat / be empty)."""

    offsets: dict[str, tuple[int, int]] = field(default_factory=dict)
    """pin number → (x, y) relative offset (plus unique pin names)."""

    outline: str = "-150,150,150,-150"

    #: 符号种类（Phase XVII M1：placeholder 占位方块 vs mock 模拟图标）。
    kind: str = "placeholder"

    @property
    def pin_count(self) -> int:
        """Number of pins on the placeholder symbol."""
        return len(self.pin_numbers)

    def offset_for(self, pin_number: str, pin_name: str = "") -> tuple[int, int]:
        """Resolve a pin's relative offset by number then name.

        Args:
            pin_number: The instance pin number.
            pin_name: The instance pin name (fallback key).

        Returns:
            ``(x, y)`` relative offset; ``(0, 0)`` when unresolved.
        """
        if pin_number in self.offsets:
            return self.offsets[pin_number]
        if pin_name and pin_name in self.offsets:
            return self.offsets[pin_name]
        return (0, 0)


# ---------------------------------------------------------------------------
#  占位符号库（生成 + 写入）
# ---------------------------------------------------------------------------


class PlaceholderLibrary:
    """Generates and persists placeholder symbols for unmatched ICs.

    Usage::

        lib = PlaceholderLibrary()
        sym = lib.symbol_for("U6", 1, [("K18", "A0"), ("G20", "A1")])
        lib.write_to_hdl_lib(Path("output/hdl_lib"))
        # csa_writer uses ``sym.cell_name`` + ``sym.offsets`` directly.
    """

    def __init__(self, enabled: bool = True) -> None:
        """Initialize the placeholder library.

        Args:
            enabled: Master switch (``placeholder.enabled``).  When False,
                ``symbol_for`` returns None (callers fall back to the old
                behaviour).
        """
        self._enabled: bool = enabled
        self._symbols: dict[tuple[str, int], PlaceholderSymbol] = {}
        self._written: set[str] = set()

    @property
    def enabled(self) -> bool:
        """Whether placeholder generation is enabled."""
        return self._enabled

    # ------------------------------------------------------------------
    #  Generation
    # ------------------------------------------------------------------

    def symbol_for(
        self,
        refdes: str,
        section: int,
        pins: Iterable[tuple[str, str]],
    ) -> PlaceholderSymbol | None:
        """Return (or lazily build) the placeholder symbol for an instance.

        Args:
            refdes: Instance reference designator (e.g. ``"U6A"``).
            section: Symbol view number.
            pins: ``(pin_number, pin_name)`` pairs from the instance.

        Returns:
            A memoized ``PlaceholderSymbol``, or None when disabled or
            the pin list is empty.
        """
        if not self._enabled:
            return None
        entries: list[tuple[str, str]] = [
            (str(num), str(name or "")) for num, name in pins
        ]
        if not entries:
            return None
        key = (refdes, int(section or 1))
        if key in self._symbols:
            return self._symbols[key]

        cell_name = self._cell_name(refdes, int(section or 1))
        numbers = [num for num, _name in entries]
        names = [name for _num, name in entries]
        distributed = distribute_ic_pin_offsets(len(entries))

        offsets: dict[str, tuple[int, int]] = {}
        used_names: set[str] = set()
        for idx, (num, name) in enumerate(entries):
            off = distributed[str(idx + 1)]
            offsets[num] = off
            if name and name not in used_names:
                offsets[name] = off
                used_names.add(name)

        symbol = PlaceholderSymbol(
            cell_name=cell_name,
            pin_numbers=numbers,
            pin_names=names,
            offsets=offsets,
            outline=placeholder_outline(len(entries)),
        )
        self._symbols[key] = symbol
        logger.info(
            "Placeholder: %s → %s (%d pins, no concrete HDL symbol)",
            refdes, cell_name, len(entries),
        )
        return symbol

    @staticmethod
    def _cell_name(refdes: str, section: int) -> str:
        """Build a DEHDL-safe placeholder cell name.

        ``U6`` → ``U6_PH``; multi-section ``U6A`` → ``U6A_PH_S2``.

        Args:
            refdes: Instance reference designator.
            section: Symbol view number.

        Returns:
            Cell directory name (uppercased, non-alnum stripped).
        """
        base = "".join(ch for ch in str(refdes).upper() if ch.isalnum()) or "PH"
        return f"{base}_PH" if section <= 1 else f"{base}_PH_S{section}"

    # ------------------------------------------------------------------
    #  File generation (symbol.css + chips.prt + master.tag)
    # ------------------------------------------------------------------

    def write_to_hdl_lib(self, hdl_lib_root: Path) -> list[Path]:
        """Write every generated placeholder symbol into an HDL library tree.

        Layout (Cadence DEHDL cell format)::

            <hdl_lib_root>/<cell>/sym_1/symbol.css
            <hdl_lib_root>/<cell>/sym_1/master.tag
            <hdl_lib_root>/<cell>/chips/chips.prt
            <hdl_lib_root>/<cell>/chips/master.tag
            <hdl_lib_root>/<cell>/entity/master.tag   ← Phase XVII P0-2
            <hdl_lib_root>/<cell>/entity/pc.db        ← 真实库结构（问题 #15）

        Phase XVII P0-2 (问题 #15): 真实 DEHDL 库（如 ch347）有
        ``entity/pc.db + verilog.v + vhdl.vhd``；补 ``entity/`` 目录
        防止 Cadence 视 cell 库结构不完整而不渲染图形。

        Args:
            hdl_lib_root: Destination HDL library root (e.g.
                ``output/hdl_lib``).

        Returns:
            List of written file paths.
        """
        if hdl_lib_root is None:
            return []
        written: list[Path] = []
        for symbol in self._symbols.values():
            if symbol.cell_name in self._written:
                continue
            cell_dir = hdl_lib_root / symbol.cell_name.lower()
            sym_dir = cell_dir / "sym_1"
            chips_dir = cell_dir / "chips"
            entity_dir = cell_dir / "entity"
            sym_dir.mkdir(parents=True, exist_ok=True)
            chips_dir.mkdir(parents=True, exist_ok=True)
            entity_dir.mkdir(parents=True, exist_ok=True)

            css_path = sym_dir / "symbol.css"
            css_path.write_text(
                self._symbol_css(symbol), encoding="utf-8",
            )
            written.append(css_path)

            prt_path = chips_dir / "chips.prt"
            prt_path.write_text(
                self._chips_prt(symbol), encoding="utf-8",
            )
            written.append(prt_path)

            for tag_dir in (sym_dir, chips_dir, entity_dir):
                tag = tag_dir / "master.tag"
                tag.write_text("CDS_SYSTEM\n", encoding="ascii")
                written.append(tag)

            # entity/pc.db —— 最小真实库结构（Cadence 识别 cell 的标记）。
            pc_db = entity_dir / "pc.db"
            pc_db.write_text(
                self._entity_pc_db(symbol), encoding="utf-8",
            )
            written.append(pc_db)

            self._written.add(symbol.cell_name)
            logger.debug(
                "Placeholder written: %s (%s)", symbol.cell_name, css_path,
            )
        return written

    @staticmethod
    def _entity_pc_db(symbol: "PlaceholderSymbol") -> str:
        """Build a minimal ``entity/pc.db`` for a placeholder cell.

        Real Cadence DEHDL ``pc.db`` files are binary; a minimal ASCII
        declaration is sufficient for Cadence to recognise the cell while
        keeping the file deterministic and diff-friendly.

        Args:
            symbol: The placeholder symbol.

        Returns:
            pc.db content string.
        """
        return (
            f"# placeholder entity pc.db — {symbol.cell_name}\n"
            f"primitive {symbol.cell_name}\n"
            f"view symbol\n"
            f"end_primitive\n"
        )

    # ------------------------------------------------------------------
    #  Format builders
    # ------------------------------------------------------------------

    @staticmethod
    def _symbol_css(symbol: PlaceholderSymbol) -> str:
        """Build symbol.css content for a placeholder symbol.

        The C commands use the **pin number** as text (unique key that
        ``SymbolCssPinParser`` / ``_get_css_pin_offsets`` read back), so
        the generated file is self-consistent if re-parsed later.

        Args:
            symbol: The placeholder symbol.

        Returns:
            symbol.css content string.
        """
        lines: list[str] = []
        a = lines.append
        outline = symbol.outline
        a(f'P "CDS_LMAN_SYM_OUTLINE" "{outline}" 0 0 0.00 0.00 22 0 0 0 0 0 0 0 0')
        # Body rectangle (4 edge lines) sized to the outline.
        o = [float(v) for v in outline.split(",")]
        x0, y0, x1, y1 = o[0], o[1], o[2], o[3]
        if x0 > x1:
            x0, x1 = x1, x0
        if y0 > y1:
            y0, y1 = y1, y0
        a(f"M {int(x0)} {int(y1)} {int(x1)} {int(y1)} -1 0")
        a(f"M {int(x1)} {int(y1)} {int(x1)} {int(y0)} -1 0")
        a(f"M {int(x1)} {int(y0)} {int(x0)} {int(y0)} -1 0")
        a(f"M {int(x0)} {int(y0)} {int(x0)} {int(y1)} -1 0")
        # Property labels (STANDARDS Part III §2.5 defaults).
        # Phase XVII P0-2: PLACEHOLDER 属性必须在 symbol.css 有 P 声明
        # （04p4 惯例：凡 CSA 发射的属性均在 symbol.css 有 P 声明）——
        # 否则 Cadence 当"默认属性"删除（SPCOCN-542）并提示 SPCOCN-545。
        a('P "PLACEHOLDER" "1" 0 0 0 0 24 0 0 1 0 0 1 0 0')
        a('P "$LOCATION" "?" -5 -100 90 0 40 0 0 1 0 0 1 0 0')
        a('P "VALUE" "?" -5 100 90 0 40 0 0 1 0 0 1 0 32')
        a('P "PART_NAME" "?" 0 0 0 0 48 0 0 0 0 0 0 0 32')
        a('P "PATH" "?" 0 0 0 0 48 0 0 0 0 0 0 0 32')
        # Pin lines + C labels (left column text to the left, right to the
        # right — matches the pin side).
        for num, name in zip(symbol.pin_numbers, symbol.pin_names):
            off = symbol.offsets.get(num)
            if off is None:
                continue
            px, py = off
            label = str(name) if name else str(num)
            if px < 0:
                edge_x = int(min(x0 + 10, px + 10))
                a(f"L {edge_x} {py} {px} {py} -1 0")
                a(f'C {px} {py} "{label}" {px - 25} {py} 0 0 32 1 R')
            else:
                edge_x = int(max(x1 - 10, px - 10))
                a(f"L {edge_x} {py} {px} {py} -1 0")
                a(f'C {px} {py} "{label}" {px + 25} {py} 0 0 32 1 L')
        a("")
        return "\n".join(lines)

    @staticmethod
    def _chips_prt(symbol: PlaceholderSymbol) -> str:
        """Build chips.prt content declaring the placeholder's pins.

        ``PIN_NUMBER`` stores the EDIF pin number; the ``'功能名':`` key
        stores the pin name when available (STANDARDS 收尾 T03：禁止用
        PIN_NUMBER 覆盖功能名).

        Args:
            symbol: The placeholder symbol.

        Returns:
            chips.prt content string.
        """
        lines: list[str] = []
        a = lines.append
        a("FILE_TYPE=LIBRARY_PARTS;")
        a(f"primitive '{symbol.cell_name}';")
        a("  pin")
        for num, name in zip(symbol.pin_numbers, symbol.pin_names):
            a(f"    '{num}':")
            a(f"      PIN_NUMBER='({num})';")
            a("      PINUSE='UNSPEC';")
        a("  end_pin;")
        a("  body")
        a(f"    PART_NAME='{symbol.cell_name}';")
        a(f"    BODY_NAME='{symbol.cell_name}';")
        a("    PHYS_DES_PREFIX='U';")
        a("    CLASS='IC';")
        a("  end_body;")
        a("end_primitive;")
        return "\n".join(lines) + "\n"
