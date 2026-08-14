# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for CIS2HDL application.

Usage:
    pyinstaller cis2hdl.spec
    # Or:
    python scripts/build_exe.py

Output:
    dist/CIS2HDL.exe   (--onefile mode, Windows)
    dist/CIS2HDL/      (--onedir mode, cross-platform)
"""

import sys
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────

_ROOT = Path(__file__).parent.absolute()
_ENTRY = str(_ROOT / "cis2hdl" / "__main__.py")
_ICON = str(_ROOT / "resources" / "icon.ico") if (_ROOT / "resources" / "icon.ico").exists() else None
_HDL_LIB_DIR = str(_ROOT / "hdl_lib")
_NAME = "CIS2HDL"

# ── Hidden imports for pydantic v2 ───────────────────────────────────────

_hiddenimports = [
    # pydantic v2 core modules
    "pydantic",
    "pydantic_core",
    "pydantic.deprecated.decorator",
    "pydantic.deprecated.copy_internals",
    "pydantic.functional_validators",
    "pydantic.main",
    "pydantic.type_adapter",
    "pydantic._internal._config",
    "pydantic._internal._decorators",
    "pydantic._internal._fields",
    "pydantic._internal._generate_schema",
    "pydantic._internal._internal_dataclass",
    "pydantic._internal._model_construction",
    "pydantic._internal._repr",
    "pydantic._internal._schema_generation_shared",
    "pydantic._internal._typing_extra",
    "pydantic._internal._utils",
    "pydantic._internal._validate_call",
    "pydantic._internal._validators",
    "pydantic.annotated_handlers",
    "pydantic.errors",
    "pydantic.warnings",
    # PySide6
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "PySide6.QtNetwork",
    # cis2hdl application modules
    "cis2hdl",
    "cis2hdl.core",
    "cis2hdl.core.config",
    "cis2hdl.core.exceptions",
    "cis2hdl.core.net_utils",
    "cis2hdl.core.parser",
    "cis2hdl.core.parser.base",
    "cis2hdl.core.parser.edif_parser",
    "cis2hdl.core.parser.hdl_scanner",
    "cis2hdl.core.parser.chips_prt",
    "cis2hdl.core.parser.part_ptf",
    "cis2hdl.core.parser.symbol_css",
    "cis2hdl.core.parser.cross_validator",
    "cis2hdl.core.parser.layout_mapper",
    "cis2hdl.core.parser.dsn",
    "cis2hdl.core.parser.dsn.binary_reader",
    "cis2hdl.core.parser.dsn.ole_reader",
    "cis2hdl.core.parser.dsn.structures",
    "cis2hdl.core.parser.dsn.page_parser",
    "cis2hdl.core.parser.dsn.dsn_parser",
    "cis2hdl.core.parser.dsn.property_audit",
    "cis2hdl.core.parser.olb",
    "cis2hdl.core.parser.olb.olb_reader",
    "cis2hdl.core.parser.olb.olb_parser",
    "cis2hdl.core.ir",
    "cis2hdl.core.ir.component",
    "cis2hdl.core.ir.design",
    "cis2hdl.core.ir.match",
    "cis2hdl.core.db",
    "cis2hdl.core.db.component_db",
    "cis2hdl.core.engine",
    "cis2hdl.core.engine.conversion_engine",
    "cis2hdl.core.matcher",
    "cis2hdl.core.matcher.base",
    "cis2hdl.core.matcher.exact",
    "cis2hdl.core.matcher.feature",
    "cis2hdl.core.matcher.fuzzy",
    "cis2hdl.core.matcher.pipeline",
    "cis2hdl.core.matcher.prefix_filter",
    "cis2hdl.core.matcher.registry",
    "cis2hdl.core.validator",
    "cis2hdl.core.validator.base",
    "cis2hdl.core.validator.net_validator",
    "cis2hdl.core.validator.pin_validator",
    "cis2hdl.core.validator.power_validator",
    "cis2hdl.core.validator.registry",
    "cis2hdl.core.writer",
    "cis2hdl.core.writer.base",
    "cis2hdl.core.writer.cpm_writer",
    "cis2hdl.core.writer.cdslib_writer",
    "cis2hdl.core.writer.sch_writer",
    "cis2hdl.core.writer.csa_writer",
    "cis2hdl.core.writer.xcon_writer",
    "cis2hdl.core.writer.output_manager",
    "cis2hdl.core.writer.cpc_writer",
    "cis2hdl.core.diagnostics",
    "cis2hdl.core.diagnostics.config_validator",
    "cis2hdl.core.diagnostics.diagnostic_report",
    "cis2hdl.core.diagnostics.error_diagnosis",
    "cis2hdl.core.diagnostics.file_inventory",
    "cis2hdl.core.diagnostics.file_validator",
    "cis2hdl.core.diagnostics.pipeline",
    "cis2hdl.core.diagnostics.quality",
    "cis2hdl.core.diagnostics.recovery",
    "cis2hdl.core.diagnostics.report_gen",
    "cis2hdl.core.diagnostics.tracker",
    "cis2hdl.gui",
    "cis2hdl.gui.app",
    "cis2hdl.gui.colors",
    "cis2hdl.gui.main_window",
    "cis2hdl.gui.dialogs",
    "cis2hdl.gui.dialogs.match_confirm",
    "cis2hdl.gui.dialogs.recovery_dialog",
    "cis2hdl.gui.dialogs.settings_dialog",
    "cis2hdl.gui.panels",
    "cis2hdl.gui.panels.diagnostic_panel",
    "cis2hdl.gui.panels.error_diagnostic_panel",
    "cis2hdl.gui.panels.log_panel",
    "cis2hdl.gui.panels.match_review",
    "cis2hdl.gui.panels.preview_panel",
    "cis2hdl.gui.panels.project_panel",
    "cis2hdl.gui.panels.report_panel",
    "cis2hdl.gui.panels.sidebar",
    "cis2hdl.gui.panels.summary_bar",
    "cis2hdl.gui.panels.tab_container",
    "cis2hdl.gui.widgets",
    "cis2hdl.gui.widgets.conversion_worker",
    "cis2hdl.utils",
    "cis2hdl.utils.naming",
    # Library dependencies
    "rapidfuzz",
    "rapidfuzz.distance",
    "rapidfuzz.process",
    "sexpdata",
    "yaml",
    "struct",
    "re",
    "logging",
    "pathlib",
    "dataclasses",
    "enum",
    "abc",
]

# ── Data files ───────────────────────────────────────────────────────────

_datas = []
_hdl_lib_path = Path(_HDL_LIB_DIR)
if _hdl_lib_path.exists() and _hdl_lib_path.is_dir():
    _datas.append((_HDL_LIB_DIR, "hdl_lib"))

# ── Spec ─────────────────────────────────────────────────────────────────

a = Analysis(
    [_ENTRY],
    pathex=[str(_ROOT)],
    binaries=[],
    datas=_datas,
    hiddenimports=_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "test",
        "unittest",
        "setuptools",
        "distutils",
        "pip",
        "pkg_resources",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

# ── One-file executable ──────────────────────────────────────────────────

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name=_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,          # Show console for CLI usage; set False for GUI-only
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=_ICON,
)

# ── One-directory (alternative) ──────────────────────────────────────────
# Uncomment the following and comment out the EXE block above to use onedir:
#
# coll = COLLECT(
#     exe,
#     a.binaries,
#     a.zipfiles,
#     a.datas,
#     strip=False,
#     upx=True,
#     upx_exclude=[],
#     name=_NAME,
# )
