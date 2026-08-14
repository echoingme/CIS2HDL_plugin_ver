"""NetNameValidator — validates network names for illegal characters and ISCF classification.

Performs two checks:
  1. Illegal character detection using normalize_net_name from naming utilities.
  2. ISCF 4-class (FLAT/GROUND/POWER/BUS) classification correctness.

Produces DiagnosisError codes 24-25.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, ClassVar

from .base import ValidatorBase
from cis2hdl.utils.naming import normalize_net_name
from cis2hdl.core.net_utils import classify_net
from cis2hdl.core.ir.design import NetCategory
from cis2hdl.core.config import config as cfg

if TYPE_CHECKING:
    from cis2hdl.core.ir.match import MatchResult
    from cis2hdl.core.ir.design import DesignIR
    from cis2hdl.core.diagnostics.diagnostic_report import DiagnosisError

logger = logging.getLogger(__name__)


class NetNameValidator(ValidatorBase):
    """Validates network names across the design.

    Two checks:
      1. _check_illegal_chars — detects illegal characters in net names.
      2. _classify_and_check — verifies ISCF 4-class classification consistency.

    Error codes produced:
      - 24 (NET_NAME_ILLEGAL_CHARS): Net name contains characters illegal in HDL.
      - 25 (NET_CLASSIFICATION_UNEXPECTED): Net classification may be incorrect.
    """

    VALIDATOR_NAME: ClassVar[str] = "net"
    VALIDATOR_PRIORITY: ClassVar[int] = 20

    # Characters that are illegal in net names but may appear in CIS
    _ILLEGAL_NET_CHARS: ClassVar[str] = cfg.net.illegal_chars

    def validate(
        self,
        match: "MatchResult",
        design: "DesignIR",
    ) -> "list[DiagnosisError]":
        """Run net name validation on all nets in the design.

        Args:
            match: MatchResult (not directly used — net validation is design-wide).
            design: DesignIR containing all nets.

        Returns:
            List of DiagnosisError entries.
        """
        errors: list["DiagnosisError"] = []
        all_nets = design.all_nets
        for net in all_nets:
            errors.extend(self._check_illegal_chars(net.name))
            errors.extend(self._classify_and_check(net))
        return errors

    def _check_illegal_chars(self, name: str) -> "list[DiagnosisError]":
        """Check a net name for illegal characters.

        Compares the original name against the normalized version. If they differ,
        illegal characters were present.

        Args:
            name: Raw net name from the design.

        Returns:
            List of NET_NAME_ILLEGAL_CHARS errors (code 24).
        """
        from cis2hdl.core.diagnostics.diagnostic_report import DiagnosisError, Severity

        errors: list["DiagnosisError"] = []

        if not name:
            return errors

        normalized = normalize_net_name(name)

        if normalized != name:
            # Find which characters were removed/replaced
            illegal_chars_found: list[str] = []
            for ch in name:
                if ch in self._ILLEGAL_NET_CHARS:
                    if ch not in illegal_chars_found:
                        illegal_chars_found.append(ch)

            errors.append(
                DiagnosisError(
                    code=24,
                    severity=Severity.WARNING,
                    category="NET",
                    message=f"网络名包含非法字符: '{name}'",
                    detail=(
                        f"原始名称: '{name}', 规范化后: '{normalized}', "
                        f"非法字符: {illegal_chars_found}"
                    ),
                    suggestion=(
                        f"网络名 '{name}' 将被规范化为 '{normalized}'。"
                        f"请确认此变更可接受，或在源文件中修正网络名"
                    ),
                    source_file="",
                    can_ignore=True,
                )
            )
            if name:
                logger.info("Net name '%s' normalized to '%s'", name, normalized)

        return errors

    def _classify_and_check(self, net: "DesignIR.all_nets[0]") -> "list[DiagnosisError]":
        """Verify ISCF 4-class classification of a net.

        Checks that the net's declared category matches the classification
        that classify_net() would produce.

        Args:
            net: A NetIR instance from the design.

        Returns:
            List of NET_CLASSIFICATION_UNEXPECTED errors (code 25).
        """
        from cis2hdl.core.diagnostics.diagnostic_report import DiagnosisError, Severity

        errors: list["DiagnosisError"] = []

        if not net.name:
            return errors

        expected_category = classify_net(net.name)
        actual_category = net.category

        if expected_category != actual_category:
            # Only warn if there's a meaningful mismatch
            # FLAT is the default, so only warn if something was classified
            # differently than expected
            if expected_category != NetCategory.FLAT or actual_category != NetCategory.FLAT:
                errors.append(
                    DiagnosisError(
                        code=25,
                        severity=Severity.WARNING,
                        category="NET",
                        message=(
                            f"网络 '{net.name}' 分类可能不正确: "
                            f"当前={actual_category.value}, 预期={expected_category.value}"
                        ),
                        detail=(
                            f"net_name='{net.name}', "
                            f"declared_category={actual_category.value}, "
                            f"detected_category={expected_category.value}"
                        ),
                        suggestion=(
                            f"网络 '{net.name}' 被分类为 {actual_category.value}，"
                            f"但根据命名规则应为 {expected_category.value}。"
                            f"请检查原始设计中的网络分类"
                        ),
                        source_file="",
                        can_ignore=True,
                    )
                )

        # Additional check: single-node nets (only one connection)
        # This is an advisory check not tied to a specific error code in the
        # 31-code system. Use code 0 for uncoded advisories.
        if len(net.connections) == 1:
            conn = net.connections[0]
            errors.append(
                DiagnosisError(
                    code=0,
                    severity=Severity.INFO,
                    category="NET",
                    message=f"单节点网络: '{net.name}' (仅连接到 {conn.refdes}.{conn.pin_number})",
                    detail=(
                        f"net_name='{net.name}', "
                        f"connection={conn.refdes}.{conn.pin_number}"
                    ),
                    suggestion=(
                        f"网络 '{net.name}' 只有一个连接点，可能是未连接引脚或设计错误"
                    ),
                    source_file="",
                    can_ignore=True,
                )
            )

        return errors

    def can_validate(self, match: "MatchResult") -> bool:
        """Net name validation always applies — it's design-wide."""
        return True
