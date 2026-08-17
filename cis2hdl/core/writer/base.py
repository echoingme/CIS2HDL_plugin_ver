from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cis2hdl.core.ir.design import DesignIR


class WriterBase(ABC):
    """Base class for all format writers.

    Each writer translates DesignIR (or PageIR) into a specific output format
    and writes the result to the file system.
    """

    FORMAT_NAME: str = ""

    @abstractmethod
    def write(self, ir: "DesignIR | PageIR | object", output_dir: Path) -> list[Path]:
        """Write IR to target format files in output_dir.

        Args:
            ir: DesignIR (for project-level writers) or PageIR (for page-level writers).
            output_dir: Output directory for generated files.

        Returns:
            List of generated file paths.
        """
        ...

    def _ensure_output_dir(self, output_dir: Path) -> None:
        """Create output directory if it does not exist."""
        output_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _resolve_body_name(inst, *, default: str = "capacitor") -> str:
        """Resolve the HDL body name (directory name) from a component instance.

        Resolution order:
          1. ``inst.library_id`` → extract last segment after ``/``, lowercased.
          2. ``inst.refdes`` → extract prefix, lowercased.
          3. Return *default*.

        Subclasses may override this to add instance-specific lookups
        (e.g. ``_match_map``, ``_component_db``).

        v1.0: Removed hardcoded _PREFIX_MAP.  RefDes prefix is used
        directly as the body name when library_id is unavailable.

        Args:
            inst: ComponentInstanceIR or similar object with ``library_id``
                  and ``refdes`` attributes.
            default: Fallback body name when no library_id or refdes prefix
                     can be resolved.

        Returns:
            Body name string in lowercase (e.g. ``"capacitor"``, ``"rtl8367"``).
        """
        # Deferred import to avoid circular dependency at module level
        from ..matcher.prefix_filter import extract_prefix  # pragma: no cover

        library_id: str = getattr(inst, "library_id", "")
        if library_id:
            return library_id.rsplit("/", 1)[-1].lower()

        refdes: str = getattr(inst, "refdes", "")
        if refdes:
            prefix: str = extract_prefix(refdes)
            if prefix:
                return prefix.lower()

        return default

    @staticmethod
    def _resolve_prop(props: dict[str, str], key: str) -> str:
        """Look up a property value case-insensitively (unified impl).

        Merged from the former ``CSAWriter._resolve_prop`` and
        ``SCHWriterCSA._resolve_property`` duplicate implementations
        (S7 cleanup, BACKLOG #24).

        Args:
            props: Property dictionary (e.g. ``inst.properties``).
            key: Property name (e.g. ``"SN_NUM"``, ``"PACKAGE_TYPE"``).

        Returns:
            Property value or empty string if not found.
        """
        if key in props:
            return props[key]
        key_lower: str = key.lower()
        for k, v in props.items():
            if k.lower() == key_lower:
                return v
        return ""


class WriterRegistry:
    """Registry of format writers accessed by FORMAT_NAME.

    Usage:
        registry = WriterRegistry()
        registry.register(CPMWriter())
        writer = registry.get("cpm")
        files = writer.write(design_ir, output_dir)
    """

    _writers: dict[str, WriterBase] = {}

    @classmethod
    def register(cls, writer: WriterBase) -> None:
        """Register a writer instance.

        Args:
            writer: WriterBase instance with a unique FORMAT_NAME.
        """
        cls._writers[writer.FORMAT_NAME] = writer

    @classmethod
    def get(cls, name: str) -> WriterBase:
        """Retrieve a writer by its FORMAT_NAME.

        Args:
            name: FORMAT_NAME of the writer (e.g., "cpm", "sch", "cdslib").

        Returns:
            The registered WriterBase instance.

        Raises:
            KeyError: If no writer with the given name is registered.
        """
        if name not in cls._writers:
            available = list(cls._writers.keys())
            raise KeyError(
                f"Writer '{name}' not registered. Available writers: {available}"
            )
        return cls._writers[name]

    @classmethod
    def list_writers(cls) -> list[str]:
        """Return names of all registered writers."""
        return list(cls._writers.keys())
