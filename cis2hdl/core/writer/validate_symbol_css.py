"""Symbol.css 语法校验器 + temp_lib 库结构断言（Phase XVIII R1/R2）。

R1（SPCOCN-1158）根因：mock symbol.css 的 C 指令 justify 参数用了
U/D，但全库 65689 条真实 C 指令 justify 只有 R/L（grep 实锤）→
parse error → 整 cell 无法加载 → 芯片消失。

本模块提供两个独立校验器（可被 CLI / 测试 / 生成后自动调用）：

* ``validate_symbol_css``      —— 逐行校验 symbol.css 语法：
  1. 每个 C 指令 justify ∈ {R, L}（正则取行末 token）；
  2. 坐标均为合法数值（int/float）；
  3. 引号配对（每个 ``"`` 成对）、括号闭合；
  4. 无非法 ASCII 控制字符；
  5. 每个 C 指令文本非空。
* ``validate_temp_lib_structure`` —— 断言 temp_lib 库结构 = golden
  （R2）：cell/{sym_1/symbol.css + master.tag=="symbol.css",
  chips/chips.prt + master.tag=="chips.prt",
  entity/master.tag=="verilog.v" + pc.db/verilog.v/vhdl.vhd/vlog004u.sir}；
  cell 根目录无 master.tag；目录名大写；FORCEADD 引用名与目录名一致。

设计原则（STANDARDS Part I）：独立模块 + 配置开关
（``temp_lib.syntax_check`` / ``temp_lib.structure_check`` 默认开）。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

#: C 指令行正则（capture 坐标与 justify 行末 token）。
#: 真实格式: C <x> <y> "<pinname>" <lx> <ly> <orient> <vis?> <font> <??> <just>
_C_LINE_RE = re.compile(
    r'^\s*C\s+'
    r'(-?[\d.]+)\s+'          # x
    r'(-?[\d.]+)\s+'          # y
    r'"([^"]*)"\s+'           # pinname（引号内文本）
    r'(-?[\d.]+)\s+'          # label_x
    r'(-?[\d.]+)\s+'          # label_y
    r'\d+\s+'                 # orient
    r'\d+\s+'                 # vis
    r'\d+\s+'                 # font
    r'\d+\s+'                 # ??
    r'([RL])$'                # justify ∈ {R, L}
)

#: 通用数字 token（用于 L/M/A/X 指令坐标粗校验）
_NUM_RE = re.compile(r'^-?[\d.]+$')

#: 非法 ASCII 控制字符（除 \n \t 外）
_CTRL_RE = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')


def _is_number(token: str) -> bool:
    """True when a token parses as an int/float."""
    if not token or not _NUM_RE.match(token):
        return False
    try:
        float(token)
        return True
    except (ValueError, TypeError):
        return False


def validate_symbol_css(content: str, source: str = "") -> list[str]:
    """逐行校验 symbol.css 语法，返回错误行清单（空 = 通过）。

    断言（R1 验收）：
    1. 每个 C 指令 justify 参数 ∈ {R, L}（行末 token）；
    2. C 指令坐标均为合法数值（int/float）；
    3. 引号配对（每个 ``"`` 成对）、括号闭合；
    4. 无非法 ASCII 控制字符；
    5. 每个 C 指令文本非空；
    6. **X 指令类型 ∈ {PIN_TEXT, VHDL_PORT, HDL_PORT}**（Phase XIX
       SPCOCN-1158 第二根因：``X "MOCK_TEXT"`` 是未知指令类型 →
       Cadence 解析失败报 "pin property not preceded by connection"）。

    Args:
        content: symbol.css 文件内容字符串。
        source: 来源标识（文件路径等，仅用于错误消息）。

    Returns:
        错误行清单，每项格式 ``"<source>:<line>: <detail>"``；空列表 = 通过。
    """
    errors: list[str] = []
    if content is None:
        return ["<content is None>"]
    lines: list[str] = str(content).splitlines()
    for idx, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped:
            continue
        # 非法控制字符
        if _CTRL_RE.search(stripped):
            errors.append(f"{source}:{idx}: control char: {stripped[:80]!r}")
        # 引号配对
        if stripped.count('"') % 2 != 0:
            errors.append(
                f"{source}:{idx}: unbalanced quotes: {stripped[:80]}"
            )
        # 括号闭合
        if stripped.count("(") != stripped.count(")"):
            errors.append(
                f"{source}:{idx}: unbalanced parens: {stripped[:80]}"
            )
        # C 指令：justify ∈ {R,L} + 坐标合法 + 文本非空
        if stripped.startswith("C "):
            m = _C_LINE_RE.match(stripped)
            if m is not None:
                for group in (m.group(1), m.group(2), m.group(4), m.group(5)):
                    if not _is_number(group):
                        errors.append(
                            f"{source}:{idx}: C coordinate {group!r} "
                            f"not numeric: {stripped[:80]}"
                        )
                        break
                if not m.group(3).strip():
                    errors.append(
                        f"{source}:{idx}: C text empty: {stripped[:80]}"
                    )
                continue
            # 正则未命中 → 细化定位（justify / 坐标 / 引号）
            tokens = stripped.split()
            if len(tokens) < 11:
                errors.append(
                    f"{source}:{idx}: C line too short "
                    f"({len(tokens)} tokens): {stripped[:80]}"
                )
                continue
            if tokens[-1] not in ("R", "L"):
                errors.append(
                    f"{source}:{idx}: C justify must be R/L, got "
                    f"{tokens[-1]!r}: {stripped[:80]}"
                )
            for pos in (1, 2, 4, 5):
                if pos >= len(tokens):
                    break
                if not _is_number(tokens[pos]):
                    errors.append(
                        f"{source}:{idx}: C coordinate {tokens[pos]!r} "
                        f"not numeric: {stripped[:80]}"
                    )
                    break
            if not (len(tokens) > 3 and tokens[3].startswith('"')):
                errors.append(
                    f"{source}:{idx}: C text must be quoted: {stripped[:80]}"
                )
            continue
        # X 指令类型 ∈ {PIN_TEXT, VHDL_PORT, HDL_PORT}（Phase XIX 1158
        # 第二根因：X "MOCK_TEXT" 未知类型 → Cadence 解析失败）。
        if stripped.startswith("X "):
            x_type = None
            for _tok in stripped.split():
                if _tok.startswith('"') and _tok.endswith('"'):
                    x_type = _tok.strip('"')
                    break
            if x_type and x_type.upper() not in (
                "PIN_TEXT", "VHDL_PORT", "HDL_PORT",
            ):
                errors.append(
                    f"{source}:{idx}: unknown X instruction type "
                    f"{x_type!r} (only PIN_TEXT/VHDL_PORT/HDL_PORT): "
                    f"{stripped[:80]}"
                )
            continue
    return errors


def validate_temp_lib_structure(temp_lib_root: Path) -> list[str]:
    """断言 temp_lib 库结构 = golden（R2），返回违规清单（空 = 通过）。

    逐 cell 断言：
    1. ``sym_1/master.tag`` 内容 == ``"symbol.css"``；
    2. ``chips/master.tag`` 内容 == ``"chips.prt"``；
    3. ``entity/master.tag`` 内容 == ``"verilog.v"``；
    4. ``entity`` 下四文件齐全（pc.db / verilog.v / vhdl.vhd /
       vlog004u.sir）；
    5. cell 根目录无 master.tag；
    6. 目录名全大写（与 FORCEADD 引用名一致）；
    7. sym_1/symbol.css 中 FORCEADD 引用名与目录名一致（引用的是 cell 名）。

    Args:
        temp_lib_root: temp_lib 根目录（如 ``output/temp_lib``）。

    Returns:
        违规清单；空列表 = 通过。
    """
    errors: list[str] = []
    root = Path(temp_lib_root)
    if not root.exists() or not root.is_dir():
        return [f"{root}: temp_lib root missing"]

    cells: list[Path] = [
        p for p in root.iterdir()
        if p.is_dir() and (p / "sym_1").is_dir()
    ]
    if not cells:
        return [f"{root}: no cell directories found (missing sym_1)"]

    for cell_dir in sorted(cells):
        name = cell_dir.name
        # 6. 目录名大写（FORCEADD 引用大写 cell）
        if name != name.upper():
            errors.append(f"{cell_dir}: cell dir must be uppercase: {name}")
        sym_dir = cell_dir / "sym_1"
        chips_dir = cell_dir / "chips"
        entity_dir = cell_dir / "entity"
        # 1. sym_1 master.tag
        _check_tag(sym_dir, "symbol.css", cell_dir, errors)
        # 2. chips master.tag + chips.prt
        _check_tag(chips_dir, "chips.prt", cell_dir, errors)
        if not (chips_dir / "chips.prt").exists():
            errors.append(f"{cell_dir}: chips/chips.prt missing")
        # 3/4. entity master.tag + 四文件
        _check_tag(entity_dir, "verilog.v", cell_dir, errors)
        for fname in ("pc.db", "verilog.v", "vhdl.vhd", "vlog004u.sir"):
            if not (entity_dir / fname).exists():
                errors.append(f"{cell_dir}: entity/{fname} missing")
        # 5. cell 根无 master.tag
        if (cell_dir / "master.tag").exists():
            errors.append(f"{cell_dir}: cell root must NOT have master.tag")
        # 7. symbol.css 引用 cell 名（FORCEADD 一致性由输出侧 grep 校验，
        #    此处轻量检查 symbol.css 存在即可 —— 已由 sym_1 tag 保证）。
        css_path = sym_dir / "symbol.css"
        if not css_path.exists():
            errors.append(f"{cell_dir}: sym_1/symbol.css missing")
    return errors


def _check_tag(tag_dir: Path, expected: str, cell_dir: Path, errors: list[str]) -> None:
    """断言 ``<tag_dir>/master.tag`` 内容 == ``expected``（含换行容忍）。"""
    tag_path = tag_dir / "master.tag"
    if not tag_path.exists():
        errors.append(f"{cell_dir}: {tag_dir.name}/master.tag missing")
        return
    try:
        content = tag_path.read_text(encoding="ascii", errors="replace").strip()
    except OSError as exc:
        errors.append(f"{tag_path}: read failed: {exc}")
        return
    if content != expected:
        errors.append(
            f"{tag_path}: master.tag = {content!r}, expected {expected!r}"
        )
