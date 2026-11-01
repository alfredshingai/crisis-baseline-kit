"""Audit HOT education-facilities (schools) coverage for Africa on HDX.

Usage: python tools/probe_schools.py
"""

from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cbk.util import new_session  # noqa: E402

HDX_API = "https://data.humdata.org/api/3/action"

ISOS = [
    "DZA", "AGO", "BEN", "BWA", "BFA", "BDI", "CMR", "CPV", "CAF", "TCD",
    "COM", "COG", "COD", "CIV", "DJI", "EGY", "GNQ", "ERI", "SWZ", "ETH",
    "GAB", "GMB", "GHA", "GIN", "GNB", "KEN", "LSO", "LBR", "LBY", "MDG",
    "MWI", "MLI", "MRT", "MUS", "MAR", "MOZ", "NAM", "NER", "NGA", "RWA",
    "STP", "SEN", "SYC", "SLE", "SOM", "ZAF", "SSD", "SDN", "TZA", "TGO",
    "TUN", "UGA", "ZMB", "ZWE", "ESH",
]


def check(iso3: str) -> dict:
    s = new_session()
    out = {"iso3": iso3}
    try:
        r = s.get(f"{HDX_API}/package_show",
                  params={"id": f"hotosm-{iso3.lower()}-education-facilities".replace("_", "-")},
                  timeout=30)
        pkg = r.json().get("result") if r.ok else None
        if not pkg:
            r = s.get(f"{HDX_API}/package_show",
                      params={"id": f"hotosm_{iso3.lower()}_education_facilities"}, timeout=30)
            pkg = r.json().get("result") if r.ok else None
        if not pkg:
            r = s.get(f"{HDX_API}/package_search",
                      params={"q": f"hotosm {iso3} education facilities", "rows": 3}, timeout=30)
            hits = r.json().get("result", {}).get("results", []) if r.ok else []
            pkg = next((p for p in hits if "education" in p.get("name", "")), None)
        out["found"] = bool(pkg)
        if pkg:
            out["slug"] = pkg["name"]
            fmts = sorted({(res.get("format") or "").lower() for res in pkg.get("resources", [])})
            out["formats"] = fmts
    except Exception as exc:
        out["found"] = False
        out["error"] = str(exc)[:80]
    s.close()
    return out


def main() -> None:
    with ThreadPoolExecutor(max_workers=8) as ex:
        rows = list(ex.map(check, ISOS))
    dest = Path(__file__).parent / "schools_audit.json"
    dest.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    found = [r for r in rows if r.get("found")]
    print(f"{len(found)}/{len(rows)} countries have HOT education-facilities packages")
    missing = [r["iso3"] for r in rows if not r.get("found")]
    print("missing:", " ".join(missing) or "-")
    for r in found[:6]:
        print("  e.g.", r["iso3"], r.get("slug"), r.get("formats"))


if __name__ == "__main__":
    main()
