# Third-Party Notices & Data Attribution

Terra uses the following third-party data and software. All are used under
compatible open licenses.

## Data

### Sentinel-2 Level-2A (Copernicus / ESA)
- Source: [Sentinel-2 L2A Cloud-Optimized GeoTIFFs, AWS Registry of Open Data](https://registry.opendata.aws/sentinel-2-l2a-cogs/)
- Discovery: [Earth Search v1 STAC API](https://earth-search.aws.element84.com/v1) (Element 84)
- Produced by the European Union's Copernicus Programme. Contains modified
  Copernicus Sentinel data. Free and open under the Copernicus data policy.
- Terra reads only the area-of-interest window of each scene; it does not
  redistribute imagery.

## Software (key runtime dependencies)

| Library | License | Purpose |
|---|---|---|
| rasterio / GDAL | BSD-3 / MIT-X11 | windowed COG raster reads |
| pystac-client | Apache-2.0 | STAC catalog discovery |
| shapely | BSD-3 | geometry validation |
| numpy | BSD-3 | array math (NDVI) |
| FastAPI | MIT | HTTP API |
| pydantic | MIT | typed domain model / validation |
| mangum | ISC | ASGI-to-Lambda adapter |
| python-jose | MIT | verifies Cognito JWTs against the pool's JWKS |
| boto3 | Apache-2.0 | AWS SDK — not listed in `requirements.txt` (imported lazily; the Lambda base image provides it) |

Full dependency versions are pinned in `backend/requirements.txt`.
Terra itself is released under the MIT License (see `LICENSE`).

## Frontend (`frontend/`)

### Basemap imagery — Sentinel-2 cloudless (EOX)

The workspace map's basemap is the **Sentinel-2 cloudless 2020** mosaic served
by EOX IT Services GmbH (<https://s2maps.eu>): *contains modified Copernicus
Sentinel data 2020*, licensed
[CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/).
**Non-commercial.** Attribution is rendered on the map (see
`frontend/components/AOIMap.tsx`). This is acceptable for the hackathon build;
swap in a commercially licensed basemap (MapTiler, Mapbox, …) before any
commercial launch. Tiles are streamed from EOX, not stored or redistributed.

### Software (key dependencies; see `frontend/package.json` for versions)

| Library | License | Purpose |
|---|---|---|
| Next.js / React | MIT | app framework / UI |
| MapLibre GL JS | BSD-3-Clause | map rendering (also served from `public/maplibre/`, copied at build) |
| Tailwind CSS | MIT | styling |
| Framer Motion | MIT | animation |
| three.js, React Three Fiber, drei | MIT | landing-page 3D globe |
| amazon-cognito-identity-js | Apache-2.0 | Cognito sign-in (SRP) |
| zustand | MIT | client state |
| clsx | MIT | class-name helper |
