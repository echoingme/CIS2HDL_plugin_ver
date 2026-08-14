"""CPM writer — generates Cadence DEHDL Project Manager .cpm files.

Output format matches the real Cadence DEHDL standard (reference: 8367.cpm).
The .cpm file is placed at the output root directory (not inside worklib).
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


class CPMWriter(WriterBase):
    """Generate .cpm project configuration file for Design Entry HDL.

    Output format matches Cadence DEHDL 16.6 standard:
        START_GLOBAL / END_GLOBAL with design_name, design_library,
        library list, temp_dir, and cpm_version fields.

    The .cpm file is placed at the **output root** (not in worklib),
    matching the real Cadence DEHDL Project Manager convention.
    """

    FORMAT_NAME = "cpm"

    def write(self, ir: "DesignIR", output_dir: Path) -> list[Path]:
        """Generate .cpm project file at the output root.

        Args:
            ir: DesignIR instance with project_name.
            output_dir: Output root directory.

        Returns:
            List containing the generated .cpm file path.
        """
        self._ensure_output_dir(output_dir)

        project_name = getattr(ir, "project_name", "") or "project"
        mgr = OutputManager(project_name=project_name, output_root=output_dir)

        cpm_path = mgr.write_cpm()
        logger.info("CPM writer: generated %s", cpm_path)
        return [cpm_path]
