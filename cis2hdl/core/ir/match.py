"""Matching layer data models — CIS to HDL component matching results."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MatchStrategy(str, Enum):
    """Matching strategy used to find the result."""

    # v1.0 strategies (retained)
    EXACT = "EXACT"  # Exact fingerprint match (confidence >= 0.95)
    JEDEC = "JEDEC"  # JEDEC_TYPE package match (confidence >= 0.95)
    FUZZY = "FUZZY"  # Fuzzy name match (confidence >= 0.75)
    FEATURE = "FEATURE"  # Feature extraction match (confidence >= 0.60)
    VALUE = "VALUE"  # Electrical value match via part.ptf (confidence >= 0.90)
    FALLBACK = "FALLBACK"  # Refdes prefix + body fallback match (confidence >= 0.50)
    MANUAL = "MANUAL"  # Manual user resolution

    # ── v2.0: Phase 2A passive matcher strategies ──
    PASSIVE_EXACT = "PASSIVE_EXACT"              # 层级1: 值+尺寸双精确
    PASSIVE_EXACT_MULTI = "PASSIVE_EXACT_MULTI"  # 层级1: 多候选JEDEC tiebreak
    PASSIVE_VALUE_ONLY = "PASSIVE_VALUE_ONLY"    # 层级2: 值精确尺寸未知
    PASSIVE_VALUE_NEAR = "PASSIVE_VALUE_NEAR"    # 层级3: 值精确尺寸近似
    PASSIVE_SIZE_ONLY = "PASSIVE_SIZE_ONLY"      # 层级4: 尺寸精确值近似
    PASSIVE_PREFIX_ONLY = "PASSIVE_PREFIX_ONLY"  # 层级5: 前缀兜底

    # ── v2.0: Phase 2B active matcher strategy ──
    ACTIVE_WITHIN_TYPE = "ACTIVE_WITHIN_TYPE"    # 类型内评分匹配

    # ── v2.0: below-threshold fallback ──
    NEEDS_REVIEW = "NEEDS_REVIEW"                # 低于阈值，需人工确认

    # ── Phase XII R2: power symbol (GND/DGND/VCC_CIRCLE/…) ──
    POWER_SYMBOL = "POWER_SYMBOL"                # 电源符号确定性匹配（conf=1.0）

    # ── Phase XIV D4: power IC auto-match (by pin count + pin names) ──
    POWER_IC_AUTO = "POWER_IC_AUTO"              # 电源芯片自动匹配（conf≥0.80）


class MatchResult(BaseModel):
    """Result of matching a CIS component to an HDL component library."""

    model_config = ConfigDict(extra="allow")

    confidence: float  # 0.0 to 1.0, v2.0: final_conf = phase1_prior × phase2_within
    strategy: MatchStrategy  # Which matching stage produced this result
    source_library_id: str = ""  # Source component library_id
    target_library_id: str = ""  # Matched target component library_id
    pin_mapping: dict[str, str] = Field(default_factory=dict)  # source_pin -> target_pin
    warnings: list[str] = Field(default_factory=list)  # Any matching warnings
    candidates: list[str] = Field(default_factory=list)
    """Candidate target library_ids for ManualMatchResolver display."""

    # v0.8.2: Report enrichment fields
    cis_value: str = ""
    pst_value: str = ""
    jedec_type: str = ""
    error_note: str = ""

    # v1.0: MultiScorer integration
    extra_data: dict[str, Any] = Field(default_factory=dict)
    """Flexible extra data storage for scoring, notes, etc.

    v2c extra_data key conventions (populated by matcher _enrich_result):
      - ``_source_value``: normalised CIS source value.
      - ``_matched_row``: the exact part.ptf row (dict with keys
        ``package_type`` / ``value`` / ``jedec_type`` / ``description``)
        that PassiveMatcher L1–L4 actually selected.  When present,
        ``hdl_value``/``hdl_footprint``/``hdl_jedec``/``hdl_package_type``
        are derived from THIS row — not from the first value-matching row
        (A.5 0402C-S fix).
      - ``_matched_size``: package size code (e.g. "0603") of the matched row.
      - ``hdl_value``: HDL-side electrical value.
      - ``hdl_footprint``: HDL-side footprint (package_type or jedec_type).
      - ``hdl_jedec``: HDL-side JEDEC_TYPE.
      - ``hdl_package_type``: HDL-side PACKAGE_TYPE (new in v2c).
      - ``hdl_category``: HDL component category.
      - ``hdl_pin_count``: HDL component pin count.
      - ``selected_primitive``: selected primitive part_name.
    """

    # ── v2.0: Two-phase matching architecture fields ──
    phase1_type: str = ""
    """Phase 1 selected type name (e.g. "capacitor", "IC")."""

    phase1_prior_conf: float = 0.0
    """Phase 1 type prior confidence (0.05–1.0)."""

    phase2_strategy_detail: str = ""
    """Phase 2 matching dimension detail (e.g. "value✅ footprint⚠️(default_0603)")."""

    phase2_within_conf: float = 0.0
    """Phase 2 within-type confidence (0.0–1.0)."""

    top3_candidates: list[dict] = Field(default_factory=list)
    """Top-3 cross-type candidates. Each entry:
    {type, library_id, part_name, primitive, final_conf, match_dims,
     value, footprint, jedec, package_type, pin_count} (v2c adds the
     last five keys for candidate-row enrichment, A.4)."""

    @classmethod
    def no_match(cls, source_library_id: str = "") -> "MatchResult":
        """Create a failed match result for manual resolution."""
        return cls(
            confidence=0.0,
            strategy=MatchStrategy.MANUAL,
            source_library_id=source_library_id,
        )
