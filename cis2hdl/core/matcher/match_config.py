"""Match rules configuration loader — reads match_rules.yaml and type_gate.yaml.

Provides a singleton MatchConfig that loads value→category hints,
type hypothesis mappings, and HDL scan settings from YAML configs.
Falls back to hardcoded defaults if YAML files are missing.

v2.0: Extended to load type_gate.yaml for Phase 1 type hypothesis generation.
      Old match_rules.yaml prefix_to_category is marked deprecated.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Default location relative to this file
_DEFAULT_CONFIG_PATH = Path(__file__).parent / "match_rules.yaml"
_DEFAULT_TYPE_GATE_PATH = (
    Path(__file__).parent.parent.parent / "config" / "type_gate.yaml"
)

# ── Hardcoded fallbacks (used when YAML is missing) ──────────────

_DEFAULT_VALUE_HINTS: dict[str, list[str]] = {
    "DZ": ["zener", "diode"],
    "TESTPOINT": ["hole", "test_point"],
}

_DEFAULT_TYPE_HYPOTHESES: dict[str, list[list]] = {
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
    "T": [["transformer", 0.70], ["inductor", 0.60]],
    "X": [["crystal", 0.85], ["oscillator", 0.75]],
    "Y": [["crystal", 0.85], ["oscillator", 0.75]],
    "J": [["connector", 0.80], ["rj45", 0.60], ["header", 0.50]],
    "S": [["switch", 0.70], ["button", 0.60]],
    "P": [["connector", 0.60], ["power", 0.50]],
    "K": [["relay", 0.80]],
    # Phase XII R4: FILTER-valued Z components (e.g. Z1/Z2 value=FILTER)
    # should be able to match the hdl_lib/filter library.  zener/diode
    # stay first so regular zener matching is unaffected.
    "Z": [["zener", 0.80], ["diode", 0.60], ["filter", 0.50]],
    "VR": [["voltage_regulator", 0.90]],
    "RN": [["resistor_network", 0.90]],
    "F": [["fuse", 0.90]],
    "Q": [["transistor", 0.85], ["mosfet", 0.75]],
    "IC": [["IC", 0.95], ["voltage_regulator", 0.70]],
    # Phase XII R3: RD prefix → resistor (RD25 = 4.7K resistor).  Matches
    # type_gate.yaml so RD components get a proper type prior instead of
    # falling to NEEDS_REVIEW conf=0.0 when YAML is unavailable.
    "RD": [["resistor", 0.90]],
}

# Phase XII R3: fixed-prefix strong bindings — mirror type_gate.yaml.
# When a prefix is in this map, the first type hypothesis's match is
# accepted regardless of confidence (no fall-through to second priority).
_DEFAULT_FIXED_PREFIXES: dict[str, str] = {
    "LB": "ferrite_bead",
    "LED": "led",
    "FB": "ferrite_bead",
    "TP": "test_point",
}

_DEFAULT_VALUE_BOOST: dict[str, list] = {
    "NH": ["inductor", 0.15],
    "UH": ["inductor", 0.15],
    "mH": ["inductor", 0.10],
    "nH": ["inductor", 0.10],
    "MHz": ["crystal", 0.20],
    "kHz": ["crystal", 0.15],
    "MARK": ["mark", 0.30],
    "TESTPOINT": ["test_point", 0.30],
}

_DEFAULT_PST_BOOST: dict[str, list] = {
    "CAPACITOR": ["capacitor", 0.10],
    "RESISTOR": ["resistor", 0.10],
    "INDUCTOR": ["inductor", 0.10],
    "DIODE": ["diode", 0.10],
    "ZENER": ["zener", 0.15],
    "CONNECTOR": ["connector", 0.15],
    "IC": ["IC", 0.10],
    "FPGA": ["IC", 0.20],
    "CRYSTAL": ["crystal", 0.20],
    "OSCILLATOR": ["oscillator", 0.15],
    "TRANSFORMER": ["transformer", 0.15],
    "SWITCH": ["switch", 0.15],
}

_DEFAULT_PASSIVE_TYPES: list[str] = [
    "capacitor", "resistor", "inductor", "diode",
    "zener", "ferrite_bead", "led",
]

# ── v2c: Part-name alias fallbacks (used when YAML is missing) ────
_DEFAULT_PART_NAME_ALIASES: dict[str, list[str]] = {
    "mj8": ["rj45", "modular", "jack"],
    "mj": ["rj45", "modular"],
}


class MatchConfig:
    """Singleton configuration loaded from match_rules.yaml and type_gate.yaml.

    v2.0: Extended with type hypothesis configuration for Phase 1.
    """

    _instance: MatchConfig | None = None

    def __init__(
        self,
        config_path: Path | None = None,
        type_gate_path: Path | None = None,
    ) -> None:
        self._config_path = config_path or _DEFAULT_CONFIG_PATH
        self._type_gate_path = type_gate_path or _DEFAULT_TYPE_GATE_PATH
        self._data: dict[str, Any] = {}
        self._type_gate_data: dict[str, Any] = {}
        self._loaded = False
        self._load()

    def _load(self) -> None:
        """Load both YAML configs or use defaults."""
        self._load_match_rules()
        self._load_type_gate()
        self._loaded = True

    def _load_match_rules(self) -> None:
        """Load match_rules.yaml."""
        try:
            import yaml
        except ImportError:
            logger.warning(
                "PyYAML not installed — match_rules.yaml is ignored, "
                "using hardcoded defaults"
            )
            return

        if not self._config_path.exists():
            logger.info(
                "match_rules.yaml not found at %s, using hardcoded defaults",
                self._config_path,
            )
            return

        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                self._data = yaml.safe_load(f) or {}
            logger.info(
                "Loaded match rules from %s (%d value hints)",
                self._config_path,
                len(self.value_category_hints),
            )
        except Exception as exc:
            logger.warning("Failed to load match_rules.yaml: %s", exc)

    def _load_type_gate(self) -> None:
        """Load type_gate.yaml."""
        try:
            import yaml
        except ImportError:
            logger.warning(
                "PyYAML not installed — type_gate.yaml is ignored, "
                "using hardcoded defaults"
            )
            return

        if not self._type_gate_path.exists():
            logger.info(
                "type_gate.yaml not found at %s, using hardcoded defaults",
                self._type_gate_path,
            )
            return

        try:
            with open(self._type_gate_path, "r", encoding="utf-8") as f:
                self._type_gate_data = yaml.safe_load(f) or {}
            logger.info(
                "Loaded type gate from %s (%d prefix mappings)",
                self._type_gate_path,
                len(self.type_hypotheses),
            )
        except Exception as exc:
            logger.warning("Failed to load type_gate.yaml: %s", exc)

    # ── Public API ─────────────────────────────────────────────────

    # -- match_rules.yaml properties (retained) --

    @property
    def value_category_hints(self) -> dict[str, list[str]]:
        """Value substring → category hints (from match_rules.yaml)."""
        result = self._data.get("value_category_hints", {})
        return result if result else _DEFAULT_VALUE_HINTS

    @property
    def prefix_to_category(self) -> dict[str, list[str]]:
        """[DEPRECATED v2.0] Prefix → category mappings.

        Replaced by type_gate.yaml type_hypotheses.  Retained for
        backward compatibility only.  New code should use
        TypeHypothesisGenerator instead.
        """
        logger.warning(
            "prefix_to_category is deprecated in v2.0. "
            "Use type_gate.yaml type_hypotheses via TypeHypothesisGenerator."
        )
        return {}

    @property
    def auto_scan_enabled(self) -> bool:
        """Whether to auto-scan hdl_lib on each conversion."""
        scan_cfg = self._data.get("hdl_scan", {})
        return scan_cfg.get("auto_scan_on_convert", True)

    @property
    def hdl_exclude_patterns(self) -> list[str]:
        """Patterns to exclude from HDL scanning."""
        scan_cfg = self._data.get("hdl_scan", {})
        return scan_cfg.get("exclude_patterns", [])

    @property
    def matching_config(self) -> dict[str, float]:
        """Matching confidence thresholds."""
        return self._data.get("matching", {})

    # -- type_gate.yaml properties (v2.0) --

    @property
    def type_hypotheses(self) -> dict[str, list[list]]:
        """Prefix → ordered type hypotheses (from type_gate.yaml).

        Returns:
            Dict mapping uppercase prefix to list of [type_name, prior_conf].
            Falls back to hardcoded defaults if YAML is missing.
        """
        result = self._type_gate_data.get("type_hypotheses", {})
        return result if result else dict(_DEFAULT_TYPE_HYPOTHESES)

    @property
    def value_type_boost(self) -> dict[str, list]:
        """Value pattern → [type_name, boost_amount] (from type_gate.yaml).

        Returns:
            Dict mapping value pattern (e.g. "NH") to [type, boost].
        """
        result = self._type_gate_data.get("value_type_boost", {})
        return result if result else dict(_DEFAULT_VALUE_BOOST)

    @property
    def pst_type_boost(self) -> dict[str, list]:
        """PST JEDEC_TYPE → [type_name, boost_amount] (from type_gate.yaml).

        Returns:
            Dict mapping JEDEC_TYPE (e.g. "FPGA") to [type, boost].
        """
        result = self._type_gate_data.get("pst_type_boost", {})
        return result if result else dict(_DEFAULT_PST_BOOST)

    @property
    def passive_types(self) -> list[str]:
        """Passive component type names (from type_gate.yaml).

        Returns:
            List of type_name strings that trigger Phase 2A passive matching.
        """
        result = self._type_gate_data.get("passive_types", [])
        return result if result else list(_DEFAULT_PASSIVE_TYPES)

    @property
    def fixed_prefixes(self) -> dict[str, str]:
        """Fixed prefix → type bindings (from type_gate.yaml).

        When a prefix is in this map, the first type hypothesis's match
        is accepted regardless of confidence — no fall-through to the
        second-priority type.

        Example: {"LB": "ferrite_bead", "LED": "led", "TP": "test_point"}
        """
        result = self._type_gate_data.get("fixed_prefixes", {})
        return result if result else dict(_DEFAULT_FIXED_PREFIXES)

    @property
    def part_name_aliases(self) -> dict[str, list[str]]:
        """Part-name token aliases for ActiveMatcher scoring (from match_rules.yaml).

        Maps a lowercase part-name token (e.g. "mj8") to a list of
        alternative words that may appear in the candidate part_name
        (e.g. ["rj45", "modular", "jack"]).  Used by
        ``ActiveMatcher._score_part_name`` and the footprint-wildcard
        rescue path so that mixed alphanumeric names (e.g. "MJ8-M2")
        can still match library names like "rj45_2x2_led".

        Returns:
            Dict mapping lowercase token → list of lowercase alias words.
            Falls back to hardcoded defaults if YAML is missing.
        """
        result = self._data.get("part_name_aliases", {})
        if not result or not isinstance(result, dict):
            return dict(_DEFAULT_PART_NAME_ALIASES)
        # Normalise: lowercase keys and values
        return {
            str(k).lower(): [str(v).lower() for v in vals]
            for k, vals in result.items()
            if isinstance(vals, list)
        }

    # -- Singleton access --

    @classmethod
    def instance(cls, config_path: Path | None = None) -> "MatchConfig":
        """Get or create the singleton instance."""
        if cls._instance is None:
            cls._instance = cls(config_path)
        return cls._instance

    @classmethod
    def reload(cls, config_path: Path | None = None) -> "MatchConfig":
        """Force reload configuration."""
        cls._instance = cls(config_path)
        return cls._instance
