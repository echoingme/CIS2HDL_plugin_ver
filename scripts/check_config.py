"""Validate the repository's configuration files.

Checks that every YAML file parses, that each profile carries the keys the profile
manager expects, and that ``pyproject.toml`` is well-formed TOML. Used by CI and
runnable locally:

    python scripts/check_config.py
"""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
REQUIRED_PROFILE_KEYS = {"schema_version", "profile"}


def _load_yaml(path: Path) -> object:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def check_pipeline(path: Path) -> list[str]:
    """Validate the authoritative pipeline file."""
    data = _load_yaml(path)
    problems: list[str] = []
    if not isinstance(data, dict):
        return [f"{path}: root is not a mapping"]
    for section in ("input", "match", "beautify", "output", "test", "engine"):
        if section not in data:
            problems.append(f"{path}: missing section '{section}'")
    if data.get("schema_version") != 1:
        problems.append(f"{path}: unexpected schema_version {data.get('schema_version')!r}")
    return problems


def check_profile(path: Path) -> list[str]:
    """Validate one profile file."""
    data = _load_yaml(path)
    problems: list[str] = []
    if not isinstance(data, dict):
        return [f"{path}: root is not a mapping"]
    missing = REQUIRED_PROFILE_KEYS - data.keys()
    if missing:
        problems.append(f"{path}: missing keys {sorted(missing)}")
    profile = data.get("profile")
    if not isinstance(profile, dict) or "name" not in profile:
        problems.append(f"{path}: profile block needs a 'name'")
    elif profile["name"] != path.stem:
        problems.append(f"{path}: profile name {profile['name']!r} does not match file name")
    return problems


def check_workflow(path: Path) -> list[str]:
    """Workflow files only need to be valid YAML."""
    _load_yaml(path)
    return []


def check_pyproject(path: Path) -> list[str]:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    problems: list[str] = []
    project = data.get("project", {})
    if not project:
        return [f"{path}: missing [project] table"]
    if "name" not in project:
        problems.append(f"{path}: missing project.name")
    dynamic = project.get("dynamic", [])
    if "version" in dynamic and "version" in project:
        problems.append(f"{path}: version is both static and dynamic")
    if "version" not in dynamic and "version" not in project:
        problems.append(f"{path}: no version declared")
    return problems


def main() -> int:
    problems: list[str] = []
    checked = 0

    pipeline = ROOT / "pipeline.yaml"
    if pipeline.exists():
        problems += check_pipeline(pipeline)
        checked += 1

    for profile in sorted((ROOT / "profiles").glob("*.yaml")):
        problems += check_profile(profile)
        checked += 1

    for workflow in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
        problems += check_workflow(workflow)
        checked += 1

    pyproject = ROOT / "pyproject.toml"
    if pyproject.exists():
        problems += check_pyproject(pyproject)
        checked += 1

    for problem in problems:
        print(f"error: {problem}", file=sys.stderr)

    print(f"{checked} file(s) checked, {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
