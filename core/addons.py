"""Finds add-ons: installed packages that register a "rocko.addons" entry point, plus local features/*.py.

An add-on package declares itself in its pyproject.toml:

    [project.entry-points."rocko.addons"]
    tarkov = "rocko_tarkov.addon"

where rocko_tarkov.addon is a module with `async def setup(bot)`, the usual discord.py extension.
Installing the package into Rocko's venv is all it takes; no Rocko code changes.
"""
from dataclasses import dataclass
from importlib.metadata import entry_points
from pathlib import Path


@dataclass
class Addon:
    name: str    # what admins type in /rocko enable, e.g. "tarkov"
    module: str  # the extension module discord.py loads
    source: str  # the package it came from, or "local"


def discover(features_dir: Path):
    found = {}
    for ep in entry_points(group="rocko.addons"):
        source = f"{ep.dist.name} {ep.dist.version}" if ep.dist else "installed"
        found[ep.name] = Addon(ep.name, ep.value.split(":")[0], source)
    for path in sorted(features_dir.glob("*.py")):
        if not path.stem.startswith("_"):
            found[path.stem] = Addon(path.stem, f"features.{path.stem}", "local")
    return list(found.values())
