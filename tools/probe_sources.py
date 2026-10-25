"""Audit source coverage for a list of countries (default: Africa).

Checks, per country:
  - OCHA COD-AB dataset on HDX (cod-ab-{iso3})
  - WorldPop 2020 raster (HEAD request)
  - healthsites.io dataset on HDX

Writes JSON to tools/africa_audit.json and prints a matrix.

Usage: python tools/probe_sources.py
"""

from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cbk.util import new_session  # noqa: E402

HDX_API = "https://data.humdata.org/api/3/action"
WP_BASE = "https://data.worldpop.org/GIS/Population/Global_2000_2020/2020"

AFRICA = [
    ("DZA", "Algeria"), ("AGO", "Angola"), ("BEN", "Benin"), ("BWA", "Botswana"),
    ("BFA", "Burkina Faso"), ("BDI", "Burundi"), ("CMR", "Cameroon"),
    ("CPV", "Cabo Verde"), ("CAF", "Central African Republic"), ("TCD", "Chad"),
    ("COM", "Comoros"), ("COG", "Congo"), ("COD", "Democratic Republic of the Congo"),
    ("CIV", "Cote d'Ivoire"), ("DJI", "Djibouti"), ("EGY", "Egypt"),
    ("GNQ", "Equatorial Guinea"), ("ERI", "Eritrea"), ("SWZ", "Eswatini"),
    ("ETH", "Ethiopia"), ("GAB", "Gabon"), ("GMB", "Gambia"), ("GHA", "Ghana"),
    ("GIN", "Guinea"), ("GNB", "Guinea-Bissau"), ("KEN", "Kenya"), ("LSO", "Lesotho"),
    ("LBR", "Liberia"), ("LBY", "Libya"), ("MDG", "Madagascar"), ("MWI", "Malawi"),
    ("MLI", "Mali"), ("MRT", "Mauritania"), ("MUS", "Mauritius"), ("MAR", "Morocco"),
    ("MOZ", "Mozambique"), ("NAM", "Namibia"), ("NER", "Niger"), ("NGA", "Nigeria"),
    ("RWA", "Rwanda"), ("STP", "Sao Tome and Principe"), ("SEN", "Senegal"),
    ("SYC", "Seychelles"), ("SLE", "Sierra Leone"), ("SOM", "Somalia"),
    ("ZAF", "South Africa"), ("SSD", "South Sudan"), ("SDN", "Sudan"),
    ("TZA", "Tanzania"), ("TGO", "Togo"), ("TUN", "Tunisia"), ("UGA", "Uganda"),
    ("ZMB", "Zambia"), ("ZWE", "Zimbabwe"), ("ESH", "Western Sahara"),
]


def check_country(iso3: str, name: str) -> dict:
    s = new_session()
    out = {"iso3": iso3, "name": name}

    try:  # COD-AB
        r = s.get(f"{HDX_API}/package_show", params={"id": f"cod-ab-{iso3.lower()}"}, timeout=30)
        out["codab"] = bool(r.ok and r.json().get("result"))
    except Exception:
        out["codab"] = False

    try:  # WorldPop
        h = s.head(f"{WP_BASE}/{iso3}/{iso3.lower()}_ppp_2020.tif", timeout=30, allow_redirects=True)
        out["worldpop"] = h.status_code == 200
        out["worldpop_mb"] = round(int(h.headers.get("Content-Length", 0)) / 1e6) if out["worldpop"] else None
    except Exception:
        out["worldpop"] = False
        out["worldpop_mb"] = None

    try:  # healthsites
        slug = f"{name.lower().replace(' ', '-')}-healthsites"
        r = s.get(f"{HDX_API}/package_show", params={"id": slug}, timeout=30)
        if r.ok and r.json().get("result"):
            out["healthsites"] = True
        else:
            r2 = s.get(f"{HDX_API}/package_search",
                       params={"q": f"healthsites {name}", "rows": 3}, timeout=30)
            hits = r2.json().get("result", {}).get("results", []) if r2.ok else []
            out["healthsites"] = any("healthsites" in (p.get("name") or "") for p in hits)
    except Exception:
        out["healthsites"] = False

    s.close()
    return out


def main() -> None:
    with ThreadPoolExecutor(max_workers=6) as ex:
        rows = list(ex.map(lambda c: check_country(*c), AFRICA))
    dest = Path(__file__).parent / "africa_audit.json"
    dest.write_text(json.dumps(rows, indent=2), encoding="utf-8")

    ok = [r for r in rows if r["codab"] and r["worldpop"]]
    print(f"{'ISO3':5s} {'country':38s} codab  worldpop  size(MB)  healthsites")
    for r in rows:
        print(f"{r['iso3']:5s} {r['name']:38s} {str(r['codab']):6s} {str(r['worldpop']):9s} "
              f"{str(r['worldpop_mb']):9s}  {r['healthsites']}")
    print(f"\n{len(ok)}/{len(rows)} countries qualify (COD-AB + WorldPop)")
    print(f"total WorldPop download: {sum(r['worldpop_mb'] or 0 for r in ok) / 1000:.1f} GB")


if __name__ == "__main__":
    main()
