"""Phase 1.5: Candidate Pool Builder.

Builds type-specific candidate pools from the HDL library based on
Phase 1 type hypotheses.  Each type hypothesis gets a filtered set
of HDL candidates that are likely to belong to that type.

Filtering uses three checks (OR logic):
    1. candidate.category == type_name
    2. candidate.phys_des_prefix matches type_name
    3. candidate.part_name contains type_name
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Iterator

from cis2hdl.core.ir.component import ComponentDef

logger = logging.getLogger(__name__)


def _is_hdl_lib_candidate(comp: Any) -> bool:
    """True when a candidate symbol comes from the hdl_lib scan (R4/Q1).

    Q1 用户决策：匹配函数只能在 hdl_lib 匹配符号，不能使用系统库符号
    （含 ORIGIN）。hdl_scanner 的产物 ``library_id`` 为裸 cell 目录名
    （如 ``capacitor``），``source_format`` 为 ``"HDL"`` —— 默认视为
    hdl_lib 符号；显式引用 ORIGIN / standard / system 等系统库的候选
    一律排除。

    Args:
        comp: ComponentDef 候选。

    Returns:
        True 保留；False 过滤（系统库/ORIGIN 符号）。
    """
    lib = str(getattr(comp, "library_id", "") or "").replace("\\", "/")
    src = str(getattr(comp, "source_file", "") or "").replace("\\", "/")
    fmt = str(getattr(comp, "source_format", "") or "").lower()
    combined = f"{lib}/{src}".lower()
    # 显式排除系统库/ORIGIN 引用
    if any(tok in combined for tok in ("origin", "standard/", "system/",
                                       "ams_cds", "cds.lib")):
        return False
    # hdl_scanner 产物（library_id=裸目录名 / source_format=HDL）→ 通过
    if fmt in ("", "hdl") or "hdl_lib" in combined:
        return True
    return False


@dataclass
class TypeCandidateSet:
    """A typed subset of HDL candidates with prior confidence.

    Attributes:
        type_name: Type name in snake_case (e.g. "capacitor").
        prior_conf: Phase 1 prior confidence for this type.
        candidates: HDL ComponentDef objects belonging to this type.
    """
    type_name: str
    prior_conf: float
    candidates: list[ComponentDef] = field(default_factory=list)


@dataclass
class CandidatePool:
    """Container for type-grouped candidate sets, ordered by priority.

    Attributes:
        type_sets: Ordered list of TypeCandidateSet (highest prior first).
    """
    type_sets: list[TypeCandidateSet] = field(default_factory=list)

    def iter_in_priority_order(self) -> Iterator[TypeCandidateSet]:
        """Iterate type sets in Phase 1 priority order (highest prior first).

        Yields:
            TypeCandidateSet in descending prior_conf order.
        """
        # Already sorted by build(), but re-sort for safety
        sorted_sets: list[TypeCandidateSet] = sorted(
            self.type_sets, key=lambda ts: ts.prior_conf, reverse=True
        )
        yield from sorted_sets

    @property
    def total_candidates(self) -> int:
        """Total number of candidates across all type sets (may have duplicates)."""
        return sum(len(ts.candidates) for ts in self.type_sets)


class CandidatePoolBuilder:
    """Build type-specific candidate pools from the HDL library.

    Phase XVIII R4/Q1: ``hdl_lib_only`` 要求候选只能来自 hdl_lib 扫描
    结果 —— 标准库/系统库符号（含 ORIGIN）不入候选池（用户决策 Q1）。

    Usage:
        builder = CandidatePoolBuilder(db)
        pool = builder.build(type_hypotheses)
        for type_set in pool.iter_in_priority_order():
            print(type_set.type_name, len(type_set.candidates))
    """

    def __init__(self, db: Any, hdl_lib_only: bool = True) -> None:
        """Initialise the builder.

        Args:
            db: ComponentDB instance with list_all() method.
            hdl_lib_only: True 时候选池只保留 hdl_lib 符号（R4/Q1，
                默认开；标准库/系统库符号被过滤）。
        """
        self._db = db
        self._hdl_lib_only: bool = bool(hdl_lib_only)
        # Cache the full candidate list
        self._all_candidates: list[ComponentDef] | None = None

    def build(
        self,
        type_hypotheses: list[Any],  # list[TypeHypothesis]
    ) -> CandidatePool:
        """Build type-grouped candidate pool from hypotheses.

        Args:
            type_hypotheses: Ordered list of TypeHypothesis from Phase 1.

        Returns:
            CandidatePool with type sets ordered by prior_conf.
        """
        if self._all_candidates is None:
            all_candidates = list(self._db.list_all())
            if self._hdl_lib_only:
                all_candidates = [
                    c for c in all_candidates if _is_hdl_lib_candidate(c)
                ]
                logger.debug(
                    "CandidatePool hdl_lib_only: kept %d/%d candidates",
                    len(all_candidates), len(self._db.list_all()),
                )
            self._all_candidates = all_candidates
            logger.debug(
                "CandidatePool: loaded %d total candidates from DB",
                len(self._all_candidates),
            )

        type_sets: list[TypeCandidateSet] = []
        seen_type_names: set[str] = set()

        for hyp in type_hypotheses:
            type_name: str = hyp.type_name.lower()

            # Skip duplicate type names (e.g. from different sources)
            if type_name in seen_type_names:
                continue
            seen_type_names.add(type_name)

            filtered: list[ComponentDef] = self._filter_by_type(
                self._all_candidates, type_name
            )

            type_sets.append(
                TypeCandidateSet(
                    type_name=type_name,
                    prior_conf=hyp.prior_conf,
                    candidates=filtered,
                )
            )

            logger.debug(
                "CandidatePool: type='%s' prior=%.2f → %d candidates",
                type_name, hyp.prior_conf, len(filtered),
            )

        # Sort by prior_conf descending
        type_sets.sort(key=lambda ts: ts.prior_conf, reverse=True)

        pool = CandidatePool(type_sets=type_sets)
        logger.info(
            "CandidatePool built: %d type sets, %d total candidates",
            len(type_sets), pool.total_candidates,
        )
        return pool

    def _filter_by_type(
        self,
        all_candidates: list[ComponentDef],
        type_name: str,
    ) -> list[ComponentDef]:
        """Filter candidates to those matching a given type.

        Uses three matching strategies (OR logic):
            1. candidate.category equals type_name (case-insensitive)
            2. candidate.phys_des_prefix maps to this type
            3. candidate.part_name contains the type_name

        Args:
            all_candidates: Full list of HDL ComponentDef objects.
            type_name: Type name in snake_case (e.g. "capacitor").

        Returns:
            Filtered list of candidates that match the type.
        """
        type_lower: str = type_name.lower()
        matched: list[ComponentDef] = []

        # Build a set of phys_des_prefix mappings for common type equivalences
        _PHYS_DES_TO_TYPE: dict[str, str] = {
            "capacitor": "capacitor",
            "cap": "capacitor",
            "resistor": "resistor",
            "res": "resistor",
            "inductor": "inductor",
            "ind": "inductor",
            "diode": "diode",
            "zener": "zener",
            "led": "led",
            "ic": "ic",
            "connector": "connector",
            "con": "connector",
            "crystal": "crystal",
            "xtal": "crystal",
            "oscillator": "oscillator",
            "transformer": "transformer",
            "switch": "switch",
            "fuse": "fuse",
            "relay": "relay",
            "test_point": "test_point",
            "tp": "test_point",
            "mark": "mark",
            "hole": "hole",
            "ferrite_bead": "ferrite_bead",
            "ferrite": "ferrite_bead",
            "fb": "ferrite_bead",
            "transistor": "transistor",
            "mosfet": "mosfet",
            "voltage_regulator": "voltage_regulator",
            "rj45": "rj45",
            "header": "header",
            "interface": "interface",
            "power": "power",
            "resistor_network": "resistor_network",
            "u": "ic",
            "xs": "connector",
            "j": "connector",
            "h": "connector",
            "sw": "switch",
            "osc": "oscillator",
            "et": "transformer",
            "th": "inductor",
            "k": "relay",
            "q": "transistor",
        }

        for candidate in all_candidates:
            # Check 1: category match
            category: str = (getattr(candidate, "category", "") or "").lower()
            if category == type_lower:
                matched.append(candidate)
                continue

            # Check 2: phys_des_prefix match
            phys_prefix: str = (getattr(candidate, "phys_des_prefix", "") or "").lower()
            mapped_type: str = _PHYS_DES_TO_TYPE.get(phys_prefix, "")
            if mapped_type == type_lower:
                matched.append(candidate)
                continue

            # Check 3: part_name contains type_name
            part_name: str = (getattr(candidate, "part_name", "") or "").lower()
            if type_lower in part_name:
                matched.append(candidate)
                continue

            # Check 4 (extra): library_id path contains type_name
            # e.g. "hdl_lib/capacitor/chip" → type "capacitor"
            lib_id: str = (getattr(candidate, "library_id", "") or "").lower()
            parts: list[str] = lib_id.replace("\\", "/").split("/")
            if type_lower in parts:
                matched.append(candidate)
                continue

        logger.debug(
            "_filter_by_type: '%s' → %d/%d candidates",
            type_name, len(matched), len(all_candidates),
        )
        return matched
