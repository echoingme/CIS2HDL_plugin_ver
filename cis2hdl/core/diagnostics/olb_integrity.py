"""OLBIntegrityChecker — three-layer OLB file integrity validator.

Performs three-layer validation of an OLB (OrCAD Library) file:

    Layer 1: Package (Type 31) existence — verify all package streams are present
             and readable in the CFB container.
    Layer 2: Device (Type 32) pinMap completeness — verify each package has a
             Device stream with valid pin definitions.
    Layer 3: NormalView symbol graphics completeness — verify each package has
             an associated symbol with graphic elements.

All errors are reported as list[DiagnosisError] using the existing error code
system (codes 51–55 allocated for OLB integrity).

Usage:
    checker = OLBIntegrityChecker()
    errors = checker.check(Path("library.olb"))
    for err in errors:
        print(err)
"""

from __future__ import annotations

import logging
from pathlib import Path

from .diagnostic_report import DiagnosisError, Severity

logger = logging.getLogger(__name__)

# ── OLB-specific error codes (51–55) ────────────────────────────────────────
# These complement the main ERROR_CODES dict (1–50) in error_diagnosis.py.

OLB_ERROR_CODES: dict[int, dict[str, object]] = {
    51: {
        "name": "OLB_PACKAGE_MISSING",
        "severity": Severity.ERROR,
        "category": "FILE",
        "message": "OLB Package 流缺失",
        "suggestion": "OLB 文件可能已损坏，请从备份恢复或使用 OrCAD 重新保存",
        "can_ignore": False,
    },
    52: {
        "name": "OLB_DEVICE_MISSING",
        "severity": Severity.ERROR,
        "category": "PIN",
        "message": "OLB Device 引脚定义缺失",
        "suggestion": "Package 缺少 Device 流，请确认 OLB 文件完整性",
        "can_ignore": True,
    },
    53: {
        "name": "OLB_PIN_MAP_EMPTY",
        "severity": Severity.WARNING,
        "category": "PIN",
        "message": "OLB Device 引脚映射为空",
        "suggestion": "该器件没有定义任何引脚，请确认是否为预期行为",
        "can_ignore": True,
    },
    54: {
        "name": "OLB_SYMBOL_MISSING",
        "severity": Severity.WARNING,
        "category": "SYMBOL",
        "message": "OLB NormalView 符号图形缺失",
        "suggestion": "Package 缺少符号图形，将使用默认矩形符号",
        "can_ignore": True,
    },
    55: {
        "name": "OLB_SYMBOL_EMPTY",
        "severity": Severity.WARNING,
        "category": "SYMBOL",
        "message": "OLB NormalView 符号图形为空（无图形元素）",
        "suggestion": "该器件的符号图形不包含任何几何元素，请检查 OLB 文件",
        "can_ignore": True,
    },
}


def _make_olb_error(code: int, detail: str = "", source_file: str = "") -> DiagnosisError:
    """Build a DiagnosisError from an OLB-specific error code.

    Args:
        code: Error code in range 51–55.
        detail: Additional detail text.
        source_file: Path to the source OLB file.

    Returns:
        DiagnosisError instance.
    """
    template = OLB_ERROR_CODES.get(code, {})
    return DiagnosisError(
        code=code,
        severity=Severity(template.get("severity", Severity.ERROR)),
        category=str(template.get("category", "FILE")),
        message=str(template.get("message", f"OLB 完整性错误 E{code:02d}")),
        detail=detail,
        suggestion=str(template.get("suggestion", "")),
        source_file=source_file,
        can_ignore=bool(template.get("can_ignore", False)),
    )


class OLBIntegrityChecker:
    """Three-layer OLB file integrity validator.

    Validates an OLB file at three levels:
      1. **Package (Type 31) existence** — the CFB container must have a
         readable Package stream for every declared package.
      2. **Device (Type 32) pinMap completeness** — each Package must have
         a Device sub-stream with at least one valid pin definition.
      3. **NormalView symbol graphics** — each Package must have an
         associated symbol definition with at least one graphic element
         (line, rectangle, ellipse, etc.).

    Usage::

        checker = OLBIntegrityChecker()
        errors = checker.check(Path("library.olb"))
        if not errors:
            print("OLB integrity check PASSED")
        else:
            for err in errors:
                print(f"  {err}")
    """

    def check(self, olb_path: Path) -> list[DiagnosisError]:
        """Run the full three-layer integrity check on an OLB file.

        Args:
            olb_path: Path to the .olb file.

        Returns:
            List of DiagnosisError entries. An empty list indicates
            all checks passed.
        """
        errors: list[DiagnosisError] = []
        olb_path_str = str(olb_path)

        if not olb_path.exists():
            errors.append(
                DiagnosisError(
                    code=1,
                    severity=Severity.FATAL,
                    category="FILE",
                    message=f"OLB 文件缺失: {olb_path.name}",
                    source_file=olb_path_str,
                    suggestion="请提供对应的 OLB 文件",
                    can_ignore=False,
                )
            )
            return errors

        if not olb_path.is_file():
            errors.append(
                DiagnosisError(
                    code=2,
                    severity=Severity.ERROR,
                    category="FILE",
                    message=f"OLB 路径不是文件: {olb_path.name}",
                    source_file=olb_path_str,
                    suggestion="请确认路径正确",
                    can_ignore=False,
                )
            )
            return errors

        # ═══════════════════════════════════════════════════════════════
        # Open the OLB file — uses OLBOleReader (CFB container reader)
        # ═══════════════════════════════════════════════════════════════
        from ..parser.olb.olb_reader import OLBOleReader, CFBError

        try:
            reader = OLBOleReader(olb_path)
        except Exception as exc:
            errors.append(
                DiagnosisError(
                    code=3,
                    severity=Severity.FATAL,
                    category="FILE",
                    message=f"无法打开 OLB 文件: {olb_path.name}",
                    detail=f"打开失败: {exc}",
                    source_file=olb_path_str,
                    suggestion="请确认文件未损坏且格式为 CFB (Compound File Binary)",
                    can_ignore=False,
                )
            )
            return errors

        # ═══════════════════════════════════════════════════════════════
        # Layer 1: Package (Type 31) existence
        # ═══════════════════════════════════════════════════════════════
        packages = reader.list_packages()
        if not packages:
            errors.append(
                _make_olb_error(
                    51,
                    detail="OLB 文件中未发现任何 Package 定义。CFB 容器可能不包含 Packages/ 目录。",
                    source_file=olb_path_str,
                )
            )
            return errors

        logger.info("Layer 1 PASSED: %d package(s) found in '%s'", len(packages), olb_path.name)

        # Track packages that pass layer 2 and 3
        packages_with_devices: int = 0
        packages_with_symbols: int = 0
        packages_with_empty_pins: int = 0
        packages_with_empty_symbols: int = 0

        # ═══════════════════════════════════════════════════════════════
        # Layer 2 & 3: Device pinMap + NormalView (per-package)
        # ═══════════════════════════════════════════════════════════════
        for pkg_name in packages:
            # ── Layer 2: Device (Type 32) pinMap ──────────────────────
            try:
                device_bytes = reader.read_device_stream(pkg_name)
                if device_bytes and len(device_bytes) > 0:
                    # Parse device to verify pin map
                    from ..parser.olb.olb_parser import parse_olb_device
                    from ..parser.dsn.binary_reader import BinaryReader

                    br_dev = BinaryReader(device_bytes)
                    device_data = parse_olb_device(br_dev)

                    if device_data.pin_count == 0:
                        packages_with_empty_pins += 1
                        errors.append(
                            _make_olb_error(
                                53,
                                detail=f"Package '{pkg_name}' 的 Device 流中未解析到任何引脚",
                                source_file=olb_path_str,
                            )
                        )
                    else:
                        packages_with_devices += 1
                else:
                    errors.append(
                        _make_olb_error(
                            52,
                            detail=f"Package '{pkg_name}' 的 Device 流为空",
                            source_file=olb_path_str,
                        )
                    )
            except (CFBError, Exception) as exc:
                errors.append(
                    _make_olb_error(
                        52,
                        detail=f"Package '{pkg_name}' 缺少 Device 流: {exc}",
                        source_file=olb_path_str,
                    )
                )

            # ── Layer 3: NormalView symbol graphics ───────────────────
            lib_part_name = self._resolve_lib_part_for_package(reader, pkg_name)
            if lib_part_name:
                try:
                    nv_bytes = reader.read_normal_view(lib_part_name)
                    if nv_bytes and len(nv_bytes) > 0:
                        from ..parser.olb.olb_parser import parse_normal_view
                        from ..parser.dsn.binary_reader import BinaryReader

                        br_nv = BinaryReader(nv_bytes)
                        nv_data = parse_normal_view(br_nv, lib_part_name)

                        if not nv_data.graphics:
                            packages_with_empty_symbols += 1
                            errors.append(
                                _make_olb_error(
                                    55,
                                    detail=f"Package '{pkg_name}' (symbol '{lib_part_name}') 的 NormalView 不包含任何图形元素",
                                    source_file=olb_path_str,
                                )
                            )
                        else:
                            packages_with_symbols += 1
                    else:
                        errors.append(
                            _make_olb_error(
                                54,
                                detail=f"Package '{pkg_name}' 的 NormalView 流为空",
                                source_file=olb_path_str,
                            )
                        )
                except (CFBError, Exception):
                    errors.append(
                        _make_olb_error(
                            54,
                            detail=f"Package '{pkg_name}' 缺少 NormalView 符号 (lib_part='{lib_part_name}')",
                            source_file=olb_path_str,
                        )
                    )
            else:
                # No matching symbol found — warn if this isn't expected
                errors.append(
                    _make_olb_error(
                        54,
                        detail=f"Package '{pkg_name}' 未找到关联的 LibPart 符号",
                        source_file=olb_path_str,
                    )
                )

        # ── Summary logging ───────────────────────────────────────────
        logger.info(
            "OLB integrity check for '%s': %d packages, %d with devices, "
            "%d with symbols, %d empty_pins, %d empty_symbols, %d total errors",
            olb_path.name,
            len(packages),
            packages_with_devices,
            packages_with_symbols,
            packages_with_empty_pins,
            packages_with_empty_symbols,
            len(errors),
        )

        return errors

    # ── Helper: resolve LibPart name for a package ─────────────────────

    @staticmethod
    def _resolve_lib_part_for_package(
        reader: object,
        pkg_name: str,
    ) -> str | None:
        """Resolve the LibPart symbol name for a given package.

        Strategy:
          1. Read Package stream and extract view_ref.
          2. Match by exact package name in symbols list.
          3. Match case-insensitively.
          4. Match by substring.

        Args:
            reader: OLBOleReader instance.
            pkg_name: Package name.

        Returns:
            LibPart name or None.
        """
        from ..parser.olb.olb_parser import parse_olb_package
        from ..parser.dsn.binary_reader import BinaryReader

        # Try to read view_ref from the Package stream
        view_ref: str | None = None
        try:
            pkg_bytes = reader.read_package_stream(pkg_name)  # type: ignore[union-attr]
            br = BinaryReader(pkg_bytes)
            pkg_data = parse_olb_package(br)
            if pkg_data.view_ref:
                view_ref = pkg_data.view_ref.split(".")[0]
        except Exception:
            pass

        symbols = reader.list_symbols()  # type: ignore[union-attr]

        # Strategy 1: use view_ref
        if view_ref and view_ref in symbols:
            return view_ref

        # Strategy 2: exact match
        if pkg_name in symbols:
            return pkg_name

        # Strategy 3: case-insensitive
        pkg_lower = pkg_name.lower()
        for sym in symbols:
            if sym.lower() == pkg_lower:
                return sym

        # Strategy 4: substring
        for sym in symbols:
            if pkg_lower in sym.lower() or sym.lower() in pkg_lower:
                return sym

        return None
