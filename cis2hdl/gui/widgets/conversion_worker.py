"""ConversionWorker — background thread wrapper for ConversionEngine.

Runs the full six-stage conversion pipeline in a QThread to keep the
GUI responsive. Communicates progress, results, and errors via Qt signals.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from ...core.engine.conversion_engine import ConversionEngine, ConversionReport

logger = logging.getLogger(__name__)


class ConversionWorker(QObject):
    """Runs ``ConversionEngine.convert()`` on a background QThread.

    Usage::

        thread = QThread()
        worker = ConversionWorker(input_path, output_dir, hdl_lib_path)
        worker.moveToThread(thread)

        worker.progress.connect(on_progress)
        worker.finished.connect(on_finished)
        worker.error.connect(on_error)

        thread.started.connect(worker.run)
        thread.start()
    """

    #: Emitted during each stage transition: (stage_name, progress_pct, message)
    progress = Signal(str, float, str)

    #: Emitted when conversion completes successfully
    finished = Signal(object)

    #: Emitted when an unrecoverable error occurs
    error = Signal(str)

    def __init__(
        self,
        input_path: Path,
        output_dir: Path,
        hdl_lib_path: Path | None = None,
    ) -> None:
        """Initialize the worker with conversion parameters.

        Args:
            input_path: Path to the .dsn or .edf input file.
            output_dir: Output directory for generated HDL files.
            hdl_lib_path: Optional path to the HDL component library root.
        """
        super().__init__()
        self._input_path = input_path
        self._output_dir = output_dir
        self._hdl_lib_path = hdl_lib_path

    # ── Public Slots ─────────────────────────────────────────────────────

    @Slot()
    def run(self) -> None:
        """Execute the full conversion pipeline (called from QThread.started).

        This method creates a fresh ConversionEngine instance and calls
        ``convert()`` with progress tracking wired to the ``progress`` signal.

        On success, emits ``finished(report)``.
        On failure, emits ``error(message)``.
        """
        try:
            engine = ConversionEngine()

            def on_progress(stage: str, pct: float, msg: str) -> None:
                """Bridge engine callback → Qt signal (thread-safe via Signal)."""
                try:
                    self.progress.emit(stage, pct, msg)
                except Exception:
                    pass  # Never let signal emission crash the pipeline

            logger.info(
                "ConversionWorker starting: input=%s, output=%s",
                self._input_path,
                self._output_dir,
            )

            report: ConversionReport = engine.convert(
                input_path=self._input_path,
                output_dir=self._output_dir,
                hdl_lib_path=self._hdl_lib_path,
                progress_callback=on_progress,
            )

            logger.info("ConversionWorker complete: %s", report)
            self.finished.emit(report)

        except Exception as exc:
            error_msg = f"Conversion failed: {exc}"
            logger.exception(error_msg)
            self.error.emit(error_msg)
