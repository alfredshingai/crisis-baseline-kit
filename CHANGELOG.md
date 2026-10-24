# Changelog

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
