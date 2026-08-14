"""Prefix affinity learning engine.

v2.0: MultiScorer has been removed.  Cross-type scoring proved
structurally unsound (see MATCHING_ANALYSIS_2026-08-06.md) —
prefix is a hard constraint, not a soft weight.

This module now contains only PrefixAffinityCalculator, repurposed
for Phase 1 type hypothesis prior adjustment.  The affinity matrix
is persisted to ``~/.cis2hdl/type_affinities.yaml`` (v2.0 renamed
from correlations.yaml).

Usage:
    from cis2hdl.core.matcher.scoring import PrefixAffinityCalculator

    affinity = PrefixAffinityCalculator()
    score = affinity.affinity("U", "IC")   # → learned correlation or floor
    affinity.record_match("U", "IC")       # learn from successful match
    affinity.save()                         # persist to disk
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ── PrefixAffinityCalculator ──────────────────────────────────────────────

class PrefixAffinityCalculator:
    """Dynamic prefix affinity via historical learning matrix.

    Learns correlations between RefDes prefixes (e.g. "U", "C", "R")
    and type names (e.g. "IC", "capacitor") from successful matches.
    Persisted to ``~/.cis2hdl/type_affinities.yaml``.

    v2.0: Repurposed for Phase 1 type hypothesis prior adjustment.
    The floor of 0.05 ensures types are never completely eliminated
    from consideration — even if the learning matrix shows zero
    matches for a type, it still gets a 0.05 prior.

    Scoring rules:
        - Exact match (refdes_prefix derived type == learned type):  1.0
        - Learned correlation from prior matches:                    stored value (0.05–1.0)
        - No history (cold start):                                   0.05 (floor — never eliminate)
    """

    FLOOR: float = 0.05
    DEFAULT_PATH: Path = Path.home() / ".cis2hdl" / "type_affinities.yaml"

    def __init__(self, correlations_path: Path | None = None) -> None:
        self._matrix: dict[str, dict[str, float]] = {}
        self._path: Path = correlations_path or self.DEFAULT_PATH
        self._load()

    # ── Public API ────────────────────────────────────────────────────

    def affinity(self, refdes_prefix: str, type_name: str) -> float:
        """Calculate prefix→type affinity score.

        Args:
            refdes_prefix: RefDes prefix extracted from source (e.g. "U", "C", "R").
            type_name: Type name in snake_case (e.g. "IC", "capacitor", "diode").

        Returns:
            Float in [0.05, 1.0].  1.0 = exact/direct match; 0.05 = no history.
        """
        if not refdes_prefix or not type_name:
            return self.FLOOR

        refdes_prefix = refdes_prefix.upper()
        type_name = type_name.lower()

        # Direct lookup in the learning matrix
        row: dict[str, float] = self._matrix.get(refdes_prefix, {})
        return row.get(type_name, self.FLOOR)

    def record_match(
        self, refdes_prefix: str, type_name: str
    ) -> None:
        """Learn from a successful match.

        Increments the correlation weight between *refdes_prefix* and
        *type_name* by 0.05, capped at 1.0.

        Args:
            refdes_prefix: RefDes prefix (e.g. "U").
            type_name: Matched type name (e.g. "IC").
        """
        if not refdes_prefix or not type_name:
            return

        refdes_prefix = refdes_prefix.upper()
        type_name = type_name.lower()

        if refdes_prefix not in self._matrix:
            self._matrix[refdes_prefix] = {}

        current: float = self._matrix[refdes_prefix].get(
            type_name, self.FLOOR
        )
        new_value: float = min(1.0, current + 0.05)
        self._matrix[refdes_prefix][type_name] = new_value

        logger.debug(
            "Prefix affinity learned: %s→%s %.2f→%.2f",
            refdes_prefix,
            type_name,
            current,
            new_value,
        )

    def save(self) -> None:
        """Persist the current matrix to disk."""
        self._save()

    # ── Internal persistence ─────────────────────────────────────────

    def _load(self) -> None:
        """Load correlation matrix from YAML file, if it exists."""
        if not self._path.exists():
            logger.debug(
                "No affinity file at %s, starting cold",
                self._path,
            )
            self._matrix = {}
            return

        try:
            import yaml as _yaml
        except ImportError:
            logger.debug("PyYAML not installed, cannot load affinities")
            self._matrix = {}
            return

        try:
            data: Any = _yaml.safe_load(
                self._path.read_text(encoding="utf-8")
            )
        except Exception as exc:
            logger.warning("Failed to parse affinities file: %s", exc)
            self._matrix = {}
            return

        if not isinstance(data, dict):
            self._matrix = {}
            return

        self._matrix = {}
        for rpfx, targets in data.items():
            if isinstance(targets, dict):
                self._matrix[rpfx] = {}
                for tpfx, weight in targets.items():
                    self._matrix[rpfx][tpfx] = float(weight)

        logger.debug(
            "Loaded %d prefix affinities from %s",
            sum(len(v) for v in self._matrix.values()),
            self._path,
        )

    def _save(self) -> None:
        """Write correlation matrix to YAML file."""
        self._path.parent.mkdir(parents=True, exist_ok=True)

        try:
            import yaml as _yaml
        except ImportError:
            logger.warning("PyYAML not installed, cannot save affinities")
            return

        output: dict[str, dict[str, float]] = {}
        for rpfx, targets in self._matrix.items():
            # Only store non-trivial entries (exclude floor-only mappings)
            output[rpfx] = {
                tpfx: w for tpfx, w in targets.items() if w > self.FLOOR
            }

        with open(self._path, "w", encoding="utf-8") as fh:
            _yaml.safe_dump(
                output,
                fh,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=True,
            )

        logger.debug("Saved affinities to %s", self._path)

    @property
    def matrix(self) -> dict[str, dict[str, float]]:
        """Read-only view of the current correlation matrix."""
        return dict(self._matrix)
