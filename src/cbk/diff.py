"""cbk diff: compare two baseline bundles of the same country.

Reports per-admin-unit changes in the joined statistics and writes a
human-readable summary plus a machine-readable JSON next to the newer
bundle. This is the "what changed since last month's baseline" report.
"""

from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd

from .util import log

STAT_FIELDS = ["population_sum", "pop_density_km2", "facility_count",
               "facilities_per_10k_pop", "road_km", "area_km2"]


def _latest_before(bundles: list[Path], ref: Path) -> Path | None:
    earlier = [b for b in bundles if b.name < ref.name]
    return earlier[-1] if earlier else None


def _stats_table(bundle: Path) -> gpd.GeoDataFrame:
    files = sorted(bundle.glob("admin[0-9].parquet")) or \
        sorted(bundle.glob("admin[0-9].geojson"))
    if not files:
        raise FileNotFoundError(f"no admin stats table in {bundle}")
    return gpd.read_file(files[-1])


def diff_bundles(old: Path, new: Path) -> dict:
    a = _stats_table(old)
    b = _stats_table(new)
    key = "adm2_pcode" if "adm2_pcode" in b.columns else b.columns[0]
    m = b[[key, "geometry"] + [c for c in STAT_FIELDS if c in b.columns]].merge(
        a[[key] + [c for c in STAT_FIELDS if c in a.columns]],
        on=key, how="outer", suffixes=("_new", "_old"), indicator=True,
    )

    units = []
    for _, r in m.iterrows():
        changes = {}
        for f in STAT_FIELDS:
            if f"{f}_new" in m.columns and f"{f}_old" in m.columns:
                nv, ov = r.get(f"{f}_new"), r.get(f"{f}_old")
                if nv is not None and ov is not None and ov == ov and nv == nv \
                        and abs(float(nv) - float(ov)) > 1e-9:
                    changes[f] = {"old": round(float(ov), 2), "new": round(float(nv), 2)}
        name = r.get("adm2_name") or r.get("adm1_name") or r.get(key)
        if changes or r["_merge"] != "both":
            units.append({
                key: r.get(key), "name": str(name),
                "status": "changed" if changes else
                          ("added" if r["_merge"] == "left_only" else "removed"),
                "changes": changes,
            })

    summary = {}
    for f in ("population_sum", "facility_count", "road_km"):
        if f"{f}_new" in m.columns and f"{f}_old" in m.columns and m[f"{f}_new"].notna().all():
            summary[f] = {
                "old_total": round(float(m[f"{f}_old"].sum()), 1),
                "new_total": round(float(m[f"{f}_new"].sum()), 1),
            }

    return {
        "old_bundle": str(old), "new_bundle": str(new),
        "units_compared": int(len(m)),
        "units_changed": len(units),
        "totals": summary,
        "units": units,
    }


def run(country_dir: Path) -> Path:
    iso = country_dir.name
    bundles = sorted(p for p in country_dir.iterdir() if p.is_dir())
    if len(bundles) < 2:
        raise SystemExit(f"only {len(bundles)} bundle(s) for {iso}; diff needs two")
    new = bundles[-1]
    old = _latest_before(bundles, new)
    if old is None:
        raise SystemExit("no earlier bundle to compare against")

    report = diff_bundles(old, new)
    out = new / "diff_report.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    log.info("diff %s: %s -> %s", iso, old.name, new.name)
    log.info("  units compared: %d, changed: %d", report["units_compared"],
             report["units_changed"])
    for f, t in report["totals"].items():
        delta = t["new_total"] - t["old_total"]
        log.info("  %s: %s -> %s (%+.1f%%)", f,
                 f"{t['old_total']:,.0f}", f"{t['new_total']:,.0f}",
                 100 * delta / t["old_total"] if t["old_total"] else 0.0)
    if report["units_changed"]:
        for u in report["units"]:
            if "population_sum" in u["changes"]:
                c = u["changes"]["population_sum"]
                log.info("  %s: pop %s -> %s", u["name"],
                         f"{c['old']:,.0f}", f"{c['new']:,.0f}")
    print(f"diff report: {out}")
    return out
