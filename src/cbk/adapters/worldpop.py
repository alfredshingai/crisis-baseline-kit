"""WorldPop population raster (Global 2000-2020 series, 100 m resolution)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

import numpy as np
import rasterio

from ..util import download, log, new_session
from .base import Adapter, BuildContext, LayerResult

BASE = "https://data.worldpop.org/GIS/Population/Global_2000_2020"


class WorldPopAdapter(Adapter):
    name = "worldpop"
    description = "WorldPop population count raster (100 m, Global 2000-2020)"

    def run(self, ctx: BuildContext, params: Mapping[str, Any]) -> LayerResult:
        year = int(params.get("year", 2020))
        dataset = str(params.get("dataset", "ppp"))        # "ppp" or "ppp_UNadj"
        suffix = "_UNadj" if dataset.endswith("UNadj") else ""
        iso3 = ctx.profile.iso3.upper()
        iso = iso3.lower()
        url = f"{BASE}/{year}/{iso3}/{iso}_ppp_{year}{suffix}.tif"

        session = new_session()
        head = session.head(url, timeout=(20, 60), allow_redirects=True)
        if head.status_code != 200:
            raise RuntimeError(
                f"WorldPop raster not available at {url} (HTTP {head.status_code}); "
                "check the year/dataset parameters in the country profile"
            )
        tif, _digest = download(url, ctx.raw_dir, session=session)

        with rasterio.open(tif) as src:
            arr = src.read(1, masked=True)
            total = float(np.asarray(arr.sum(), dtype="float64"))
            meta = {
                "width": src.width,
                "height": src.height,
                "crs": str(src.crs),
                "resolution": [round(float(r), 8) for r in src.res],
                "nodata": src.nodata,
                "bounds": [round(float(b), 6) for b in src.bounds],
            }
        log.info("WorldPop %s %s: national raster total %.0f people", iso3, year, total)

        return LayerResult(
            layer="population",
            adapter=self.name,
            kind="raster",
            license="CC-BY 4.0",
            attribution=f"WorldPop ({iso3} {year}, {dataset}{suffix}, 100 m)",
            source_urls=[url, "https://www.worldpop.org/"],
            source_version=f"{year}{suffix}",
            retrieved_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            outputs={"raster": tif},
            raw=[tif],
            extra={"total_population": total, "year": year, "dataset": f"{dataset}{suffix}", **meta},
        )
