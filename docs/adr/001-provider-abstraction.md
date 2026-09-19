# ADR 001 — Provider abstraction (DataProvider + ProviderRegistry)

## Context

Terra's thesis (per the original MERU deck) is unifying access to Earth
Observation data. The hackathon MVP uses exactly one real data source
(Sentinel-2 L2A via Earth Search STAC), but the architecture must not
hard-code that fact throughout the codebase -- both to honestly reflect the
product thesis and because the deterministic core (app.services.analysis_engine)
must be testable without any network access.

## Decision

Define a single interface, `app.providers.base.DataProvider`:

```python
class DataProvider(abc.ABC):
    def search(self, aoi, date_range, cloud_threshold, limit=20) -> list[Scene]: ...
    def read_window(self, scene, band_key, aoi, out_shape=None) -> BandWindow: ...
```

`app.providers.base.ProviderRegistry` maps a string name (e.g.
`"sentinel-2-l2a"`, `"fixtures"`) to a `DataProvider` instance. `app.services.analysis_engine.run_analysis`
takes a `DataProvider` as a parameter -- it never imports a specific provider
module or branches on provider identity.

Two providers implement the interface today:

- `app.providers.sentinel2.Sentinel2Provider` -- real, production-capable,
  backed by Earth Search STAC + windowed COG reads.
- `app.providers.fixtures.FixturesProvider` -- deterministic, synthetic,
  in-memory scenes with exact, known NDVI values. Used by the entire
  integration/contract/e2e test suite and the reproducible demo path (§13),
  so none of that depends on network availability.

## Consequences

- Adding a second real provider (e.g. Landsat/HLS, mentioned as a possible
  P2 in the brief) means writing one new module implementing the same two
  methods -- no changes anywhere else.
- The quality filter, NDVI engine, and API layer are all provider-agnostic
  by construction, not by discipline someone has to remember to maintain.
- The trade-off: `BandWindow`'s `scale`/`offset`/`nodata` fields assume a
  raster-band model that fits COG-based optical imagery well but would need
  extension for e.g. SAR (mentioned in the original deck's long-term vision,
  explicitly out of scope for this MVP -- §79).
