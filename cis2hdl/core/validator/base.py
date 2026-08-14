"""ValidatorBase — abstract base class for all post-match validators.

Each validator checks a specific aspect of a MatchResult against the target DesignIR,
producing a list of DiagnosisError entries.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from cis2hdl.core.ir.match import MatchResult
    from cis2hdl.core.ir.design import DesignIR
    from cis2hdl.core.diagnostics.diagnostic_report import DiagnosisError


class ValidatorBase(ABC):
    """Abstract base class for all validators.

    Subclasses must set VALIDATOR_NAME and VALIDATOR_PRIORITY, and implement
    the validate() method. The can_validate() method provides early-exit filtering.

    Usage:
        class MyValidator(ValidatorBase):
            VALIDATOR_NAME: ClassVar[str] = "my_validator"
            VALIDATOR_PRIORITY: ClassVar[int] = 10

            def validate(self, match, design):
                errors = []
                if match.pin_mapping:
                    # check pin mapping validity
                    pass
                return errors
    """

    VALIDATOR_NAME: ClassVar[str] = ""
    """Unique name for this validator, used as key in ValidatorRegistry."""

    VALIDATOR_PRIORITY: ClassVar[int] = 50
    """Execution priority — lower numbers run first."""

    @abstractmethod
    def validate(
        self,
        match: "MatchResult",
        design: "DesignIR",
    ) -> "list[DiagnosisError]":
        """Run validation on a single match result.

        Args:
            match: The MatchResult to validate (contains pin_mapping, source_library_id,
                   target_library_id, confidence, strategy).
            design: The DesignIR containing all pages, instances, and nets of
                    the source design.

        Returns:
            List of DiagnosisError entries. Return empty list if validation passes.
        """
        ...

    def can_validate(self, match: "MatchResult") -> bool:
        """Check whether this validator can meaningfully validate the given match.

        The default implementation returns True for all matches. Override to
        provide early-exit filtering (e.g., skip if confidence is too low).

        Args:
            match: The MatchResult to check.

        Returns:
            True if this validator should run on this match.
        """
        return True
