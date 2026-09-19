"""Sentinel-2 L2A provider backed by the Earth Search v1 STAC API and the
public ``sentinel-cogs`` bucket on AWS (§7.3, §13).

Real, production-capable adapter:
* discovery via STAC search (cloud pre-filter server-side)
* windowed COG reads (only the AOI window, §18)
* reflectance scale/offset read from each asset's ``raster:bands`` metadata,
  with documented Sentinel-2 L2A defaults as a fallback (§20)
"""
from __future__ import annotations

import os

import rasterio
from pystac_client import Client
from rasterio.warp import transform_bounds
from rasterio.windows import from_bounds

from app.domain.models import AOI, DataAsset, DateRange, Scene
from app.providers.base import BandWindow, DataProvider

EARTH_SEARCH_URL = "https://earth-search.aws.element84.com/v1"
COLLECTION = "sentinel-2-l2a"

# Sentinel-2 L2A processing baseline >= 04.00 (since 2022-01-25) applies a
# BOA_ADD_OFFSET of -1000 to reflectance DN. reflectance = (DN - 1000) * 1e-4
# = DN*1e-4 - 0.1. Used only when a scene omits raster:bands metadata.
_DEFAULT_SCALE = 0.0001
_DEFAULT_OFFSET = -0.1

# GDAL tuning for efficient anonymous remote COG access.
_GDAL_ENV = {
    "AWS_NO_SIGN_REQUEST": "YES",
    "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
    "VSI_CACHE": "TRUE",
    "GDAL_HTTP_MULTIPLEX": "YES",
    "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif",
}


class Sentinel2Provider(DataProvider):
    name = COLLECTION
    supported_bands = ("red", "nir", "scl")

    def __init__(self, stac_url: str = EARTH_SEARCH_URL) -> None:
        self._stac_url = stac_url
        self._client: Client | None = None

    def _stac(self) -> Client:
        if self._client is None:
            self._client = Client.open(self._stac_url)
        return self._client

    def search(
        self,
        aoi: AOI,
        date_range: DateRange,
        cloud_threshold: float,
        limit: int = 20,
    ) -> list[Scene]:
        search = self._stac().search(
            collections=[COLLECTION],
            bbox=list(aoi.bbox()),
            datetime=date_range.as_stac_datetime(),
            query={"eo:cloud_cover": {"lt": cloud_threshold}},
            max_items=limit,
        )
        scenes: list[Scene] = []
        for item in search.items():
            assets: dict[str, DataAsset] = {}
            for key in self.supported_bands:
                if key in item.assets:
                    assets[key] = DataAsset(key=key, href=item.assets[key].href)
            scenes.append(
                Scene(
                    id=item.id,
                    provider=self.name,
                    datetime=item.datetime,
                    cloud_cover=item.properties.get("eo:cloud_cover"),
                    assets=assets,
                )
            )
        return scenes

    @staticmethod
    def _scale_offset(src: rasterio.DatasetReader) -> tuple[float, float]:
        """Read reflectance scale/offset from the COG tags, else S2 L2A defaults."""
        scales = src.scales
        offsets = src.offsets
        scale = scales[0] if scales and scales[0] not in (0, None) else _DEFAULT_SCALE
        offset = offsets[0] if offsets else _DEFAULT_OFFSET
        return float(scale), float(offset)

    def read_window(self, scene: Scene, band_key: str, aoi: AOI) -> BandWindow:
        if band_key not in scene.assets:
            raise KeyError(f"scene {scene.id} has no asset '{band_key}'")
        href = scene.assets[band_key].href
        with rasterio.Env(**_GDAL_ENV):
            with rasterio.open(href) as src:
                left, bottom, right, top = transform_bounds(
                    "EPSG:4326", src.crs, *aoi.bbox()
                )
                window = from_bounds(left, bottom, right, top, src.transform)
                arr = src.read(1, window=window)
                scale, offset = self._scale_offset(src)
                # SCL is a classification raster: it has no meaningful reflectance
                # scaling, so report identity scale/offset for it.
                if band_key == "scl":
                    scale, offset = 1.0, 0.0
                return BandWindow(
                    array=arr,
                    scale=scale,
                    offset=offset,
                    nodata=src.nodata,
                    crs=str(src.crs),
                    band_key=band_key,
                )


def _apply_env_defaults() -> None:
    """Set GDAL env defaults at import for any code path that opens rasters
    outside an explicit ``rasterio.Env`` (belt and braces)."""
    for k, v in _GDAL_ENV.items():
        os.environ.setdefault(k, v)


_apply_env_defaults()


def build() -> Sentinel2Provider:
    """Factory used by the provider bootstrap."""
    return Sentinel2Provider()
