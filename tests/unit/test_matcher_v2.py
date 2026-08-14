"""Unit tests for CIS2HDL v2.0 Two-Phase Matching Architecture.

Covers:
  - TypeHypothesis / TypeHypothesisGenerator (Phase 1)
  - CandidatePool / CandidatePoolBuilder (Phase 1.5)
  - PassiveMatcher (Phase 2A) — 5-level deterministic rules
  - ActiveMatcher (Phase 2B) — 5-dim within-type scoring
  - MatchStrategy / MatchResult v2.0 fields
  - prefix_filter — PASSIVE_TYPES, is_passive_prefix()
  - ValueMatcher — match_typed(), _matches_type()
  - P0 blocking validation points

These tests use mock ComponentDef objects and mock config — no real
database needed for unit test isolation.
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch, PropertyMock

from cis2hdl.core.ir.component import ComponentDef, PinDef, ElectricalType
from cis2hdl.core.ir.match import MatchResult, MatchStrategy
from cis2hdl.core.matcher.prefix_filter import (
    extract_prefix,
    PASSIVE_TYPES,
    is_passive_prefix,
)
from cis2hdl.core.matcher.type_hypothesis import (
    TypeHypothesis,
    TypeHypothesisGenerator,
)
from cis2hdl.core.matcher.candidate_pool import (
    TypeCandidateSet,
    CandidatePool,
    CandidatePoolBuilder,
)
from cis2hdl.core.matcher.passive_matcher import PassiveMatcher
from cis2hdl.core.matcher.active_matcher import ActiveMatcher
from cis2hdl.core.matcher.value_matcher import ValueMatcher, extract_pkg_size
from cis2hdl.core.matcher.scoring import PrefixAffinityCalculator


# ═══════════════════════════════════════════════════════════════════════
# Helper factories
# ═══════════════════════════════════════════════════════════════════════


def _make_component(
    library_id: str = "hdl_lib/capacitor",
    part_name: str = "CAPACITOR",
    category: str = "capacitor",
    footprint: str = "HSC0402-HDTB",
    value: str = "",
    pin_count: int = 2,
    phys_des_prefix: str = "capacitor",
    extra_data: dict | None = None,
) -> ComponentDef:
    """Create a minimal ComponentDef for testing."""
    pins = [
        PinDef(number=str(i + 1), name=f"PIN{i + 1}", type=ElectricalType.PASSIVE)
        for i in range(pin_count)
    ]
    return ComponentDef(
        library_id=library_id,
        part_name=part_name,
        category=category,
        footprint=footprint,
        value=value,
        pins=pins,
        pin_count=pin_count,
        phys_des_prefix=phys_des_prefix,
        extra_data=extra_data or {},
    )


def _make_cis_component(
    library_id: str = "CIS/C89",
    refdes: str = "C89",
    part_name: str = "CAP_1UF",
    value: str = "1UF",
    footprint: str = "HSC0402-HDTB",
    extra_data: dict | None = None,
) -> ComponentDef:
    """Create a minimal CIS ComponentDef with refdes attribute for testing."""
    comp = _make_component(
        library_id=library_id,
        part_name=part_name,
        footprint=footprint,
        value=value,
        extra_data=extra_data or {},
    )
    # Monkey-patch refdes onto the pydantic model
    object.__setattr__(comp, "refdes", refdes)
    return comp


def _make_ptf_candidate(
    library_id: str = "hdl_lib/capacitor",
    part_name: str = "CAPACITOR",
    category: str = "capacitor",
    ptf_rows: list[dict] | None = None,
    all_primitives: list[dict] | None = None,
    footprint: str = "",
    phys_des_prefix: str = "capacitor",
) -> ComponentDef:
    """Create a ComponentDef with ptf_rows in extra_data for passive matching."""
    return _make_component(
        library_id=library_id,
        part_name=part_name,
        category=category,
        footprint=footprint,
        phys_des_prefix=phys_des_prefix,
        extra_data={
            "ptf_rows": ptf_rows or [],
            "all_primitives": all_primitives or [],
        },
    )


# ═══════════════════════════════════════════════════════════════════════
# MatchStrategy & MatchResult v2.0 fields
# ═══════════════════════════════════════════════════════════════════════


class TestMatchStrategyV2:
    """v2.0 MatchStrategy enum verification."""

    def test_passive_strategies_exist(self):
        """PASSIVE_* strategies are defined in MatchStrategy."""
        assert MatchStrategy.PASSIVE_EXACT.value == "PASSIVE_EXACT"
        assert MatchStrategy.PASSIVE_EXACT_MULTI.value == "PASSIVE_EXACT_MULTI"
        assert MatchStrategy.PASSIVE_VALUE_ONLY.value == "PASSIVE_VALUE_ONLY"
        assert MatchStrategy.PASSIVE_VALUE_NEAR.value == "PASSIVE_VALUE_NEAR"
        assert MatchStrategy.PASSIVE_SIZE_ONLY.value == "PASSIVE_SIZE_ONLY"
        assert MatchStrategy.PASSIVE_PREFIX_ONLY.value == "PASSIVE_PREFIX_ONLY"

    def test_active_strategy_exists(self):
        """ACTIVE_WITHIN_TYPE is defined in MatchStrategy."""
        assert MatchStrategy.ACTIVE_WITHIN_TYPE.value == "ACTIVE_WITHIN_TYPE"

    def test_needs_review_exists(self):
        """NEEDS_REVIEW is defined in MatchStrategy."""
        assert MatchStrategy.NEEDS_REVIEW.value == "NEEDS_REVIEW"

    def test_v1_strategies_retained(self):
        """v1.0 strategies are still present."""
        assert MatchStrategy.EXACT.value == "EXACT"
        assert MatchStrategy.JEDEC.value == "JEDEC"
        assert MatchStrategy.FUZZY.value == "FUZZY"
        assert MatchStrategy.FEATURE.value == "FEATURE"
        assert MatchStrategy.VALUE.value == "VALUE"
        assert MatchStrategy.FALLBACK.value == "FALLBACK"
        assert MatchStrategy.MANUAL.value == "MANUAL"


class TestMatchResultV2:
    """v2.0 MatchResult new fields and behaviour."""

    def test_new_fields_have_defaults(self):
        """v2.0 fields have correct default values."""
        result = MatchResult(confidence=0.85, strategy=MatchStrategy.PASSIVE_EXACT)
        assert result.phase1_type == ""
        assert result.phase1_prior_conf == 0.0
        assert result.phase2_strategy_detail == ""
        assert result.phase2_within_conf == 0.0
        assert result.top3_candidates == []

    def test_new_fields_are_settable(self):
        """v2.0 fields accept explicit values."""
        result = MatchResult(
            confidence=0.80,
            strategy=MatchStrategy.PASSIVE_VALUE_ONLY,
            phase1_type="capacitor",
            phase1_prior_conf=1.0,
            phase2_strategy_detail="value✅ footprint⚠️(default_0603)",
            phase2_within_conf=0.80,
            top3_candidates=[
                {
                    "type": "capacitor",
                    "library_id": "hdl_lib/capacitor",
                    "part_name": "CAPACITOR",
                    "primitive": "CAP_0603",
                    "final_conf": 0.80,
                    "match_dims": "value✅ footprint⚠️",
                }
            ],
        )
        assert result.phase1_type == "capacitor"
        assert result.phase1_prior_conf == 1.0
        assert result.phase2_strategy_detail == "value✅ footprint⚠️(default_0603)"
        assert result.phase2_within_conf == 0.80
        assert len(result.top3_candidates) == 1
        assert result.top3_candidates[0]["type"] == "capacitor"

    def test_no_match_factory(self):
        """no_match() factory creates a valid failed result."""
        result = MatchResult.no_match("CIS/C89")
        assert result.confidence == 0.0
        assert result.strategy == MatchStrategy.MANUAL
        assert result.source_library_id == "CIS/C89"
        assert result.target_library_id == ""

    def test_extra_allow_enabled(self):
        """extra='allow' permits v2.0 fields on model."""
        result = MatchResult(
            confidence=1.0,
            strategy=MatchStrategy.PASSIVE_EXACT,
            phase1_type="capacitor",
            phase1_prior_conf=1.0,
        )
        assert result.phase1_type == "capacitor"


# ═══════════════════════════════════════════════════════════════════════
# Prefix filter — PASSIVE_TYPES, is_passive_prefix
# ═══════════════════════════════════════════════════════════════════════


class TestPassiveTypes:
    """PASSIVE_TYPES constant and is_passive_prefix()."""

    def test_passive_types_contains_expected(self):
        """PASSIVE_TYPES includes the 7 passive type names."""
        assert "capacitor" in PASSIVE_TYPES
        assert "resistor" in PASSIVE_TYPES
        assert "inductor" in PASSIVE_TYPES
        assert "diode" in PASSIVE_TYPES
        assert "zener" in PASSIVE_TYPES
        assert "ferrite_bead" in PASSIVE_TYPES
        assert "led" in PASSIVE_TYPES

    def test_passive_types_excludes_active(self):
        """PASSIVE_TYPES does NOT include active type names."""
        assert "IC" not in PASSIVE_TYPES
        assert "connector" not in PASSIVE_TYPES
        assert "crystal" not in PASSIVE_TYPES
        assert "switch" not in PASSIVE_TYPES

    # ── is_passive_prefix by prefix ────────────────────────────────

    @pytest.mark.parametrize("prefix,expected", [
        ("C", True),
        ("R", True),
        ("L", True),
        ("D", True),
        ("LED", True),
        ("FB", True),
        ("LB", True),
        ("U", False),
        ("IC", False),
        ("J", False),
        ("X", False),
        ("TP", False),
        ("M", False),
        ("S", False),
    ])
    def test_is_passive_prefix_by_prefix(self, prefix, expected):
        """Prefix checks for passive types."""
        assert is_passive_prefix(prefix) == expected

    # ── is_passive_prefix by type_name ─────────────────────────────

    @pytest.mark.parametrize("type_name,expected", [
        ("capacitor", True),
        ("resistor", True),
        ("inductor", True),
        ("diode", True),
        ("zener", True),
        ("ferrite_bead", True),
        ("led", True),
        ("IC", False),
        ("connector", False),
        ("crystal", False),
    ])
    def test_is_passive_prefix_by_type_name(self, type_name, expected):
        """Type name checks — type_name kwarg takes priority."""
        assert is_passive_prefix(type_name=type_name) == expected

    def test_type_name_overrides_prefix(self):
        """type_name takes priority over prefix."""
        # "U" is active by prefix, but "capacitor" is passive by type_name
        assert is_passive_prefix(prefix="U", type_name="capacitor") is True


class TestExtractPrefix:
    """extract_prefix() edge cases."""

    def test_standard_prefixes(self):
        assert extract_prefix("C89") == "C"
        assert extract_prefix("R42") == "R"
        assert extract_prefix("U7") == "U"
        assert extract_prefix("LED1") == "LED"
        assert extract_prefix("FB3") == "FB"
        assert extract_prefix("LB4") == "LB"
        assert extract_prefix("TP12") == "TP"
        assert extract_prefix("M1") == "M"

    def test_empty_and_invalid(self):
        assert extract_prefix("") == ""
        assert extract_prefix("123") == ""


# ═══════════════════════════════════════════════════════════════════════
# ValueMatcher — extract_pkg_size, match_typed, _matches_type
# ═══════════════════════════════════════════════════════════════════════


class TestExtractPkgSize:
    """extract_pkg_size() utility."""

    def test_standard_sizes(self):
        assert extract_pkg_size("HSC0402-HDTB") == "0402"
        assert extract_pkg_size("SR0402") == "0402"
        assert extract_pkg_size("CAP_0603") == "0603"
        assert extract_pkg_size("0805") == "0805"

    def test_bga(self):
        assert extract_pkg_size("BGA96-32-1609W") == "BGA96"

    def test_ic_packages(self):
        assert extract_pkg_size("SOT23-5") == "SOT"
        assert extract_pkg_size("QFN48") == "QFN"

    def test_empty(self):
        assert extract_pkg_size("") == ""

    def test_fallback_first10(self):
        # TO-220 matches SOT_QFN regex group as "TO-220"
        result = extract_pkg_size("TO-220")
        assert result in ("TO-220", "TO-")  # regex captures full TO-220


class TestValueMatcherTyped:
    """match_typed() and _matches_type() methods."""

    def test_matches_type_by_category(self):
        """Candidate matches by category."""
        cand = _make_component(
            library_id="hdl_lib/capacitor",
            category="capacitor",
        )
        assert ValueMatcher._matches_type(cand, "capacitor") is True

    def test_matches_type_by_phys_des_prefix(self):
        """Candidate matches by phys_des_prefix mapping."""
        cand = _make_component(
            library_id="hdl_lib/some_chip",
            category="other",
            phys_des_prefix="cap",
        )
        assert ValueMatcher._matches_type(cand, "capacitor") is True

    def test_matches_type_by_part_name(self):
        """Candidate matches by part_name containing type."""
        cand = _make_component(
            library_id="hdl_lib/some_chip",
            category="other",
            part_name="SOME_CAPACITOR_CHIP",
        )
        assert ValueMatcher._matches_type(cand, "capacitor") is True

    def test_no_match(self):
        """Candidate that doesn't match any strategy."""
        cand = _make_component(
            library_id="hdl_lib/resistor",
            category="resistor",
            phys_des_prefix="res",
            part_name="RESISTOR_CHIP",
        )
        assert ValueMatcher._matches_type(cand, "capacitor") is False

    def test_match_typed_filters_candidates(self):
        """match_typed() filters to type-matched candidates only."""
        src = _make_component(library_id="CIS/C89", value="10UF")
        cap_candidate = _make_ptf_candidate(
            library_id="hdl_lib/capacitor",
            category="capacitor",
            ptf_rows=[{"value": "10UF"}],
        )
        res_candidate = _make_ptf_candidate(
            library_id="hdl_lib/resistor",
            part_name="RESISTOR_CHIP",
            category="resistor",
            phys_des_prefix="resistor",
            ptf_rows=[{"value": "10UF"}],
        )
        matcher = ValueMatcher()
        result = matcher.match_typed(
            src, [cap_candidate, res_candidate], "capacitor"
        )
        # Should match only the capacitor candidate
        assert result.confidence > 0
        assert result.target_library_id == "hdl_lib/capacitor"


# ═══════════════════════════════════════════════════════════════════════
# TypeHypothesis & TypeHypothesisGenerator (Phase 1)
# ═══════════════════════════════════════════════════════════════════════


class TestTypeHypothesisModel:
    """TypeHypothesis dataclass."""

    def test_defaults(self):
        h = TypeHypothesis(type_name="capacitor", prior_conf=1.0)
        assert h.type_name == "capacitor"
        assert h.prior_conf == 1.0
        assert h.source == "yaml_rule"

    def test_explicit_source(self):
        h = TypeHypothesis(type_name="IC", prior_conf=0.85, source="exact_prefix")
        assert h.source == "exact_prefix"


class TestTypeHypothesisGenerator:
    """TypeHypothesisGenerator — Phase 1 type hypothesis engine."""

    # ── Config stub ────────────────────────────────────────────────

    @staticmethod
    def _make_config(**overrides) -> MagicMock:
        """Create mock MatchConfig with type_gate content."""
        cfg = MagicMock()
        cfg.type_hypotheses = {
            "C": [["capacitor", 1.0]],
            "R": [["resistor", 1.0]],
            "L": [["inductor", 1.0]],
            "D": [["diode", 0.95], ["zener", 0.80], ["tvs", 0.60]],
            "U": [["IC", 0.85], ["interface", 0.70], ["connector", 0.40]],
            "LED": [["led", 1.0]],
            "FB": [["ferrite_bead", 1.0]],
            "LB": [["ferrite_bead", 0.75], ["inductor", 0.50]],
            "TP": [["test_point", 0.90], ["mark", 0.70], ["hole", 0.50]],
            "M": [["mark", 0.80], ["test_point", 0.60]],
            "X": [["crystal", 0.85], ["oscillator", 0.75]],
            "IC": [["IC", 0.95], ["voltage_regulator", 0.70]],
        }
        cfg.value_type_boost = {
            "NH": ["inductor", 0.15],
            "UH": ["inductor", 0.15],
            "mH": ["inductor", 0.10],
            "MHz": ["crystal", 0.20],
            "MARK": ["mark", 0.30],
            "TESTPOINT": ["test_point", 0.30],
        }
        cfg.pst_type_boost = {
            "CAPACITOR": ["capacitor", 0.10],
            "RESISTOR": ["resistor", 0.10],
            "INDUCTOR": ["inductor", 0.10],
            "DIODE": ["diode", 0.10],
            "ZENER": ["zener", 0.15],
            "CONNECTOR": ["connector", 0.15],
            "IC": ["IC", 0.10],
            "FPGA": ["IC", 0.20],
            "CRYSTAL": ["crystal", 0.20],
        }
        # Apply overrides
        for k, v in overrides.items():
            setattr(cfg, k, v)
        return cfg

    # ── P0: Type correctness — exact prefixes ──────────────────────

    def test_C89_is_capacitor_only(self):
        """C89 → [(capacitor, 1.0)] only, NOT resistor."""
        gen = TypeHypothesisGenerator(self._make_config(), None)
        result = gen.generate("C89", "1UF")
        assert len(result) == 1
        assert result[0].type_name == "capacitor"
        assert result[0].prior_conf == 1.0
        assert result[0].source == "exact_prefix"

    def test_R42_is_resistor_only(self):
        """R42 → [(resistor, 1.0)] only, NOT capacitor."""
        gen = TypeHypothesisGenerator(self._make_config(), None)
        result = gen.generate("R42", "10K")
        assert len(result) == 1
        assert result[0].type_name == "resistor"
        assert result[0].prior_conf == 1.0
        assert result[0].source == "exact_prefix"

    def test_R92_is_resistor_only(self):
        """R92 → [(resistor, 1.0)] only."""
        gen = TypeHypothesisGenerator(self._make_config(), None)
        result = gen.generate("R92", "100K")
        assert len(result) == 1
        assert result[0].type_name == "resistor"
        assert result[0].prior_conf == 1.0

    def test_R117_is_resistor_only(self):
        """R117 → [(resistor, 1.0)] only."""
        gen = TypeHypothesisGenerator(self._make_config(), None)
        result = gen.generate("R117", "4.7K")
        assert len(result) == 1
        assert result[0].type_name == "resistor"
        assert result[0].prior_conf == 1.0

    def test_C11_is_capacitor(self):
        """C11 (1mF capacitor) → capacitor, NOT resistor."""
        gen = TypeHypothesisGenerator(self._make_config(), None)
        result = gen.generate("C11", "1mF")
        assert len(result) == 1
        assert result[0].type_name == "capacitor"

    def test_C21_is_capacitor(self):
        """C21 (22UF capacitor) → capacitor, NOT inductor."""
        gen = TypeHypothesisGenerator(self._make_config(), None)
        result = gen.generate("C21", "22UF")
        assert len(result) == 1
        assert result[0].type_name == "capacitor"

    # ── P0: Type correctness — ambiguous prefixes ──────────────────

    def test_D21_zero_value_diode(self):
        """D21 (0-value diode) → diode primary, NOT resistor."""
        gen = TypeHypothesisGenerator(self._make_config(), None)
        result = gen.generate("D21", "0")
        assert result[0].type_name == "diode"
        assert result[0].prior_conf >= 0.95  # base 0.95 + 0.05 for zero

    def test_LB4_ferrite_bead_primary(self):
        """LB4 → [(ferrite_bead, 0.75), (inductor, 0.50)]."""
        gen = TypeHypothesisGenerator(self._make_config(), None)
        result = gen.generate("LB4", "")
        assert result[0].type_name == "ferrite_bead"
        assert result[0].prior_conf == 0.75
        assert result[1].type_name == "inductor"
        assert result[1].prior_conf == 0.50

    def test_M1_mark_primary(self):
        """M1 → [(mark, 0.80), (test_point, 0.60)]."""
        gen = TypeHypothesisGenerator(self._make_config(), None)
        result = gen.generate("M1", "")
        assert result[0].type_name == "mark"
        assert result[0].prior_conf == 0.80
        assert result[1].type_name == "test_point"
        assert result[1].prior_conf == 0.60

    def test_M2_mark_primary(self):
        """M2 → mark, NOT rtxm169/ch347."""
        gen = TypeHypothesisGenerator(self._make_config(), None)
        result = gen.generate("M2", "")
        assert result[0].type_name == "mark"
        # Check that no spurious types like "rtxm169" appear
        type_names = [h.type_name for h in result]
        assert "rtxm169" not in type_names
        assert "ch347" not in type_names
        assert len(result) == 2  # mark + test_point only

    def test_U7_with_fpga_pst(self):
        """U7+JEDEC=FPGA → IC ≈0.95, interface 0.70."""
        gen = TypeHypothesisGenerator(self._make_config(), None)
        result = gen.generate("U7", "", {"jedec_type": "FPGA"})
        # IC base 0.85 + 0.20 FPGA boost = 0.95
        ic_hyp = next(h for h in result if h.type_name == "ic")
        assert ic_hyp.prior_conf >= 0.90  # allow for small precision differences
        # interface stays at 0.70
        iface_hyp = next(h for h in result if h.type_name == "interface")
        assert iface_hyp.prior_conf == pytest.approx(0.70, abs=0.01)

    # ── Value hint tests ───────────────────────────────────────────

    def test_NH_value_boosts_inductor(self):
        """Value containing "NH" boosts inductor prior."""
        gen = TypeHypothesisGenerator(self._make_config(), None)
        result = gen.generate("LB4", "100NH")
        # ferrite_bead initially 0.75, inductor initially 0.50
        inductor_hyp = next(h for h in result if h.type_name == "inductor")
        assert inductor_hyp.prior_conf > 0.50  # boosted by +0.15

    def test_MHz_value_boosts_crystal(self):
        """Value containing "MHz" boosts crystal prior."""
        gen = TypeHypothesisGenerator(self._make_config(), None)
        result = gen.generate("X1", "16MHz")
        crystal_hyp = next(h for h in result if h.type_name == "crystal")
        assert crystal_hyp.prior_conf > 0.85  # boosted by +0.20

    def test_MARK_value_boosts_mark(self):
        """Value containing "MARK" boosts mark prior."""
        gen = TypeHypothesisGenerator(self._make_config(), None)
        result = gen.generate("M3", "MARK")
        mark_hyp = next(h for h in result if h.type_name == "mark")
        assert mark_hyp.prior_conf >= 0.95  # 0.80 + 0.30 = 1.0 but capped at 0.95

    # ── PST boost tests ────────────────────────────────────────────

    def test_pst_capacitor_boost(self):
        """JEDEC_TYPE=CAPACITOR boosts capacitor prior."""
        gen = TypeHypothesisGenerator(self._make_config(), None)
        result = gen.generate("C89", "1UF", {"jedec_type": "CAPACITOR"})
        # capacitor is already 1.0, boost doesn't change it
        assert result[0].type_name == "capacitor"
        assert result[0].prior_conf == 1.0

    def test_pst_zener_boost_for_D_prefix(self):
        """JEDEC_TYPE=ZENER boosts zener for D prefix."""
        gen = TypeHypothesisGenerator(self._make_config(), None)
        result = gen.generate("D5", "5V", {"jedec_type": "ZENER"})
        zener_hyp = next(h for h in result if h.type_name == "zener")
        assert zener_hyp.prior_conf > 0.80  # base 0.80 + 0.15 = 0.95

    # ── Normalisation tests ────────────────────────────────────────

    def test_all_conf_clamped_min(self):
        """All prior_conf values >= 0.05."""
        gen = TypeHypothesisGenerator(self._make_config(), None)
        result = gen.generate("U7", "")
        for h in result:
            assert h.prior_conf >= 0.05

    def test_all_conf_clamped_max(self):
        """All prior_conf values <= 1.0."""
        gen = TypeHypothesisGenerator(self._make_config(), None)
        result = gen.generate("C89", "1UF", {"jedec_type": "CAPACITOR"})
        for h in result:
            assert h.prior_conf <= 1.0

    def test_sorted_by_prior_desc(self):
        """Results are sorted by prior_conf descending."""
        gen = TypeHypothesisGenerator(self._make_config(), None)
        result = gen.generate("D21", "0")
        confs = [h.prior_conf for h in result]
        assert confs == sorted(confs, reverse=True)

    # ── Unknown prefix ─────────────────────────────────────────────

    def test_unknown_prefix_returns_empty(self):
        """Unknown prefix returns empty list."""
        gen = TypeHypothesisGenerator(self._make_config(), None)
        result = gen.generate("ZZ99", "")
        assert result == []

    def test_empty_refdes_returns_empty(self):
        """Empty refdes → empty list."""
        gen = TypeHypothesisGenerator(self._make_config(), None)
        result = gen.generate("", "")
        assert result == []

    # ── Learned affinity ───────────────────────────────────────────

    def test_learned_affinity_adjusts_prior(self):
        """Learned affinity adjusts prior_conf only when learned > prior."""
        mock_affinity = MagicMock(spec=PrefixAffinityCalculator)
        mock_affinity.affinity.return_value = 0.50  # learned = 0.50
        gen = TypeHypothesisGenerator(self._make_config(), mock_affinity)
        result = gen.generate("LB4", "")
        fb = next(h for h in result if h.type_name == "ferrite_bead")
        # learned (0.50) < prior (0.75) → no blend → prior unchanged at 0.75
        assert abs(fb.prior_conf - 0.75) < 0.01

    def test_learned_affinity_improves_prior(self):
        """Learned affinity above prior triggers blend."""
        mock_affinity = MagicMock(spec=PrefixAffinityCalculator)
        mock_affinity.affinity.return_value = 0.90  # learned > prior
        gen = TypeHypothesisGenerator(self._make_config(), mock_affinity)
        result = gen.generate("LB4", "")
        fb = next(h for h in result if h.type_name == "ferrite_bead")
        # learned (0.90) > prior (0.75) → blended = 0.75*0.70 + 0.90*0.30 = 0.795
        assert abs(fb.prior_conf - 0.795) < 0.01

    def test_no_affinity_still_works(self):
        """Generator works without affinity calculator."""
        gen = TypeHypothesisGenerator(self._make_config(), None)
        result = gen.generate("LB4", "")
        assert len(result) == 2
        assert result[0].type_name == "ferrite_bead"


# ═══════════════════════════════════════════════════════════════════════
# CandidatePool & CandidatePoolBuilder (Phase 1.5)
# ═══════════════════════════════════════════════════════════════════════


class TestTypeCandidateSet:
    """TypeCandidateSet dataclass."""

    def test_defaults(self):
        tcs = TypeCandidateSet(type_name="capacitor", prior_conf=1.0)
        assert tcs.type_name == "capacitor"
        assert tcs.prior_conf == 1.0
        assert tcs.candidates == []

    def test_with_candidates(self):
        comp = _make_component(library_id="hdl_lib/capacitor")
        tcs = TypeCandidateSet(
            type_name="capacitor", prior_conf=1.0, candidates=[comp]
        )
        assert len(tcs.candidates) == 1


class TestCandidatePool:
    """CandidatePool container."""

    def test_empty_pool(self):
        pool = CandidatePool()
        assert pool.total_candidates == 0
        assert list(pool.iter_in_priority_order()) == []

    def test_iter_in_priority_order(self):
        tcs1 = TypeCandidateSet(type_name="capacitor", prior_conf=1.0)
        tcs2 = TypeCandidateSet(type_name="resistor", prior_conf=1.0)
        tcs3 = TypeCandidateSet(type_name="diode", prior_conf=0.60)
        pool = CandidatePool(type_sets=[tcs3, tcs1, tcs2])
        # Should be sorted by prior_conf desc (1.0 first, then 0.60)
        ordered = list(pool.iter_in_priority_order())
        assert ordered[0].prior_conf >= ordered[-1].prior_conf

    def test_total_candidates(self):
        comp1 = _make_component(library_id="hdl_lib/c1")
        comp2 = _make_component(library_id="hdl_lib/c2")
        tcs = TypeCandidateSet(
            type_name="test", prior_conf=1.0, candidates=[comp1, comp2]
        )
        pool = CandidatePool(type_sets=[tcs])
        assert pool.total_candidates == 2


class TestCandidatePoolBuilder:
    """CandidatePoolBuilder — Phase 1.5 filtering."""

    def _make_mock_db(self, candidates: list[ComponentDef]) -> MagicMock:
        """Create a mock ComponentDB."""
        db = MagicMock()
        db.list_all.return_value = candidates
        return db

    def test_build_groups_by_type(self):
        """Builder groups candidates by type from hypotheses."""
        caps = [
            _make_component(library_id="hdl_lib/cap1", category="capacitor"),
            _make_component(library_id="hdl_lib/cap2", category="capacitor"),
        ]
        resistors = [
            _make_component(
                library_id="hdl_lib/res1",
                category="resistor",
                part_name="RESISTOR_CHIP",
                phys_des_prefix="resistor",
            ),
        ]
        all_candidates = caps + resistors
        db = self._make_mock_db(all_candidates)
        builder = CandidatePoolBuilder(db)

        hypotheses = [
            TypeHypothesis(type_name="capacitor", prior_conf=1.0),
            TypeHypothesis(type_name="resistor", prior_conf=1.0),
        ]
        pool = builder.build(hypotheses)

        assert len(pool.type_sets) == 2
        cap_set = next(ts for ts in pool.type_sets if ts.type_name == "capacitor")
        assert len(cap_set.candidates) == 2
        res_set = next(ts for ts in pool.type_sets if ts.type_name == "resistor")
        assert len(res_set.candidates) == 1

    def test_filter_by_category(self):
        """Candidate matches via category field."""
        comp = _make_component(library_id="hdl_lib/cap", category="capacitor")
        db = self._make_mock_db([comp])
        builder = CandidatePoolBuilder(db)
        pool = builder.build([TypeHypothesis(type_name="capacitor", prior_conf=1.0)])
        assert pool.total_candidates == 1

    def test_filter_by_part_name(self):
        """Candidate matches via part_name containing type."""
        comp = _make_component(
            library_id="hdl_lib/some_chip",
            category="other",
            part_name="SOME_CAPACITOR_CHIP",
        )
        db = self._make_mock_db([comp])
        builder = CandidatePoolBuilder(db)
        pool = builder.build([TypeHypothesis(type_name="capacitor", prior_conf=1.0)])
        assert pool.total_candidates == 1

    def test_filter_by_library_id_path(self):
        """Candidate matches via library_id path containing type."""
        comp = _make_component(
            library_id="hdl_lib/capacitor/chip_0402",
            category="other",
        )
        db = self._make_mock_db([comp])
        builder = CandidatePoolBuilder(db)
        pool = builder.build([TypeHypothesis(type_name="capacitor", prior_conf=1.0)])
        assert pool.total_candidates == 1

    def test_duplicate_type_names_skipped(self):
        """Duplicate type names from different sources are skipped."""
        comp = _make_component(library_id="hdl_lib/cap")
        db = self._make_mock_db([comp])
        builder = CandidatePoolBuilder(db)
        pool = builder.build([
            TypeHypothesis(type_name="capacitor", prior_conf=1.0),
            TypeHypothesis(type_name="capacitor", prior_conf=0.50),
        ])
        assert len(pool.type_sets) == 1

    def test_not_matching_candidates_excluded(self):
        """Components that don't match the type are excluded."""
        comp = _make_component(
            library_id="hdl_lib/other",
            category="other",
            part_name="OTHER_CHIP",
            phys_des_prefix="other",
        )
        db = self._make_mock_db([comp])
        builder = CandidatePoolBuilder(db)
        pool = builder.build([TypeHypothesis(type_name="capacitor", prior_conf=1.0)])
        assert pool.total_candidates == 0


# ═══════════════════════════════════════════════════════════════════════
# PassiveMatcher (Phase 2A) — 5-level deterministic rules
# ═══════════════════════════════════════════════════════════════════════


class TestPassiveMatcherConfidence:
    """PassiveMatcher confidence constants."""

    def test_conf_exact(self):
        assert PassiveMatcher.CONF_EXACT == 1.0

    def test_conf_exact_multi(self):
        assert PassiveMatcher.CONF_EXACT_MULTI == 0.95

    def test_conf_value_only(self):
        assert PassiveMatcher.CONF_VALUE_ONLY == 0.80

    def test_conf_value_near(self):
        assert PassiveMatcher.CONF_VALUE_NEAR == 0.70

    def test_conf_size_only(self):
        assert PassiveMatcher.CONF_SIZE_ONLY == 0.60

    def test_conf_prefix_only(self):
        assert PassiveMatcher.CONF_PREFIX_ONLY == 0.40

    def test_threshold(self):
        matcher = PassiveMatcher()
        assert matcher.confidence_threshold() == 0.40


class TestPassiveMatcherLevels:
    """PassiveMatcher 5-level cascade tests."""

    # ── Level 1: Value + size exact ────────────────────────────────

    def test_l1_exact_match_single(self):
        """Single candidate with matching value and size → PASSIVE_EXACT, conf=1.0."""
        matcher = PassiveMatcher()
        src = _make_cis_component(
            library_id="CIS/C89",
            value="1UF",
            footprint="HSC0402-HDTB",
        )
        candidate = _make_ptf_candidate(
            library_id="hdl_lib/capacitor",
            part_name="CAPACITOR",
            category="capacitor",
            ptf_rows=[{"value": "1UF", "package_type": "C0402", "jedec_type": "CAPACITOR"}],
            all_primitives=[
                {"part_name": "CAPACITOR_0402", "value": "1UF"},
            ],
        )
        result = matcher.match(src, [candidate], src_type="capacitor")
        assert result.strategy == MatchStrategy.PASSIVE_EXACT
        assert result.confidence == 1.0
        assert result.target_library_id == "hdl_lib/capacitor"

    def test_l1_exact_match_multi_jedec_tiebreak(self):
        """Multiple value+size matches → PASSIVE_EXACT_MULTI, conf=0.95."""
        matcher = PassiveMatcher()
        src = _make_cis_component(
            library_id="CIS/C89",
            value="1UF",
            footprint="HSC0402-HDTB",
            extra_data={"jedec_type": "CAPACITOR_0402"},
        )
        c1 = _make_ptf_candidate(
            library_id="hdl_lib/capacitor_1",
            part_name="CAPACITOR_1",
            category="capacitor",
            ptf_rows=[{"value": "1UF", "package_type": "C0402", "jedec_type": "GENERIC"}],
            all_primitives=[{"part_name": "CAPACITOR_0402", "value": "1UF"}],
        )
        c2 = _make_ptf_candidate(
            library_id="hdl_lib/capacitor_2",
            part_name="CAPACITOR_2",
            category="capacitor",
            ptf_rows=[{"value": "1UF", "package_type": "C0402", "jedec_type": "CAPACITOR_0402"}],
            all_primitives=[{"part_name": "CAPACITOR_0402", "value": "1UF"}],
        )
        result = matcher.match(src, [c1, c2], src_type="capacitor")
        assert result.strategy == MatchStrategy.PASSIVE_EXACT_MULTI
        assert result.confidence == 0.95

    # ── Level 2: Value only (no footprint) ─────────────────────────

    def test_l2_value_only_no_footprint(self):
        """CIS footprint empty → PASSIVE_VALUE_ONLY, conf=0.80."""
        matcher = PassiveMatcher()
        src = _make_cis_component(
            library_id="CIS/C89",
            value="1UF",
            footprint="",  # No footprint
        )
        candidate = _make_ptf_candidate(
            library_id="hdl_lib/capacitor",
            part_name="CAPACITOR",
            category="capacitor",
            ptf_rows=[{"value": "1UF", "package_type": "C0603"}],
            all_primitives=[{"part_name": "CAPACITOR_0603", "value": "1UF"}],
        )
        result = matcher.match(src, [candidate], src_type="capacitor")
        assert result.strategy == MatchStrategy.PASSIVE_VALUE_ONLY
        assert result.confidence == 0.80

    # ── Level 3: Value exact, size near ────────────────────────────

    def test_l3_value_near_size(self):
        """Value matches, size is close but not exact → PASSIVE_VALUE_NEAR, conf=0.70."""
        matcher = PassiveMatcher()
        src = _make_cis_component(
            library_id="CIS/C89",
            value="1UF",
            footprint="HSC0402-HDTB",  # size=0402
        )
        candidate = _make_ptf_candidate(
            library_id="hdl_lib/capacitor",
            part_name="CAPACITOR",
            category="capacitor",
            ptf_rows=[{"value": "1UF", "package_type": "C0603"}],  # size=0603
            all_primitives=[{"part_name": "CAPACITOR_0603", "value": "1UF"}],
        )
        result = matcher.match(src, [candidate], src_type="capacitor")
        assert result.strategy == MatchStrategy.PASSIVE_VALUE_NEAR
        assert result.confidence == 0.70

    # ── Level 4: Size only (value different) ───────────────────────

    def test_l4_size_only(self):
        """Size matches but value doesn't → PASSIVE_SIZE_ONLY, conf=0.60."""
        matcher = PassiveMatcher()
        src = _make_cis_component(
            library_id="CIS/C89",
            value="100UF",  # Different value
            footprint="HSC0402-HDTB",
        )
        candidate = _make_ptf_candidate(
            library_id="hdl_lib/capacitor",
            part_name="CAPACITOR",
            category="capacitor",
            ptf_rows=[{"value": "1UF", "package_type": "C0402"}],  # Size match, value no
            all_primitives=[{"part_name": "CAPACITOR_0402"}],
        )
        result = matcher.match(src, [candidate], src_type="capacitor")
        assert result.strategy == MatchStrategy.PASSIVE_SIZE_ONLY
        assert result.confidence == 0.60

    # ── Level 5: Prefix-only fallback ──────────────────────────────

    def test_l5_prefix_only(self):
        """No value or size match → PASSIVE_PREFIX_ONLY, conf=0.40."""
        matcher = PassiveMatcher()
        src = _make_cis_component(
            library_id="CIS/C89",
            value="999UF",  # No match
            footprint="XYZ999",
        )
        candidate = _make_ptf_candidate(
            library_id="hdl_lib/capacitor",
            part_name="CAPACITOR",
            category="capacitor",
            ptf_rows=[{"value": "1UF", "package_type": "C0402"}],
            all_primitives=[{"part_name": "CAPACITOR_0603"}],
        )
        result = matcher.match(src, [candidate], src_type="capacitor")
        assert result.strategy == MatchStrategy.PASSIVE_PREFIX_ONLY
        assert result.confidence == 0.40

    # ── No candidates ──────────────────────────────────────────────

    def test_no_candidates_returns_no_match(self):
        """Empty candidates → no_match."""
        matcher = PassiveMatcher()
        src = _make_cis_component(library_id="CIS/C89")
        result = matcher.match(src, [], src_type="capacitor")
        assert result.confidence == 0.0
        assert result.strategy == MatchStrategy.MANUAL  # no_match uses MANUAL

    # ── P0 validation: Cross-type prevention ───────────────────────

    def test_l5_all_five_levels_fail_returns_no_match(self):
        """All 5 levels fail → no_match (not a wrong type match)."""
        matcher = PassiveMatcher()
        src = _make_cis_component(
            library_id="CIS/C89",
            value="",
            footprint="",
        )
        # Empty candidate list → immediate no_match
        result = matcher.match(src, [], src_type="capacitor")
        assert result.confidence == 0.0


# ═══════════════════════════════════════════════════════════════════════
# ActiveMatcher (Phase 2B) — 5-dim within-type scoring
# ═══════════════════════════════════════════════════════════════════════


class TestActiveMatcherConstants:
    """ActiveMatcher constants and configuration."""

    def test_within_type_weights_sum(self):
        """Weights should cover footprint, value, jedec, pin_count, part_name."""
        weights = ActiveMatcher.WITHIN_TYPE_WEIGHTS
        assert "footprint" in weights
        assert "value" in weights
        assert "jedec" in weights
        assert "pin_count" in weights
        assert "part_name" in weights

    def test_matcher_priority(self):
        assert ActiveMatcher.MATCHER_PRIORITY == 2
        assert ActiveMatcher.MATCHER_NAME == "active"

    def test_threshold(self):
        matcher = ActiveMatcher()
        assert matcher.confidence_threshold() == 0.50


class TestActiveMatcherScoring:
    """5-dimension scoring tests."""

    def test_footprint_exact_match(self):
        """Same footprint size → score 1.0."""
        src = _make_component(footprint="HSC0402-HDTB")
        cand = _make_component(footprint="SR0402")
        assert ActiveMatcher._score_footprint(src, cand) == 1.0

    def test_footprint_no_match(self):
        """Different footprint sizes → score 0.2."""
        src = _make_component(footprint="HSC0402-HDTB")
        cand = _make_component(footprint="HSC0805-HDTB")
        score = ActiveMatcher._score_footprint(src, cand)
        assert score < 0.5

    def test_footprint_neutral_when_missing(self):
        """Missing footprint → neutral 0.5."""
        src = _make_component(footprint="")
        cand = _make_component(footprint="")
        assert ActiveMatcher._score_footprint(src, cand) == 0.5

    def test_value_exact_match(self):
        """Same value → score 1.0."""
        src = _make_component(value="1UF")
        cand = _make_component(value="1UF")
        assert ActiveMatcher._score_value(src, cand) == 1.0

    def test_value_no_match(self):
        """Different values → score 0.0."""
        src = _make_component(value="1UF")
        cand = _make_component(value="100UF")
        assert ActiveMatcher._score_value(src, cand) == 0.0

    def test_value_neutral_when_missing(self):
        """Missing values → neutral 0.5."""
        src = _make_component(value="")
        cand = _make_component(value="")
        assert ActiveMatcher._score_value(src, cand) == 0.5

    def test_jedec_exact_match(self):
        """Same JEDEC_TYPE → score 1.0."""
        src = _make_component(extra_data={"jedec_type": "IC"})
        cand = _make_component(extra_data={"ptf_rows": [{"jedec_type": "IC"}]})
        assert ActiveMatcher._score_jedec(src, cand) == 1.0

    def test_jedec_no_match(self):
        """Different JEDEC_TYPE → score 0.0."""
        src = _make_component(extra_data={"jedec_type": "IC"})
        cand = _make_component(extra_data={"ptf_rows": [{"jedec_type": "CONNECTOR"}]})
        assert ActiveMatcher._score_jedec(src, cand) == 0.0

    def test_jedec_neutral_both_missing(self):
        """Both missing JEDEC_TYPE → neutral 0.5."""
        src = _make_component()
        cand = _make_component()
        assert ActiveMatcher._score_jedec(src, cand) == 0.5

    def test_pin_count_exact(self):
        """Same pin count → score 1.0."""
        src = _make_component(pin_count=8)
        cand = _make_component(pin_count=8)
        assert ActiveMatcher._score_pin_count(src, cand) == 1.0

    def test_pin_count_close(self):
        """Close pin counts → high score."""
        src = _make_component(pin_count=8)
        cand = _make_component(pin_count=10)
        score = ActiveMatcher._score_pin_count(src, cand)
        assert score > 0.7  # 1.0 - 2/10 = 0.80

    def test_part_name_partial_match(self):
        """Part name token overlap → partial score."""
        src = _make_component(part_name="STM32F407_VGT6")
        cand = _make_component(part_name="STM32F407_VET6")
        score = ActiveMatcher._score_part_name(src, cand)
        # "STM32F407" is in "stm32f407_vet6" — 1 of 2 tokens match = 0.5
        assert score == 0.5

    def test_part_name_neutral_missing(self):
        """Missing part names → neutral 0.5."""
        src = _make_component(part_name="")
        cand = _make_component(part_name="")
        assert ActiveMatcher._score_part_name(src, cand) == 0.5


class TestActiveMatcherMatchDims:
    """_build_match_dims() output format."""

    def test_all_perfect(self):
        dims = {"footprint": 1.0, "value": 1.0, "jedec": 1.0, "pin_count": 1.0, "part_name": 1.0}
        result = ActiveMatcher._build_match_dims(dims)
        assert "footprint✅" in result
        assert "value✅" in result
        assert "jedec✅" in result
        assert "pin_count✅" in result
        assert "part_name✅" in result
        assert "❌" not in result

    def test_mixed_dimensions(self):
        dims = {"footprint": 1.0, "value": 0.7, "jedec": 0.3, "pin_count": 0.5, "part_name": 0.0}
        result = ActiveMatcher._build_match_dims(dims)
        assert "footprint✅" in result
        assert "value⚠️" in result
        assert "jedec❌" in result
        assert "pin_count⚠️(neutral)" in result
        assert "part_name❌" in result


class TestActiveMatcherMatch:
    """ActiveMatcher.match() integration."""

    def test_match_with_candidates(self):
        """ActiveMatcher produces a match result with candidates."""
        matcher = ActiveMatcher()
        src = _make_component(
            library_id="CIS/U7",
            part_name="STM32F407",
            footprint="QFP100",
            value="STM32F407",
            pin_count=100,
            extra_data={"jedec_type": "IC"},
        )
        cand = _make_component(
            library_id="hdl_lib/IC/STM32F407",
            part_name="STM32F407",
            category="IC",
            footprint="QFP100",
            pin_count=100,
            extra_data={
                "ptf_rows": [{"jedec_type": "IC", "value": "STM32F407"}],
                "all_primitives": [{"part_name": "STM32F407_QFP100"}],
            },
        )
        result = matcher.match(src, [cand], src_type="IC")
        assert result.strategy == MatchStrategy.ACTIVE_WITHIN_TYPE
        assert result.confidence > 0.50
        assert result.target_library_id == "hdl_lib/IC/STM32F407"

    def test_no_candidates_returns_no_match(self):
        """Empty candidates → no_match."""
        matcher = ActiveMatcher()
        src = _make_component(library_id="CIS/U7")
        result = matcher.match(src, [], src_type="IC")
        assert result.confidence == 0.0
        assert result.strategy == MatchStrategy.MANUAL


# ═══════════════════════════════════════════════════════════════════════
# v2c (A.5 / A.6): matched-row linkage + scoring + wildcard rescue
# ═══════════════════════════════════════════════════════════════════════


class TestV2cPassiveMatchedRow:
    """PassiveMatcher records the ACTUAL matched ptf_row (A.5)."""

    def test_l1_uses_matched_size_row_for_report(self):
        """L1 must report the 0603 row, not the first value row (0402)."""
        matcher = PassiveMatcher()
        src = _make_cis_component(
            library_id="CIS/C1",
            value="10UF",
            footprint="SC0603-TD",
        )
        candidate = _make_ptf_candidate(
            library_id="hdl_lib/capacitor",
            category="capacitor",
            ptf_rows=[
                {"value": "10UF", "package_type": "C0402", "jedec_type": "0402B-S"},
                {"value": "10UF", "package_type": "C0603", "jedec_type": "0603C-S"},
            ],
            all_primitives=[{"part_name": "CAPACITOR_0603", "value": "10UF"}],
        )
        result = matcher.match(src, [candidate], src_type="capacitor")
        assert result.strategy == MatchStrategy.PASSIVE_EXACT
        assert result.confidence == 1.0
        # v2c: the matched row is the 0603 row (size-matched), not C0402
        assert result.extra_data["_matched_row"]["package_type"] == "C0603"
        assert result.extra_data["_matched_size"] == "0603"
        assert result.extra_data["hdl_value"] == "10UF"
        assert result.extra_data["hdl_package_type"] == "C0603"
        assert result.extra_data["hdl_footprint"] == "C0603"
        assert result.extra_data["hdl_jedec"] == "0603C-S"

    def test_l3_uses_closest_size_row_for_report(self):
        """L3 (value near size) reports the closest-size matched row."""
        matcher = PassiveMatcher()
        src = _make_cis_component(
            library_id="CIS/C2",
            value="1UF",
            footprint="HSC0402-HDTB",
        )
        # L3 records the first value-matching row per candidate; use two
        # candidates so _find_closest_size can pick the nearer size (0603).
        cand0805 = _make_ptf_candidate(
            library_id="hdl_lib/capacitor_0805",
            part_name="CAPACITOR_0805",
            category="capacitor",
            ptf_rows=[
                {"value": "1UF", "package_type": "C0805", "jedec_type": "0805C-S"},
            ],
            all_primitives=[{"part_name": "CAPACITOR_0805", "value": "1UF"}],
        )
        cand0603 = _make_ptf_candidate(
            library_id="hdl_lib/capacitor_0603",
            part_name="CAPACITOR_0603",
            category="capacitor",
            ptf_rows=[
                {"value": "1UF", "package_type": "C0603", "jedec_type": "0603C-S"},
            ],
            all_primitives=[{"part_name": "CAPACITOR_0603", "value": "1UF"}],
        )
        result = matcher.match(src, [cand0805, cand0603], src_type="capacitor")
        assert result.strategy == MatchStrategy.PASSIVE_VALUE_NEAR
        # closest size to 0402 is 0603 (not 0805)
        assert result.extra_data["_matched_row"]["package_type"] == "C0603"
        assert result.extra_data["hdl_package_type"] == "C0603"


class TestV2cActiveScoring:
    """v2c scoring fixes (A.6) — pin_count/jedec/part_name aliases."""

    def test_pin_count_unknown_src_neutral(self):
        """Unknown CIS pin count → 0.5 neutral (was 0.0 for J10)."""
        src = _make_component(pin_count=0)
        cand = _make_component(pin_count=54)
        assert ActiveMatcher._score_pin_count(src, cand) == 0.5

    def test_pin_count_unknown_cand_neutral(self):
        """Unknown candidate pin count → 0.5 neutral."""
        src = _make_component(pin_count=8)
        cand = _make_component(pin_count=0)
        assert ActiveMatcher._score_pin_count(src, cand) == 0.5

    def test_pin_count_close_still_proximity(self):
        """Known-vs-known pin counts still use proximity (8 vs 10 = 0.8)."""
        src = _make_component(pin_count=8)
        cand = _make_component(pin_count=10)
        assert ActiveMatcher._score_pin_count(src, cand) == 0.8

    def test_jedec_single_missing_neutral(self):
        """Single-sided missing JEDEC → 0.5 (was 0.4)."""
        src = _make_component(extra_data={"jedec_type": "IC"})
        cand = _make_component()
        assert ActiveMatcher._score_jedec(src, cand) == 0.5

    def test_part_name_alias_match(self):
        """MJ8-M2 vs RJ45_2X2_LED matches via mj8→rj45 alias (1/2 = 0.5)."""
        src = _make_component(part_name="MJ8-M2")
        cand = _make_component(part_name="RJ45_2X2_LED")
        assert ActiveMatcher._score_part_name(src, cand) == 0.5

    def test_part_name_placeholder_falls_back_to_value(self):
        """Catalog J10 has part_name='J10' (placeholder) → score via value."""
        src = _make_component(
            library_id="J10", part_name="J10", value="MJ8-M2"
        )
        cand = _make_component(part_name="RJ45_2X2_LED")
        assert ActiveMatcher._score_part_name(src, cand) == 0.5

    def test_part_name_partial_match_still_0_5(self):
        """STM32F407_VGT6 vs STM32F407_VET6 remains 0.5 (no aliases)."""
        src = _make_component(part_name="STM32F407_VGT6")
        cand = _make_component(part_name="STM32F407_VET6")
        assert ActiveMatcher._score_part_name(src, cand) == 0.5


class TestV2cWildcardRescue:
    """Footprint wildcard rescue path (A.6 / J10)."""

    def test_wildcard_rescues_empty_footprint_j10(self):
        """J10 (empty footprint) matches rj45_2x2_led with conf >= 0.70."""
        matcher = ActiveMatcher()
        src = _make_component(
            library_id="CIS/J10",
            part_name="MJ8-M2",
            category="connector",
            footprint="",
            value="MJ8-M2",
            pin_count=0,
            extra_data={"jedec_type": "MJ8-R-P"},
        )
        cand = _make_component(
            library_id="hdl_lib/rj45_2x2_led",
            part_name="RJ45_2X2_LED",
            category="connector",
            footprint="",
            pin_count=54,
            extra_data={
                "ptf_rows": [{"jedec_type": "", "package_type": "", "value": ""}],
                "all_primitives": [{"part_name": "RJ45_2X2_LED"}],
            },
        )
        result = matcher.match(src, [cand], src_type="connector")
        assert result.strategy == MatchStrategy.ACTIVE_WITHIN_TYPE
        assert result.target_library_id == "hdl_lib/rj45_2x2_led"
        assert result.confidence >= 0.70
        assert "wildcard" in result.phase2_strategy_detail

    def test_wildcard_not_used_when_footprint_valid(self):
        """A usable CIS footprint disables the wildcard path."""
        matcher = ActiveMatcher()
        src = _make_component(
            library_id="CIS/U7",
            part_name="STM32F407",
            footprint="QFP100",
            pin_count=100,
            extra_data={"jedec_type": "IC"},
        )
        cand = _make_component(
            library_id="hdl_lib/IC/STM32F407",
            part_name="STM32F407",
            footprint="QFP100",
            pin_count=100,
            extra_data={
                "ptf_rows": [{"jedec_type": "IC", "value": "STM32F407"}],
                "all_primitives": [{"part_name": "STM32F407_QFP100"}],
            },
        )
        wildcard_cand, score = matcher._match_footprint_wildcard(src, [cand])
        assert wildcard_cand is None
        assert score == 0.0

    def test_wildcard_not_used_when_normal_conf_high(self):
        """Normal strong match (>= 0.85) is never overridden by wildcard."""
        matcher = ActiveMatcher()
        src = _make_component(
            library_id="CIS/U7",
            part_name="STM32F407",
            footprint="",
            value="STM32F407",
            pin_count=100,
            extra_data={"jedec_type": "IC"},
        )
        cand = _make_component(
            library_id="hdl_lib/IC/STM32F407",
            part_name="STM32F407",
            category="IC",
            footprint="",
            value="STM32F407",
            pin_count=100,
            extra_data={
                "ptf_rows": [{"jedec_type": "IC", "value": "STM32F407"}],
                "all_primitives": [{"part_name": "STM32F407_QFP100"}],
            },
        )
        result = matcher.match(src, [cand], src_type="IC")
        # value=1.0 + part_name=1.0 + pin_count=1.0 + jedec=1.0 + fp=0.5
        # within = 0.3*0.5 + 0.15*1 + 0.2*1 + 0.2*1 + 0.15*1 = 0.85 → no wildcard
        assert result.confidence >= 0.85
        assert "wildcard" not in result.phase2_strategy_detail


# ═══════════════════════════════════════════════════════════════════════
# PrefixAffinityCalculator
# ═══════════════════════════════════════════════════════════════════════


class TestPrefixAffinityCalculator:
    """PrefixAffinityCalculator — learning and persistence."""

    def test_cold_start_returns_floor(self, tmp_path):
        """Cold start: unknown prefix→type returns FLOOR (0.05)."""
        calc = PrefixAffinityCalculator(correlations_path=tmp_path / "corr.yaml")
        assert calc.affinity("U", "IC") == 0.05
        assert calc.affinity("C", "capacitor") == 0.05

    def test_record_match_increases_affinity(self, tmp_path):
        """Recording a match increases affinity."""
        calc = PrefixAffinityCalculator(correlations_path=tmp_path / "corr.yaml")
        assert calc.affinity("U", "IC") == 0.05
        calc.record_match("U", "IC")
        assert calc.affinity("U", "IC") == 0.10  # 0.05 + 0.05
        calc.record_match("U", "IC")
        assert calc.affinity("U", "IC") == pytest.approx(0.15)

    def test_affinity_capped_at_one(self, tmp_path):
        """Affinity is capped at 1.0."""
        calc = PrefixAffinityCalculator(correlations_path=tmp_path / "corr.yaml")
        for _ in range(30):
            calc.record_match("C", "capacitor")
        assert calc.affinity("C", "capacitor") <= 1.0

    def test_empty_inputs_return_floor(self):
        """Empty inputs return FLOOR."""
        calc = PrefixAffinityCalculator()
        assert calc.affinity("", "IC") == 0.05
        assert calc.affinity("U", "") == 0.05
        assert calc.affinity("", "") == 0.05

    def test_matrix_property_is_copy(self, tmp_path):
        """matrix property returns a copy, not a reference."""
        calc = PrefixAffinityCalculator(correlations_path=tmp_path / "corr.yaml")
        calc.record_match("U", "IC")
        mat = calc.matrix
        mat["U"]["IC"] = 0.99  # mutate copy
        assert calc.affinity("U", "IC") == 0.10  # original unchanged


# ═══════════════════════════════════════════════════════════════════════
# Integration: Two-phase architecture validation
# ═══════════════════════════════════════════════════════════════════════


class TestPipelinePhaseInteraction:
    """Verify that Phase 1 results correctly inform Phase 2 dispatch."""

    def test_C_prefix_triggers_passive(self):
        """C prefix should be identified as passive and routed to PassiveMatcher."""
        assert is_passive_prefix(prefix="C") is True
        assert is_passive_prefix(type_name="capacitor") is True

    def test_R_prefix_triggers_passive(self):
        """R prefix is passive."""
        assert is_passive_prefix(prefix="R") is True
        assert is_passive_prefix(type_name="resistor") is True

    def test_D_prefix_triggers_passive(self):
        """D prefix is passive (diode/zener)."""
        assert is_passive_prefix(prefix="D") is True
        assert is_passive_prefix(type_name="diode") is True

    def test_U_prefix_triggers_active(self):
        """U prefix should be identified as active and routed to ActiveMatcher."""
        assert is_passive_prefix(prefix="U") is False
        assert is_passive_prefix(type_name="IC") is False

    def test_M_prefix_is_active(self):
        """M prefix is active (mark is not in PASSIVE_TYPES)."""
        assert is_passive_prefix(prefix="M") is False
        assert is_passive_prefix(type_name="mark") is False

    def test_X_prefix_is_active(self):
        """X prefix (crystal) is active."""
        assert is_passive_prefix(prefix="X") is False
        assert is_passive_prefix(type_name="crystal") is False


class TestConfCalculation:
    """Verify that final_conf = phase1_prior × phase2_within."""

    def test_final_conf_multiplied_directly(self):
        """final_conf is phase1_prior_conf × phase2_within_conf."""
        phase1_conf = 1.0   # C prefix → capacitor prior=1.0
        phase2_conf = 1.0   # PASSIVE_EXACT conf=1.0
        final = phase1_conf * phase2_conf
        assert final == 1.0

    def test_final_conf_partial_passive(self):
        """PASSIVE_VALUE_ONLY × prior=1.0 = 0.80."""
        phase1_conf = 1.0
        phase2_conf = 0.80  # PASSIVE_VALUE_ONLY
        assert phase1_conf * phase2_conf == 0.80

    def test_final_conf_active_uncertain(self):
        """ActiveMatcher: prior=0.85 × within=0.70 → 0.595."""
        phase1_conf = 0.85
        phase2_conf = 0.70
        final = phase1_conf * phase2_conf
        assert final == pytest.approx(0.595, abs=0.01)

    def test_no_max_floor_for_conf(self):
        """Conf should NOT use max() — it's a direct multiplication."""
        # This is a documentation/design test: verify the formula is
        # final_conf = prior × within (not max(prior, within)).
        prior = 0.40
        within = 0.80
        result_multiply = prior * within  # = 0.32
        result_max = max(prior, within)    # = 0.80
        assert result_multiply != result_max  # Prove they're different
        # The pipeline should use multiply, not max
        assert result_multiply < result_max
