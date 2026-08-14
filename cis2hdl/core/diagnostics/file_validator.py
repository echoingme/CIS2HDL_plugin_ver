"""ProjectFileValidator and DependencyResolver (D1.3 + D1.4).

Three-layer file validation:
    (a) File existence check
    (b) CFB magic/header format validation
    (c) CFB version compatibility detection

Dependency resolution:
    Extract OLB references from DSN Cache → compare against user-supplied files
    → generate MISSING_OLB list with actionable suggestions.
"""

from __future__ import annotations

import logging
from pathlib import Path

from .diagnostic_report import (
    FileState,
    FileStatus,
    ProjectInventory,
    DSNInternalInventory,
    DiagnosisError,
    Severity,
    ActionItem,
    ActionVerb,
)

logger = logging.getLogger(__name__)

# ── Known standard OLB files shipped with OrCAD ────────────────────────────
# These are typically optional — user may not need them if symbols are embedded.

STANDARD_OLB_NAMES: set[str] = {
    "CAPSYM",
    "ANSI_M",
    "IEC_M",
    "Discrete",
    "Connector",
    "OPAmp",
    "Amplifier",
    "MicroController",
    "Transistor",
    "FPGA",
    "Gate",
    "Power",
    "Source",
    "Misc",
}


# ── ProjectFileValidator (D1.3) ────────────────────────────────────────────


class ProjectFileValidator:
    """Three-tier file integrity validator.

    Layer 1: File existence and basic read access.
    Layer 2: Magic bytes / format header validation.
    Layer 3: CFB version compatibility.
    """

    @staticmethod
    def validate_layer1_existence(inventory: ProjectInventory) -> list[DiagnosisError]:
        """Check: does each expected file exist and is it readable?

        Returns:
            List of DiagnosisError for each missing/unreadable file.
        """
        errors: list[DiagnosisError] = []

        for key, status in inventory.files.items():
            path = status.path
            if not path.exists():
                errors.append(
                    DiagnosisError(
                        code=1,
                        severity=Severity.FATAL if status.file_type == "DSN" else Severity.ERROR,
                        category="FILE",
                        message=f"文件缺失: {path.name}",
                        detail=f"路径不存在: {path}",
                        suggestion=f"请提供 {status.file_type} 文件",
                        source_file=str(path),
                        can_ignore=status.file_type != "DSN",
                    )
                )
                continue

            if not path.is_file():
                errors.append(
                    DiagnosisError(
                        code=1,
                        severity=Severity.ERROR,
                        category="FILE",
                        message=f"路径不是文件: {path.name}",
                        source_file=str(path),
                        suggestion="请确认路径正确",
                        can_ignore=True,
                    )
                )
                continue

            # Check read access
            try:
                with open(path, "rb") as f:
                    f.read(1)
            except PermissionError:
                errors.append(
                    DiagnosisError(
                        code=1,
                        severity=Severity.ERROR,
                        category="FILE",
                        message=f"文件不可读（权限不足）: {path.name}",
                        source_file=str(path),
                        suggestion="请检查文件权限设置",
                        can_ignore=False,
                    )
                )

        return errors

    @staticmethod
    def validate_layer2_format(inventory: ProjectInventory) -> list[DiagnosisError]:
        """Check: do CFB files have valid magic bytes? Are EDIF files valid S-expr?

        Returns:
            DiagnosisError for each file with format issues.
        """
        errors: list[DiagnosisError] = []

        for key, status in inventory.files.items():
            if status.state == FileState.BAD_FORMAT:
                errors.append(
                    DiagnosisError(
                        code=2,
                        severity=Severity.ERROR,
                        category="FILE",
                        message=f"文件格式无效: {status.path.name}",
                        detail=status.detail,
                        suggestion=(
                            "文件可能已损坏，请尝试从 .dbk 备份恢复"
                            if status.file_type == "DSN"
                            else "请确认文件来源正确"
                        ),
                        source_file=str(status.path),
                        can_ignore=status.file_type != "DSN",
                    )
                )

            if status.state == FileState.CORRUPTED:
                errors.append(
                    DiagnosisError(
                        code=3,
                        severity=Severity.FATAL if status.file_type == "DSN" else Severity.ERROR,
                        category="FILE",
                        message=f"文件已损坏: {status.path.name} ({status.summary})",
                        source_file=str(status.path),
                        suggestion=(
                            "请从备份恢复或重新生成此文件"
                        ),
                        can_ignore=status.file_type != "DSN",
                    )
                )

        return errors

    @staticmethod
    def validate_layer3_version(inventory: ProjectInventory) -> list[DiagnosisError]:
        """Check: CFB version compatibility.

        Currently detects CFB version from header bytes at offset 0x1A (dll_version).
        OrCAD 16.6 uses version 4.0x.  Versions < 3 or > 5 warrant warnings.
        """
        errors: list[DiagnosisError] = []

        for key, status in inventory.files.items():
            if status.file_type not in ("DSN", "OLB", "DBK"):
                continue
            if status.state != FileState.FOUND_OK:
                continue

            try:
                with open(status.path, "rb") as f:
                    f.seek(0x1A)
                    dll_ver = int.from_bytes(f.read(2), "little")

                # OrCAD 16.6 uses CFB version 4.X
                if dll_ver < 3:
                    errors.append(
                        DiagnosisError(
                            code=4,
                            severity=Severity.WARNING,
                            category="FILE",
                            message=f"CFB 版本较旧 ({dll_ver}) — 可能来自 OrCAD 9.x 或更早",
                            source_file=str(status.path),
                            suggestion="建议使用 OrCAD 16.6+ 重新保存项目文件",
                            can_ignore=True,
                        )
                    )
                elif dll_ver > 6:
                    errors.append(
                        DiagnosisError(
                            code=5,
                            severity=Severity.WARNING,
                            category="FILE",
                            message=f"CFB 版本较新 ({dll_ver}) — 可能来自更现代的 OrCAD 版本",
                            source_file=str(status.path),
                            suggestion="格式版本尚在验证中，如有解析异常请反馈",
                            can_ignore=True,
                        )
                    )

            except (OSError, PermissionError) as exc:
                logger.warning("Cannot read CFB version from %s: %s", status.path, exc)

        return errors

    def full_validate(self, inventory: ProjectInventory) -> list[DiagnosisError]:
        """Run all three validation layers in sequence.

        Returns:
            Aggregated list of all errors encountered.
        """
        all_errors: list[DiagnosisError] = []
        all_errors.extend(self.validate_layer1_existence(inventory))
        all_errors.extend(self.validate_layer2_format(inventory))
        all_errors.extend(self.validate_layer3_version(inventory))
        return all_errors


# ── DependencyResolver (D1.4) ──────────────────────────────────────────────


class DependencyResolver:
    """Resolve OLB and other cross-file dependencies.

    Extracts OLB references from the DSN's internal Cache streams
    and checks them against the user-supplied file set.
    """

    def resolve_olb_dependencies(
        self,
        inventory: ProjectInventory,
    ) -> tuple[list[str], list[DiagnosisError]]:
        """Extract OLB references and identify missing ones.

        Args:
            inventory: Project inventory with DSN internal data populated.

        Returns:
            (missing_olb_names, list of DiagnosisError for each missing OLB).
        """
        dsn = inventory.dsn_internal

        # Extract OLB references from DSN internal inventory
        olb_refs = set(dsn.olb_references)

        # Also check referenced_packages which contain OLB names
        for pkg_name, (olb_name, count) in dsn.referenced_packages.items():
            if olb_name:
                olb_refs.add(olb_name)

        # Compare against user-supplied OLB files
        user_olbs: set[str] = {
            status.path.stem
            for status in inventory.files.values()
            if status.file_type == "OLB" and status.state == FileState.FOUND_OK
        }

        missing_olbs: list[str] = []
        errors: list[DiagnosisError] = []

        for olb_name in sorted(olb_refs):
            # Check if user provided this OLB
            found = olb_name in user_olbs
            # Also check partial matches (case-insensitive)
            if not found:
                for uolb in user_olbs:
                    if uolb.upper() == olb_name.upper():
                        found = True
                        break

            if not found:
                missing_olbs.append(olb_name)

                # Special handling for CAPSYM — always available from OrCAD install
                is_standard = olb_name in STANDARD_OLB_NAMES

                error = DiagnosisError(
                    code=6,
                    severity=Severity.WARNING if is_standard else Severity.ERROR,
                    category="FILE",
                    message=f"OLB 库引用缺失: {olb_name}.olb",
                    detail=(
                        f"DSN 内部引用了器件库 {olb_name}.olb。"
                        f"{'此为标准库，通常不需要单独提供。' if is_standard else '器件引脚名称和属性将无法提取。'}"
                    ),
                    suggestion=(
                        "标准库无需单独提供" if is_standard
                        else f"请上传 {olb_name}.olb 文件以获取器件引脚名称和属性"
                    ),
                    source_file=None,
                    can_ignore=True,
                )
                errors.append(error)

        # Update inventory
        inventory.missing_olbs = missing_olbs

        if missing_olbs:
            non_standard = [o for o in missing_olbs if o not in STANDARD_OLB_NAMES]
            if non_standard:
                inventory.actions.append(
                    ActionItem(
                        verb=ActionVerb.PROVIDE,
                        target=f"{len(non_standard)} 个缺失 OLB 文件: {', '.join(non_standard[:5])}{'...' if len(non_standard) > 5 else ''}",
                        reason="这些 OLB 库文件包含器件引脚名称和属性定义",
                        priority=0,
                    )
                )

        return missing_olbs, errors
