#!/usr/bin/env python3
"""Multi-source cross-validation script.

Usage:
    python scripts/verify_multi_source.py <dsn_path> <edf_path> [pstxnet_path]

Example:
    python scripts/verify_multi_source.py \\
        tests/fixtures/RTL8367RB-VC-DEMO-LQFP128EP-P4L-V1_0.DSN \\
        tests/fixtures/RTL8367RB-VC-DEMO-LQFP128EP-P4L-V1_0.EDF
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure cis2hdl is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cis2hdl.core.parser.dsn.dsn_parser import DSNParser
from cis2hdl.core.parser.edif_parser import EDIFParser
from cis2hdl.core.diagnostics.multi_source import (
    MultiSourceCrossValidator,
    MultiSourceValidationReport,
)


def main() -> None:
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    dsn_path = Path(sys.argv[1])
    edf_path = Path(sys.argv[2])
    pstxnet_path = Path(sys.argv[3]) if len(sys.argv) > 3 else None

    print(f"DSN: {dsn_path}")
    print(f"EDF: {edf_path}")
    if pstxnet_path:
        print(f"PSTXNET: {pstxnet_path}")

    # Parse
    dsn_parser = DSNParser()
    edf_parser = EDIFParser()
    dsn_ir = dsn_parser.parse(dsn_path)
    edf_ir = edf_parser.parse(edf_path)

    dsn_total = sum(len(p.instances) for p in dsn_ir.pages)
    edf_total = sum(len(p.instances) for p in edf_ir.pages)
    print(f"\nDSN instances: {dsn_total}, EDF instances: {edf_total}")

    # Validate
    validator = MultiSourceCrossValidator()
    report = validator.validate(
        dsn_ir=dsn_ir,
        edf_ir=edf_ir,
        pstxnet_path=pstxnet_path,
        dsn_path=str(dsn_path),
        edf_path=str(edf_path),
    )

    print(f"\n{report.summary()}")
    print(f"\nDetailed report:")
    print(report.detailed_report())

    if report.error_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
