# Changelog

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
