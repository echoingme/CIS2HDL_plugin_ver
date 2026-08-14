"""FileRecoveryStrategy — 5-tier degradation path system.

When file-level errors are detected, the recovery strategy evaluates which
degradation paths are applicable and recommends the best one based on
data loss level and quality impact.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, ClassVar

from .diagnostic_report import (
    ProjectInventory,
    FileState,
)

logger = logging.getLogger(__name__)


# ── Data Loss Level Enum ────────────────────────────────────────────────────


class DataLossLevel(Enum):
    """Severity of data loss for a recovery path.

    Ordered from least to most severe:
        NONE              — No data loss (pure recovery).
        COORDINATES       — Coordinate / position data lost.
        PARTIAL_PAGES     — Some schematic pages are skipped.
        SYMBOL_FIDELITY   — Symbol graphics degraded.
        GRAPHICS          — All graphics lost, logic-only conversion.
    """

    NONE = "NONE"
    COORDINATES = "COORDINATES"
    PARTIAL_PAGES = "PARTIAL_PAGES"
    SYMBOL_FIDELITY = "SYMBOL_FIDELITY"
    GRAPHICS = "GRAPHICS"


# ── Recovery Path ───────────────────────────────────────────────────────────


@dataclass
class RecoveryPath:
    """A single recovery/degradation path.

    Attributes:
        id: Unique path identifier (e.g., "DSN_RECOVER_FROM_BACKUP").
        condition: Callable that returns True if this path is applicable.
        action: Human-readable action name.
        data_loss: Expected data loss level.
        quality_impact: Human-readable description of quality impact.
    """

    id: str
    condition: Callable[[ProjectInventory], bool]
    action: str
    data_loss: DataLossLevel
    quality_impact: str


# ── FileRecoveryStrategy ────────────────────────────────────────────────────


class FileRecoveryStrategy:
    """5-tier file recovery strategy.

    Evaluates which degradation paths are applicable based on the current
    project inventory state, and recommends the best (least data loss) path.

    Recovery paths (ordered by preference):
      1. DSN_RECOVER_FROM_BACKUP — Use .dbk backup instead of .dsn
      2. DSN_TO_EDIF — Fall back to EDIF for logic-only conversion
      3. SKIP_CORRUPTED_PAGES — Skip unparseable pages
      4. OLB_FROM_DSN_CACHE — Extract device definitions from DSN cache
      5. DEFAULT_RECTANGLE_SYMBOLS — Use default rectangle symbols
    """

    RECOVERY_PATHS: ClassVar[list[RecoveryPath]] = [
        # Path 1: Recover from .dbk backup
        RecoveryPath(
            id="DSN_RECOVER_FROM_BACKUP",
            condition=lambda inv: any(
                fs.file_type == "DBK" and fs.state == FileState.FOUND_OK
                for fs in inv.files.values()
            ),
            action="使用 .dbk 备份文件替代损坏的 .dsn",
            data_loss=DataLossLevel.NONE,
            quality_impact="使用最近备份恢复，可能丢失自上次保存以来的编辑内容",
        ),
        # Path 2: Fall back to EDIF logic-only
        RecoveryPath(
            id="DSN_TO_EDIF",
            condition=lambda inv: any(
                fs.file_type == "EDF" and fs.state == FileState.FOUND_OK
                for fs in inv.files.values()
            ),
            action="使用 EDIF 文件进行仅逻辑转换",
            data_loss=DataLossLevel.COORDINATES,
            quality_impact="逻辑数据完整，但器件坐标和连线路径将不可用。建议连接成功能恢复的 DSN 文件",
        ),
        # Path 3: Skip corrupted pages
        RecoveryPath(
            id="SKIP_CORRUPTED_PAGES",
            condition=lambda inv: (
                inv.dsn_internal.total_pages > 0
                and inv.dsn_internal.pages_parsed < inv.dsn_internal.total_pages
            ),
            action="跳过损坏的页面，仅转换可成功解析的页面",
            data_loss=DataLossLevel.PARTIAL_PAGES,
            quality_impact="部分页面将被跳过，仅转换可成功解析的页面",
        ),
        # Path 4: Extract from DSN cache
        RecoveryPath(
            id="OLB_FROM_DSN_CACHE",
            condition=lambda inv: (
                inv.dsn_internal.cache_entries > 0
                and not any(
                    fs.file_type == "OLB" and fs.state == FileState.FOUND_OK
                    for fs in inv.files.values()
                )
            ),
            action="从 DSN Cache 中提取嵌入式器件定义",
            data_loss=DataLossLevel.SYMBOL_FIDELITY,
            quality_impact=(
                "无引脚名称信息，器件符号使用默认矩形。"
                "提供 OLB 文件可大幅提升转换质量"
            ),
        ),
        # Path 5: Default rectangle symbols
        RecoveryPath(
            id="DEFAULT_RECTANGLE_SYMBOLS",
            condition=lambda inv: True,  # Always applicable as last resort
            action="使用默认矩形符号生成器件",
            data_loss=DataLossLevel.GRAPHICS,
            quality_impact=(
                "所有器件使用默认矩形符号，无原始图形保真度。"
                "逻辑连接保持完整"
            ),
        ),
    ]

    def find_applicable(self, inventory: ProjectInventory) -> list[RecoveryPath]:
        """Find all recovery paths applicable to the current inventory.

        Args:
            inventory: ProjectInventory with file status information.

        Returns:
            List of applicable RecoveryPath entries, sorted by data loss
            (least loss first).
        """
        applicable: list[RecoveryPath] = []
        for path in self.RECOVERY_PATHS:
            try:
                if path.condition(inventory):
                    applicable.append(path)
                    logger.debug("Recovery path '%s' is applicable", path.id)
            except Exception as exc:
                logger.warning(
                    "Recovery path '%s' condition check failed: %s", path.id, exc
                )

        # Sort by data loss level (NONE first, GRAPHICS last)
        applicable.sort(key=lambda p: list(DataLossLevel).index(p.data_loss))
        return applicable

    def recommend(self, paths: list[RecoveryPath]) -> RecoveryPath | None:
        """Recommend the best recovery path from a list of applicable paths.

        Returns the path with the least data loss. If the list is empty,
        returns None (no recovery possible).

        Args:
            paths: List of applicable RecoveryPath entries (from find_applicable).

        Returns:
            The highest-priority RecoveryPath, or None.
        """
        if not paths:
            logger.warning("No recovery paths available")
            return None

        # Already sorted by data loss in find_applicable
        best = paths[0]
        logger.info(
            "Recommended recovery: %s (data_loss=%s, impact='%s')",
            best.id, best.data_loss.value, best.quality_impact,
        )
        return best

    def evaluate(self, inventory: ProjectInventory) -> list[RecoveryPath]:
        """Evaluate and return sorted applicable recovery paths.

        Convenience method: calls find_applicable then returns sorted result.

        Args:
            inventory: ProjectInventory to evaluate.

        Returns:
            Sorted list of applicable RecoveryPath entries.
        """
        return self.find_applicable(inventory)

    def execute(
        self,
        path: RecoveryPath,
        inventory: ProjectInventory,
    ) -> ProjectInventory:
        """Execute a recovery path on the inventory.

        Applies the recovery action to the inventory and returns the
        modified (recovered) inventory. The action depends on the path:

          - DSN_RECOVER_FROM_BACKUP: Switches DSN to DBK.
          - DSN_TO_EDIF: Switches primary source to EDIF.
          - SKIP_CORRUPTED_PAGES: Marks corrupted pages as skipped.
          - OLB_FROM_DSN_CACHE: Adds note about cache extraction.
          - DEFAULT_RECTANGLE_SYMBOLS: Adds note about default symbols.

        Args:
            path: The RecoveryPath to execute.
            inventory: The current ProjectInventory.

        Returns:
            A potentially modified ProjectInventory after recovery.
        """
        from .diagnostic_report import ActionItem, ActionVerb, FileStatus

        logger.info("Executing recovery path: %s — %s", path.id, path.action)

        if path.id == "DSN_RECOVER_FROM_BACKUP":
            # Swap DSN with DBK
            for key, status in inventory.files.items():
                if status.file_type == "DSN" and status.state != FileState.FOUND_OK:
                    # Find the DBK
                    for k2, s2 in inventory.files.items():
                        if s2.file_type == "DBK" and s2.state == FileState.FOUND_OK:
                            # Replace DSN with DBK
                            inventory.files[key] = FileStatus(
                                path=s2.path,
                                file_type="DSN",  # Treat as DSN now
                                state=FileState.FOUND_OK,
                                size=s2.size,
                                summary=f"从 DBK 备份恢复: {s2.path}",
                                data_quality=s2.data_quality,
                            )
                            inventory.actions.append(
                                ActionItem(
                                    verb=ActionVerb.REPAIR,
                                    target=str(s2.path),
                                    reason="已从 DBK 备份恢复 DSN 文件",
                                    priority=0,
                                )
                            )
                            break
                    break

        elif path.id == "DSN_TO_EDIF":
            # Add EDIF as primary source
            for key, status in inventory.files.items():
                if status.file_type == "EDF" and status.state == FileState.FOUND_OK:
                    inventory.actions.append(
                        ActionItem(
                            verb=ActionVerb.CHECK,
                            target=str(status.path),
                            reason="已切换到 EDIF 逻辑转换模式",
                            priority=0,
                        )
                    )
                    break

        elif path.id == "SKIP_CORRUPTED_PAGES":
            inventory.dsn_internal.pages_parsed = sum(
                1 for v in inventory.dsn_internal.page_details.values() if v
            )
            skipped = inventory.dsn_internal.total_pages - inventory.dsn_internal.pages_parsed
            inventory.actions.append(
                ActionItem(
                    verb=ActionVerb.IGNORE,
                    target="损坏页面",
                    reason=f"已跳过 {skipped} 个无法解析的页面",
                    priority=0,
                )
            )

        elif path.id == "OLB_FROM_DSN_CACHE":
            inventory.actions.append(
                ActionItem(
                    verb=ActionVerb.CHECK,
                    target="DSN Cache",
                    reason=f"从 DSN Cache 提取了 {inventory.dsn_internal.cache_entries} 个器件定义",
                    priority=0,
                )
            )

        elif path.id == "DEFAULT_RECTANGLE_SYMBOLS":
            inventory.actions.append(
                ActionItem(
                    verb=ActionVerb.IGNORE,
                    target="默认矩形符号",
                    reason="使用默认矩形符号生成所有器件",
                    priority=0,
                )
            )

        return inventory
