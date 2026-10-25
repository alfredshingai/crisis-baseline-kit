# Changelog

## 0.3.0 — 2026-10-25

Africa-wide coverage.

- **54 country baselines** — every African country with buildable public
  sources (all except Mauritius, whose COD-AB ships only image files):
  OCHA COD-AB boundaries, WorldPop 2020 population, healthsites.io
  facility counts, quality-gated and committed one country at a time.
- **COD-AB adapter hardened against the real world**: tries ranked
  resources until one yields admin levels (Lesotho's preview-only zip),
  merges per-level resource packages via union fallback (Tanzania),
  reads ESRI geodatabases and GeoPackage layers, demotes junk formats.
- **Stats level generalized**: countries whose COD-AB stops at admin-1
  (São Tomé, Western Sahara) build stats at their deepest level.
- **Live map UI rebuilt**: searchable country sidebar with populations,
  field switcher (population / density / facilities per 10k), 7-class
  quantile ramp, hover highlighting, richer popups, keyless Esri light
  basemap; CI builds countries in parallel and the site republishes
  weekly.
- **Quality gates pinned** per country from verified builds (admin-unit
  counts) and UN-2020 population bands (±40%, justified exceptions like
  South Sudan's census gap documented in-profile).
- **Tools**: `probe_sources.py` (coverage audit), `gen_profiles.py`,
  `pin_counts.py`, `zip_bundles.py`, commit-per-country `run_wave.sh`.

## 0.2.0 — 2026-10-25

Second country and the first service layer.

- **Mozambique** as the second country profile (~161 districts), validating
  that adding a country is a YAML file, not code. Uses an Africa equal-area
  CRS (ESRI:102022) because Mozambique spans two UTM zones.
- **Health facilities layer**: new `healthsites` adapter fetches
  healthsites.io facility points via HDX; admin-2 units gain
  `facility_count` and `facilities_per_10k_pop`. Facilities stay in their
  own ODbL table — only aggregates join into boundary tables
  (see docs/sources.md).
- **Live map**: GitHub Pages site (site/) with a country switcher,
  auto-published from the weekly CI rebuild.
- CI builds both countries as a matrix; self-test covers the facilities
  join.

## 0.1.0 — 2026-10-25

Initial release: Crisis Baseline Kit with the Malawi pilot.

- Adapter framework for public data sources: OCHA COD-AB administrative
  boundaries (via the HDX API) and WorldPop population rasters (100 m).
- Zonal statistics per admin-2 unit: population, area, population density.
- Quality gates that fail broken builds (expected admin-2 counts, p-code
  presence/uniqueness, national population ranges, geometry checks).
- Provenance manifests: source URLs, licenses, versions, retrieval times
  and SHA-256 checksums for every layer and file.
- Bundled MapLibre choropleth viewer (`cbk serve`).
- Countries are YAML profiles (`profiles/MWI.yaml`) — adding a country
  requires no code changes.
- CI: synthetic self-test on every push/PR; scheduled weekly rebuild of
  the Malawi baseline.
