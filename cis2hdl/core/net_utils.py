"""ISCF network classification and net name utilities.

Reference: ORCAD_SOURCE_ANALYSIS §11.3 ISCF 4-class network model.

Moved from utils/naming.py to resolve the utils→core reverse dependency.
"""

from __future__ import annotations

import re

from cis2hdl.core.config import config as cfg
from cis2hdl.core.ir.design import NetCategory

# Ground net names from central config (ISCF classification)
GROUND_NET_NAMES: set[str] = cfg.net.ground_names

# Power net prefixes from central config
POWER_NET_PREFIXES: tuple[str, ...] = cfg.net.power_prefixes


def classify_net(name: str) -> NetCategory:
    """Classify a net name using ISCF 4-class model.

    Args:
        name: Net name (e.g., "GND", "VCC_3V3", "NET_01", "DATA[7:0]")

    Returns:
        NetCategory enum: FLAT, GROUND, POWER, or BUS
    """
    upper = name.upper().strip()

    # Ground detection
    if upper in GROUND_NET_NAMES:
        return NetCategory.GROUND

    # Bus detection (contains array syntax)
    if "[" in name or "(" in name:
        return NetCategory.BUS

    # Power detection: +V style nets (e.g., +5V, +12V, +3.3V)
    # These are common in CIS/EDIF to denote positive supply rails.
    if re.match(r'^\+?\d+(\.\d+)?V', upper):
        return NetCategory.POWER

    # Power detection via prefix matching
    for prefix in POWER_NET_PREFIXES:
        if upper.startswith(prefix):
            return NetCategory.POWER

    return NetCategory.FLAT


def classify_net_str(net_name: str) -> str:
    """Classify a net name and return ISCF category as a string.

    Reference: ROADMAP B2.11 — ISCF 4-class model.

    Args:
        net_name: Net name to classify.

    Returns:
        One of: 'FLAT', 'GROUND', 'POWER', 'BUS'
    """
    category = classify_net(net_name)
    return category.name  # NetCategory enum name matches these strings


# =============================================================================
#  Phase XI P0-B: DEHDL naming conventions (system_design.md C.5)
#
#  Three-state net naming shared by ALL writers (con / xcon / csv / cpc / csa):
#    * CSV display name : "GND_POWER\\g" / "UN$1$CAPACITOR$I12$1" / original
#    * con internal name: lowercase, '$'->'_', strip '\\g', local adds 'pageN_'
#    * SIG_NAME         : identical to CSV display name
# =============================================================================


def con_name(name: str, page: int = 0, local: bool = False) -> str:
    """Convert a raw net name to the DEHDL con/xcon internal name.

    Rules (system_design.md A.1.2 / C.5):
      - lowercase
      - '\\g' suffix removed (global marker lives in the scope flag, not the name)
      - '$' -> '_'  (auto-net separator)
      - when *local* (scope=0), prefix with ``page<page>_`` so same-named
        local nets on different pages never collide

    Args:
        name: Raw net name (e.g. "GND_POWER\\g", "$27N444466", "CLK2SLAVE_OUTN_5G").
        page: Physical page number (1-based); only used when local=True.
        local: True to produce the page-scoped local form.

    Returns:
        The DEHDL internal net name (never empty for a non-empty input).
    """
    n = name.strip()
    if not n:
        return ""
    # OrCAD EDIF escape prefix
    if n.startswith("&"):
        n = n[1:]
    # Strip global marker
    n = n.replace("\\g", "").replace("\\G", "")
    # '$' -> '_', backslashes removed, lowercase
    n = n.replace("$", "_").replace("\\", "_").lower()
    # A leading '$' would produce a leading '_'; strip it (auto-net names
    # like "$27N444466" → "27n444466", matching the 8367 unnamed_* style)
    n = n.lstrip("_")
    if local and page:
        n = f"page{page}_{n}"
    return n


def csv_display_name(name: str, is_global: bool = False) -> str:
    """Return the CSV display name for a net (system_design.md A.3.2).

    Rules:
      - global (scope=2) power/ground nets keep the ``\\g`` suffix
        (e.g. ``GND_POWER\\g``, ``VCC_12\\g``) and are uppercased
      - everything else is returned verbatim (auto-nets stay ``UN$...``
        when the source already used that spelling, otherwise the raw name)

    Args:
        name: Raw net name (e.g. "GND_POWER", "UN$1$CAPACITOR$I12$1").
        is_global: True for scope=2 global nets.

    Returns:
        Display name for the CSV network list / CSA SIG_NAME label.
    """
    n = name.strip()
    if not n:
        return ""
    if n.startswith("&"):
        n = n[1:]
    if is_global:
        body = n.replace("\\g", "").replace("\\G", "")
        return f"{body.upper()}\\g"
    return n


def auto_net_csv_name(con_internal: str) -> str:
    """Convert a con internal auto-net name back to the CSV ``UN$`` spelling.

    ``unnamed_1_capacitor_i12_1`` -> ``UN$1$CAPACITOR$I12$1``

    Only meaningful for names produced by :func:`auto_net_con_name`.  Names
    that do not match the ``unnamed_<page>_<cell>_<i>_<pin>`` pattern are
    returned unchanged (they are not auto-nets).

    Args:
        con_internal: DEHDL internal net name.

    Returns:
        CSV ``UN$...`` display name, or the input unchanged.
    """
    m = re.match(r"^unnamed_(\d+)_(.+)_i(\d+)_(.+)$", con_internal)
    if not m:
        return con_internal
    page, cell, k, pin = m.groups()
    return f"UN${page}${cell.upper()}$I{k}${pin}"


def auto_net_con_name(page: int, cell: str, k: int, pin: str) -> str:
    """Build the con internal auto-net name from page/cell/instance/pin.

    ``(1, "capacitor", 12, "1")`` -> ``unnamed_1_capacitor_i12_1``

    Args:
        page: Physical page number.
        cell: Lowercase HDL cell name.
        k: Page-local instance index.
        pin: Pin number.

    Returns:
        Con internal auto-net name.
    """
    return f"unnamed_{page}_{cell.lower()}_i{k}_{pin}"


def is_power_or_ground(name: str) -> bool:
    """True when a net name classifies as POWER or GROUND (ISCF)."""
    return classify_net(name) in (NetCategory.POWER, NetCategory.GROUND)


def net_scope(name: str, appears_on_pages: int, page_num: int = 0) -> tuple[int, str]:
    """Compute con net scope and internal name for a net.

    Scope rules (system_design.md A.1.2 / C.6):
      - scope=2 (global): power/ground nets that appear on >= 2 pages,
        bare name, no page prefix
      - scope=0 (local): every other net; name carries ``page<page>_`` prefix

    Args:
        name: Raw net name.
        appears_on_pages: Number of distinct pages this net is seen on.
        page_num: Physical page number used for the local prefix.

    Returns:
        (scope_int, con_internal_name)
    """
    is_pwr = is_power_or_ground(name)
    if is_pwr and appears_on_pages >= 2:
        return (2, con_name(name))
    return (0, con_name(name, page=page_num, local=True))
