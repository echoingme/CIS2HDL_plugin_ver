"""Shared pytest fixtures for CIS2HDL tests.

Provides:
    - DSN/EDF/OLB fixture file paths (session-scoped).
    - Minimal DesignIR, PageIR, ComponentDB, MatchResult builders
      for unit tests (function-scoped).
    - ``temp_output_dir`` alias for ``tmp_path``.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from cis2hdl.core.ir.component import ComponentDef, ComponentInstanceIR, ElectricalType, PinDef
from cis2hdl.core.ir.design import DesignIR, NetConnection, NetIR, PageIR
from cis2hdl.core.ir.match import MatchResult, MatchStrategy
from cis2hdl.core.db.component_db import ComponentDB

if TYPE_CHECKING:
    from collections.abc import Generator


# ═══════════════════════════════════════════════════════════════════════════
#  Session-scoped fixture file paths
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    """Root directory containing test fixture data files (DSN, EDF, OLB, etc.)."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def simple_dsn_path(fixtures_dir: Path) -> Path:
    """Path to a minimal DSN fixture (dff_sync_sr.dsn) — 1 page, ~2 instances."""
    return fixtures_dir / "dff_sync_sr.dsn"


@pytest.fixture(scope="session")
def real_dsn_path(fixtures_dir: Path) -> Path:
    """Path to a real-world RTL8367RB DSN fixture (6 pages, ~12+ instances)."""
    return fixtures_dir / "RTL8367RB-VC-DEMO-LQFP128EP-P4L-V1_0.DSN"


@pytest.fixture(scope="session")
def real_edf_path(fixtures_dir: Path) -> Path:
    """Path to the EDIF export of the RTL8367RB project."""
    return fixtures_dir / "RTL8367RB-VC-DEMO-LQFP128EP-P4L-V1_0.EDF"


@pytest.fixture(scope="session")
def real_olb_path(fixtures_dir: Path) -> Path:
    """Path to the OLB component library fixture."""
    return fixtures_dir / "LIBRARY2CLEAN.OLB"


@pytest.fixture(scope="session")
def hdl_lib_dir(fixtures_dir: Path) -> Path:
    """Path to the HDL component library directory used for matching."""
    return fixtures_dir / "hdl_lib"


@pytest.fixture(scope="session")
def corrupted_dsn_truncated(fixtures_dir: Path) -> Path:
    """Path to a DSN file truncated mid-stream (corruption test fixture)."""
    return fixtures_dir / "RTL8367RB-CORRUPTED-TRUNCATED.DSN"


@pytest.fixture(scope="session")
def corrupted_dsn_sector(fixtures_dir: Path) -> Path:
    """Path to a DSN file with a corrupted sector (corruption test fixture)."""
    return fixtures_dir / "RTL8367RB-CORRUPTED-SECTOR.DSN"


# ═══════════════════════════════════════════════════════════════════════════
#  Function-scoped model builders (shared across unit tests)
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture
def sample_design() -> DesignIR:
    """Minimal DesignIR with 1 page containing 2 resistors and 1 net.

    Suitable for writer unit tests (CPM, SCH, CDSLib, etc.).
    """
    r1 = ComponentInstanceIR(
        refdes="R1", library_id="RES_0603_10K", loc_x=100, loc_y=100,
    )
    r2 = ComponentInstanceIR(
        refdes="R2", library_id="RES_0603_10K", loc_x=300, loc_y=100,
    )
    net = NetIR(name="N00001", connections=[
        NetConnection(refdes="R1", pin_number="1"),
        NetConnection(refdes="R2", pin_number="2"),
    ])
    page = PageIR(
        page_id="1.1", page_name="MAIN", instances=[r1, r2], nets=[net],
    )
    return DesignIR(project_name="test_design", pages=[page])


@pytest.fixture
def sample_page(sample_design: DesignIR) -> PageIR:
    """Single PageIR with 2 resistor instances (extracted from sample_design)."""
    return sample_design.pages[0]


@pytest.fixture
def sample_component_db() -> ComponentDB:
    """Minimal ComponentDB pre-populated with 2 resistor components.

    Each component has 2 pins (1, 2) and a standard 0603 footprint.
    """
    db = ComponentDB()
    for lid in ("RES_0603_10K", "RES_0603_1K"):
        pins = [
            PinDef(number="1", name="A", type=ElectricalType.PASSIVE),
            PinDef(number="2", name="B", type=ElectricalType.PASSIVE),
        ]
        comp = ComponentDef(
            library_id=lid,
            part_name=lid,
            footprint="0603",
            value="10K" if "10K" in lid else "1K",
            pins=pins,
        )
        db.add(comp)
    return db


@pytest.fixture
def sample_match_result() -> MatchResult:
    """A MatchResult representing a high-confidence exact match."""
    return MatchResult(
        confidence=1.0,
        strategy=MatchStrategy.EXACT,
        source_library_id="RES_0603_10K",
        target_library_id="hdl_lib/resistor",
        warnings=[],
    )


@pytest.fixture
def temp_output_dir(tmp_path: Path) -> Path:
    """Temporary output directory for writer tests (alias for tmp_path)."""
    return tmp_path
