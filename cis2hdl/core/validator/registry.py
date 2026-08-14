"""ValidatorRegistry — manages all validators and provides batch execution.

Follows the same pattern as MatcherRegistry: class-level registration with
run_all() that executes validators in priority order.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from cis2hdl.core.ir.match import MatchResult
    from cis2hdl.core.ir.design import DesignIR
    from cis2hdl.core.diagnostics.diagnostic_report import DiagnosisError
    from .base import ValidatorBase

logger = logging.getLogger(__name__)


class ValidatorRegistry:
    """Class-level registry for validators.

    Validators are registered automatically by importing their modules and
    calling register(). Use run_all() to execute all validators against a
    batch of match results.

    Usage:
        ValidatorRegistry.register(PinValidator())
        errors = ValidatorRegistry.run_all(match, design)
    """

    _validators: ClassVar[dict[str, "ValidatorBase"]] = {}

    @classmethod
    def register(cls, validator: "ValidatorBase") -> None:
        """Register a validator instance.

        Args:
            validator: ValidatorBase instance with a unique VALIDATOR_NAME.
        """
        name = validator.VALIDATOR_NAME
        if name in cls._validators:
            logger.warning(
                "Validator '%s' already registered, overwriting", name
            )
        cls._validators[name] = validator
        logger.debug("Registered validator: %s (priority=%d)", name, validator.VALIDATOR_PRIORITY)

    @classmethod
    def get(cls, name: str) -> "ValidatorBase | None":
        """Get a validator by name.

        Args:
            name: Validator name (VALIDATOR_NAME).

        Returns:
            The validator instance, or None if not found.
        """
        return cls._validators.get(name)

    @classmethod
    def list_all(cls) -> "list[ValidatorBase]":
        """List all registered validators, sorted by priority.

        Returns:
            List of ValidatorBase instances.
        """
        return sorted(cls._validators.values(), key=lambda v: v.VALIDATOR_PRIORITY)

    @classmethod
    def run_all(
        cls,
        match: "MatchResult",
        design: "DesignIR",
    ) -> "list[DiagnosisError]":
        """Run all registered validators against a single match.

        Validators are executed in priority order. Each validator's can_validate()
        is checked before running validate().

        Args:
            match: The MatchResult to validate.
            design: The DesignIR for context.

        Returns:
            Aggregated list of all DiagnosisError entries from all validators.
        """
        all_errors: list["DiagnosisError"] = []
        for validator in cls.list_all():
            if not validator.can_validate(match):
                logger.debug(
                    "Skipping validator '%s' — can_validate returned False",
                    validator.VALIDATOR_NAME,
                )
                continue
            try:
                errors = validator.validate(match, design)
                all_errors.extend(errors)
            except Exception as exc:
                logger.error(
                    "Validator '%s' raised exception: %s", validator.VALIDATOR_NAME, exc,
                    exc_info=True,
                )
        return all_errors

    @classmethod
    def run_all_batch(
        cls,
        matches: "list[MatchResult]",
        design: "DesignIR",
    ) -> "list[DiagnosisError]":
        """Run all validators against a batch of match results.

        Args:
            matches: List of MatchResult entries to validate.
            design: The DesignIR for context.

        Returns:
            Aggregated list of all DiagnosisError entries.
        """
        all_errors: list["DiagnosisError"] = []
        for match in matches:
            all_errors.extend(cls.run_all(match, design))
        return all_errors

    @classmethod
    def clear(cls) -> None:
        """Remove all registered validators (useful for testing)."""
        cls._validators.clear()

    @classmethod
    def count(cls) -> int:
        """Return the number of registered validators."""
        return len(cls._validators)
