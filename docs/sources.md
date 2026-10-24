# Data sources & licenses

The kit only uses publicly available data. Every bundle records the exact
URL, license, version and SHA-256 of each source in its `manifest.json`;
this page is the human-readable overview and the license policy.

## v0.1 layers

| Layer | Source | License | Notes |
|---|---|---|---|
| Admin boundaries (COD-AB) | OCHA via [HDX](https://data.humdata.org/) | varies by country (recorded per build from the HDX API) | Common Core Operational Datasets; the version every org responds with |
| Population raster | [WorldPop](https://www.worldpop.org/) Global 2000-2020 | CC-BY 4.0 | 100 m; unconstrained (`ppp`) and UN-adjusted (`ppp_UNadj`) variants exist |

## Planned layers

| Layer | Source | License | Target |
|---|---|---|---|
| Roads / buildings | OpenStreetMap (Geofabrik extracts) | ODbL (share-alike) | v0.2 |
| Health facilities | healthsites.io, WHO/KEMRI-Wellcome, OSM | mixed | v0.2 |
| Schools | UNICEF x OSM global schools | CC-BY / ODbL | v0.2 |
| Surface water | EC JRC Global Surface Water | CC-BY 4.0 | v0.3 |
| Elevation / slope | Copernicus DEM GLO-30 | open | v0.3 |

## License policy

- **Code** in this repository is MIT.
- **Data** stays under its source license. Bundles keep layers in separate
  files/tables so each license can be honored; the composite bundle never
  re-licenses anything — check `manifest.json` for per-layer terms.
- **ODbL (OSM) is share-alike**: when OSM-derived layers arrive in v0.2 they
  will live in their own tables, clearly marked, so ODbL obligations apply
  only to those tables and not to the whole bundle.
- When in doubt, prefer per-layer attribution exactly as recorded in the
  manifest's `attribution` field.
