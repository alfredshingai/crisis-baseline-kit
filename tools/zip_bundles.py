"""Zip every passing country's latest bundle into dist/ for a release.

Skips countries whose latest bundle failed its quality gate; prints a
per-country summary and total size. raw/ files are trimmed by the wave
runner (re-downloadable via manifest URLs; checksums are recorded), so
release bundles ship without them by design.

Usage: python tools/zip_bundles.py
"""

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"


def main() -> None:
    DIST.mkdir(exist_ok=True)
    rows, total = [], 0
    for iso_dir in sorted((ROOT / "baselines").iterdir()):
        if not iso_dir.is_dir():
            continue
        bundles = sorted(p for p in iso_dir.iterdir() if p.is_dir())
        if not bundles:
            continue
        bundle = bundles[-1]
        qr = bundle / "quality_report.json"
        if not qr.is_file():
            rows.append((iso_dir.name, "SKIP", "no quality report"))
            continue
        q = json.loads(qr.read_text(encoding="utf-8"))
        if not q.get("passed"):
            rows.append((iso_dir.name, "SKIP", "quality FAIL"))
            continue
        out = DIST / f"{iso_dir.name.lower()}-baseline-{bundle.name}.zip"
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
            for p in sorted(bundle.rglob("*")):
                if p.is_file():
                    z.write(p, f"{iso_dir.name.lower()}-baseline-{bundle.name}/{p.relative_to(bundle)}")
        mb = out.stat().st_size / 1e6
        total += mb
        n = next((c["detail"].split()[0] for c in q["checks"] if c["check"] == "admin2_nonempty"), "?")
        rows.append((iso_dir.name, f"{mb:7.1f} MB", f"admin{n}"))
    for iso, size, note in rows:
        print(f"{iso:5s} {size:12s} {note}")
    print(f"\n{sum(1 for r in rows if 'MB' in r[1])} bundles, {total / 1000:.1f} GB total -> {DIST}")


if __name__ == "__main__":
    sys.exit(main())
