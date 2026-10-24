"""Zonal statistics: join raster population onto admin polygons.

Uses exactextract when available (fast); falls back to per-feature rasterio
masking, which is fine for the few-hundred-features admin-2 level.
"""

from __future__ import annotations

import geopandas as gpd
import pandas as pd
import rasterio
from shapely.geometry import mapping

try:  # optional speed-up
    from exactextract import exact_extract
except ImportError:  # pragma: no cover
    exact_extract = None


def zonal_sum(raster_path, gdf: gpd.GeoDataFrame, key: str) -> gpd.GeoDataFrame:
    """Attach a `population_sum` column (raster sum per polygon) to gdf."""
    if exact_extract is not None:
        result = exact_extract(raster_path, gdf, ["sum"], include_cols=[key])
        stats = _as_dataframe(result, key)
    else:
        stats = _masking_sum(raster_path, gdf, key)
    stats = stats.rename(columns={"sum": "population_sum"})
    stats["population_sum"] = stats["population_sum"].astype("float64")
    return gdf.merge(stats, on=key, how="left", validate="one_to_one")


def _as_dataframe(result, key: str) -> pd.DataFrame:
    if isinstance(result, pd.DataFrame):
        df = result.copy()
    else:
        rows = []
        for item in result:
            if isinstance(item, dict) and "properties" in item and key not in item:
                rows.append(dict(item["properties"]))
            else:
                rows.append(dict(item))
        df = pd.DataFrame(rows)
    return df[[key, "sum"]]


def _masking_sum(raster_path, gdf: gpd.GeoDataFrame, key: str) -> pd.DataFrame:
    """Fallback zonal sum: one rasterio.mask pass per feature."""
    from rasterio.mask import mask

    sums = []
    with rasterio.open(raster_path) as src:
        for _, row in gdf.iterrows():
            try:
                arr, _ = mask(src, [mapping(row.geometry)], crop=True, filled=True, nodata=src.nodata)
                band = arr[0]
                vals = band[band != src.nodata] if src.nodata is not None else band.ravel()
                sums.append(float(vals.astype("float64").sum()) if vals.size else 0.0)
            except ValueError:  # geometry outside raster extent
                sums.append(0.0)
    return pd.DataFrame({key: gdf[key].tolist(), "sum": sums})


def add_derived(gdf: gpd.GeoDataFrame, crs_analysis: str) -> gpd.GeoDataFrame:
    """Add area_km2 and pop_density_km2, computed in a projected CRS."""
    gdf = gdf.copy()
    gdf["area_km2"] = (gdf.to_crs(crs_analysis).area / 1e6).round(2)
    gdf["population_sum"] = gdf["population_sum"].round(1)
    gdf["pop_density_km2"] = (gdf["population_sum"] / gdf["area_km2"]).round(1)
    return gdf
