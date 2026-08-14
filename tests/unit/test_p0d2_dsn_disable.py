"""P0-D2 unit tests — DSN disabled as component/net source.

Phase XI P0-D2: OrCAD projects ship a ``.dsn`` plus a same-name EDIF
export (``.edf``/``.EDF``).  The DSN RTL variant parses to 0 real
instances and thousands of fake nets (misparsed port names / raw
binary — e.g. HG5015: 3717 garbage nets), so ``convert()`` prefers the
sibling EDIF file whenever ``cfg.app.use_dsn_components`` is False
(the default).  ``pstxnet.dat`` remains the authoritative pin→net
injection (Stage 5.5b).

These tests cover the pure helper ``_prefer_edif_sibling`` and the
config contract that disables DSN components by default.
"""
from __future__ import annotations

from pathlib import Path


def _make_dsn(path: Path) -> Path:
    """Create a minimal .dsn placeholder file."""
    path.write_text("fake dsn content", encoding="utf-8")
    return path


def test_prefer_edif_sibling_returns_edf(tmp_path: Path) -> None:
    """A .dsn with a same-name .EDF sibling resolves to the EDIF file."""
    from cis2hdl.core.engine.conversion_engine import ConversionEngine
    dsn = _make_dsn(tmp_path / "proj.DSN")
    edf = tmp_path / "proj.EDF"
    edf.write_text("(edif X)", encoding="utf-8")
    result = ConversionEngine._prefer_edif_sibling(dsn)
    assert result is not None
    assert result == edf


def test_prefer_edif_sibling_lowercase(tmp_path: Path) -> None:
    """Lowercase .edf siblings are also preferred over the DSN."""
    from cis2hdl.core.engine.conversion_engine import ConversionEngine
    dsn = _make_dsn(tmp_path / "proj.dsn")
    edf = tmp_path / "proj.edf"
    edf.write_text("(edif X)", encoding="utf-8")
    result = ConversionEngine._prefer_edif_sibling(dsn)
    # Note: on case-insensitive filesystems (e.g. macOS default) the
    # helper may report the .EDF spelling even when the file was created
    # as .edf — both name spellings denote the same file.
    assert result is not None
    assert result.name.lower() == "proj.edf"


def test_prefer_edif_sibling_no_edif_returns_none(tmp_path: Path) -> None:
    """A .dsn without a sibling EDIF keeps DSN (standard-variant fallback)."""
    from cis2hdl.core.engine.conversion_engine import ConversionEngine
    dsn = _make_dsn(tmp_path / "proj.dsn")
    assert ConversionEngine._prefer_edif_sibling(dsn) is None


def test_prefer_edif_sibling_non_dsn_input_returns_none(tmp_path: Path) -> None:
    """Non-DSN inputs are never redirected."""
    from cis2hdl.core.engine.conversion_engine import ConversionEngine
    edf = tmp_path / "proj.edf"
    edf.write_text("(edif X)", encoding="utf-8")
    assert ConversionEngine._prefer_edif_sibling(edf) is None


def test_config_dsn_components_disabled_by_default() -> None:
    """P0-D2 contract: DSN component source is disabled by default."""
    from cis2hdl.core.config import config as cfg
    assert cfg.app.use_dsn_components is False
