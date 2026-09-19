"""Deterministic fixture provider (§13).

Lets the entire pipeline — discovery, quality filter, windowed read, NDVI,
comparison, evidence — run with no network and no AWS credentials, so tests and
the demo are reproducible. Fixture "reads" return synthetic reflectance arrays
with identity scale/offset, so NDVI is an exact, known function of the inputs.

This is clearly labelled fixture data; it is never presented as live imagery.
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field

import numpy as np

from app.domain.models import AOI, DataAsset, DateRange, Scene
from app.providers.base import BandWindow, DataProvider

# SCL vegetation class — every fixture pixel is "valid vegetation" unless a
# scenario overrides the scl array.
_SCL_VEG = 4


@dataclass
class FixtureScene:
    """A synthetic scene with in-memory band arrays (reflectance, 0..1)."""

    id: str
    datetime: _dt.datetime
    cloud_cover: float
    red: np.ndarray
    nir: np.ndarray
    scl: np.ndarray = field(default=None)  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.scl is None:
            self.scl = np.full(self.red.shape, _SCL_VEG, dtype=np.uint8)


class FixturesProvider(DataProvider):
    name = "fixtures"
    supported_bands = ("red", "nir", "scl")

    def __init__(self, scenes: list[FixtureScene] | None = None) -> None:
        self._scenes: dict[str, FixtureScene] = {}
        for sc in scenes or []:
            self._scenes[sc.id] = sc

    def add(self, scene: FixtureScene) -> None:
        self._scenes[scene.id] = scene

    def search(
        self,
        aoi: AOI,
        date_range: DateRange,
        cloud_threshold: float,
        limit: int = 20,
    ) -> list[Scene]:
        out: list[Scene] = []
        for fx in self._scenes.values():
            d = fx.datetime.date()
            if not (date_range.start <= d <= date_range.end):
                continue
            if fx.cloud_cover >= cloud_threshold:
                # mirror server-side pre-filter; authoritative filter is downstream
                continue
            assets = {
                b: DataAsset(key=b, href=f"fixture://{fx.id}/{b}")
                for b in self.supported_bands
            }
            out.append(
                Scene(
                    id=fx.id,
                    provider=self.name,
                    datetime=fx.datetime,
                    cloud_cover=fx.cloud_cover,
                    assets=assets,
                )
            )
            if len(out) >= limit:
                break
        return out

    def read_window(self, scene: Scene, band_key: str, aoi: AOI) -> BandWindow:
        fx = self._scenes.get(scene.id)
        if fx is None:
            raise KeyError(f"unknown fixture scene '{scene.id}'")
        band = {"red": fx.red, "nir": fx.nir, "scl": fx.scl}.get(band_key)
        if band is None:
            raise KeyError(f"fixture scene '{scene.id}' has no band '{band_key}'")
        return BandWindow(
            array=band,
            scale=1.0,
            offset=0.0,
            nodata=None,
            crs="EPSG:4326",
            band_key=band_key,
        )


def _uniform_scene(
    scene_id: str,
    when: _dt.date,
    cloud: float,
    ndvi_target: float,
    shape: tuple[int, int] = (16, 16),
) -> FixtureScene:
    """Build a scene whose every pixel has exactly ``ndvi_target``.

    Choose red so that for a fixed nir, (nir-red)/(nir+red) == ndvi_target:
        red = nir * (1 - t) / (1 + t)
    """
    nir_val = 0.4
    red_val = nir_val * (1.0 - ndvi_target) / (1.0 + ndvi_target)
    red = np.full(shape, red_val, dtype=np.float32)
    nir = np.full(shape, nir_val, dtype=np.float32)
    return FixtureScene(
        id=scene_id,
        datetime=_dt.datetime(when.year, when.month, when.day, 10, 0, 0, tzinfo=_dt.UTC),
        cloud_cover=cloud,
        red=red,
        nir=nir,
    )


def demo_decline_provider() -> FixturesProvider:
    """A reproducible 'vegetation decline' scenario used by the demo/e2e.

    Comparison period (July) mean NDVI ~0.50; current period (August) ~0.41,
    i.e. an ~18% decrease — matching the canonical Terra example. Includes a
    high-cloud scene in each period that the quality filter must reject."""
    scenes = [
        # comparison period (July 2025): NDVI ~0.50
        _uniform_scene("fx-jul-01", _dt.date(2025, 7, 5), cloud=6.0, ndvi_target=0.50),
        _uniform_scene("fx-jul-02", _dt.date(2025, 7, 17), cloud=9.0, ndvi_target=0.50),
        _uniform_scene("fx-jul-cloudy", _dt.date(2025, 7, 22), cloud=72.0, ndvi_target=0.10),
        # current period (August 2025): NDVI ~0.41
        _uniform_scene("fx-aug-01", _dt.date(2025, 8, 6), cloud=4.0, ndvi_target=0.41),
        _uniform_scene("fx-aug-02", _dt.date(2025, 8, 18), cloud=8.0, ndvi_target=0.41),
        _uniform_scene("fx-aug-cloudy", _dt.date(2025, 8, 25), cloud=80.0, ndvi_target=0.05),
    ]
    return FixturesProvider(scenes)
