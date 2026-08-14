"""IncrementalConversionTracker — checkpoint/resume support for conversion.

Persists conversion state to ``.cis2hdl_state.json`` so that interrupted
conversions can be resumed from the last completed page.

Reference: ROADMAP D2.6.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class IncrementalConversionTracker:
    """Tracks conversion progress for checkpoint/resume support.

    Writes a ``.cis2hdl_state.json`` file in the output directory recording
    which pages have been completed, matched components, and generated files.
    On resume, reads the state file and returns pending pages.

    Usage:
        tracker = IncrementalConversionTracker()
        tracker.save(output_dir, {"completed_pages": [1, 2], ...})
        state = tracker.load(output_dir)
        pending = tracker.get_pending_pages(5, output_dir)
    """

    STATE_FILE: str = ".cis2hdl_state.json"

    # ── Save / Load ──────────────────────────────────────────────────

    def save(self, output_dir: Path, state: dict[str, Any]) -> None:
        """Persist the current conversion state to disk.

        Args:
            output_dir: The conversion output directory.
            state: Arbitrary state dictionary to persist. Must be
                   JSON-serializable.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        state_path = output_dir / self.STATE_FILE

        # Ensure path values are strings
        serializable = self._make_serializable(state)

        try:
            state_path.write_text(
                json.dumps(serializable, indent=2, ensure_ascii=False, default=str),
                encoding="utf-8",
            )
            logger.debug("State saved to %s: %d keys", state_path, len(serializable))
        except (OSError, TypeError) as exc:
            logger.warning("Failed to save state to %s: %s", state_path, exc)

    def load(self, output_dir: Path) -> dict[str, Any] | None:
        """Load the persisted conversion state, if it exists.

        Args:
            output_dir: The conversion output directory.

        Returns:
            The state dictionary, or None if no state file exists or
            it cannot be read.
        """
        state_path = output_dir / self.STATE_FILE
        if not state_path.exists():
            logger.debug("No state file at %s", state_path)
            return None

        try:
            content = state_path.read_text(encoding="utf-8")
            state: dict[str, Any] = json.loads(content)
            logger.debug("State loaded from %s: %d keys", state_path, len(state))
            return state
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load state from %s: %s", state_path, exc)
            return None

    # ── Page tracking ────────────────────────────────────────────────

    def mark_page_done(self, page_id: int, output_dir: Path) -> None:
        """Record a page as completed in the state file.

        Args:
            page_id: The 1-based page number that has been completed.
            output_dir: The conversion output directory.
        """
        state = self.load(output_dir) or {}
        completed: list[int] = state.get("completed_pages", [])
        if page_id not in completed:
            completed.append(page_id)
            completed.sort()
        state["completed_pages"] = completed
        self.save(output_dir, state)
        logger.debug("Page %d marked as done", page_id)

    def get_pending_pages(
        self,
        total_pages: int,
        output_dir: Path,
    ) -> list[int]:
        """Return the list of page numbers that still need processing.

        Args:
            total_pages: Total number of pages in the design (1-based).
            output_dir: The conversion output directory.

        Returns:
            Sorted list of pending (not yet completed) page numbers.
        """
        state = self.load(output_dir)
        completed: list[int] = state.get("completed_pages", []) if state else []
        completed_set = set(completed)
        pending = [i for i in range(1, total_pages + 1) if i not in completed_set]
        logger.debug(
            "Pending pages: %s (completed: %s, total: %d)",
            pending, completed, total_pages,
        )
        return pending

    # ── Match tracking ───────────────────────────────────────────────

    def mark_match_done(
        self,
        source_library_id: str,
        target_library_id: str,
        output_dir: Path,
    ) -> None:
        """Record a component match in the state file.

        Args:
            source_library_id: CIS component library ID.
            target_library_id: Matched HDL component library ID.
            output_dir: The conversion output directory.
        """
        state = self.load(output_dir) or {}
        matches: dict[str, str] = state.get("completed_matches", {})
        matches[source_library_id] = target_library_id
        state["completed_matches"] = matches
        self.save(output_dir, state)

    # ── Helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _make_serializable(obj: Any) -> Any:
        """Recursively convert Path objects and other non-serializable
        types to JSON-safe equivalents."""
        if isinstance(obj, Path):
            return str(obj)
        if isinstance(obj, dict):
            return {
                str(k): IncrementalConversionTracker._make_serializable(v)
                for k, v in obj.items()
            }
        if isinstance(obj, (list, tuple, set)):
            return [IncrementalConversionTracker._make_serializable(v) for v in obj]
        return obj
