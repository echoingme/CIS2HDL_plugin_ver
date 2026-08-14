"""CDSLib writer — generates cds.lib library definition file.

Output format matches the real Cadence DEHDL standard (reference: cds.lib).
The cds.lib file is placed at the output root.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from .base import WriterBase
from .output_manager import OutputManager
from ..config import config as cfg

if TYPE_CHECKING:
    from cis2hdl.core.ir.design import DesignIR

logger = logging.getLogger(__name__)


class CDSLibWriter(WriterBase):
    """Generate cds.lib library definition file.

    Format (matching Cadence DEHDL standard)::

        DEFINE <library_alias> worklib
        INCLUDE $CONCEPT_INST_DIR/share/cdssetup/cds.lib
        DEFINE hdl_lib hdl_lib
    """

    FORMAT_NAME = "cdslib"

    def write(self, ir: "DesignIR", output_dir: Path) -> list[Path]:
        """Generate cds.lib file at the output root.

        Args:
            ir: DesignIR instance with project_name.
            output_dir: Output root directory.

        Returns:
            List containing the generated cds.lib file path.
        """
        self._ensure_output_dir(output_dir)

        project_name = getattr(ir, "project_name", "") or "project"
        mgr = OutputManager(project_name=project_name, output_root=output_dir)

        cdslib_path = mgr.write_cdslib()
        logger.info("CDSLib writer: generated %s", cdslib_path)
        return [cdslib_path]
