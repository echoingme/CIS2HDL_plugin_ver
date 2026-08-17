"""Top-3 Candidate Selector GUI.

Allows users to review and change component matches from the top-3 list,
or browse the entire hdl_lib for manual selection.

Uses tkinter (Python standard library) for zero-dependency operation.

Usage:
    from cis2hdl.gui.candidate_selector import CandidateSelector

    selector = CandidateSelector(top3_path, all_catalog)
    selector.run()

    # Or open standalone:
    python -m cis2hdl.gui.candidate_selector <top3_file> [hdl_lib_dir]
"""

from __future__ import annotations

import logging
import re
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any, Optional

from cis2hdl.core.ir.component import ComponentDef
from cis2hdl.core.matcher.active_matcher import ActiveMatcher

logger = logging.getLogger(__name__)


# ── Top-3 file parser ──────────────────────────────────────────────────────


def _parse_top3_file(filepath: Path) -> list[dict[str, Any]]:
    """Parse a top-3 candidate file into structured data.

    Returns:
        List of entries, each containing:
            refdes, candidates (list of rank/hdl_cell/primitive/score/selected),
            selected_idx (0-2 or None).
    """
    entries: list[dict[str, Any]] = []
    current_refdes: str = ""
    current_candidates: list[dict[str, Any]] = []
    current_selected: Optional[int] = None

    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")

            # Skip headers, separators, and blank lines
            if line.startswith("#") or line.startswith("-") or not line.strip():
                # Flush current entry if we have one
                if current_refdes and current_candidates:
                    entries.append({
                        "refdes": current_refdes,
                        "candidates": current_candidates,
                        "selected_idx": current_selected,
                    })
                    current_refdes = ""
                    current_candidates = []
                    current_selected = None
                continue

            # Parse: refdes | rank*| hdl_cell | hdl_primitive | score | match_confidence
            parts = [p.strip() for p in line.split("|")]
            if len(parts) < 5:
                continue

            refdes = parts[0]
            rank_str = parts[1]  # e.g. "1*" or "2 "
            hdl_cell = parts[2]
            primitive = parts[3] if len(parts) > 3 else ""
            score = float(parts[4]) if len(parts) > 4 else 0.0
            match_conf = parts[5] if len(parts) > 5 else "-"

            if refdes != current_refdes:
                if current_refdes and current_candidates:
                    entries.append({
                        "refdes": current_refdes,
                        "candidates": current_candidates,
                        "selected_idx": current_selected,
                    })
                current_refdes = refdes
                current_candidates = []
                current_selected = None

            is_selected = rank_str.endswith("*")
            rank = int(rank_str.rstrip("*").strip())

            current_candidates.append({
                "rank": rank,
                "hdl_cell": hdl_cell,
                "primitive": primitive,
                "score": score,
                "match_confidence": match_conf,
                "selected": is_selected,
            })

            if is_selected:
                current_selected = len(current_candidates) - 1

    # Flush last entry
    if current_refdes and current_candidates:
        entries.append({
            "refdes": current_refdes,
            "candidates": current_candidates,
            "selected_idx": current_selected,
        })

    return entries


# ── Weight Editor Dialog ───────────────────────────────────────────────────


class WeightEditor(tk.Toplevel):
    """Dialog for editing Phase 2B ActiveMatcher weights."""

    def __init__(self, parent: tk.Widget, current_weights: dict[str, float]) -> None:
        super().__init__(parent)
        self.title("Edit Phase 2B ActiveMatcher Weights")
        self._weights: dict[str, float] = dict(current_weights)
        self._entries: dict[str, ttk.Entry] = {}
        self.resizable(False, False)

        # Make dialog modal
        self.transient(parent)
        self.grab_set()

        # Header
        ttk.Label(
            self,
            text="Edit dimension weights (normalized to 1.0 on save)",
            font=("TkDefaultFont", 10, "bold"),
        ).pack(pady=(10, 5), padx=10)

        # Description labels
        dim_descriptions: dict[str, str] = {
            "footprint": "Package size match",
            "value": "Value comparison",
            "jedec": "JEDEC_TYPE match",
            "pin_count": "Pin count proximity",
            "part_name": "Part name overlap",
        }

        main_frame = ttk.Frame(self)
        main_frame.pack(pady=5, padx=15)

        for dim, weight in self._weights.items():
            frame = ttk.Frame(main_frame)
            ttk.Label(frame, text=dim, width=12, anchor=tk.W).pack(side=tk.LEFT)
            entry = ttk.Entry(frame, width=8, justify=tk.CENTER)
            entry.insert(0, f"{weight:.2f}")
            entry.pack(side=tk.LEFT, padx=(0, 5))
            desc = dim_descriptions.get(dim, "")
            ttk.Label(frame, text=desc, foreground="gray").pack(side=tk.LEFT)
            self._entries[dim] = entry
            frame.pack(pady=2, fill=tk.X)

        # Buttons
        btn_frame = ttk.Frame(self)
        btn_frame.pack(pady=10)

        ttk.Button(
            btn_frame, text="Save & Re-score", command=self._save
        ).pack(side=tk.LEFT, padx=5)
        ttk.Button(
            btn_frame, text="Reset Defaults", command=self._reset_defaults
        ).pack(side=tk.LEFT, padx=5)
        ttk.Button(
            btn_frame, text="Cancel", command=self.destroy
        ).pack(side=tk.LEFT, padx=5)

        # Center on parent
        self.update_idletasks()
        px = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{px}+{py}")

    def _reset_defaults(self) -> None:
        """Reset all entries to default values."""
        defaults = dict(ActiveMatcher.WITHIN_TYPE_WEIGHTS)
        for dim, entry in self._entries.items():
            entry.delete(0, tk.END)
            entry.insert(0, f"{defaults.get(dim, 0.0):.2f}")

    def _save(self) -> None:
        """Validate, normalize, and save weights."""
        for dim, entry in self._entries.items():
            try:
                val = float(entry.get())
                if val < 0:
                    messagebox.showerror("Error", f"Weight for '{dim}' cannot be negative")
                    return
                self._weights[dim] = val
            except ValueError:
                messagebox.showerror("Error", f"Invalid number for '{dim}': {entry.get()}")
                return

        # Normalize
        total = sum(self._weights.values())
        if total <= 0:
            messagebox.showerror("Error", "Total weight must be > 0")
            return

        for dim in self._weights:
            self._weights[dim] = round(self._weights[dim] / total, 4)

        # Save to YAML
        try:
            import yaml as _yaml
            weights_path = Path("cis2hdl/config/weights.yaml")
            weights_path.parent.mkdir(parents=True, exist_ok=True)
            with open(weights_path, "w", encoding="utf-8") as f:
                _yaml.safe_dump({"weights": self._weights}, f, default_flow_style=False)
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to save weights: {exc}")
            return

        messagebox.showinfo(
            "Weights Saved",
            f"Phase 2B weights normalized and saved:\n"
            + "\n".join(f"  {k}: {v:.4f}" for k, v in self._weights.items())
            + "\n\nRe-run conversion for changes to take effect.",
        )
        self.destroy()


# ── Browse All HDL Library Dialog ──────────────────────────────────────────


class BrowseHDLDialog(tk.Toplevel):
    """Dialog for browsing the entire HDL library and selecting a candidate."""

    def __init__(
        self,
        parent: tk.Widget,
        all_catalog: dict[str, ComponentDef],
        current_refdes: str = "",
    ) -> None:
        super().__init__(parent)
        self.title(f"Browse HDL Library — {current_refdes}")
        self._catalog = all_catalog
        self._selected: Optional[str] = None
        self._current_refdes = current_refdes

        self.transient(parent)
        self.geometry("700x500")

        # Search bar
        search_frame = ttk.Frame(self)
        search_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT)
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", self._on_search)
        search_entry = ttk.Entry(search_frame, textvariable=self._search_var, width=40)
        search_entry.pack(side=tk.LEFT, padx=5)
        search_entry.focus_set()

        # Tree view
        columns = ("part_name", "library_id", "primitive", "pins")
        self._tree = ttk.Treeview(self, columns=columns, show="headings", selectmode="browse")
        self._tree.heading("part_name", text="Part Name")
        self._tree.heading("library_id", text="Library ID")
        self._tree.heading("primitive", text="Primitive")
        self._tree.heading("pins", text="Pins")
        self._tree.column("part_name", width=150)
        self._tree.column("library_id", width=250)
        self._tree.column("primitive", width=150)
        self._tree.column("pins", width=60, anchor=tk.CENTER)
        self._tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Scrollbar
        scrollbar = ttk.Scrollbar(self._tree, orient=tk.VERTICAL, command=self._tree.yview)
        self._tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._tree.bind("<Double-1>", self._on_select)

        # Buttons
        btn_frame = ttk.Frame(self)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="Select", command=self._on_select).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side=tk.LEFT, padx=5)

        # Populate
        self._populate()

    def _populate(self, filter_text: str = "") -> None:
        """Populate the tree with catalog entries."""
        self._tree.delete(*self._tree.get_children())
        filter_lower = filter_text.lower()

        for lib_id, comp in sorted(self._catalog.items()):
            if filter_lower:
                pn = comp.part_name.lower()
                lid = lib_id.lower()
                if filter_lower not in pn and filter_lower not in lid:
                    continue

            pin_count = getattr(comp, "pin_count", 0) or 0
            primitive = ""
            if hasattr(comp, "extra_data") and comp.extra_data:
                primitive = comp.extra_data.get("selected_primitive_body", "")

            self._tree.insert(
                "",
                tk.END,
                values=(comp.part_name, lib_id, primitive, str(pin_count)),
            )

    def _on_search(self, *args: Any) -> None:
        """Handle search input changes."""
        self._populate(self._search_var.get())

    def _on_select(self, event: Any = None) -> None:
        """Handle selection."""
        selection = self._tree.selection()
        if not selection:
            return
        values = self._tree.item(selection[0], "values")
        if values:
            self._selected = values[1]  # library_id
        self.destroy()

    @property
    def selected_library_id(self) -> Optional[str]:
        """Return the selected library ID."""
        return self._selected


# ── Main Candidate Selector ────────────────────────────────────────────────


class CandidateSelector:
    """GUI for reviewing/changing component matches.

    Layout:
        Left panel:  Component list (scrollable, sorted by refdes)
        Right upper: Match detail info
        Right middle: Top-3 candidate table (clickable)
        Buttons: Browse All, Save Changes, Edit Weights
    """

    def __init__(
        self,
        top3_path: Optional[Path] = None,
        all_catalog: Optional[dict[str, ComponentDef]] = None,
    ) -> None:
        self._top3_path = top3_path
        self._catalog: dict[str, ComponentDef] = all_catalog or {}
        self._entries: list[dict[str, Any]] = []
        self._changes: dict[str, str] = {}  # refdes → new library_id
        self._selected_idx: int = -1

        if top3_path and top3_path.exists():
            self._entries = _parse_top3_file(top3_path)

    def _load_top3(self, path: Path) -> list[dict[str, Any]]:
        """Load and parse a top-3 file."""
        return _parse_top3_file(path)

    def run(self) -> dict[str, str]:
        """Run the GUI and return user changes.

        Returns:
            Dict of refdes → new_library_id for changed matches.
        """
        root = tk.Tk()
        root.title("CIS2HDL — Top-3 Candidate Selector")
        root.geometry("950x600")
        root.minsize(800, 400)

        self._root = root
        self._build_ui()
        root.mainloop()

        # Return changes after GUI closes
        return dict(self._changes)

    # ── UI Construction ──────────────────────────────────────────────

    def _build_ui(self) -> None:
        """Build the main UI layout."""
        root = self._root

        # ── Top toolbar ──────────────────────────────────────────────
        toolbar = ttk.Frame(root)
        toolbar.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(
            toolbar,
            text=f"CIS2HDL Candidate Selector — {len(self._entries)} components",
            font=("TkDefaultFont", 11, "bold"),
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            toolbar, text="Save Changes", command=self._save_changes
        ).pack(side=tk.RIGHT, padx=3)

        ttk.Button(
            toolbar, text="Browse All hdl_lib", command=self._show_all_candidates
        ).pack(side=tk.RIGHT, padx=3)

        ttk.Button(
            toolbar, text="Edit Weights", command=self._edit_weights
        ).pack(side=tk.RIGHT, padx=3)

        # ── Main paned window ────────────────────────────────────────
        paned = ttk.PanedWindow(root, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Left panel: component list
        left_frame = ttk.LabelFrame(paned, text="Components (refdes)", padding=2)
        paned.add(left_frame, weight=1)

        # Search bar for left panel
        search_frame = ttk.Frame(left_frame)
        search_frame.pack(fill=tk.X, padx=2, pady=2)
        ttk.Label(search_frame, text="Filter:").pack(side=tk.LEFT)
        self._filter_var = tk.StringVar()
        self._filter_var.trace_add("write", self._on_filter)
        ttk.Entry(search_frame, textvariable=self._filter_var).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=2
        )

        self._listbox = tk.Listbox(left_frame, exportselection=False)
        self._listbox.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        self._listbox.bind("<<ListboxSelect>>", self._on_select_component)

        scroll_left = ttk.Scrollbar(self._listbox, orient=tk.VERTICAL, command=self._listbox.yview)
        self._listbox.configure(yscrollcommand=scroll_left.set)
        scroll_left.pack(side=tk.RIGHT, fill=tk.Y)

        # Right panel: detail + top-3
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=2)

        # Right upper: match info
        info_frame = ttk.LabelFrame(right_frame, text="Match Detail", padding=5)
        info_frame.pack(fill=tk.X, padx=2, pady=2)

        self._info_text = tk.Text(info_frame, height=5, wrap=tk.WORD, state=tk.DISABLED)
        self._info_text.pack(fill=tk.X, padx=2, pady=2)

        # Right middle: top-3 table
        table_frame = ttk.LabelFrame(right_frame, text="Top-3 Candidates (click to select)", padding=5)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        columns = ("rank", "cell", "primitive", "score", "conf")
        self._table = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")
        self._table.heading("rank", text="#")
        self._table.heading("cell", text="HDL Cell")
        self._table.heading("primitive", text="Primitive")
        self._table.heading("score", text="MultiScore")
        self._table.heading("conf", text="Confidence")
        self._table.column("rank", width=30, anchor=tk.CENTER)
        self._table.column("cell", width=160)
        self._table.column("primitive", width=160)
        self._table.column("score", width=80, anchor=tk.CENTER)
        self._table.column("conf", width=80, anchor=tk.CENTER)

        self._table.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        self._table.bind("<ButtonRelease-1>", self._on_select_candidate)

        scroll_right = ttk.Scrollbar(self._table, orient=tk.VERTICAL, command=self._table.yview)
        self._table.configure(yscrollcommand=scroll_right.set)
        scroll_right.pack(side=tk.RIGHT, fill=tk.Y)

        # Status bar
        self._status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(
            root, textvariable=self._status_var, relief=tk.SUNKEN, anchor=tk.W
        )
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)

        # Populate listbox
        self._refresh_listbox()

    # ── Event Handlers ───────────────────────────────────────────────

    def _on_filter(self, *args: Any) -> None:
        """Filter the component list."""
        self._refresh_listbox()

    def _refresh_listbox(self) -> None:
        """Refresh the left-side listbox with filtered entries."""
        self._listbox.delete(0, tk.END)
        filter_text = self._filter_var.get().lower()

        for i, entry in enumerate(self._entries):
            refdes = entry["refdes"]
            if filter_text and filter_text not in refdes.lower():
                continue

            # Show changed indicator
            display = refdes
            if refdes in self._changes:
                display = f"✎ {refdes}"

            self._listbox.insert(tk.END, display)

    def _on_select_component(self, event: Any = None) -> None:
        """Handle component selection from listbox."""
        selection = self._listbox.curselection()
        if not selection:
            return

        idx = selection[0]
        # Map filtered index back to actual entry
        filter_text = self._filter_var.get().lower()
        real_idx = -1
        count = -1
        for i, entry in enumerate(self._entries):
            refdes = entry["refdes"]
            if filter_text and filter_text not in refdes.lower():
                continue
            count += 1
            if count == idx:
                real_idx = i
                break

        if real_idx < 0:
            return

        self._selected_idx = real_idx
        self._display_component(real_idx)

    def _display_component(self, idx: int) -> None:
        """Display a component's details and top-3 candidates."""
        if idx < 0 or idx >= len(self._entries):
            return

        entry = self._entries[idx]
        refdes = entry["refdes"]
        candidates = entry["candidates"]
        selected_idx = entry.get("selected_idx")

        # Update info text
        self._info_text.configure(state=tk.NORMAL)
        self._info_text.delete("1.0", tk.END)

        info_lines = [f"Refdes: {refdes}"]
        if selected_idx is not None and 0 <= selected_idx < len(candidates):
            sel = candidates[selected_idx]
            info_lines.append(f"Selected: {sel['hdl_cell']} | {sel['primitive']}")
            info_lines.append(f"Score: {sel['score']:.4f}  Confidence: {sel['match_confidence']}")

        if refdes in self._changes:
            info_lines.append(f"⚠ Changed to: {self._changes[refdes]}")

        self._info_text.insert("1.0", "\n".join(info_lines))
        self._info_text.configure(state=tk.DISABLED)

        # Update table
        self._table.delete(*self._table.get_children())
        for i, cand in enumerate(candidates):
            is_sel = cand.get("selected", False)
            tag = "selected" if is_sel else "normal"
            self._table.insert(
                "",
                tk.END,
                values=(
                    f"{cand['rank']}{'*' if is_sel else ''}",
                    cand["hdl_cell"],
                    cand["primitive"],
                    f"{cand['score']:.4f}",
                    cand["match_confidence"],
                ),
                tags=(tag,),
            )

        self._table.tag_configure("selected", background="#c8e6c9", font=("TkDefaultFont", 9, "bold"))

        self._status_var.set(
            f"Component {idx + 1}/{len(self._entries)}: {refdes}"
            + (f" [CHANGED]" if refdes in self._changes else "")
        )

    def _on_select_candidate(self, event: Any = None) -> None:
        """Handle row click on the top-3 table to change selection."""
        selection = self._table.selection()
        if not selection or self._selected_idx < 0:
            return

        values = self._table.item(selection[0], "values")
        if not values:
            return

        entry = self._entries[self._selected_idx]
        refdes = entry["refdes"]
        candidates = entry["candidates"]

        # Find which candidate was clicked
        clicked_rank = int(values[0].rstrip("*"))
        clicked_cell = values[1]
        new_lib_id = ""
        for cand in candidates:
            if cand["rank"] == clicked_rank and cand["hdl_cell"] == clicked_cell:
                new_lib_id = cand.get("library_id", cand["hdl_cell"])
                break

        if not new_lib_id:
            return

        # Record change
        self._changes[refdes] = new_lib_id

        # Update display
        self._display_component(self._selected_idx)
        self._refresh_listbox()
        self._status_var.set(f"Changed: {refdes} → {new_lib_id}")

    def _show_all_candidates(self) -> None:
        """Open the full HDL library browser dialog."""
        if not self._catalog:
            messagebox.showwarning(
                "Not Available",
                "Full HDL library catalog is not loaded.\n"
                "Provide --hdl-lib when launching the GUI.",
            )
            return

        refdes = ""
        if self._selected_idx >= 0:
            refdes = self._entries[self._selected_idx]["refdes"]

        dialog = BrowseHDLDialog(self._root, self._catalog, refdes)
        self._root.wait_window(dialog)

        selected = dialog.selected_library_id
        if selected and self._selected_idx >= 0:
            entry = self._entries[self._selected_idx]
            refdes = entry["refdes"]
            self._changes[refdes] = selected
            self._display_component(self._selected_idx)
            self._refresh_listbox()
            self._status_var.set(f"Changed: {refdes} → {selected}")

    def _edit_weights(self) -> None:
        """Open the weight editor dialog."""
        current = self._load_weights()
        dialog = WeightEditor(self._root, current)
        self._root.wait_window(dialog)

    @staticmethod
    def _load_weights() -> dict[str, float]:
        """Load weights from YAML config, falling back to ActiveMatcher defaults."""
        weights_path = Path("cis2hdl/config/weights.yaml")
        if weights_path.exists():
            try:
                import yaml as _yaml
                with open(weights_path, "r", encoding="utf-8") as f:
                    data = _yaml.safe_load(f)
                if isinstance(data, dict) and "weights" in data:
                    return dict(data["weights"])
            except Exception:
                pass
        return dict(ActiveMatcher.WITHIN_TYPE_WEIGHTS)

    def _save_changes(self) -> None:
        """Save changes and close the GUI."""
        if not self._changes:
            messagebox.showinfo("No Changes", "No changes have been made.")
            self._root.destroy()
            return

        # Confirm
        confirm = messagebox.askyesno(
            "Save Changes",
            f"Save {len(self._changes)} change(s)?\n\n"
            + "\n".join(
                f"  {rd} → {lid}" for rd, lid in list(self._changes.items())[:10]
            )
            + ("\n  ..." if len(self._changes) > 10 else ""),
        )

        if confirm:
            self._save_to_yaml()
            self._root.destroy()

    def _save_to_yaml(self) -> None:
        """Persist changes to the unified chip_config.yaml (Phase XVII M8).

        用户 D7：删除 mapping_rules.yaml 独立格式，改写统一
        ``chip_config.yaml``（v2.0 schema，与 manual_matches 合并）。
        """
        output_path = Path.home() / ".cis2hdl" / "chip_config.yaml"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            from cis2hdl.core.matcher.manual_matches import (
                ManualMatch,
                ManualMatchesConfig,
            )

            matches = [
                ManualMatch(
                    refdes=refdes,
                    library_id=lib_id,
                    section=1,
                    note="gui confirmed",
                )
                for refdes, lib_id in self._changes.items()
            ]
            config = ManualMatchesConfig(version="2.0", matches=matches)
            config.write_yaml(output_path)

            logger.info(
                "Saved %d mapping(s) to unified %s",
                len(matches), output_path,
            )
            self._status_var.set(
                f"Saved {len(matches)} change(s) to {output_path}"
            )

        except Exception as exc:
            logger.warning("Failed to save chip_config: %s", exc)
            messagebox.showerror("Error", f"Failed to save changes: {exc}")

    @property
    def changes(self) -> dict[str, str]:
        """Return the current changes dict."""
        return dict(self._changes)


# ── Standalone entry point ─────────────────────────────────────────────────


def _load_catalog_from_dir(lib_dir: Path) -> dict[str, ComponentDef]:
    """Build a catalog dict from an HDL library directory.

    Uses HDLLibScanner if available. Falls back to a simple directory
    listing.
    """
    catalog: dict[str, ComponentDef] = {}
    try:
        from cis2hdl.core.db.component_db import ComponentDB
        from cis2hdl.core.parser.hdl_scanner import HDLLibScanner

        scanner = HDLLibScanner()
        db: ComponentDB = scanner.scan(lib_dir)
        for comp in db.list_all():
            catalog[comp.library_id] = comp
    except Exception as exc:
        logger.warning("Could not use HDLLibScanner: %s — falling back to dir listing", exc)
        # Simple fallback: use directory names as cells
        for item in sorted(lib_dir.iterdir()):
            if item.is_dir() and not item.name.startswith("."):
                catalog[item.name] = ComponentDef(
                    library_id=str(item),
                    part_name=item.name,
                )

    return catalog


def main() -> None:
    """Standalone CLI entry point for the candidate selector GUI."""
    import argparse

    parser = argparse.ArgumentParser(
        description="CIS2HDL Top-3 Candidate Selector GUI"
    )
    parser.add_argument("top3_file", help="Path to _top3.txt file")
    parser.add_argument("--hdl-lib", help="Path to HDL library directory")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)

    top3_path = Path(args.top3_file)
    if not top3_path.exists():
        print(f"Error: top3 file not found: {top3_path}")
        sys.exit(1)

    catalog: dict[str, ComponentDef] = {}
    if args.hdl_lib:
        lib_dir = Path(args.hdl_lib)
        if lib_dir.exists():
            catalog = _load_catalog_from_dir(lib_dir)
            print(f"Loaded {len(catalog)} HDL components from {lib_dir}")
        else:
            print(f"Warning: HDL library not found: {lib_dir}")

    selector = CandidateSelector(top3_path, catalog)
    changes = selector.run()

    if changes:
        print(f"\n{len(changes)} change(s) recorded:")
        for refdes, lib_id in changes.items():
            print(f"  {refdes} → {lib_id}")
    else:
        print("\nNo changes were made.")


if __name__ == "__main__":
    main()
