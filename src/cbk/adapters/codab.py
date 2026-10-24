"""OCHA COD-AB administrative boundaries (admin 0-2), fetched via the HDX API.

Handles the real-world variation in COD-AB packages: shapefile vs GeoPackage
vs GeoJSON, flat vs nested zips, and the many spellings of admin columns
(ADM2_PCODE, admin2Name_en, ADM2_EN, ...).
"""

from __future__ import annotations

import re
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import geopandas as gpd

from ..util import download, log, new_session
from .base import Adapter, BuildContext, LayerResult

HDX_API = "https://data.humdata.org/api/3/action"
VECTOR_SUFFIXES = {".shp", ".geojson", ".gpkg", ".json"}


def _hdx_get(session, action: str, params: dict) -> dict:
    r = session.get(f"{HDX_API}/{action}", params=params, timeout=60)
    r.raise_for_status()
    payload = r.json()
    if not payload.get("success"):
        raise RuntimeError(f"HDX API call {action} failed: {payload.get('error')}")
    return payload["result"]


def _find_package(session, slug: str, iso3: str) -> dict:
    try:
        return _hdx_get(session, "package_show", {"id": slug})
    except Exception as exc:
        log.warning("HDX package_show for %r failed (%s); falling back to search", slug, exc)
    results = _hdx_get(session, "package_search", {"q": f"cod-ab {iso3.lower()}", "rows": 10})
    for pkg in results.get("results", []):
        if pkg.get("name", "").startswith("cod-ab-") and iso3.lower() in pkg["name"]:
            return pkg
    raise RuntimeError(f"Could not find a COD-AB dataset on HDX for {iso3}")


def _pick_resource(pkg: dict) -> dict:
    """Choose the boundary resource (zip/gpkg/shapefile) from a COD-AB package."""

    def rank(res: dict) -> tuple[int, int, int]:
        fmt = (res.get("format") or "").lower()
        ext = Path(res.get("url") or "").suffix.lower().lstrip(".")
        fmt_rank = 0
        for i, key in enumerate(("geojson", "shp", "gpkg", "zip")):
            if key in fmt or ext == key:
                fmt_rank = i + 1
        name_url = (res.get("name", "") + " " + (res.get("url") or "")).lower()
        return (1 if "adm" in name_url else 0, fmt_rank, len(res.get("url") or ""))

    candidates = []
    for res in pkg.get("resources", []):
        fmt = (res.get("format") or "").lower()
        ext = Path(res.get("url") or "").suffix.lower().lstrip(".")
        boundaryish = any(k in fmt for k in ("shp", "zip", "gpkg", "geojson")) or ext in {
            "zip", "shp", "gpkg", "geojson",
        }
        if boundaryish:
            candidates.append(res)
    if not candidates:
        raise RuntimeError(f"No boundary resource found in HDX package {pkg.get('name')!r}")
    return max(candidates, key=rank)


def _level_from_name(name: str) -> int | None:
    """Extract the admin level from a file/layer name.

    Handles both spellings: 'mwi_admbnda_adm1_ocha' and 'mwi_admin1'.
    """
    stem = re.sub(r"[^a-z0-9]+", "_", Path(name).stem.lower()).strip("_")
    stem = stem.replace("admin", "adm")
    m = re.search(r"(?:^|_)adm(\d)(?:_|$)", f"_{stem}_")
    return int(m.group(1)) if m else None


def _extract(zip_path: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(dest)
    # Some COD-ABs nest per-level zips one level down; unpack those too.
    has_vectors = any(
        _level_from_name(p.name) is not None
        for p in dest.rglob("*")
        if p.is_file() and p.suffix.lower() in VECTOR_SUFFIXES
    )
    if not has_vectors:
        for inner in list(dest.rglob("*.zip")):
            sub = inner.with_suffix("")
            sub.mkdir(parents=True, exist_ok=True)
            try:
                with zipfile.ZipFile(inner) as zf:
                    zf.extractall(sub)
            except zipfile.BadZipFile:
                log.warning("Skipping unreadable inner zip %s", inner.name)


def _read_level(extract_dir: Path, level: int) -> gpd.GeoDataFrame:
    pref = {".gpkg": 0, ".shp": 1, ".geojson": 2, ".json": 3}
    candidates = [
        p for p in extract_dir.rglob("*")
        if p.is_file() and p.suffix.lower() in VECTOR_SUFFIXES and _level_from_name(p.name) == level
    ]
    if candidates:
        candidates.sort(key=lambda p: (pref.get(p.suffix.lower(), 9), len(p.parts), len(str(p))))
        gdf = gpd.read_file(candidates[0])
    else:
        # Fallback: a single GeoPackage whose internal layers are named adm0/adm1/...
        gdf = None
        try:
            import pyogrio

            for p in extract_dir.rglob("*.gpkg"):
                try:
                    layers = [str(row[0]) for row in pyogrio.list_layers(p)]
                except Exception:
                    continue
                for lname in layers:
                    if _level_from_name(f"{lname}.x") == level:
                        gdf = gpd.read_file(p, layer=lname)
                        break
                if gdf is not None:
                    break
        except ImportError:
            pass
        if gdf is None:
            found = sorted(p.name for p in extract_dir.rglob("*") if p.is_file())[:25]
            raise RuntimeError(
                f"No admin level {level} found in COD-AB extract; files: {found}"
            )
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    return gdf


def normalize_admin_columns(gdf: gpd.GeoDataFrame, level: int) -> gpd.GeoDataFrame:
    """Map COD-AB column variants (ADM2_PCODE, admin2Name_en, ADM2_EN, ...)
    onto canonical adm{N}_pcode / adm{N}_name columns, keeping parent columns."""
    out = gdf.copy()
    norm = {}
    for c in out.columns:
        if c == "geometry":
            continue
        n = re.sub(r"[^a-z0-9]+", "_", str(c).lower()).strip("_")
        norm[c] = n.replace("admin", "adm")

    renames: dict[str, str] = {}
    meta_words = ("date", "type", "src", "alt", "source", "level")
    for lvl in range(0, level + 1):
        cols = [c for c, n in norm.items() if f"adm{lvl}" in n]
        pcode = next((c for c in cols if "pcode" in norm[c]), None)
        if pcode:
            renames[pcode] = f"adm{lvl}_pcode"
        name_cands = [c for c in cols if c != pcode]
        named = [c for c in name_cands if "name" in norm[c]]
        en = [c for c in name_cands if norm[c].endswith("_en") or norm[c].endswith("en")]
        clean = [c for c in name_cands if not any(w in norm[c] for w in meta_words)]
        for group in (named, en, clean, name_cands):
            if group:
                renames[group[0]] = f"adm{lvl}_name"
                break
    out = out.rename(columns=renames)
    keep = ["geometry"]
    for lvl in range(0, level + 1):
        keep += [f"adm{lvl}_pcode", f"adm{lvl}_name"]
    return out[[c for c in keep if c in out.columns]]


class CodabAdapter(Adapter):
    name = "codab"
    description = "OCHA COD-AB administrative boundaries (admin 0-2) from HDX"

    def run(self, ctx: BuildContext, params: Mapping[str, Any]) -> LayerResult:
        levels = list(params.get("admin_levels", [0, 1, 2]))
        session = new_session()
        pkg = _find_package(session, ctx.profile.hdx_slug, ctx.profile.iso3)
        res = _pick_resource(pkg)
        log.info("COD-AB package %r -> resource %r", pkg.get("title"), res.get("name"))

        zip_path, _digest = download(res["url"], ctx.raw_dir, session=session)
        extract_dir = ctx.raw_dir / "codab_extract"
        _extract(zip_path, extract_dir)

        outputs: dict[str, Path] = {}
        feature_counts: dict[str, int] = {}
        for level in levels:
            gdf = _read_level(extract_dir, level)
            gdf = normalize_admin_columns(gdf, level)
            if f"adm{level}_pcode" not in gdf.columns:
                log.warning("admin%s: no p-code column recognized; quality gate will flag it", level)
            out_path = ctx.data_dir / f"admin{level}.geojson"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            gdf.to_file(out_path, driver="GeoJSON")
            outputs[f"admin{level}"] = out_path
            feature_counts[f"admin{level}_features"] = int(len(gdf))
            log.info("admin%s: %d features -> %s", level, len(gdf), out_path.name)

        # The unpacked copy is intermediate; the original zip stays in raw/.
        shutil.rmtree(extract_dir, ignore_errors=True)

        return LayerResult(
            layer="admin_boundaries",
            adapter=self.name,
            kind="vector",
            license=pkg.get("license_title") or "See dataset page on HDX",
            attribution=f"{pkg.get('dataset_source') or 'OCHA'} via HDX ({pkg.get('title')})",
            source_urls=[f"https://data.humdata.org/dataset/{pkg.get('name')}"],
            source_version=res.get("last_modified") or pkg.get("last_modified"),
            retrieved_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            outputs=outputs,
            raw=[zip_path],
            extra=feature_counts,
        )
