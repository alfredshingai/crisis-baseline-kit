"""Health facility points from healthsites.io, fetched via HDX.

healthsites.io data is ODbL (share-alike, largely OSM-derived): facilities
stay in their own table/layer and never get merged into boundary tables;
only aggregated counts per admin unit are joined into the admin-2 table
(see docs/sources.md for the license policy).
"""

from __future__ import annotations

import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import geopandas as gpd

from ..util import download, get_json, log, new_session
from .base import Adapter, BuildContext, LayerResult

HDX_API = "https://data.humdata.org/api/3/action"
VECTOR_SUFFIXES = {".geojson", ".gpkg", ".shp", ".json"}


def _hdx_get(session, action: str, params: dict) -> dict:
    payload = get_json(session, f"{HDX_API}/{action}", params=params)
    if not payload.get("success"):
        raise RuntimeError(f"HDX API call {action} failed: {payload.get('error')}")
    return payload["result"]


def _find_package(session, profile) -> dict:
    slug = f"{profile.name.lower().replace(' ', '-')}-healthsites"
    try:
        return _hdx_get(session, "package_show", {"id": slug})
    except Exception as exc:
        log.warning("HDX package_show for %r failed (%s); falling back to search", slug, exc)
    results = _hdx_get(session, "package_search", {"q": f"healthsites {profile.name}", "rows": 10})
    for pkg in results.get("results", []):
        if "healthsites" in pkg.get("name", ""):
            return pkg
    raise RuntimeError(f"No healthsites dataset found on HDX for {profile.name}")


def _pick_resource(pkg: dict) -> dict:
    """Prefer plain GeoJSON, then HXL GeoJSON, then shapefile."""
    best, best_key = None, None
    for res in pkg.get("resources", []):
        fmt = (res.get("format") or "").lower()
        name_url = ((res.get("name") or "") + " " + (res.get("url") or "")).lower()
        if "geojson" in fmt or ".geojson" in name_url:
            kind = 0
        elif "shp" in fmt or "shapefile" in fmt:
            kind = 1
        else:
            continue
        key = (kind, 1 if "hxl" in name_url else 0)
        if best_key is None or key < best_key:
            best, best_key = res, key
    if best is None:
        raise RuntimeError(f"No GeoJSON/shapefile resource in HDX package {pkg.get('name')!r}")
    return best


def _load_vector(path: Path) -> gpd.GeoDataFrame:
    """Read a downloaded file; if it is a zip, find the vector file inside."""
    if path.suffix.lower() == ".zip":
        extract = path.with_suffix("")
        extract.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(path) as zf:
            zf.extractall(extract)
        pref = {".geojson": 0, ".gpkg": 1, ".shp": 2, ".json": 3}
        candidates = sorted(
            (p for p in extract.rglob("*") if p.is_file() and p.suffix.lower() in VECTOR_SUFFIXES),
            key=lambda p: pref.get(p.suffix.lower(), 9),
        )
        if not candidates:
            raise RuntimeError(f"No vector file inside {path.name}")
        path = candidates[0]
    return gpd.read_file(path)


def _normalize(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    out = gdf.copy()
    if out.crs is None:
        out = out.set_crs("EPSG:4326")
    norm = {c: re.sub(r"[^a-z0-9]+", "_", str(c).lower()).strip("_") for c in out.columns}

    def pick(*, contains, exclude=()):
        for c, n in norm.items():
            if c == "geometry" or n in exclude:
                continue
            if any(k in n for k in contains):
                return c
        return None

    name_col = pick(contains=("name",), exclude=("changeset", "osm", "version", "source"))
    type_col = pick(contains=("amenity", "facility_type", "type", "kind"))
    renamed = {}
    if name_col:
        renamed[name_col] = "facility_name"
    if type_col and type_col != name_col:
        renamed[type_col] = "facility_type"
    out = out.rename(columns=renamed)
    keep = ["geometry"] + [c for c in ("facility_name", "facility_type") if c in out.columns]
    out = out[keep]
    out = out[out.geometry.notna() & out.geometry.is_valid]
    return out.reset_index(drop=True)


class HealthsitesAdapter(Adapter):
    name = "healthsites"
    description = "Health facility points from healthsites.io (via HDX, ODbL)"

    def run(self, ctx: BuildContext, params: Mapping[str, Any]) -> LayerResult:
        session = new_session()
        pkg = _find_package(session, ctx.profile)
        res = _pick_resource(pkg)
        log.info("healthsites: dataset %r -> resource %r", pkg.get("title"), res.get("name"))

        raw_path, _digest = download(res["url"], ctx.raw_dir, session=session)
        gdf = _normalize(_load_vector(raw_path))
        out_path = ctx.data_dir / "facilities.geojson"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        gdf.to_file(out_path, driver="GeoJSON")
        log.info("healthsites: %d facilities -> %s", len(gdf), out_path.name)

        return LayerResult(
            layer="facilities",
            adapter=self.name,
            kind="vector",
            license=pkg.get("license_title") or "ODbL",
            attribution=f"healthsites.io via HDX ({pkg.get('title')})",
            source_urls=[f"https://data.humdata.org/dataset/{pkg.get('name')}",
                         "https://healthsites.io/"],
            source_version=res.get("last_modified") or pkg.get("last_modified"),
            retrieved_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            outputs={"facilities": out_path},
            raw=[raw_path],
            extra={"facility_count": int(len(gdf))},
        )
