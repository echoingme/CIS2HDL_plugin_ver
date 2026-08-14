"""ConfigValidator — validates Config singleton for path existence, encoding,
and page/grid dimension legality.

Produces a list of DiagnosisError; empty list = configuration is valid.
Reference: ROADMAP D2.7.
"""

from __future__ import annotations

import logging
from pathlib import Path

from .diagnostic_report import Severity, DiagnosisError
from ..exceptions import CIS2HDLConfigError

logger = logging.getLogger(__name__)


class ConfigValidator:
    """Validates the global Config singleton against system reality.

    Checks:
      1. Path existence: hdl_lib_path, cadence_root (if set)
      2. Encoding declarations: must be valid Python codec names
      3. Grid/page dimension legality: positive integers, reasonable ranges

    Usage:
        validator = ConfigValidator()
        errors = validator.validate()
        if errors:
            for e in errors:
                print(e)
        else:
            print("Configuration is valid.")
    """

    # Reasonable page dimension bounds (in HDL grid units)
    MIN_PAGE_WIDTH: int = 100
    MAX_PAGE_WIDTH: int = 20000
    MIN_PAGE_HEIGHT: int = 100
    MAX_PAGE_HEIGHT: int = 20000
    MIN_GRID_SPACING: int = 1
    MAX_GRID_SPACING: int = 1000

    # Valid Python codec names (subset covering expected encodings)
    VALID_ENCODINGS: set[str] = {
        "utf-8", "utf-16", "utf-16le", "utf-16be",
        "ascii", "latin-1", "gbk", "gb2312", "shift-jis",
        "euc-jp", "euc-kr", "big5",
    }

    # ── Error code base ──────────────────────────────────────────────
    # Using reserved codes 35-38 for config errors
    CONFIG_ERROR_BASE: int = 35

    def validate(self) -> list[DiagnosisError]:
        """Run all configuration validations and return any errors found.

        Returns:
            List of DiagnosisError entries. Empty list means config is valid.
        """
        from cis2hdl.core.config import config as cfg

        errors: list[DiagnosisError] = []

        # 1. Path existence checks
        errors.extend(self._validate_paths(cfg))

        # 2. Encoding checks
        errors.extend(self._validate_encodings(cfg))

        # 3. Dimension / grid checks
        errors.extend(self._validate_dimensions(cfg))

        if errors:
            logger.warning("Config validation found %d issue(s)", len(errors))
        else:
            logger.info("Config validation passed")

        return errors

    # ── Path validation ──────────────────────────────────────────────

    def _validate_paths(self, cfg) -> list[DiagnosisError]:
        """Validate that configured paths exist and are accessible."""
        errors: list[DiagnosisError] = []

        # HDL library path
        hdl_path = cfg.hdl_lib.hdl_lib_path
        if hdl_path:
            p = Path(hdl_path)
            if not p.exists():
                errors.append(DiagnosisError(
                    code=self.CONFIG_ERROR_BASE,
                    severity=Severity.ERROR,
                    category="CONFIG",
                    message=f"HDL 库路径不存在: {hdl_path}",
                    detail=f"配置的 hdl_lib_path '{hdl_path}' 不存在或无法访问",
                    suggestion="请在 Settings 中设置正确的 HDL 库根目录路径",
                    source_file="config.hdl_lib.hdl_lib_path",
                    can_ignore=False,
                ))
            elif not p.is_dir():
                errors.append(DiagnosisError(
                    code=self.CONFIG_ERROR_BASE + 1,
                    severity=Severity.ERROR,
                    category="CONFIG",
                    message=f"HDL 库路径不是目录: {hdl_path}",
                    detail=f"'{hdl_path}' 存在但不是目录",
                    suggestion="请确认 HDL 库路径指向正确的目录",
                    source_file="config.hdl_lib.hdl_lib_path",
                    can_ignore=False,
                ))

        # Cadence root (if set)
        cadence_root = cfg.hdl.cadence_root
        if cadence_root:
            p = Path(cadence_root)
            if not p.exists():
                errors.append(DiagnosisError(
                    code=self.CONFIG_ERROR_BASE + 2,
                    severity=Severity.WARNING,
                    category="CONFIG",
                    message=f"Cadence 根目录不存在: {cadence_root}",
                    detail="Cadence 安装路径不存在，生成的文件可能无法直接打开",
                    suggestion="请确认 Cadence SPB 安装路径正确",
                    source_file="config.hdl.cadence_root",
                    can_ignore=True,
                ))

        return errors

    # ── Encoding validation ──────────────────────────────────────────

    def _validate_encodings(self, cfg) -> list[DiagnosisError]:
        """Validate that declared encodings are valid Python codec names."""
        errors: list[DiagnosisError] = []

        encoding_fields = [
            ("chips_prt_encoding", cfg.hdl_lib.chips_prt_encoding),
            ("symbol_css_encoding", cfg.hdl_lib.symbol_css_encoding),
            ("part_ptf_encoding", cfg.hdl_lib.part_ptf_encoding),
            ("input_encoding", cfg.app.input_encoding),
            ("output_encoding", cfg.app.output_encoding),
        ]

        for field_name, encoding in encoding_fields:
            if not encoding or encoding.lower() not in self.VALID_ENCODINGS:
                normalized = encoding.lower() if encoding else ""
                errors.append(DiagnosisError(
                    code=self.CONFIG_ERROR_BASE + 3,
                    severity=Severity.WARNING,
                    category="CONFIG",
                    message=f"编码声明可能无效: {field_name} = '{encoding}'",
                    detail=(
                        f"编码 '{normalized}' 不在已知有效编码列表中。"
                        f"如果文件使用此编码，解析可能失败"
                    ),
                    suggestion=f"请确认 {field_name} 设置正确，常见编码: utf-8, gbk, ascii",
                    source_file=f"config.{field_name}",
                    can_ignore=True,
                ))

        return errors

    # ── Dimension validation ─────────────────────────────────────────

    def _validate_dimensions(self, cfg) -> list[DiagnosisError]:
        """Validate page size and grid spacing are within reasonable ranges."""
        errors: list[DiagnosisError] = []

        # Page width
        w = cfg.page.default_width
        if not isinstance(w, int) or w <= 0:
            errors.append(DiagnosisError(
                code=self.CONFIG_ERROR_BASE + 4,
                severity=Severity.ERROR,
                category="CONFIG",
                message=f"页面宽度非法: {w}",
                detail="页面宽度必须为正整数",
                suggestion="请设置合理的页面宽度（如 3520）",
                source_file="config.page.default_width",
                can_ignore=False,
            ))
        elif w < self.MIN_PAGE_WIDTH or w > self.MAX_PAGE_WIDTH:
            errors.append(DiagnosisError(
                code=self.CONFIG_ERROR_BASE + 4,
                severity=Severity.WARNING,
                category="CONFIG",
                message=f"页面宽度超出合理范围: {w}",
                detail=f"页面宽度应在 {self.MIN_PAGE_WIDTH}-{self.MAX_PAGE_WIDTH} 之间",
                suggestion=f"建议使用 creferhdl 标准页面尺寸（如 A=1700, C=2200, E=3520）",
                source_file="config.page.default_width",
                can_ignore=True,
            ))

        # Page height
        h = cfg.page.default_height
        if not isinstance(h, int) or h <= 0:
            errors.append(DiagnosisError(
                code=self.CONFIG_ERROR_BASE + 5,
                severity=Severity.ERROR,
                category="CONFIG",
                message=f"页面高度非法: {h}",
                detail="页面高度必须为正整数",
                suggestion="请设置合理的页面高度（如 2720）",
                source_file="config.page.default_height",
                can_ignore=False,
            ))
        elif h < self.MIN_PAGE_HEIGHT or h > self.MAX_PAGE_HEIGHT:
            errors.append(DiagnosisError(
                code=self.CONFIG_ERROR_BASE + 5,
                severity=Severity.WARNING,
                category="CONFIG",
                message=f"页面高度超出合理范围: {h}",
                detail=f"页面高度应在 {self.MIN_PAGE_HEIGHT}-{self.MAX_PAGE_HEIGHT} 之间",
                suggestion=f"建议使用 creferhdl 标准页面尺寸",
                source_file="config.page.default_height",
                can_ignore=True,
            ))

        # Grid spacing
        gs = cfg.page.grid_spacing
        if not isinstance(gs, int) or gs <= 0:
            errors.append(DiagnosisError(
                code=self.CONFIG_ERROR_BASE + 6,
                severity=Severity.ERROR,
                category="CONFIG",
                message=f"网格间距非法: {gs}",
                detail="网格间距必须为正整数",
                suggestion="建议使用标准网格间距 16",
                source_file="config.page.grid_spacing",
                can_ignore=False,
            ))
        elif gs < self.MIN_GRID_SPACING or gs > self.MAX_GRID_SPACING:
            errors.append(DiagnosisError(
                code=self.CONFIG_ERROR_BASE + 6,
                severity=Severity.WARNING,
                category="CONFIG",
                message=f"网格间距超出合理范围: {gs}",
                detail=f"网格间距应在 {self.MIN_GRID_SPACING}-{self.MAX_GRID_SPACING} 之间",
                suggestion="建议使用标准网格间距 16",
                source_file="config.page.grid_spacing",
                can_ignore=True,
            ))

        return errors
