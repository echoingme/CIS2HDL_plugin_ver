"""Prefix utilities — RefDes prefix extraction and PHYS_DES_PREFIX expansion.

Provides:
    extract_prefix                          — Extract the alphabetic prefix from a refdes
    expand_candidates_with_phys_des_prefix  — Add cells with matching PHYS_DES_PREFIX

v2.0: Added PASSIVE_TYPES constant and is_passive_prefix() helper for
Phase 1→Phase 2A dispatch in the two-phase matching architecture.
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# Compile once — matches leading alphabetic characters
_RE_REFDES_PREFIX = re.compile(r"^([A-Za-z]+)")


# ── v2.0: Passive component type constants ───────────────────────────────

# Types that trigger Phase 2A deterministic rule matching (PassiveMatcher).
# All other types go to Phase 2B (ActiveMatcher).
PASSIVE_TYPES: frozenset[str] = frozenset({
    "capacitor",
    "resistor",
    "inductor",
    "diode",
    "zener",
    "ferrite_bead",
    "led",
})


def is_passive_prefix(prefix: str = "", type_name: str | None = None) -> bool:
    """Check whether a refdes prefix or type name triggers passive matching.

    Args:
        prefix: RefDes prefix (e.g. "C", "R", "LB") or a type name.
        type_name: Optional explicit type name to check.  If given,
            uses *type_name* directly; otherwise checks *prefix*
            against the passive types set.

    Returns:
        True if this is a passive component that should use Phase 2A
        deterministic rule matching instead of Phase 2B scoring.

    Examples:
        >>> is_passive_prefix("C")
        True
        >>> is_passive_prefix("capacitor")
        True
        >>> is_passive_prefix("U")
        False
        >>> is_passive_prefix(type_name="ferrite_bead")
        True
        >>> is_passive_prefix(type_name="IC")
        False
    """
    if type_name is not None:
        return type_name.lower() in PASSIVE_TYPES
    return prefix.upper() in {"C", "R", "L", "D", "LED", "FB", "LB"}


# ── Public API ────────────────────────────────────────────────────────────


def extract_prefix(refdes: str) -> str:
    """Extract the alphabetic prefix from a reference designator.

    Examples:
        >>> extract_prefix("C460")
        "C"
        >>> extract_prefix("R12")
        "R"
        >>> extract_prefix("TP1")
        "TP"
        >>> extract_prefix("FB3")
        "FB"
        >>> extract_prefix("U5")
        "U"
        >>> extract_prefix("")
        ""

    Args:
        refdes: Reference designator string (e.g. "R1", "C460", "U5").

    Returns:
        Uppercase alphabetic prefix, or empty string if not found.
    """
    if not refdes:
        return ""
    m = _RE_REFDES_PREFIX.match(refdes.upper())
    return m.group(1) if m else ""


# ── PHYS_DES_PREFIX dynamic candidate expansion ──────────────────────────


def expand_candidates_with_phys_des_prefix(
    refdes: str,
    current_candidates: list,
    phys_des_index: dict[str, list[str]],
    all_catalog: dict[str, object],
) -> list:
    """Add cells with matching PHYS_DES_PREFIX to the candidate pool.

    Uses the runtime-scanned ``phys_des_index`` to discover cells whose
    ``chips.prt`` declares a PHYS_DES_PREFIX matching the refdes prefix.
    No hardcoded cross-mappings — direct prefix lookup only.

    This ensures specific chip cells (88e6320, bcm53125, ad7170, etc.)
    are included even when the initial search query was narrow.

    Args:
        refdes: Reference designator (e.g. "U5", "C460").
        current_candidates: Current list of candidate ComponentDef objects.
        phys_des_index: Dict mapping phys_des_prefix → [cell_names].
            Built from ``ComponentDB.phys_des_prefix_index``.
        all_catalog: Dict mapping cell_name (lowercase) → ComponentDef.
            Built from ``ComponentDB.list_all()`` for O(1) lookup.

    Returns:
        Augmented list of candidates (original list plus new additions).
    """
    prefix: str = extract_prefix(refdes)
    if not prefix:
        return current_candidates

    # Direct lookup — no cross-mapping, no hardcoded categories
    matching_cells: set[str] = set()

    if prefix in phys_des_index:
        matching_cells.update(phys_des_index[prefix])

    if not matching_cells:
        return current_candidates

    # Build set of existing library_ids for deduplication
    existing_ids: set[str] = set()
    for c in current_candidates:
        existing_ids.add(getattr(c, "library_id", "").lower())
        existing_ids.add(getattr(c, "part_name", "").lower())

    # Add missing cells to candidates
    added_count: int = 0
    for cell_name in matching_cells:
        if cell_name.lower() not in existing_ids:
            comp = all_catalog.get(cell_name)
            if comp is not None:
                current_candidates.append(comp)
                existing_ids.add(cell_name.lower())
                added_count += 1

    if added_count > 0:
        logger.debug(
            "PHYS_DES_PREFIX expansion for '%s' (prefix=%s): "
            "+%d candidates from phys_des_index",
            refdes,
            prefix,
            added_count,
        )

    return current_candidates
