"""Sentinel-2 L2A provider backed by the Earth Search v1 STAC API and the
public ``sentinel-cogs`` bucket on AWS (§7.3, §13).

Real, production-capable adapter:
* discovery via STAC search (generous server-side cloud pre-filter)
* windowed COG reads (only the AOI window, §18)
* reflectance scale/offset read from STAC ``raster:bands`` metadata at search
  time (NOT from the COG's own GDAL band tags — verified empirically against a
  live scene that those tags report the uninformative default (1.0, 0.0) even
  though the STAC item's ``raster:bands`` carries the real (0.0001, -0.1)),
  with documented Sentinel-2 L2A defaults as a fallback (§20)
* SCL (20 m) is resampled to the red/nir (10 m) grid on read via nearest-
  neighbor — verified empirically that SCL and red/nir windows otherwise come
  back at different shapes and cannot be combined for masking (§17)
"""
from __future__ import annotations

import os

import rasterio
from pystac_client import Client
from rasterio.enums import Resampling
from rasterio.warp import transform_bounds
from rasterio.windows import from_bounds

from app.domain.models import AOI, DataAsset, DateRange, Scene
from app.providers.base import BandWindow, DataProvider

EARTH_SEARCH_URL = "https://earth-search.aws.element84.com/v1"
COLLECTION = "sentinel-2-l2a"

# Sentinel-2 L2A processing baseline >= 04.00 (since 2022-01-25) applies a
# BOA_ADD_OFFSET of -1000 to reflectance DN. reflectance = (DN - 1000) * 1e-4
# = DN*1e-4 - 0.1. Used only when a scene's STAC item omits raster:bands.
_DEFAULT_SCALE = 0.0001
_DEFAULT_OFFSET = -0.1

# Server-side pre-filter cap: an optimization to avoid pulling back scenes that
# are unusable at any plausible threshold, while still letting the downstream
# quality filter reject-with-reason anything between the user's cloud_threshold
# and this cap. Not the same as the user's threshold — see search().
SEARCH_CLOUD_COVER_CAP = 80.0

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
        # Query a generous server-side cloud cap — not the user's exact
        # threshold — so scenes between cloud_threshold and the cap still come
        # back and get rejected *downstream* by app.services.quality_filter,
        # with an evidence-visible reason (§7.4, §11). Without this, a
        # STAC-side filter would silently drop those scenes and the evidence
        # panel could never explain why they were excluded.
        search_cap = max(cloud_threshold, SEARCH_CLOUD_COVER_CAP)
        search = self._stac().search(
            collections=[COLLECTION],
            bbox=list(aoi.bbox()),
            datetime=date_range.as_stac_datetime(),
            query={"eo:cloud_cover": {"lt": search_cap}},
            max_items=limit,
        )
        scenes: list[Scene] = []
        for item in search.items():
            assets: dict[str, DataAsset] = {}
            for key in self.supported_bands:
                asset = item.assets.get(key)
                if asset is None:
                    continue
                scale, offset = self._raster_bands_scale_offset(asset.extra_fields)
                assets[key] = DataAsset(
                    key=key, href=asset.href, scale=scale, offset=offset
                )
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
    def _raster_bands_scale_offset(
        extra_fields: dict,
    ) -> tuple[float | None, float | None]:
        """Extract (scale, offset) from a STAC asset's ``raster:bands`` field.

        Returns (None, None) when the field is absent so the caller can apply
        documented defaults instead of a silently wrong identity transform."""
        bands = extra_fields.get("raster:bands")
        if not bands:
            return None, None
        first = bands[0]
        scale = first.get("scale")
        offset = first.get("offset")
        return (
            float(scale) if scale is not None else None,
            float(offset) if offset is not None else None,
        )

    def read_window(
        self,
        scene: Scene,
        band_key: str,
        aoi: AOI,
        out_shape: tuple[int, int] | None = None,
    ) -> BandWindow:
        if band_key not in scene.assets:
            raise KeyError(f"scene {scene.id} has no asset '{band_key}'")
        asset = scene.assets[band_key]
        with rasterio.Env(**_GDAL_ENV):
            with rasterio.open(asset.href) as src:
                left, bottom, right, top = transform_bounds(
                    "EPSG:4326", src.crs, *aoi.bbox()
                )
                window = from_bounds(left, bottom, right, top, src.transform)
                if out_shape is not None:
                    # Categorical (SCL) or continuous data being aligned to a
                    # different band's grid: nearest-neighbor never invents an
                    # intermediate class code or reflectance value (§17).
                    arr = src.read(
                        1,
                        window=window,
                        out_shape=out_shape,
                        resampling=Resampling.nearest,
                    )
                else:
                    arr = src.read(1, window=window)

                if band_key == "scl":
                    # SCL is a classification raster: reflectance scaling is
                    # meaningless for it.
                    scale, offset = 1.0, 0.0
                elif asset.scale is not None and asset.offset is not None:
                    scale, offset = asset.scale, asset.offset
                else:
                    scale, offset = _DEFAULT_SCALE, _DEFAULT_OFFSET

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
