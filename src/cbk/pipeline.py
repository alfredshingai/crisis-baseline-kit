"""Build orchestration: adapters -> zonal join -> quality gate -> bundle.

`build()` fetches layers through adapters; `assemble_bundle()` does all the
downstream composition (zonal stats, GeoPackage/Parquet/GeoJSON outputs,
viewer, manifest, quality gate). The self-test drives `assemble_bundle()`
with synthetic data, so everything except the network adapters is covered.
"""

from __future__ import annotations

import json
import math
import shutil
from datetime import datetime
from pathlib import Path

import geopandas as gpd
import pandas as pd

from .adapters import ADAPTERS
from .manifest import build_manifest, render_readme
from .quality import run_checks as run_quality
from .quality import write_report
from .util import log
from .zonal import add_derived, zonal_sum

CHOROPLETH_COLORS = ["#eff3ff", "#bdd7e7", "#6baed6", "#3182bd", "#08519c"]


def build(country: str, out_root: Path, force: bool = False, date: str | None = None) -> Path:
    from .adapters.base import BuildContext
    from .profile import load_profile

    profile = load_profile(country)
    date = date or datetime.now().strftime("%Y-%m-%d")
    bundle_dir = out_root / profile.iso3 / date
    if bundle_dir.exists():
        if force:
            shutil.rmtree(bundle_dir)
        else:
            n = 2
            while bundle_dir.exists():
                bundle_dir = out_root / profile.iso3 / f"{date}-r{n}"
                n += 1
    raw_dir = bundle_dir / "raw"
    data_dir = bundle_dir / "data"
    for d in (raw_dir, data_dir):
        d.mkdir(parents=True, exist_ok=True)

    ctx = BuildContext(profile=profile, bundle_dir=bundle_dir, raw_dir=raw_dir, data_dir=data_dir)

    results = {}
    for layer_name, cfg in profile.layers.items():
        adapter_cls = ADAPTERS[cfg["adapter"]]
        log.info("Building layer %r with adapter %r", layer_name, cfg["adapter"])
        results[layer_name] = adapter_cls().run(ctx, cfg.get("params") or {})

    return assemble_bundle(profile, results, bundle_dir)


def assemble_bundle(profile, results: dict, bundle_dir: Path) -> Path:
    if "admin_boundaries" not in results or "population" not in results:
        raise ValueError("v0.1 requires both an 'admin_boundaries' and a 'population' layer")

    admin_paths = results["admin_boundaries"].outputs
    raster = results["population"].outputs.get("raster")
    if not raster or not Path(raster).exists():
        raise FileNotFoundError("population raster output missing")

    admin = {
        int(k.replace("admin", "")): gpd.read_file(p)
        for k, p in sorted(admin_paths.items())
        if k.startswith("admin")
    }
    if 2 not in admin:
        raise ValueError("admin level 2 is required (COD-AB adapter produced no admin2 output)")

    key = "adm2_pcode"
    admin2 = zonal_sum(raster, admin[2], key)
    admin2 = add_derived(admin2, profile.crs_analysis)

    gpkg = bundle_dir / "cbk_baseline.gpkg"
    for i, level in enumerate(sorted(admin)):
        layer_gdf = admin2 if level == 2 else admin[level]
        if i == 0:
            layer_gdf.to_file(gpkg, layer=f"admin{level}", driver="GPKG")
        else:
            layer_gdf.to_file(gpkg, layer=f"admin{level}", driver="GPKG", mode="a")
    admin2.to_parquet(bundle_dir / "admin2.parquet")
    admin2.to_file(bundle_dir / "admin2.geojson", driver="GeoJSON")

    _write_viewer(bundle_dir, profile, admin2)

    population_total = float(results["population"].extra.get("total_population", float("nan")))
    quality, passed = run_quality(profile.checks, admin | {2: admin2}, population_total)
    write_report(bundle_dir / "quality_report.json", quality, passed)

    output_files = {
        "cbk_baseline.gpkg": gpkg,
        "admin2.parquet": bundle_dir / "admin2.parquet",
        "admin2.geojson": bundle_dir / "admin2.geojson",
    }
    manifest = build_manifest(profile, results, bundle_dir, quality, output_files=output_files)
    render_readme(bundle_dir, profile, manifest, {
        "population_total": population_total,
        "admin2_count": int(len(admin2)),
    })

    log.info("Bundle written to %s (quality gate: %s)", bundle_dir, "PASS" if passed else "FAIL")
    if not passed:
        failed = [c["check"] for c in quality if c["status"] == "FAIL"]
        raise RuntimeError(f"Quality gate failed: {failed}; see quality_report.json")
    return bundle_dir


def _quantile_breaks(values, n: int = 5) -> list[float]:
    s = pd.Series([v for v in values if v is not None and v == v])
    if s.empty:
        return []
    breaks, last = [], None
    for i in range(1, n):
        b = float(s.quantile(i / n))
        if last is None or b > last:
            breaks.append(round(b, 1))
            last = b
    return breaks


def _viewer_index_src() -> Path | None:
    cand = Path(__file__).resolve().parents[2] / "viewer" / "index.html"
    return cand if cand.is_file() else None


def _write_viewer(bundle_dir: Path, profile, admin2: gpd.GeoDataFrame) -> None:
    field = profile.viewer.get("choropleth_field", "population_sum")
    label = profile.viewer.get("choropleth_label", field)
    total = float(admin2["population_sum"].sum()) if "population_sum" in admin2 else 0.0
    cfg = {
        "country": profile.name,
        "iso3": profile.iso3,
        "date": bundle_dir.name,
        "field": field,
        "label": label,
        "breaks": _quantile_breaks(admin2[field].tolist()) if field in admin2 else [],
        "colors": CHOROPLETH_COLORS,
        "total_population": total if math.isfinite(total) else 0.0,
        "admin2_count": int(len(admin2)),
    }
    (bundle_dir / "viewer_config.json").write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    src = _viewer_index_src()
    if src:
        shutil.copy(src, bundle_dir / "index.html")
    else:
        log.warning("viewer/index.html not found in the repo checkout; skipped map viewer")
