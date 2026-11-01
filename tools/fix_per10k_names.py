"""Rename singular per-10k columns to the documented plural names in the
latest bundle of every country, then refresh its dist/ zip.

v0.5.0 bundles were built while the point-count join emitted
school_per_10k_pop / facility_per_10k_pop; the documented schema (and
viewers) use schools_per_10k_pop / facilities_per_10k_pop. This patches
admin{N}.parquet, .geojson and the GeoPackage admin layer in place.

Usage: python tools/fix_per10k_names.py
"""

from __future__ import annotations

import geopandas as gpd
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RENAMES = {"school_per_10k_pop": "schools_per_10k_pop",
           "facility_per_10k_pop": "facilities_per_10k_pop"}


def latest_bundle(iso_dir: Path) -> Path | None:
    bundles = sorted(p for p in iso_dir.iterdir() if p.is_dir())
    return bundles[-1] if bundles else None


def fix_gdf(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    cols = {c: RENAMES[c] for c in gdf.columns if c in RENAMES}
    return gdf.rename(columns=cols) if cols else gdf


def main() -> None:
    patched = []
    for iso_dir in sorted((ROOT / "baselines").iterdir()):
        if not iso_dir.is_dir():
            continue
        bundle = latest_bundle(iso_dir)
        if bundle is None or not (bundle / "manifest.json").is_file():
            continue
        admin_file = next(iter(sorted(bundle.glob("admin[0-9].parquet"))), None)
        if admin_file is None:
            continue
        lvl = admin_file.stem
        df = gpd.read_parquet(admin_file)
        if not any(c in df.columns for c in RENAMES):
            continue
        df = fix_gdf(df)
        df.to_parquet(admin_file)

        gj = bundle / f"{lvl}.geojson"
        if gj.is_file():
            fix_gdf(gpd.read_file(gj)).to_file(gj, driver="GeoJSON")

        gpkg = bundle / "cbk_baseline.gpkg"
        if gpkg.is_file():
            layers = {name: gpd.read_file(gpkg, layer=name)
                      for name, _ in __import__("pyogrio").list_layers(gpkg)}
            gpkg.unlink()
            for name, layer_gdf in layers.items():
                mode = "w" if name == next(iter(layers)) else "a"
                fix_gdf(layer_gdf).to_file(gpkg, layer=name, driver="GPKG", mode=mode)

        zname = f"{iso_dir.name.lower()}-baseline-{bundle.name}.zip"
        zpath = ROOT / "dist" / zname
        if zpath.is_file():
            import zipfile

            with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
                for p in sorted(bundle.rglob("*")):
                    if p.is_file():
                        z.write(p, f"{iso_dir.name.lower()}-baseline-{bundle.name}/{p.relative_to(bundle)}")
        patched.append(iso_dir.name)
    print(f"patched {len(patched)} bundles: {' '.join(patched)}")


if __name__ == "__main__":
    main()
