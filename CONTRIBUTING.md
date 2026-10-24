# Contributing to Crisis Baseline Kit

Thanks for helping build pre-crisis baselines for the world. Issues and
pull requests are both welcome; this guide covers the common paths.

## Ways to contribute

### Adopt a country

The highest-value contribution. A country is one YAML file —
see `profiles/MWI.yaml` as the template:

1. Copy `profiles/MWI.yaml` to `profiles/XXX.yaml` (your country's ISO3).
2. Adjust the COD-AB slug (`cod-ab-xxx` on [HDX](https://data.humdata.org/)),
   the analysis CRS (a local UTM zone is usually right), the expected
   admin-2 count, and the expected population range (check the source).
3. Run `cbk build XXX`. Fix whatever breaks — source quirks are normal
   and the fixes usually belong in the adapters, where every country
   benefits.
4. Open a PR with the profile (and any adapter fixes) plus a short note
   of what the build produced.

### Write an adapter

Sources are adapters: one module in `src/cbk/adapters/` implementing
`run(ctx, params) -> LayerResult`. The contract:

- **Fetch** from the official public source (respect rate limits; set a
  descriptive User-Agent — see `cbk.util.new_session`).
- **Normalize** into canonical, documented outputs. Keep geometries in
  EPSG:4326; use stable column names.
- **Document provenance**: license, attribution string, source URLs,
  version, retrieval timestamp. An adapter without complete provenance
  metadata will not be merged — provenance is the product.
- Make it deterministic: same params in, same bundle out.

Register the class in `src/cbk/adapters/__init__.py`, add the layer to a
profile, and extend the self-test if you introduce new machinery.

Good first adapters: OSM roads via Geofabrik extracts, JRC Global Surface
Water, health facilities (healthsites.io / WHO), schools (UNICEF x OSM).

### Other contributions

Bug reports (especially source-drift bugs: "the HDX package changed and
now the build fails" is a real and recurring category), documentation,
quality-check ideas, and viewer improvements are all welcome.

## Development setup

```bash
git clone https://github.com/alfredshingai/crisis-baseline-kit
cd crisis-baseline-kit
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
cbk selftest
```

Python 3.10+ (CI tests on 3.12). The self-test runs the entire pipeline
on synthetic data with hand-computed expected values — run it before
every PR; CI runs it on every push.

## Pull request checklist

- [ ] `cbk selftest` passes locally
- [ ] If you touched an adapter: the affected country builds (`cbk build XXX`)
- [ ] If you added an adapter: provenance fields are complete, and the
      license is recorded (check `docs/sources.md` policy)
- [ ] If you added a country: the profile's quality ranges are justified
      (cite where the expected numbers come from in a comment)

## Licensing

Your code contributions are MIT (see [LICENSE](LICENSE)). Bundled data
always remains under its source license — never re-license data, never
mix ODbL-derived content into non-ODbL tables (see
[docs/sources.md](docs/sources.md) for the policy).
