"""Country profile loading and validation.

A profile is a small YAML file that fully describes one baseline: which
layers (via adapters + params), which quality expectations, how the viewer
is styled. Adding a country means adding a YAML file, not code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class Profile:
    path: Path
    iso3: str
    name: str
    profile_version: str
    hdx_slug: str
    crs_analysis: str
    layers: dict[str, dict[str, Any]]
    checks: dict[str, Any] = field(default_factory=dict)
    viewer: dict[str, Any] = field(default_factory=dict)


def default_profiles_dir() -> Path:
    # Repository checkout (editable install / CI); fall back to cwd.
    root = Path(__file__).resolve().parents[2]
    if (root / "profiles").is_dir():
        return root / "profiles"
    return Path.cwd() / "profiles"


def find_profile(country: str) -> Path:
    p = Path(country)
    if p.is_file():
        return p
    if p.suffix.lower() in (".yaml", ".yml"):
        raise FileNotFoundError(f"Profile file not found: {country}")
    iso = country.upper()
    for base in (Path.cwd() / "profiles", default_profiles_dir()):
        cand = base / f"{iso}.yaml"
        if cand.is_file():
            return cand
    raise FileNotFoundError(
        f"No profile found for {country!r}; looked for {iso}.yaml in ./profiles "
        f"and {default_profiles_dir()}. Add a profile YAML to build a new country."
    )


def load_profile(path_or_iso3: str | Path) -> Profile:
    from .adapters import ADAPTERS

    path = find_profile(str(path_or_iso3))
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    for key in ("iso3", "name", "layers"):
        if key not in raw:
            raise ValueError(f"Profile {path} is missing required key {key!r}")
    unknown = [
        cfg.get("adapter") for cfg in raw["layers"].values()
        if cfg.get("adapter") not in ADAPTERS
    ]
    if unknown:
        raise ValueError(
            f"Profile {path} references unknown adapters {unknown}; "
            f"available: {sorted(ADAPTERS)}"
        )
    return Profile(
        path=path,
        iso3=str(raw["iso3"]).upper(),
        name=raw["name"],
        profile_version=str(raw.get("profile_version", "0.0.0")),
        hdx_slug=raw.get("hdx_slug") or f"cod-ab-{str(raw['iso3']).lower()}",
        crs_analysis=raw.get("crs_analysis", "EPSG:4326"),
        layers=raw["layers"],
        checks=raw.get("checks") or {},
        viewer=raw.get("viewer") or {},
    )
