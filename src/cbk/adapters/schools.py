"""Schools (education facilities) from HOT's OSM extracts, via HDX.

HOT publishes `hotosm_{iso3}_education_facilities` per country with
GeoJSON resources. OSM-derived and ODbL: school points stay in their own
table/layer; only aggregate counts join the admin table.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import geopandas as gpd

from ..util import download, get_json, log, new_session
from .base import Adapter, BuildContext, LayerResult

HDX_API = "https://data.humdata.org/api/3/action"


def _pick_resource(pkg: dict) -> dict:
    best, best_key = None, None
    for res in pkg.get("resources", []):
        fmt = (res.get("format") or "").lower()
        url = res.get("url") or ""
        if "geojson" in fmt or url.endswith(".geojson"):
            kind = 0
        elif "geopackage" in fmt or "gpkg" in fmt or url.endswith(".gpkg"):
            kind = 1
        else:
            continue
        key = (kind, len(url))
        if best_key is None or key < best_key:
            best, best_key = res, key
    if best is None:
        raise RuntimeError(f"No GeoJSON/GeoPackage resource in {pkg.get('name')!r}")
    return best


def _normalize(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    out = gdf.copy()
    if out.crs is None:
        out = out.set_crs("EPSG:4326")
    norm = {c: re.sub(r"[^a-z0-9]+", "_", str(c).lower()).strip("_") for c in out.columns}
    name_col = next((c for c, n in norm.items()
                     if c != "geometry" and "name" in n and "osm" not in n), None)
    type_col = next((c for c, n in norm.items()
                     if c != "geometry" and c != name_col and
                     any(k in n for k in ("amenity", "type", "kind"))), None)
    renames = {}
    if name_col:
        renames[name_col] = "school_name"
    if type_col and type_col != name_col:
        renames[type_col] = "school_type"
    out = out.rename(columns=renames)
    keep = ["geometry"] + [c for c in ("school_name", "school_type") if c in out.columns]
    out = out[keep]
    out = out[out.geometry.notna() & out.geometry.is_valid]
    return out.reset_index(drop=True)


class SchoolsAdapter(Adapter):
    name = "schools"
    description = "Schools from HOT OSM education-facilities extracts (via HDX, ODbL)"

    def run(self, ctx: BuildContext, params: Mapping[str, Any]) -> LayerResult:
        iso3 = ctx.profile.iso3.lower()
        session = new_session()
        pkg = None
        for candidate in (f"hotosm_{iso3}_education_facilities",
                          f"hotosm-{iso3}-education-facilities"):
            payload = get_json(session, f"{HDX_API}/package_show", params={"id": candidate})
            if payload.get("success") and payload.get("result"):
                pkg = payload["result"]
                break
        if pkg is None:  # slug variations exist across HOT's publishing history
            payload = get_json(session, f"{HDX_API}/package_search",
                               params={"q": f"hotosm {iso3} education facilities", "rows": 5})
            hits = payload.get("result", {}).get("results", [])
            pkg = next((p for p in hits if "education" in (p.get("name") or "")), None)
        if pkg is None:
            raise RuntimeError(f"No HOT education-facilities dataset found for {iso3.upper()}")
        res = _pick_resource(pkg)
        log.info("schools: dataset %r -> resource %r", pkg.get("title"), res.get("name"))

        raw_path, _digest = download(res["url"], ctx.raw_dir, session=session)
        if raw_path.suffix.lower() == ".zip":
            import zipfile

            extract = raw_path.with_suffix("")
            extract.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(raw_path) as zf:
                zf.extractall(extract)
            pref = {".geojson": 0, ".gpkg": 1, ".json": 2}
            inner = sorted(
                (p for p in extract.rglob("*")
                 if p.is_file() and p.suffix.lower() in pref),
                key=lambda p: pref[p.suffix.lower()],
            )
            if not inner:
                raise RuntimeError(f"No vector file inside {raw_path.name}")
            read_path = inner[0]
        else:
            read_path = raw_path
        gdf = gpd.read_file(read_path)
        gdf = _normalize(gdf)

        out_path = ctx.data_dir / "schools.geojson"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        gdf.to_file(out_path, driver="GeoJSON")
        log.info("schools: %d points -> %s", len(gdf), out_path.name)

        return LayerResult(
            layer="schools",
            adapter=self.name,
            kind="vector",
            license=pkg.get("license_title") or "ODbL",
            attribution=f"HOT OSM education facilities via HDX ({pkg.get('title')})",
            source_urls=[f"https://data.humdata.org/dataset/{pkg.get('name')}",
                         "https://www.openstreetmap.org/copyright"],
            source_version=res.get("last_modified") or pkg.get("last_modified"),
            retrieved_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            outputs={"schools": out_path},
            raw=[raw_path],
            extra={"school_count": int(len(gdf))},
        )
