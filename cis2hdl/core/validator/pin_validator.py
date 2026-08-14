"""PinValidator — validates pin number existence and pin count matching.

Checks that every pin in the source component exists in the target HDL component,
and that the total pin counts match. Produces DiagnosisError codes 22-23.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, ClassVar

from .base import ValidatorBase

if TYPE_CHECKING:
    from cis2hdl.core.ir.match import MatchResult
    from cis2hdl.core.ir.design import DesignIR
    from cis2hdl.core.diagnostics.diagnostic_report import DiagnosisError

logger = logging.getLogger(__name__)


class PinValidator(ValidatorBase):
    """Validates pin integrity between CIS source and HDL target components.

    Two checks are performed:
      1. _check_pin_number — every source pin number must exist in the target.
      2. _check_pin_count  — the total number of mapped pins must match.

    Error codes produced:
      - 22 (PIN_NUMBER_MISSING): A source pin number is not found in target.
      - 23 (PIN_COUNT_MISMATCH): Total pin count differs between source and target.
    """

    VALIDATOR_NAME: ClassVar[str] = "pin"
    VALIDATOR_PRIORITY: ClassVar[int] = 10

    def validate(
        self,
        match: "MatchResult",
        design: "DesignIR",
    ) -> "list[DiagnosisError]":
        """Run both pin checks.

        Args:
            match: MatchResult with pin_mapping (source_pin -> target_pin).
            design: DesignIR containing the component_db with target components.

        Returns:
            List of DiagnosisError entries.
        """
        from cis2hdl.core.diagnostics.diagnostic_report import DiagnosisError, Severity

        errors: list[DiagnosisError] = []
        errors.extend(self._check_pin_number(match, design))
        errors.extend(self._check_pin_count(match, design))
        return errors

    def _check_pin_number(
        self,
        match: "MatchResult",
        design: "DesignIR",
    ) -> "list[DiagnosisError]":
        """Check that every source pin number exists in the target component.

        For each pin in pin_mapping, verify the target pin number exists in
        the target component definition.

        Args:
            match: MatchResult with pin_mapping.
            design: DesignIR with component_db.

        Returns:
            List of PIN_NUMBER_MISSING errors (code 22).
        """
        from cis2hdl.core.diagnostics.diagnostic_report import DiagnosisError, Severity

        errors: list[DiagnosisError] = []

        if not match.target_library_id:
            return errors

        # Look up the target component in the design's component DB
        target_comp = design.component_db.get_by_library_id(match.target_library_id)
        if target_comp is None:
            logger.debug(
                "Target component '%s' not found in component_db — skipping pin number check",
                match.target_library_id,
            )
            return errors

        # Build set of valid target pin numbers
        valid_target_pins: set[str] = {pin.number for pin in target_comp.pins}

        # Check each source pin in the mapping
        for source_pin, target_pin in match.pin_mapping.items():
            if target_pin not in valid_target_pins and target_pin != "":
                errors.append(
                    DiagnosisError(
                        code=22,
                        severity=Severity.ERROR,
                        category="PIN",
                        message=(
                            f"引脚编号不存在: 源引脚 {source_pin} 映射到 "
                            f"目标引脚 {target_pin}，但目标器件 {match.target_library_id} "
                            f"中不存在此引脚"
                        ),
                        detail=(
                            f"source_pin={source_pin}, target_pin={target_pin}, "
                            f"valid_pins={sorted(valid_target_pins)}"
                        ),
                        suggestion=(
                            f"请检查引脚映射配置，或将 {source_pin} 映射到 "
                            f"{match.target_library_id} 的可用引脚"
                        ),
                        source_file=match.target_library_id,
                        can_ignore=True,
                    )
                )

        return errors

    def _check_pin_count(
        self,
        match: "MatchResult",
        design: "DesignIR",
    ) -> "list[DiagnosisError]":
        """Check that the total pin count matches between source and target.

        Args:
            match: MatchResult with pin_mapping.
            design: DesignIR with component_db.

        Returns:
            List of PIN_COUNT_MISMATCH errors (code 23).
        """
        from cis2hdl.core.diagnostics.diagnostic_report import DiagnosisError, Severity

        errors: list[DiagnosisError] = []

        if not match.target_library_id:
            return errors

        # Count mapped pins (source side)
        mapped_pin_count = len(match.pin_mapping)

        # Get target component pin count
        target_comp = design.component_db.get_by_library_id(match.target_library_id)
        if target_comp is None:
            logger.debug(
                "Target component '%s' not found in component_db — skipping pin count check",
                match.target_library_id,
            )
            return errors

        target_pin_count = target_comp.pin_count

        if mapped_pin_count != target_pin_count and mapped_pin_count > 0:
            errors.append(
                DiagnosisError(
                    code=23,
                    severity=Severity.ERROR,
                    category="PIN",
                    message=(
                        f"引脚总数不匹配: 源器件 {match.source_library_id} 有 "
                        f"{mapped_pin_count} 个映射引脚，目标器件 "
                        f"{match.target_library_id} 有 {target_pin_count} 个引脚"
                    ),
                    detail=(
                        f"source_library_id={match.source_library_id}, "
                        f"target_library_id={match.target_library_id}, "
                        f"mapped_count={mapped_pin_count}, "
                        f"target_count={target_pin_count}"
                    ),
                    suggestion=(
                        f"请检查 {match.source_library_id} 与 "
                        f"{match.target_library_id} 是否对应同一器件型号，"
                        f"或手动调整引脚映射"
                    ),
                    source_file=match.target_library_id,
                    can_ignore=True,
                )
            )

        return errors

    def can_validate(self, match: "MatchResult") -> bool:
        """Only validate if there is a target library ID and pin mapping."""
        return bool(match.target_library_id and match.pin_mapping)
