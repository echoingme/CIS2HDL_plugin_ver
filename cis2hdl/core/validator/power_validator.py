"""PowerPinValidator — validates power pin handling and detects duplicates.

Checks:
  1. Power pins that are not marked as power type.
  2. Duplicate power pin definitions in the target component.

Produces DiagnosisError codes 26-27.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, ClassVar

from .base import ValidatorBase
from cis2hdl.core.ir.component import ElectricalType

if TYPE_CHECKING:
    from cis2hdl.core.ir.match import MatchResult
    from cis2hdl.core.ir.design import DesignIR
    from cis2hdl.core.diagnostics.diagnostic_report import DiagnosisError

logger = logging.getLogger(__name__)

# Common power pin name patterns (lowercase for case-insensitive matching)
_POWER_PIN_NAMES: set[str] = {
    "vcc", "vdd", "vss", "gnd", "vref", "vpp",
    "vccint", "vccaux", "vcco", "vccpll",
    "vdd_core", "vdd_io", "vdda", "vssa",
    "avcc", "agnd", "dvcc", "dgnd",
    "pvcc", "pgnd", "vbat", "vcore",
}


class PowerPinValidator(ValidatorBase):
    """Validates power pin integrity.

    Two checks:
      1. _check_power_pin_unmarked — power pins not typed as POWER/GROUND.
      2. _check_power_pin_duplicate — duplicate power pin definitions.

    Error codes produced:
      - 26 (POWER_PIN_DUPLICATE): Same power pin defined multiple times.
      - 27 (POWER_PIN_UNCONNECTED): Power pin not properly connected/marked.
    """

    VALIDATOR_NAME: ClassVar[str] = "power"
    VALIDATOR_PRIORITY: ClassVar[int] = 30

    def validate(
        self,
        match: "MatchResult",
        design: "DesignIR",
    ) -> "list[DiagnosisError]":
        """Run power pin validation.

        Args:
            match: MatchResult with target_library_id referencing target component.
            design: DesignIR with component_db.

        Returns:
            List of DiagnosisError entries.
        """
        errors: list["DiagnosisError"] = []
        errors.extend(self._check_power_pin_handling(match, design))
        return errors

    def _check_power_pin_handling(
        self,
        match: "MatchResult",
        design: "DesignIR",
    ) -> "list[DiagnosisError]":
        """Check power pin handling in the target component.

        Detects:
          - Power pin names that are not marked as POWER/GROUND type.
          - Duplicate power pin names in the target component.
          - Power pins that may be unconnected in the design.

        Args:
            match: MatchResult with target_library_id.
            design: DesignIR with component_db.

        Returns:
            List of POWER_PIN_DUPLICATE (26) and POWER_PIN_UNCONNECTED (27) errors.
        """
        from cis2hdl.core.diagnostics.diagnostic_report import DiagnosisError, Severity

        errors: list["DiagnosisError"] = []

        if not match.target_library_id:
            return errors

        target_comp = design.component_db.get_by_library_id(match.target_library_id)
        if target_comp is None:
            logger.debug(
                "Target component '%s' not found in component_db — skipping power check",
                match.target_library_id,
            )
            return errors

        # Track power pins for duplicate detection
        seen_power_pins: dict[str, int] = {}  # pin_name_lower -> count

        for pin in target_comp.pins:
            pin_name_lower = pin.name.lower().strip()

            # Check if this pin name looks like a power pin
            is_likely_power = pin_name_lower in _POWER_PIN_NAMES
            is_typed_power = pin.type in (ElectricalType.POWER, ElectricalType.GROUND)

            if is_likely_power and not is_typed_power:
                errors.append(
                    DiagnosisError(
                        code=27,
                        severity=Severity.WARNING,
                        category="PIN",
                        message=(
                            f"电源引脚未标记: 引脚 '{pin.name}' (编号 {pin.number}) "
                            f"在器件 {match.target_library_id} 中疑似电源引脚，"
                            f"但未标记为 POWER/GROUND 类型"
                        ),
                        detail=(
                            f"pin_name='{pin.name}', pin_number='{pin.number}', "
                            f"pin_type={pin.type.value}, "
                            f"component={match.target_library_id}"
                        ),
                        suggestion=(
                            f"请确认引脚 '{pin.name}' 是否为电源引脚，"
                            f"若是请在 HDL 库中将其标记为 POWER 或 GROUND"
                        ),
                        source_file=match.target_library_id,
                        can_ignore=True,
                    )
                )

            # Track for duplicate detection
            if pin_name_lower in seen_power_pins:
                seen_power_pins[pin_name_lower] += 1
            else:
                seen_power_pins[pin_name_lower] = 1

        # Report duplicates
        for pin_name, count in seen_power_pins.items():
            if count > 1:
                errors.append(
                    DiagnosisError(
                        code=26,
                        severity=Severity.WARNING,
                        category="PIN",
                        message=(
                            f"重复电源引脚: '{pin_name}' 在器件 "
                            f"{match.target_library_id} 中出现 {count} 次"
                        ),
                        detail=(
                            f"pin_name='{pin_name}', occurrences={count}, "
                            f"component={match.target_library_id}"
                        ),
                        suggestion=(
                            f"器件 {match.target_library_id} 中电源引脚 '{pin_name}' "
                            f"重复定义 {count} 次，请检查 HDL 库中该器件的引脚定义"
                        ),
                        source_file=match.target_library_id,
                        can_ignore=True,
                    )
                )

        # Check for power pins with no connections in the design
        if match.pin_mapping:
            # Get all connected pin numbers from the design
            # We need to find instances matching this source_library_id
            connected_pins: set[str] = set()
            for page in design.pages:
                for instance in page.instances:
                    if instance.library_id == match.source_library_id:
                        connected_pins.update(instance.pin_connections.keys())

            # Check each target power pin
            for pin in target_comp.pins:
                if pin.is_power:
                    # Find the source pin mapped to this target pin
                    source_pin = None
                    for sp, tp in match.pin_mapping.items():
                        if tp == pin.number:
                            source_pin = sp
                            break

                    if source_pin and source_pin not in connected_pins:
                        errors.append(
                            DiagnosisError(
                                code=27,
                                severity=Severity.WARNING,
                                category="PIN",
                                message=(
                                    f"电源引脚未连接: '{pin.name}' (编号 {pin.number}) "
                                    f"在实例 {match.source_library_id} 中似乎未连接"
                                ),
                                detail=(
                                    f"pin_name='{pin.name}', pin_number='{pin.number}', "
                                    f"source_pin='{source_pin}', "
                                    f"component={match.source_library_id}"
                                ),
                                suggestion=(
                                    f"请确认电源引脚 '{pin.name}' 是否需要连接，"
                                    f"或在原理图中添加连接"
                                ),
                                source_file=match.source_library_id,
                                can_ignore=True,
                            )
                        )

        return errors

    def can_validate(self, match: "MatchResult") -> bool:
        """Only validate if there is a target library ID."""
        return bool(match.target_library_id)
