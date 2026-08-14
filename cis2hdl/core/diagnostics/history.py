"""ConversionHistoryManager — persistent conversion history log.

Records each conversion run to a local JSON file (~/.cis2hdl/conversion_history.json)
with input file fingerprints, match statistics, error types, and user adjudications.
Automatically prunes entries beyond the configured maximum (default: 50).

Reference: ROADMAP D3.3.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────
MAX_ENTRIES: int = 50
"""Maximum number of history entries to retain before auto-pruning oldest."""

DEFAULT_HISTORY_DIR: Path = Path.home() / ".cis2hdl"
"""Default directory for conversion history storage."""

DEFAULT_HISTORY_FILE: str = "conversion_history.json"
"""Default filename for the history JSON file."""

# ── Data classes ─────────────────────────────────────────────────────────────


@dataclass
class HistoryEntry:
    """A single conversion history record.

    Attributes:
        id: Unique entry identifier (ISO-8601 timestamp).
        timestamp: When the conversion was performed.
        project_name: Name of the converted project.
        input_files: Dict of filename → MD5 hex digest.
        match_count: Total number of match results.
        auto_match_count: Number of automatically matched components.
        manual_match_count: Number of components requiring manual resolution.
        error_types: Unique error types encountered (e.g., "FILE_NOT_FOUND").
        warning_count: Total number of warnings.
        fatal_count: Number of FATAL-level errors (0 = successful conversion).
        output_file_count: Number of generated output files.
        user_adjudications: Dict of source_library_id → target_library_id
            for manually accepted matches during this conversion.
        quality_score: Overall quality score (0.0–1.0), if available.
    """

    id: str = ""
    timestamp: str = ""
    project_name: str = ""
    input_files: dict[str, str] = field(default_factory=dict)
    match_count: int = 0
    auto_match_count: int = 0
    manual_match_count: int = 0
    error_types: list[str] = field(default_factory=list)
    warning_count: int = 0
    fatal_count: int = 0
    output_file_count: int = 0
    user_adjudications: dict[str, str] = field(default_factory=dict)
    quality_score: Optional[float] = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary for JSON storage."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HistoryEntry":
        """Deserialize from a plain dictionary."""
        return cls(**{
            k: v for k, v in data.items()
            if k in cls.__dataclass_fields__
        })


# ── ConversionHistoryManager ─────────────────────────────────────────────────


class ConversionHistoryManager:
    """Manages persistent conversion history with automatic pruning.

    Stores up to MAX_ENTRIES records in ~/.cis2hdl/conversion_history.json.
    Thread-safe for concurrent access.

    Usage::

        mgr = ConversionHistoryManager()
        mgr.add_entry(report)
        entries = mgr.list_entries()
        entry = mgr.get_entry("2025-01-15T14-30-00")
    """

    def __init__(
        self,
        history_path: Optional[Path] = None,
        max_entries: int = MAX_ENTRIES,
    ) -> None:
        """Create a ConversionHistoryManager.

        Args:
            history_path: Path to the history JSON file.  If None, uses
                ~/.cis2hdl/conversion_history.json.
            max_entries: Maximum entries before auto-pruning (default: 50).
        """
        self._max_entries: int = max_entries
        self._lock: threading.Lock = threading.Lock()

        if history_path is None:
            history_path = DEFAULT_HISTORY_DIR / DEFAULT_HISTORY_FILE

        self._history_path: Path = history_path
        self._entries: list[HistoryEntry] = []

        # Ensure parent directory exists
        try:
            self._history_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            logger.warning(
                "Could not create history directory %s: %s",
                self._history_path.parent, exc,
            )

        # Load existing entries
        self._load()

    # ── Public API ────────────────────────────────────────────────────────

    def add_entry(self, report: Any) -> Optional[HistoryEntry]:
        """Record a conversion report in the history.

        Extracts relevant fields from a ConversionReport instance and
        saves the entry to the persistent JSON file.

        Args:
            report: A ConversionReport from conversion_engine.

        Returns:
            The created HistoryEntry, or None if the entry could not be saved.
        """
        from ..ir.match import MatchStrategy

        # Build entry ID from current timestamp
        now = datetime.now()
        entry_id = now.strftime("%Y-%m-%dT%H-%M-%S")
        timestamp = now.strftime("%Y-%m-%d %H:%M:%S")

        # ── Extract input files with MD5 ────────────────────────────────
        input_files: dict[str, str] = {}
        if hasattr(report, "diagnostic_report") and report.diagnostic_report is not None:
            dr = report.diagnostic_report
            if hasattr(dr, "inventory") and dr.inventory is not None:
                for key, fs in dr.inventory.files.items():
                    path_obj = Path(fs.path) if hasattr(fs, "path") else Path(str(fs))
                    if path_obj.exists():
                        try:
                            md5 = _compute_md5(path_obj)
                            input_files[str(path_obj)] = md5
                        except (OSError, PermissionError) as exc:
                            logger.debug("Could not hash %s: %s", path_obj, exc)

        # ── Match statistics ────────────────────────────────────────────
        match_results = getattr(report, "match_results", None) or []
        match_count = len(match_results)
        auto_match_count = sum(
            1 for m in match_results
            if getattr(m, "strategy", None) != MatchStrategy.MANUAL
        )
        manual_match_count = match_count - auto_match_count

        # ── Error types ─────────────────────────────────────────────────
        error_types: list[str] = []
        validation_errors = getattr(report, "validation_errors", None) or []
        stage_errors = getattr(report, "stage_errors", None) or {}
        for err in validation_errors:
            code_str = str(getattr(err, "code", "UNKNOWN"))
            if code_str not in error_types:
                error_types.append(code_str)
        for err_list in stage_errors.values():
            for err in err_list:
                code_str = str(getattr(err, "code", "UNKNOWN"))
                if code_str not in error_types:
                    error_types.append(code_str)

        # Also capture string errors from the errors list
        string_errors = getattr(report, "errors", None) or []
        for err_text in string_errors:
            err_type = _extract_error_type(str(err_text))
            if err_type not in error_types and err_type != "UNKNOWN":
                error_types.append(err_type)

        # ── Warning and fatal counts ────────────────────────────────────
        warning_count = len(getattr(report, "warnings", []) or [])
        fatal_count = 0
        for err_list in (getattr(report, "stage_errors", {}) or {}).values():
            fatal_count += sum(
                1 for e in err_list
                if str(getattr(e, "severity", "")).upper() == "FATAL"
            )

        # ── Output file count ───────────────────────────────────────────
        output_files = getattr(report, "output_files", None) or []

        # ── Quality score ───────────────────────────────────────────────
        quality = getattr(report, "quality", None)
        quality_score: Optional[float] = None
        if quality is not None and hasattr(quality, "overall_score"):
            quality_score = float(quality.overall_score)

        # ── User adjudications (manual matches) ─────────────────────────
        user_adjudications: dict[str, str] = {}
        manual_matches = getattr(report, "manual_matches", None) or []
        for m in manual_matches:
            src = getattr(m, "source_library_id", "")
            tgt = getattr(m, "target_library_id", "")
            if src and tgt:
                user_adjudications[src] = tgt

        entry = HistoryEntry(
            id=entry_id,
            timestamp=timestamp,
            project_name=getattr(report, "project_name", ""),
            input_files=input_files,
            match_count=match_count,
            auto_match_count=auto_match_count,
            manual_match_count=manual_match_count,
            error_types=error_types,
            warning_count=warning_count,
            fatal_count=fatal_count,
            output_file_count=len(output_files),
            user_adjudications=user_adjudications,
            quality_score=quality_score,
        )

        with self._lock:
            self._entries.append(entry)
            self._prune()
            self._save()

        logger.info(
            "History entry saved: %s (project='%s', matched=%d/%d, errors=%d)",
            entry.id,
            entry.project_name,
            entry.auto_match_count,
            entry.match_count,
            len(entry.error_types),
        )
        return entry

    def list_entries(
        self,
        limit: Optional[int] = None,
    ) -> list[HistoryEntry]:
        """List all history entries, newest first.

        Args:
            limit: Optional maximum number of entries to return.

        Returns:
            List of HistoryEntry objects in reverse chronological order.
        """
        with self._lock:
            entries = list(self._entries)
        # Newest first
        entries.sort(key=lambda e: e.id, reverse=True)
        if limit is not None:
            entries = entries[:limit]
        return entries

    def get_entry(self, entry_id: str) -> Optional[HistoryEntry]:
        """Retrieve a single history entry by its ID.

        Args:
            entry_id: The entry identifier (ISO-8601 timestamp).

        Returns:
            The matching HistoryEntry, or None if not found.
        """
        with self._lock:
            for entry in self._entries:
                if entry.id == entry_id:
                    return entry
        return None

    def count(self) -> int:
        """Return the total number of entries in the history."""
        with self._lock:
            return len(self._entries)

    def clear(self) -> None:
        """Clear all history entries and persist the empty state."""
        with self._lock:
            self._entries.clear()
            self._save()
        logger.info("History cleared")

    # ── Internal helpers ──────────────────────────────────────────────────

    def _load(self) -> None:
        """Load entries from the JSON file.  Silently succeeds if file
        does not exist or is malformed."""
        if not self._history_path.exists():
            return

        try:
            raw = self._history_path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load history file: %s", exc)
            return

        if not isinstance(data, list):
            logger.warning("History file is not a JSON array — resetting")
            return

        self._entries = [
            HistoryEntry.from_dict(item)
            for item in data
            if isinstance(item, dict)
        ]
        logger.debug("Loaded %d history entries from %s", len(self._entries), self._history_path)

    def _save(self) -> None:
        """Persist all entries to the JSON file (atomic write)."""
        try:
            data = [entry.to_dict() for entry in self._entries]
            json_text = json.dumps(data, indent=2, ensure_ascii=False, default=str)

            # Atomic write: write to temp file first, then rename
            tmp_path = self._history_path.with_suffix(".tmp")
            tmp_path.write_text(json_text, encoding="utf-8")
            tmp_path.replace(self._history_path)
        except OSError as exc:
            logger.error("Failed to save history file: %s", exc)

    def _prune(self) -> None:
        """Remove oldest entries if count exceeds max_entries."""
        while len(self._entries) > self._max_entries:
            removed = self._entries.pop(0)
            logger.debug("Pruned oldest history entry: %s", removed.id)


# ── File-level helpers ───────────────────────────────────────────────────────


def _compute_md5(file_path: Path, chunk_size: int = 8192) -> str:
    """Compute the MD5 hex digest of a file.

    Args:
        file_path: Path to the file.
        chunk_size: Read buffer size in bytes.

    Returns:
        Lowercase hex MD5 digest string.
    """
    md5 = hashlib.md5()
    with open(file_path, "rb") as fh:
        while True:
            chunk = fh.read(chunk_size)
            if not chunk:
                break
            md5.update(chunk)
    return md5.hexdigest()


def _extract_error_type(error_text: str) -> str:
    """Heuristically extract an error type keyword from an error message.

    Args:
        error_text: The full error message string.

    Returns:
        A short error type keyword (e.g., "FILE_NOT_FOUND", "PARSE_ERROR"),
        or "UNKNOWN" if no keyword is identified.
    """
    text_upper = error_text.upper()
    keywords = [
        "FILE_NOT_FOUND",
        "PARSE_ERROR",
        "MATCH_ERROR",
        "VALIDATION_ERROR",
        "WRITE_ERROR",
        "DIRECTORY_ERROR",
        "PERMISSION_DENIED",
        "FATAL",
        "ABORTED",
        "SCAN_ERROR",
        "GENERATION_ERROR",
        "IO_ERROR",
    ]
    for kw in keywords:
        if kw in text_upper:
            return kw
    return "UNKNOWN"
