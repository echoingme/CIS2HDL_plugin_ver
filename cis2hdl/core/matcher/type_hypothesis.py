"""Phase 1: Type Hypothesis Generator.

Produces an ordered list of type hypotheses for a given CIS component
based on refdes prefix, PST data, value hints, and learned affinities.

Architecture:
    refdes prefix → _from_yaml() → base hypotheses
    → _apply_pst_boost() (JEDEC_TYPE confirmation)
    → _apply_value_hints() (value string patterns)
    → _apply_learned_affinity() (historical correlations)
    → normalise → sorted by prior_conf descending

All prior_conf values are clamped to [0.05, 1.0].
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from cis2hdl.core.matcher.prefix_filter import extract_prefix

logger = logging.getLogger(__name__)

# Minimum prior confidence — types are never completely eliminated
_MIN_PRIOR: float = 0.05
# Maximum prior confidence — preserve uncertainty
_MAX_PRIOR: float = 1.0


@dataclass
class TypeHypothesis:
    """A single type hypothesis with prior confidence.

    Attributes:
        type_name: Type name in snake_case (e.g. "capacitor", "IC").
        prior_conf: Prior confidence in [0.05, 1.0].
        source: How this hypothesis was determined
            ("exact_prefix", "yaml_rule", "pst_boost", "value_hint", "learned").
    """
    type_name: str
    prior_conf: float
    source: str = "yaml_rule"


class TypeHypothesisGenerator:
    """Generate ordered type hypotheses for a CIS component.

    Uses refdes prefix as the primary signal, then adjusts priors
    based on PST JEDEC_TYPE, value patterns, and learned affinities.

    Usage:
        gen = TypeHypothesisGenerator(config, affinity_calc)
        hypotheses = gen.generate("C89", "10UF", {"jedec_type": "CAPACITOR"})
        # → [TypeHypothesis(type_name="capacitor", prior_conf=1.0, ...)]
    """

    def __init__(
        self,
        config: Any,  # MatchConfig
        affinity: Any,  # PrefixAffinityCalculator
    ) -> None:
        """Initialise the generator.

        Args:
            config: MatchConfig instance (must have type_hypotheses,
                    value_type_boost, pst_type_boost properties).
            affinity: PrefixAffinityCalculator for learned adjustments.
        """
        self._config = config
        self._affinity = affinity
        self._type_hypotheses: dict[str, list[list]] = config.type_hypotheses
        self._value_boost: dict[str, list] = config.value_type_boost
        self._pst_boost: dict[str, list] = config.pst_type_boost

    # ── Public API ────────────────────────────────────────────────────

    def generate(
        self,
        refdes: str,
        value: str,
        pst_data: dict | None = None,
    ) -> list[TypeHypothesis]:
        """Generate ordered type hypotheses for a CIS component.

        Args:
            refdes: Reference designator (e.g. "C89", "U7", "LB4").
            value: Component value string (e.g. "10UF", "100K", "").
            pst_data: Optional PST metadata dict with keys:
                - "jedec_type": JEDEC_TYPE from pstchip
                - "part_name": PART_NAME from pstchip

        Returns:
            List of TypeHypothesis sorted by prior_conf descending.
            Always non-empty — falls back to a generic hypothesis if
            the prefix is unknown.
        """
        prefix: str = extract_prefix(refdes)
        if not prefix:
            logger.debug("TypeHypothesis: cannot extract prefix from '%s'", refdes)
            return []

        # Step A: Base hypotheses from YAML config
        hypotheses: list[TypeHypothesis] = self._from_yaml(prefix)

        # Step B: Apply PST JEDEC_TYPE boost
        if pst_data:
            self._apply_pst_boost(hypotheses, pst_data)

        # Step C: Apply value pattern hints
        if value:
            self._apply_value_hints(hypotheses, value)

        # Step D: Apply learned affinity adjustments
        self._apply_learned_affinity(hypotheses, prefix)

        # Step E: Normalise and sort
        hypotheses = self._normalise(hypotheses)
        hypotheses.sort(key=lambda h: h.prior_conf, reverse=True)

        logger.debug(
            "TypeHypothesis: '%s' (prefix=%s) → %d hypotheses: %s",
            refdes,
            prefix,
            len(hypotheses),
            [(h.type_name, round(h.prior_conf, 3)) for h in hypotheses[:5]],
        )
        return hypotheses

    # ── Step A: Base hypotheses from YAML ─────────────────────────────

    def _from_yaml(self, prefix: str) -> list[TypeHypothesis]:
        """Generate base hypotheses from type_gate.yaml.

        Args:
            prefix: Uppercase refdes prefix (e.g. "C", "U", "LB").

        Returns:
            List of TypeHypothesis from YAML config.  If prefix is
            unknown, returns an empty list (caller handles fallback).
        """
        entries = self._type_hypotheses.get(prefix, [])
        if not entries:
            logger.debug(
                "TypeHypothesis: unknown prefix '%s' — no YAML rules",
                prefix,
            )
            return []

        hypotheses: list[TypeHypothesis] = []
        for entry in entries:
            if isinstance(entry, list) and len(entry) >= 2:
                type_name: str = str(entry[0]).lower()
                prior_conf: float = float(entry[1])
                hypotheses.append(
                    TypeHypothesis(
                        type_name=type_name,
                        prior_conf=min(prior_conf, _MAX_PRIOR),
                        source="exact_prefix" if prior_conf >= 1.0 else "yaml_rule",
                    )
                )

        return hypotheses

    # ── Step B: PST JEDEC_TYPE boost ─────────────────────────────────

    def _apply_pst_boost(
        self,
        hypotheses: list[TypeHypothesis],
        pst_data: dict,
    ) -> None:
        """Boost prior_conf for types confirmed by PST JEDEC_TYPE.

        Args:
            hypotheses: Current list of TypeHypothesis (mutated in place).
            pst_data: PST metadata dict with "jedec_type" key.
        """
        jedec_type: str = (pst_data.get("jedec_type") or "").upper().strip()
        if not jedec_type:
            return

        boost_entry = self._pst_boost.get(jedec_type)
        if boost_entry is None:
            return

        if not isinstance(boost_entry, list) or len(boost_entry) < 2:
            return

        boost_type: str = str(boost_entry[0]).lower()
        boost_amount: float = float(boost_entry[1])

        for h in hypotheses:
            if h.type_name == boost_type:
                new_conf: float = h.prior_conf + boost_amount
                capped: float = min(new_conf, 0.95)
                if capped > h.prior_conf:
                    h.prior_conf = capped
                    h.source = f"{h.source}+pst_boost"
                logger.debug(
                    "PST boost: %s +%.2f for type '%s' (JEDEC=%s)",
                    h.type_name, boost_amount, boost_type, jedec_type,
                )
                break

    # ── Step C: Value pattern hints ──────────────────────────────────

    def _apply_value_hints(
        self,
        hypotheses: list[TypeHypothesis],
        value: str,
    ) -> None:
        """Boost prior_conf for types confirmed by value patterns.

        Checks the component value string for known patterns like
        "NH"/"UH" → inductor, "MHz" → crystal, etc.

        Args:
            hypotheses: Current list of TypeHypothesis (mutated in place).
            value: Component value string (e.g. "10UF", "100NH", "16MHz").
        """
        value_upper: str = (value or "").upper().strip()
        if not value_upper:
            return

        # Check each boost pattern against the value string
        for pattern, boost_entry in self._value_boost.items():
            if pattern.upper() not in value_upper:
                continue

            if not isinstance(boost_entry, list) or len(boost_entry) < 2:
                continue

            boost_type: str = str(boost_entry[0]).lower()
            boost_amount: float = float(boost_entry[1])

            for h in hypotheses:
                if h.type_name == boost_type:
                    h.prior_conf = min(h.prior_conf + boost_amount, 0.95)
                    h.source = f"{h.source}+value_hint"
                    logger.debug(
                        "Value hint: '%s' matches '%s' → %s +%.2f",
                        value_upper, pattern, boost_type, boost_amount,
                    )
                    break

        # Special case: value="0" → boost diode types
        if value_upper in ("0", "0R", "0Ω"):
            for h in hypotheses:
                if h.type_name in ("diode", "zener", "tvs"):
                    h.prior_conf = min(h.prior_conf + 0.05, 0.95)
                    h.source = f"{h.source}+zero_value"

    # ── Step D: Learned affinity adjustments ─────────────────────────

    def _apply_learned_affinity(
        self,
        hypotheses: list[TypeHypothesis],
        prefix: str,
    ) -> None:
        """Adjust prior_conf based on historical learning matrix.

        Args:
            hypotheses: Current list of TypeHypothesis (mutated in place).
            prefix: Uppercase refdes prefix.
        """
        if not self._affinity:
            return

        for h in hypotheses:
            learned: float = self._affinity.affinity(prefix, h.type_name)
            # Only apply learned affinity if it IMPROVES upon the YAML prior.
            # A low learned value (cold start = FLOOR) should never drag down
            # a confident YAML prior like IC:0.85 → 0.625.
            if learned > h.prior_conf:
                # Blend towards learned (30% weight)
                blended: float = h.prior_conf * 0.70 + learned * 0.30
                h.prior_conf = min(blended, _MAX_PRIOR)
                h.source = f"{h.source}+learned"

    # ── Step E: Normalisation ────────────────────────────────────────

    def _normalise(
        self, hypotheses: list[TypeHypothesis]
    ) -> list[TypeHypothesis]:
        """Clamp all prior_conf to [0.05, 1.0] range.

        No re-scaling — individual values are preserved.  Only clamping
        to ensure minimum floor and maximum cap.

        Args:
            hypotheses: List of TypeHypothesis to normalise.

        Returns:
            Normalised list (same objects, values clamped).
        """
        for h in hypotheses:
            h.prior_conf = max(_MIN_PRIOR, min(h.prior_conf, _MAX_PRIOR))
        return hypotheses
