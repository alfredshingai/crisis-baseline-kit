# Changelog

## 0.4.0 — 2026-10-31

Roads everywhere, plus the change-detection primitive.

- **Major-road network per admin unit** for 53 of 54 countries (km and
  km/100km²), extracted from OpenStreetMap via Geofabrik country extracts
  through GDAL's OSM driver — motorway through tertiary plus link classes.
  OSM geometry stays in a separate ODbL table; only aggregates join the
  admin data. Nigeria alone contributes 121,000 km across its 774 LGAs.
- **`cbk diff`** — compares a country's two latest bundles and writes a
  per-unit change report (`diff_report.json`); the weekly rebuilds now
  accumulate comparable baselines.
- **Map UIs**: roads-density field added to the live site and bundle
  viewer popups.
- **Adapter hardening**: Geofabrik slug corrections found the hard way
  (Comoros publishes as `comores`, Eswatini as `swaziland`); download
  retries with backoff survived several upstream connection-drop episodes
  across the 53-country rebuild waves.
- Western Sahara has no separate OSM extract (covered by Morocco's);
  its roads layer is skipped by design.

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
