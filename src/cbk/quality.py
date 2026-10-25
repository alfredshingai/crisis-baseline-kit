"""Data-quality gates. Every check returns PASS / WARN / FAIL.

A single FAIL fails the build (non-zero exit) so a silently-broken baseline
can never ship. WARNs are surfaced but do not block.
"""

from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd


def run_checks(
    checks: dict,
    admin: dict[int, gpd.GeoDataFrame],
    population_total: float,
) -> tuple[list[dict], bool]:
    results: list[dict] = []

    def add(cid: str, status: str, detail: str) -> None:
        results.append({"check": cid, "status": status, "detail": detail})

    for level, gdf in sorted(admin.items()):
        n = len(gdf)
        if n == 0:
            add(f"admin{level}_nonempty", "FAIL", "0 features")
            continue
        add(f"admin{level}_nonempty", "PASS", f"{n} features")
        nulls = int(gdf.geometry.isna().sum())
        add(f"admin{level}_geometry_present", "PASS" if nulls == 0 else "FAIL",
            f"{nulls} null geometries")
        invalid = int((~gdf.geometry.is_valid).sum())
        add(f"admin{level}_geometry_valid", "WARN" if invalid else "PASS",
            f"{invalid} invalid geometries")
        pc = f"adm{level}_pcode"
        if pc in gdf.columns:
            dup = int(gdf[pc].duplicated().sum())
            missing = int(gdf[pc].isna().sum())
            add(f"admin{level}_pcodes", "FAIL" if (dup or missing) else "PASS",
                f"{missing} missing, {dup} duplicate p-codes")
        else:
            add(f"admin{level}_pcodes", "FAIL", "no p-code column recognized")

    if admin:
        # Deepest level carries the stats; `expected_admin2_count` applies
        # to it regardless of actual depth (name kept for compatibility).
        lvl = max(admin)
        gdf = admin[lvl]
        n = len(gdf)
        rng = checks.get("expected_admin2_count")
        if rng:
            ok = rng[0] <= n <= rng[1]
            add("admin2_count_in_range", "PASS" if ok else "FAIL",
                f"{n} stats-level (admin-{lvl}) units, expected {rng[0]}-{rng[1]}")
        if "population_sum" in gdf.columns:
            missing = int(gdf["population_sum"].isna().sum())
            add("admin2_population_assigned", "FAIL" if missing else "PASS",
                f"{missing} admin-{lvl} units without a population value")
        if "facility_count" in gdf.columns:
            total = int(gdf["facility_count"].sum())
            add("facilities_present", "FAIL" if total == 0 else "PASS",
                f"{total} facilities joined to admin-{lvl} units")
        if "road_km" in gdf.columns:
            total_km = float(gdf["road_km"].sum())
            add("roads_present", "FAIL" if total_km == 0 else "PASS",
                f"{total_km:,.0f} km of major roads joined to admin-{lvl} units")

    if "expected_population_total_millions" in checks:
        lo, hi = checks["expected_population_total_millions"]
        mn = population_total / 1e6
        ok = lo <= mn <= hi
        add("population_total_in_range", "PASS" if ok else "FAIL",
            f"national raster total {mn:.2f}M, expected {lo}-{hi}M")
    if "expected_population_total" in checks:
        lo, hi = checks["expected_population_total"]
        ok = lo <= population_total <= hi
        add("population_total_in_range", "PASS" if ok else "FAIL",
            f"national raster total {population_total:,.0f}, expected {lo:,.0f}-{hi:,.0f}")

    passed = all(r["status"] != "FAIL" for r in results)
    return results, passed


def write_report(path: Path, results: list[dict], passed: bool) -> None:
    path.write_text(
        json.dumps({"passed": passed, "checks": results}, indent=2),
        encoding="utf-8",
    )
