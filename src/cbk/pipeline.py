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
        try:
            results[layer_name] = adapter_cls().run(ctx, cfg.get("params") or {})
        except Exception as exc:
            if cfg.get("optional"):
                log.warning("Optional layer %r failed (%s); skipping it", layer_name, exc)
            else:
                raise

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
    if not admin:
        raise ValueError("no admin levels produced by the COD-AB adapter")
    # Deepest available level carries the stats (admin-2 normally; some
    # countries' COD-AB stops at admin-1, e.g. Sao Tome).
    stats_level = max(admin)

    key = f"adm{stats_level}_pcode"
    admin2 = zonal_sum(raster, admin[stats_level], key)
    admin2 = add_derived(admin2, profile.crs_analysis)

    if "facilities" in results:
        admin2, facilities = _join_facilities(admin2, results["facilities"])
    else:
        facilities = None

    roads = None
    if "roads" in results:
        admin2, roads = _join_roads(admin2, results["roads"], profile.crs_analysis, key)

    gpkg = bundle_dir / "cbk_baseline.gpkg"
    for i, level in enumerate(sorted(admin)):
        layer_gdf = admin2 if level == stats_level else admin[level]
        if i == 0:
            layer_gdf.to_file(gpkg, layer=f"admin{level}", driver="GPKG")
        else:
            layer_gdf.to_file(gpkg, layer=f"admin{level}", driver="GPKG", mode="a")
    if facilities is not None:
        facilities.to_file(gpkg, layer="facilities", driver="GPKG", mode="a")
        facilities.to_parquet(bundle_dir / "facilities.parquet")
    if roads is not None:
        roads.to_file(gpkg, layer="roads", driver="GPKG", mode="a")
        roads.to_parquet(bundle_dir / "roads.parquet")
    admin2.to_parquet(bundle_dir / f"admin{stats_level}.parquet")
    admin2.to_file(bundle_dir / f"admin{stats_level}.geojson", driver="GeoJSON")

    _write_viewer(bundle_dir, profile, admin2, stats_level)

    population_total = float(results["population"].extra.get("total_population", float("nan")))
    quality, passed = run_quality(profile.checks, admin | {stats_level: admin2}, population_total)
    write_report(bundle_dir / "quality_report.json", quality, passed)

    output_files = {
        "cbk_baseline.gpkg": gpkg,
        f"admin{stats_level}.parquet": bundle_dir / f"admin{stats_level}.parquet",
        f"admin{stats_level}.geojson": bundle_dir / f"admin{stats_level}.geojson",
    }
    if facilities is not None:
        output_files["facilities.parquet"] = bundle_dir / "facilities.parquet"
    if roads is not None:
        output_files["roads.parquet"] = bundle_dir / "roads.parquet"
    manifest = build_manifest(profile, results, bundle_dir, quality, output_files=output_files)
    (bundle_dir / "meta.json").write_text(json.dumps({
        "iso3": profile.iso3,
        "date": bundle_dir.name,
        "sources": [
            {"layer": res.layer, "attribution": res.attribution, "license": res.license}
            for res in results.values()
        ],
    }, indent=2), encoding="utf-8")
    render_readme(bundle_dir, profile, manifest, {
        "population_total": population_total,
        "admin2_count": int(len(admin2)),
        "stats_level": stats_level,
    })

    log.info("Bundle written to %s (quality gate: %s)", bundle_dir, "PASS" if passed else "FAIL")
    if not passed:
        failed = [c["check"] for c in quality if c["status"] == "FAIL"]
        raise RuntimeError(f"Quality gate failed: {failed}; see quality_report.json")
    return bundle_dir


def _join_facilities(admin2: gpd.GeoDataFrame, fac_result) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    """Count facilities per admin-2 unit (points-in-polygon spatial join).

    Facility points stay a separate table (ODbL share-alike source); only
    the count aggregate is joined into the admin-2 table.
    """
    fac = gpd.read_file(fac_result.outputs["facilities"])
    if fac.crs is None:
        fac = fac.set_crs("EPSG:4326")
    fac = fac.to_crs(admin2.crs)
    key = "adm2_pcode"
    joined = gpd.sjoin(fac, admin2[[key, "geometry"]], predicate="within", how="inner")
    counts = joined.groupby(key).size().rename("facility_count")
    out = admin2.merge(counts, left_on=key, right_index=True, how="left")
    out["facility_count"] = out["facility_count"].fillna(0).astype("int64")
    out["facilities_per_10k_pop"] = (
        out["facility_count"] / out["population_sum"].where(out["population_sum"] > 0) * 10_000
    ).round(2)
    log.info(
        "facilities: %d points, %d of %d admin-2 units have at least one",
        len(fac), int((out["facility_count"] > 0).sum()), len(out),
    )
    return out, fac


def _join_roads(admin2: gpd.GeoDataFrame, roads_result, crs_analysis: str, key: str):
    """Attach road_km (major-road length per admin unit) via line-polygon overlay.

    Road geometry stays a separate table (ODbL share-alike source); only
    the aggregate length joins the admin table.
    """
    roads = gpd.read_file(roads_result.outputs["roads"], layer="roads")
    if roads.crs is None:
        roads = roads.set_crs("EPSG:4326")
    roads = roads.to_crs(crs_analysis)
    units = admin2[[key, "geometry"]].to_crs(crs_analysis)
    inter = gpd.overlay(roads[["highway", "geometry"]], units, how="intersection")
    km = (inter.groupby(key)["geometry"].apply(lambda s: s.length.sum() / 1000)
          if len(inter) else None)
    out = admin2.copy()
    if km is not None:
        out = out.merge(km.rename("road_km"), left_on=key, right_index=True, how="left")
    else:
        out["road_km"] = None
    out["road_km"] = out["road_km"].astype("float64").round(2).fillna(0.0)
    if "area_km2" in out.columns:
        out["road_km_per_100km2"] = (out["road_km"] / out["area_km2"] * 100).round(2)
    log.info("roads: %d segments, %.0f km total across %d admin units",
             len(roads), float(out["road_km"].sum()), len(out))
    return out, roads


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


def _write_viewer(bundle_dir: Path, profile, admin2: gpd.GeoDataFrame, stats_level: int) -> None:
    field = profile.viewer.get("choropleth_field", "population_sum")
    label = profile.viewer.get("choropleth_label", field)
    total = float(admin2["population_sum"].sum()) if "population_sum" in admin2 else 0.0
    cfg = {
        "country": profile.name,
        "iso3": profile.iso3,
        "date": bundle_dir.name,
        "field": field,
        "label": label,
        "geojson": f"admin{stats_level}.geojson",
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
