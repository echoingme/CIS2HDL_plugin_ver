from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Optional


class ComponentDB:
    """Unified component database — stores components from CIS and HDL sources.

    All components use ComponentDef regardless of origin format.
    """

    def __init__(self):
        self._by_library_id: dict[str, "ComponentDef"] = {}
        self._by_part_name: dict[str, list["ComponentDef"]] = defaultdict(list)
        self._by_footprint: dict[str, list["ComponentDef"]] = defaultdict(list)
        self._by_category: dict[str, list["ComponentDef"]] = defaultdict(list)
        # PHYS_DES_PREFIX index: prefix → [cell_names (library_id + part_name)]
        self._phys_des_index: dict[str, list[str]] = {}
        self._phys_des_index_built: bool = False

    # ------------------------------------------------------------------
    #  Registration
    # ------------------------------------------------------------------

    def add(self, component: "ComponentDef") -> None:
        """Add a component definition to the database.

        If a component with the same library_id already exists, it is overwritten
        and all indexes are updated.
        """
        existing = self._by_library_id.get(component.library_id)
        if existing is not None:
            self._remove_from_indexes(existing)

        self._by_library_id[component.library_id] = component
        self._by_part_name[component.part_name].append(component)
        if component.footprint:
            self._by_footprint[component.footprint].append(component)
        if component.category:
            self._by_category[component.category].append(component)

        # Invalidate phys_des_index cache on any new addition
        self._phys_des_index_built = False

    def _remove_from_indexes(self, component: "ComponentDef") -> None:
        """Remove a component from all secondary indexes (used before overwrite)."""
        comps = self._by_part_name.get(component.part_name, [])
        if component in comps:
            comps.remove(component)
        if not comps:
            self._by_part_name.pop(component.part_name, None)

        if component.footprint:
            comps = self._by_footprint.get(component.footprint, [])
            if component in comps:
                comps.remove(component)
            if not comps:
                self._by_footprint.pop(component.footprint, None)

        if component.category:
            comps = self._by_category.get(component.category, [])
            if component in comps:
                comps.remove(component)
            if not comps:
                self._by_category.pop(component.category, None)

    def add_batch(self, components: list["ComponentDef"]) -> None:
        for comp in components:
            self.add(comp)

    # ------------------------------------------------------------------
    #  Lookup
    # ------------------------------------------------------------------

    def get_by_library_id(self, library_id: str) -> Optional["ComponentDef"]:
        """Exact lookup by library_id."""
        return self._by_library_id.get(library_id)

    def get_by_part_name(self, part_name: str) -> list["ComponentDef"]:
        """Get all components with the given part name (may have variants)."""
        return self._by_part_name.get(part_name, [])

    # ------------------------------------------------------------------
    #  Search
    # ------------------------------------------------------------------

    def search(
        self,
        part_name: str = "",
        footprint: str = "",
        category: str = "",
        pin_count: int = 0,
    ) -> list["ComponentDef"]:
        """Multi-criteria search.

        Returns all components matching every non-empty criterion (AND logic).
        """
        from ..ir.component import ComponentDef

        candidates: dict[str, ComponentDef] = dict(self._by_library_id)

        if part_name:
            hits: dict[str, ComponentDef] = {}
            for name, comps in self._by_part_name.items():
                if part_name.lower() in name.lower():
                    for c in comps:
                        hits[c.library_id] = c
            candidates = {lid: comp for lid, comp in candidates.items() if lid in hits}

        if footprint:
            fp_ids = {c.library_id for c in self._by_footprint.get(footprint, [])}
            candidates = {lid: comp for lid, comp in candidates.items() if lid in fp_ids}

        if category:
            cat_ids = {c.library_id for c in self._by_category.get(category, [])}
            candidates = {lid: comp for lid, comp in candidates.items() if lid in cat_ids}

        if pin_count:
            candidates = {
                lid: comp
                for lid, comp in candidates.items()
                if comp.pin_count == pin_count
            }

        return list(candidates.values())

    # ------------------------------------------------------------------
    #  Queries
    # ------------------------------------------------------------------

    def list_all(self) -> list["ComponentDef"]:
        return list(self._by_library_id.values())

    # ------------------------------------------------------------------
    #  PHYS_DES_PREFIX Index
    # ------------------------------------------------------------------

    @property
    def phys_des_prefix_index(self) -> dict[str, list[str]]:
        """Lazy-built PHYS_DES_PREFIX index: prefix → [cell_names].

        Maps PHYS_DES_PREFIX values (e.g. 'U', 'IC', 'XS', 'R', 'C') to
        the list of library_id and part_name strings that share that prefix.

        This index enables the prefix_filter to expand the candidate pool
        with specific chip cells (88e6320, bcm53125, etc.).

        Returns:
            Dict mapping phys_des_prefix string to list of cell name strings.
        """
        if not self._phys_des_index_built:
            self._build_phys_des_index()
        return self._phys_des_index

    def _build_phys_des_index(self) -> None:
        """Build the PHYS_DES_PREFIX index from all stored components."""
        from collections import defaultdict
        index: dict[str, list[str]] = defaultdict(list)
        seen: dict[str, set[str]] = defaultdict(set)

        for comp in self._by_library_id.values():
            prefix: str = getattr(comp, 'phys_des_prefix', '')
            if not prefix:
                continue
            # Add library_id and part_name (deduplicated per prefix)
            if comp.library_id not in seen[prefix]:
                index[prefix].append(comp.library_id)
                seen[prefix].add(comp.library_id)
            if comp.part_name not in seen[prefix]:
                index[prefix].append(comp.part_name)
                seen[prefix].add(comp.part_name)

        self._phys_des_index = dict(index)
        self._phys_des_index_built = True

    def contains(self, library_id: str) -> bool:
        return library_id in self._by_library_id

    @property
    def count(self) -> int:
        return len(self._by_library_id)

    def stats(self) -> dict:
        return {
            "total": len(self._by_library_id),
            "categories": {k: len(v) for k, v in self._by_category.items()},
        }

    def __len__(self) -> int:
        return len(self._by_library_id)

    def __contains__(self, library_id: str) -> bool:
        return library_id in self._by_library_id


class ComponentDBSerializer:
    """JSON serialization for ComponentDB — supports save, load, and merge."""

    @staticmethod
    def save(db: ComponentDB, path: Path) -> None:
        """Serialize the database to a JSON file."""
        data = [comp.model_dump() for comp in db.list_all()]
        path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    @staticmethod
    def load(path: Path) -> ComponentDB:
        """Load a database from a JSON file."""
        db = ComponentDB()
        data = json.loads(path.read_text(encoding="utf-8"))
        for item in data:
            from ..ir.component import ComponentDef

            db.add(ComponentDef(**item))
        return db

    @staticmethod
    def merge(target: ComponentDB, source: ComponentDB) -> ComponentDB:
        """Merge two databases — source components added if not already present."""
        for comp in source.list_all():
            if comp.library_id not in target:
                target.add(comp)
        return target
