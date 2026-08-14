"""Net name normalization utilities.

Reference: ORCAD_SOURCE_ANALYSIS §4.3 network naming conventions,
§12 EDIF rename syntax.

Note: Net classification functions (classify_net, classify_net_str)
have been moved to cis2hdl.core.net_utils to resolve the utils→core
reverse dependency.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cis2hdl.core.config import Config

# Module-level default — avoids utils→core reverse dependency.
# Matches NetConfig.illegal_chars default in cis2hdl.core.config.
_DEFAULT_ILLEGAL_CHARS: str = "/<>#$()"


def normalize_net_name(name: str, config: "Config | None" = None) -> str:
    """Normalize a net name by removing illegal characters.

    Reference: ORCAD_SOURCE_ANALYSIS §4.3.3 signal naming traps.

    Args:
        name: Raw net name from CIS/EDIF.
        config: Optional Config instance. If None, uses module-level defaults.

    Returns:
        Normalized net name suitable for HDL.
    """
    # Use config-provided illegal chars when available, else module default
    if config is not None:
        illegal_chars = config.net.illegal_chars
    else:
        illegal_chars = _DEFAULT_ILLEGAL_CHARS

    # Strip leading +/- (confused with power polarity)
    cleaned = name.strip()
    while cleaned and cleaned[0] in ("+", "-"):
        cleaned = cleaned[1:]

    # Replace illegal characters with underscore
    for ch in illegal_chars:
        cleaned = cleaned.replace(ch, "_")

    # Collapse multiple underscores
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")

    return cleaned.strip("_")


def edif_rename_to_hdl(rename_str: str) -> str:
    """Map an EDIF (rename X "Y") expression to an HDL net name.

    In EDIF, nets are often renamed from internal aliases to human-readable
    names using the ``(rename <internal> "<display>")`` syntax. This function
    extracts the display name and normalizes it for HDL.

    Reference: ROADMAP B2.11, ORCAD_SOURCE §12.

    Args:
        rename_str: The raw rename string, e.g. ``(rename N12345 "VCC_3V3")``
                    or just the display name ``"VCC_3V3"``.

    Returns:
        Normalized HDL net name string.
    """
    if not rename_str or not rename_str.strip():
        return ""

    s = rename_str.strip()

    # Try to extract quoted display name from rename expression
    # Pattern: (rename <internal> "<display>")
    m = re.match(
        r'\(\s*rename\s+\S+\s+"([^"]*)"\s*\)',
        s,
    )
    if m:
        display = m.group(1)
        return normalize_net_name(display)

    # Try to extract a bare quoted string
    m = re.match(r'"([^"]*)"', s)
    if m:
        return normalize_net_name(m.group(1))

    # Fallback: use as-is after stripping
    return normalize_net_name(s)


def expand_bus_name(name: str) -> list[str]:
    """Expand a CIS bus name to individual HDL net names.

    Supports both descending and ascending bus ranges:
        - ``DATA[7:0]`` → ``["DATA7","DATA6","DATA5","DATA4","DATA3","DATA2","DATA1","DATA0"]``
        - ``ADDR[0:3]`` → ``["ADDR0","ADDR1","ADDR2","ADDR3"]``

    Non-bus names are returned as a single-element list.

    Args:
        name: A net name, possibly with bus syntax ``NAME[HI:LO]``.

    Returns:
        List of individual net names.  If the name does not contain bus
        syntax, returns ``[name]``.
    """
    import re

    m = re.match(r"^(\w+)\[(\d+):(\d+)\]$", name.strip())
    if not m:
        return [name]

    prefix: str = m.group(1)
    hi: int = int(m.group(2))
    lo: int = int(m.group(3))

    if hi >= lo:
        # Descending: DATA[7:0] → DATA7, DATA6, ..., DATA0
        return [f"{prefix}{i}" for i in range(hi, lo - 1, -1)]
    else:
        # Ascending: ADDR[0:3] → ADDR0, ADDR1, ADDR2, ADDR3
        return [f"{prefix}{i}" for i in range(hi, lo + 1)]


def normalize_value(value: str) -> str:
    """Normalize a component value for comparison matching.

    Standardizes electrical component values (resistance, capacitance,
    inductance) to a canonical form for reliable comparison.
    Examples:
        100nF → 100N
        10uF → 10U
        4.7K → 4.7K
        1M → 1M
        0.1UF → 0.1U

    Args:
        value: Raw component value string (e.g. "100nF", "10K", "4.7KΩ").

    Returns:
        Normalized value string suitable for comparison.
    """
    if not value:
        return ""

    v = value.strip().rstrip("*")

    # Try capacitance pattern: numeric + optional unit prefix + optional F
    m = re.match(r"([\d.]+)([pnumk]?)F?", v, re.IGNORECASE)
    if m:
        return m.group(1) + m.group(2).upper()

    # Try resistance/inductance pattern: numeric + optional K/M multiplier
    m = re.match(r"([\d.]+)([KM]?)", v, re.IGNORECASE)
    if m:
        return m.group(1) + m.group(2).upper()

    return v.upper()


def stabilize_un_name(display: str, page: int = 0, cell: str = "",
                      k: int = 0, pin: str = "") -> str:
    """UN$ 自动网名 → 稳定可读名（默认策略 rename，Phase XVIII R3⑤）。

    Cadence 16.6 对 ``UN$5SCAPACITORSI43$2`` 这类自动网名 SIG_NAME
    实测报 deleted（SPCOCN-543 ⑤）；本函数将其规范为稳定可读名
    （``$``→``_``、折叠连续 ``_``、去首尾 ``_``、大写保留），如
    ``"UN$5SCAPACITORSI43$2"`` → ``"UN_5SCAPACITORSI43_2"``。

    数据源铁律（STANDARDS Part I）：仅做字符规范化，不改电气名；
    csv/con 同步由 ``net_utils`` 统一生成，writer 禁止自拼。

    Args:
        display: UN$ 自动网名（如 ``"UN$5SCAPACITORSI43$2"``）。
        page: 页面号（保留参数，供后续策略扩展）。
        cell: cell 名（保留参数）。
        k: 实例序号（保留参数）。
        pin: 引脚号（保留参数）。

    Returns:
        稳定可读网名；不含 ``$`` 的非 UN$ 名原样返回。
    """
    if not display:
        return display
    s = str(display)
    if "$" not in s:
        return s
    s = s.replace("$", "_")
    while "__" in s:
        s = s.replace("__", "_")
    return s.strip("_")


def is_valid_refdes(refdes: str) -> bool:
    """Check if a string is a valid reference designator.

    Valid format: one or two letters followed by digits.
    Examples: R1, C10, U3A, IC42

    Args:
        refdes: Candidate reference designator.

    Returns:
        True if the string looks like a valid refdes.
    """
    if not refdes or len(refdes) < 2:
        return False
    # Must start with letter(s), followed by digit(s)
    i = 0
    while i < len(refdes) and refdes[i].isalpha():
        i += 1
    if i == 0 or i == len(refdes):
        return False
    while i < len(refdes):
        if not refdes[i].isdigit():
            return False
        i += 1
    return True
