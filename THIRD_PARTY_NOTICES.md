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
| boto3 | Apache-2.0 | AWS SDK |

Full dependency versions are pinned in `backend/requirements.txt`.
Terra itself is released under the MIT License (see `LICENSE`).
