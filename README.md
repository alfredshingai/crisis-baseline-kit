# Crisis Baseline Kit

> Type a country code, get a documented, crisis-ready baseline map and
> database — built entirely from public data, refreshed on a schedule,
> with provenance for every row.

When a crisis hits, responders spend the first days assembling the same
layers from a dozen inconsistent sources: boundaries, population, roads,
facilities, exposure. This kit makes that assembly a finished, reproducible
artifact **before** the emergency — a pre-crisis baseline that anyone can
rebuild and verify.

**Status: v0.1 pilot (Malawi).** Boundaries + population + zonal statistics
+ provenance manifest + quality gates + a bundled map viewer.

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .

cbk build MWI          # fetch sources, build the Malawi baseline bundle
cbk serve MWI          # open the bundled map viewer (http://127.0.0.1:8000)
cbk selftest           # synthetic end-to-end test, no network needed
cbk adapters           # list available source adapters
```

## What a build produces

```
baselines/MWI/2026-10-25/
├── cbk_baseline.gpkg    # admin 0/1/2 boundaries; admin 2 carries the stats
├── admin2.parquet       # admin-2 table (GeoParquet, analysis-ready)
├── admin2.geojson       # same table, used by the viewer
├── manifest.json        # per-layer source URL, license, version, SHA-256, timestamps
├── quality_report.json  # automated quality-gate results
├── index.html           # MapLibre choropleth viewer (no tile server needed)
├── viewer_config.json   # viewer styling + computed class breaks
├── README.md            # human-readable summary, auto-generated
├── data/                # normalized per-layer outputs
└── raw/                 # original downloads, checksummed
```

Every admin-2 row ends up with `population_sum`, `area_km2` and
`pop_density_km2` — the zonal-statistics join that turns a pile of
downloads into a database. A build whose quality gate fails (unexpected
admin-2 count, population total out of range, missing p-codes, ...) exits
non-zero, so broken baselines cannot ship silently.

## Adding a country

Create `profiles/XXX.yaml` (see `profiles/MWI.yaml`). The profile picks
adapters and parameters, the analysis CRS, expected quality ranges, and
viewer styling. No code required — then `cbk build XXX`.

## Adding a data source

Sources are adapters: one Python module in `src/cbk/adapters/` implementing
`run(ctx, params) -> LayerResult` with full provenance (license, source
URL, version, retrieval time). Register it in `adapters/__init__.py`.
Adapters are deliberately small — fetch, normalize, document. Everything
downstream (joins, stats, manifest, viewer) is shared.

Good first adapters: OSM roads via Geofabrik extracts, JRC surface water,
health facilities.

## Design notes

- **Provenance is the product.** `manifest.json` answers "where did this
  come from, how old is it, under what license" for every layer and file.
- **Quality gates block bad builds.** Expectations live in the country
  profile and run on every build, locally and in CI.
- **Reproducible by construction.** Bundles are dated, checksummed, and
  rebuilt from pinned source URLs; nothing is hand-edited.
- **License-clean composites.** Layers stay separable with per-layer
  licenses; see `docs/sources.md` for the full policy (incl. planned ODbL
  handling for OSM data).

## Roadmap

- v0.2 — roads & buildings (OSM), health facilities, schools; PMTiles
  output; bundle diffing ("what changed since last month's baseline")
- v0.3 — hazard layers (JRC surface water, Copernicus DEM) and simple
  exposure scoring per admin unit
- growth — more countries (each is one YAML file), a cross-country
  Parquet dataset for region-wide queries

## Contributing

Issues and PRs welcome. Two great ways to start: **adopt a country** (write
a profile, run it, fix what breaks) or **write an adapter** for a source
you know. Please keep provenance metadata complete in any new adapter.

## License

Code: MIT. Data: per-source licenses, recorded per layer in each bundle's
`manifest.json` — see `docs/sources.md`.
