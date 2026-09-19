"""Data-provider abstraction (§12).

The analysis engine talks only to :class:`DataProvider`; it never knows whether
data came from Earth Search, a fixture, or a future Landsat/HLS adapter. New
providers register themselves in :class:`ProviderRegistry` and become usable
without touching the engine.
"""
from __future__ import annotations

import abc
from dataclasses import dataclass

import numpy as np

from app.domain.models import AOI, DateRange, Scene


@dataclass(frozen=True)
class BandWindow:
    """A windowed read of one band over an AOI.

    ``array`` holds raw DN (integer) values as read; ``scale``/``offset`` are the
    reflectance conversion factors the provider extracted from scene metadata so
    the processing layer can convert to reflectance deterministically.
    ``nodata`` is the sentinel value in the source, if any.
    """

    array: np.ndarray
    scale: float
    offset: float
    nodata: float | None
    crs: str
    band_key: str


class DataProvider(abc.ABC):
    """Interface every EO data source must implement."""

    #: stable identifier used in requests and the registry
    name: str = "abstract"

    #: logical band keys this provider can supply
    supported_bands: tuple[str, ...] = ()

    @abc.abstractmethod
    def search(
        self,
        aoi: AOI,
        date_range: DateRange,
        cloud_threshold: float,
        limit: int = 20,
    ) -> list[Scene]:
        """Return candidate scenes intersecting ``aoi`` within ``date_range``.

        Implementations should pre-filter on cloud cover where the source
        supports it, but the authoritative quality filter runs downstream."""

    @abc.abstractmethod
    def read_window(
        self,
        scene: Scene,
        band_key: str,
        aoi: AOI,
        out_shape: tuple[int, int] | None = None,
    ) -> BandWindow:
        """Windowed read of ``band_key`` for ``scene`` clipped to ``aoi``.

        Must read only the AOI window, never the whole scene (§18).

        ``out_shape``, when given, requests the array be returned at that
        exact (rows, cols) shape via nearest-neighbor resampling — used to
        align a lower-resolution band (e.g. Sentinel-2's 20 m SCL) onto a
        higher-resolution band's grid (e.g. 10 m red/nir) so they can be
        combined pixel-for-pixel. Nearest-neighbor is mandatory for
        categorical data (never interpolate class codes); providers should use
        it unconditionally here since this method has no way to know whether
        ``band_key`` is categorical or continuous."""


class ProviderRegistry:
    """Process-wide registry of available providers, keyed by ``name``."""

    _providers: dict[str, DataProvider] = {}

    @classmethod
    def register(cls, provider: DataProvider) -> None:
        cls._providers[provider.name] = provider

    @classmethod
    def get(cls, name: str) -> DataProvider:
        try:
            return cls._providers[name]
        except KeyError as exc:
            available = ", ".join(sorted(cls._providers)) or "(none)"
            raise KeyError(
                f"unknown provider '{name}'; registered: {available}"
            ) from exc

    @classmethod
    def names(cls) -> list[str]:
        return sorted(cls._providers)

    @classmethod
    def clear(cls) -> None:  # pragma: no cover - test helper
        cls._providers.clear()
