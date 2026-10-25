"""Assemble the GitHub Pages site from built baseline bundles.

Copies the static app plus per-country data (geometry simplified for the
web; the downloadable bundles keep full detail) into _site/.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import geopandas as gpd

ROOT = Path(__file__).resolve().parents[1]
BASELINES = ROOT / "baselines"
SITE_OUT = ROOT / "_site"
SIMPLIFY_TOLERANCE_DEG = 0.002  # ~200 m; web display only


def latest_bundle(iso_dir: Path) -> Path | None:
    dated = sorted(p for p in iso_dir.iterdir() if p.is_dir())
    return dated[-1] if dated else None


def main() -> None:
    if not BASELINES.is_dir():
        sys.exit("baselines/ not found - run `cbk build` first")
    SITE_OUT.mkdir(parents=True, exist_ok=True)
    for f in (ROOT / "site").glob("*"):
        if f.is_file() and f.name != "build.py":
            shutil.copy(f, SITE_OUT / f.name)

    countries = []
    for iso_dir in sorted(BASELINES.iterdir()):
        if not iso_dir.is_dir():
            continue
        bundle = latest_bundle(iso_dir)
        if bundle is None:
            continue
        iso = iso_dir.name
        out = SITE_OUT / iso
        out.mkdir(exist_ok=True)

        gdf = gpd.read_file(bundle / "admin2.geojson")
        gdf["geometry"] = gdf.geometry.simplify(SIMPLIFY_TOLERANCE_DEG, preserve_topology=True)
        gdf.to_file(out / "admin2.geojson", driver="GeoJSON")

        shutil.copy(bundle / "viewer_config.json", out / "viewer_config.json")
        manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
        sources = [
            {"layer": l["layer"], "attribution": l["attribution"], "license": l["license"]}
            for l in manifest["layers"]
        ]
        (out / "meta.json").write_text(
            json.dumps({"iso3": iso, "date": bundle.name, "sources": sources}, indent=2),
            encoding="utf-8",
        )
        cfg = json.loads((bundle / "viewer_config.json").read_text(encoding="utf-8"))
        countries.append({"iso3": iso, "name": cfg["country"], "date": bundle.name})

    if not countries:
        sys.exit("no country bundles found under baselines/")
    (SITE_OUT / "countries.json").write_text(json.dumps(countries, indent=2), encoding="utf-8")
    files = [p for p in SITE_OUT.rglob("*") if p.is_file()]
    total = sum(p.stat().st_size for p in files)
    print(f"site assembled: {len(files)} files, {total / 1e6:.1f} MB")
    for c in countries:
        print(f"  {c['iso3']}: {c['name']} ({c['date']})")


if __name__ == "__main__":
    main()
