"""Provenance manifest (machine-readable) and bundle README (human-readable).

Every raw file gets a SHA-256; every layer records its source URL, license,
version and retrieval time. This is what makes the bundle trustworthy.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from . import __version__
from .util import sha256_file


def _jsonable(obj):
    """Make a value JSON-safe (NaN/Inf -> null, numpy scalars -> plain)."""
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (float, np.floating)):
        f = float(obj)
        return f if math.isfinite(f) else None
    return obj


def _path_ref(p: Path, bundle_dir: Path) -> str:
    """Path relative to the bundle when possible, absolute otherwise."""
    try:
        return str(p.relative_to(bundle_dir))
    except ValueError:
        return str(p)


def build_manifest(
    profile,
    results: dict,
    bundle_dir: Path,
    quality: list[dict],
    output_files: dict[str, Path] | None = None,
) -> dict:
    layers = []
    for layer_name, res in results.items():
        layers.append({
            "layer": layer_name,
            "adapter": res.adapter,
            "kind": res.kind,
            "license": res.license,
            "attribution": res.attribution,
            "source_urls": res.source_urls,
            "source_version": res.source_version,
            "retrieved_at": res.retrieved_at,
            "raw_files": [
                {"name": p.name, "bytes": p.stat().st_size, "sha256": sha256_file(p)}
                for p in res.raw
            ],
            "outputs": {k: _path_ref(v, bundle_dir) for k, v in res.outputs.items()},
            "metadata": res.extra,
        })

    manifest = {
        "baseline_id": f"{profile.iso3}-{bundle_dir.name}",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "cbk_version": __version__,
        "profile": {
            "path": str(profile.path),
            "version": profile.profile_version,
            "iso3": profile.iso3,
            "name": profile.name,
        },
        "layers": layers,
        "bundle_outputs": {
            name: {"path": _path_ref(p, bundle_dir), "sha256": sha256_file(p)}
            for name, p in (output_files or {}).items()
        },
        "quality": {
            "passed": all(c["status"] != "FAIL" for c in quality),
            "checks": quality,
        },
    }
    (bundle_dir / "manifest.json").write_text(
        json.dumps(_jsonable(manifest), indent=2), encoding="utf-8"
    )
    return manifest


def render_readme(bundle_dir: Path, profile, manifest: dict, stats: dict) -> None:
    total = stats.get("population_total")
    total_str = f"{total:,.0f}" if isinstance(total, (int, float)) and math.isfinite(total) else "n/a"
    lines = [
        f"# Crisis Baseline: {profile.name} ({profile.iso3})",
        "",
        f"Baseline ID `{manifest['baseline_id']}` - generated {manifest['generated_at']} "
        f"with cbk v{manifest['cbk_version']}.",
        "",
        "## Sources & provenance",
        "",
        "| Layer | Adapter | Source | License | Version |",
        "|---|---|---|---|---|",
    ]
    for l in manifest["layers"]:
        src = l["source_urls"][0] if l["source_urls"] else ""
        lines.append(
            f"| {l['layer']} | {l['adapter']} | {src} | {l['license']} | {l['source_version'] or ''} |"
        )
    lines += [
        "",
        "## Contents",
        "",
        "- `cbk_baseline.gpkg` - admin 0/1/2 boundaries, admin 2 with population stats (GeoPackage)",
        "- `admin2.parquet` - admin-2 table (GeoParquet, analysis-ready)",
        "- `admin2.geojson` - same table for the bundled map viewer",
        "- `raw/` - original downloads, checksums in `manifest.json`",
        "- `manifest.json` - full provenance: URLs, licenses, SHA-256, timestamps",
        "- `quality_report.json` - automated quality-gate results",
        "",
        "## Summary",
        "",
        f"- National population (raster sum): **{total_str}**",
        f"- Admin-2 units: **{stats.get('admin2_count', 'n/a')}**",
        f"- Quality gate: **{'PASS' if manifest['quality']['passed'] else 'FAIL'}**",
        "",
        "## View the map",
        "",
        "```",
        f"cbk serve {profile.iso3}",
        "```",
        "",
    ]
    (bundle_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")
