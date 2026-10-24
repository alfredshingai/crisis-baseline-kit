"""Synthetic end-to-end test: runs the real pipeline (zonal stats, quality
gate, bundle writer, manifest, viewer config) on a fabricated country.

No network needed. Run with `cbk selftest`.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import box

from .adapters.base import LayerResult
from .adapters.codab import normalize_admin_columns
from .pipeline import assemble_bundle
from .profile import load_profile

PROFILE_YAML = """
iso3: TST
name: Testland
profile_version: 0.1.0-test
hdx_slug: cod-ab-tst
crs_analysis: "EPSG:32633"
layers:
  admin_boundaries:
    adapter: codab
    params:
      admin_levels: [0, 1, 2]
  population:
    adapter: worldpop
    params:
      year: 2020
      dataset: ppp
checks:
  expected_admin2_count: [4, 4]
  expected_population_total: [15000, 15500]
viewer:
  choropleth_field: population_sum
  choropleth_label: "Population (synthetic)"
"""


def _make_country(work: Path):
    """A 4x4 km country in UTM 33N: 40x40 pixels of 100 m; last row/col nodata.

    Every valid pixel holds 10 people, so the national total is 39*39*10 = 15,210.
    """
    crs = "EPSG:32633"
    arr = np.full((40, 40), 10.0, dtype="float32")
    arr[-1, :] = -99999.0
    arr[:, -1] = -99999.0
    tif = work / "tst_ppp_2020.tif"
    with rasterio.open(
        tif, "w", driver="GTiff", height=40, width=40, count=1, dtype="float32",
        crs=crs, transform=from_origin(0, 4000, 100, 100), nodata=-99999.0,
    ) as dst:
        dst.write(arr, 1)

    def quad(name, pcode, parent, pparent, geom):
        # Deliberately messy COD-AB-style column names, to exercise normalization.
        return {"ADM2_EN": name, "ADM2_PCODE": pcode, "ADM1_EN": parent,
                "ADM1_PCODE": pparent, "geometry": geom}

    west = box(0, 0, 2000, 4000)
    east = box(2000, 0, 4000, 4000)
    adm2 = gpd.GeoDataFrame([
        quad("Northwest", "TST002001", "North", "TST001", box(0, 2000, 2000, 4000)),
        quad("Northeast", "TST002002", "North", "TST001", box(2000, 2000, 4000, 4000)),
        quad("Southwest", "TST002003", "South", "TST002", box(0, 0, 2000, 2000)),
        quad("Southeast", "TST002004", "South", "TST002", box(2000, 0, 4000, 2000)),
    ], crs=crs)
    adm1 = gpd.GeoDataFrame([
        {"ADM1_EN": "North", "ADM1_PCODE": "TST001", "geometry": west},
        {"ADM1_EN": "South", "ADM1_PCODE": "TST002", "geometry": east},
    ], crs=crs)
    adm0 = gpd.GeoDataFrame([
        {"ADM0_EN": "Testland", "ADM0_PCODE": "TST", "geometry": west.union(east)},
    ], crs=crs)
    return tif, 39 * 39 * 10.0, {
        "admin0": normalize_admin_columns(adm0, 0),
        "admin1": normalize_admin_columns(adm1, 1),
        "admin2": normalize_admin_columns(adm2, 2),
    }


def run(keep: bool = False) -> bool:
    work = Path(tempfile.mkdtemp(prefix="cbk-selftest-"))
    try:
        profile_path = work / "TST.yaml"
        profile_path.write_text(PROFILE_YAML, encoding="utf-8")
        profile = load_profile(profile_path)

        bundle = work / "baselines" / "TST" / "2000-01-01"
        data_dir = bundle / "data"
        (bundle / "raw").mkdir(parents=True, exist_ok=True)
        data_dir.mkdir(parents=True, exist_ok=True)

        tif, total, frames = _make_country(work)
        outputs = {}
        for name, gdf in frames.items():
            p = data_dir / f"{name}.geojson"
            gdf.to_file(p, driver="GeoJSON")
            outputs[name] = p

        results = {
            "admin_boundaries": LayerResult(
                layer="admin_boundaries", adapter="codab", kind="vector",
                license="CC-BY 4.0 (test)", attribution="OCHA COD-AB (synthetic)",
                source_urls=["https://example.org/cod-ab-tst"], source_version="test-1",
                retrieved_at="2000-01-01T00:00:00+00:00",
                outputs=outputs, raw=[], extra={"admin2_features": 4},
            ),
            "population": LayerResult(
                layer="population", adapter="worldpop", kind="raster",
                license="CC-BY 4.0 (test)", attribution="WorldPop (synthetic)",
                source_urls=["https://example.org/tst.tif"], source_version="2020",
                retrieved_at="2000-01-01T00:00:00+00:00",
                outputs={"raster": tif}, raw=[tif],
                extra={"total_population": total, "year": 2020, "dataset": "ppp"},
            ),
        }
        assemble_bundle(profile, results, bundle)

        expected = ["cbk_baseline.gpkg", "admin2.parquet", "admin2.geojson",
                    "manifest.json", "quality_report.json", "README.md",
                    "viewer_config.json"]
        missing = [f for f in expected if not (bundle / f).exists()]
        q = json.loads((bundle / "quality_report.json").read_text(encoding="utf-8"))
        a2 = gpd.read_file(bundle / "admin2.geojson")
        sums = sorted(a2["population_sum"].round(0).tolist())
        print(f"[cbk] selftest bundle: {bundle}")
        print(f"[cbk] admin-2 population sums: {sums} (expected 15210 total)")

        ok = (not missing) and q["passed"] and len(a2) == 4 and all(s > 0 for s in sums)
        detail = f" (missing files: {missing})" if missing else ""
        print(f"[cbk] selftest: {'PASS' if ok else 'FAIL'}{detail}")
        return ok
    finally:
        if not keep:
            shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(0 if run() else 1)
