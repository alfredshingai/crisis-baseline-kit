"""Major roads from OpenStreetMap, via Geofabrik country extracts.

Reads motorway/trunk/primary/secondary/tertiary (+ links) ways from the
country .osm.pbf using GDAL's OSM driver (no PBF toolchain needed).
OSM data is ODbL share-alike: roads stay in their own table/layer and
never merge into boundary tables; only aggregate length per admin unit
is joined (see docs/sources.md).

Note: Geofabrik publishes one shared extract for Senegal and The Gambia;
Western Sahara has no separate extract (part of Morocco's) so ESH simply
skips this optional layer.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import geopandas as gpd
import pyogrio

from ..util import download, log, new_session
from .base import Adapter, BuildContext, LayerResult

GEOFABRIK_SLUGS = {
    "DZA": "algeria", "AGO": "angola", "BEN": "benin", "BWA": "botswana",
    "BFA": "burkina-faso", "BDI": "burundi", "CMR": "cameroon",
    "CPV": "cape-verde", "CAF": "central-african-republic", "TCD": "chad",
    "COM": "comoros", "COG": "congo-brazzaville", "COD": "congo-democratic-republic",
    "CIV": "ivory-coast", "DJI": "djibouti", "EGY": "egypt",
    "GNQ": "equatorial-guinea", "ERI": "eritrea", "SWZ": "eswatini",
    "ETH": "ethiopia", "GAB": "gabon", "GMB": "senegal-and-gambia",
    "GHA": "ghana", "GIN": "guinea", "GNB": "guinea-bissau", "KEN": "kenya",
    "LSO": "lesotho", "LBR": "liberia", "LBY": "libya", "MDG": "madagascar",
    "MWI": "malawi", "MLI": "mali", "MRT": "mauritania", "MUS": "mauritius",
    "MAR": "morocco", "MOZ": "mozambique", "NAM": "namibia", "NER": "niger",
    "NGA": "nigeria", "RWA": "rwanda", "STP": "sao-tome-and-principe",
    "SEN": "senegal-and-gambia", "SYC": "seychelles", "SLE": "sierra-leone",
    "SOM": "somalia", "ZAF": "south-africa", "SSD": "south-sudan",
    "SDN": "sudan", "TZA": "tanzania", "TGO": "togo", "TUN": "tunisia",
    "UGA": "uganda", "ZMB": "zambia", "ZWE": "zimbabwe",
}

ROAD_CLASSES = (
    "motorway", "trunk", "primary", "secondary", "tertiary",
    "motorway_link", "trunk_link", "primary_link", "secondary_link",
    "tertiary_link",
)


class RoadsAdapter(Adapter):
    name = "roads"
    description = "Major roads from OpenStreetMap via Geofabrik extracts (ODbL)"

    def run(self, ctx: BuildContext, params: Mapping[str, Any]) -> LayerResult:
        slug = GEOFABRIK_SLUGS.get(ctx.profile.iso3)
        if not slug:
            raise RuntimeError(
                f"No Geofabrik extract mapped for {ctx.profile.iso3}; "
                "skipping roads (add a slug in adapters/roads.py if one exists)"
            )
        url = f"https://download.geofabrik.de/africa/{slug}-latest.osm.pbf"
        session = new_session()
        pbf, _digest = download(url, ctx.raw_dir, session=session)

        where = "highway IN (" + ",".join(f"'{c}'" for c in ROAD_CLASSES) + ")"
        roads = pyogrio.read_dataframe(pbf, layer="lines", where=where,
                                       columns=["highway", "name"])
        roads = roads[roads.geometry.notna() & roads.geometry.is_valid].reset_index(drop=True)
        if roads.crs is None:
            roads = roads.set_crs("EPSG:4326")
        log.info("roads: %d major-road segments from %s", len(roads), pbf.name)

        out_path = ctx.data_dir / "roads.gpkg"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        roads.to_file(out_path, layer="roads", driver="GPKG")

        return LayerResult(
            layer="roads",
            adapter=self.name,
            kind="vector",
            license="ODbL",
            attribution="OpenStreetMap contributors, via Geofabrik "
                        f"(africa/{slug}-latest.osm.pbf)",
            source_urls=[url, "https://www.openstreetmap.org/copyright"],
            source_version=pbf.name,  # -latest extracts; checksum pins the exact file
            retrieved_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            outputs={"roads": out_path},
            raw=[pbf],
            extra={"segment_count": int(len(roads)),
                   "road_classes": sorted(roads["highway"].dropna().unique().tolist())},
        )
