# Terra — Risk Register (§98)

| # | Risk | Probability | Impact | Mitigation | Status |
|---|---|---|---|---|---|
| 1 | Live EO API/network unavailable during demo | Medium | High | `FixturesProvider` gives a fully offline, deterministic demo path; default test suite never touches the network | Mitigated |
| 2 | Lambda package size (GDAL/rasterio) | High | High | Container-image Lambda from the start (`infra/Dockerfile`) | Resolved |
| 3 | Request latency exceeds API Gateway's 29s timeout | Medium | High | Scene cap (4/period) + concurrent reads: 116s to 18.6s measured on the canonical demo request, live-verified. Still close to the limit under slow network — see ADR 002 | Mitigated, not eliminated |
| 4 | No AWS credentials in the dev environment | Certain | Medium | Bedrock/DynamoDB/S3 code paths either optional-with-fallback (Bedrock) or documented-but-not-built (DynamoDB job store, S3 evidence store) rather than shipped untested (§57) | Accepted, documented |
| 5 | Wrong reflectance scale/offset (silent) | Occurred, found via live test | High — invalidates every NDVI value | Found and fixed during development: GDAL band tags report (1,0) even when STAC `raster:bands` has the real (0.0001,-0.1); now read from STAC metadata; regression-tested both offline and live | Resolved |
| 6 | SCL/red-nir resolution mismatch (silent) | Occurred, found via live test | High — would crash every live analysis | Found and fixed during development: SCL is natively 20m vs red/nir's 10m; `read_window`'s `out_shape` param aligns them via nearest-neighbor; regression-tested both offline and live | Resolved |
| 7 | Scientific overclaiming in UI/explanation copy | Low | High — credibility | Every result carries a standing NDVI-is-a-proxy limitation (§20); explainer only ever references values already on the result | Mitigated |
| 8 | Demo AOI has poor real coverage | Medium | Medium | Verified live: central California farmland AOI has 17-20 low-cloud scenes/period across Jun-Sep 2025 | Verified |
| 9 | Frontend integration surprises (team builds separately) | Medium | Medium | OpenAPI schema auto-generated at `/docs`; API contract pinned by 13 contract tests | Mitigated |
| 10 | AWS deployment untested end-to-end | High | Medium | IaC written and YAML-validated; deploy steps documented exactly; explicitly not claimed as done (§66) | Accepted, documented |

Highest-probability, highest-impact items (3, 4, 10) all trace back to the
same root cause — no AWS credentials available during development — and are
handled the same way throughout: build the real thing where it is testable,
document precisely what is not, and never claim a checkbox that was not
actually run.
