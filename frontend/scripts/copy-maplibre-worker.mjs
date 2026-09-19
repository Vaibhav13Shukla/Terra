// MapLibre GL JS v6 runs its geometry work (GeoJSON sources — including the
// AOI overlay) in a web worker, and ships that worker as separate ES-module
// files. The main bundle finds the worker relative to its own `import.meta.url`,
// but once Next/Turbopack has bundled it into `/_next/static/chunks/…` that
// path points at a file that does not exist: the server answers with an HTML
// 404, the worker never starts, and every GeoJSON layer silently renders
// nothing ("Failed to load module script: … MIME type of text/html"). The
// raster basemap still works because it doesn't need the worker, which is
// what makes this failure so easy to miss.
//
// Fix: serve the worker (and the shared chunk it imports) from /public and
// point MapLibre at it with setWorkerUrl() (see components/AOIMap.tsx). They
// are copied from node_modules at predev/prebuild rather than committed, so the
// worker always matches the installed maplibre-gl version.
//
// The copies are minified third-party code that ESLint would otherwise scan
// (public/ is inside the project), producing ~1,100 meaningless warnings that
// bury real ones. Rather than loosen the shared ESLint config, each generated
// file gets an `eslint-disable` header — our own source stays fully linted.

import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const dist = join(root, "node_modules", "maplibre-gl", "dist");
const out = join(root, "public", "maplibre");

mkdirSync(out, { recursive: true });
for (const file of ["maplibre-gl-worker.mjs", "maplibre-gl-shared.mjs"]) {
  const source = readFileSync(join(dist, file), "utf8");
  writeFileSync(join(out, file), `/* eslint-disable */\n${source}`);
}
console.log(`[maplibre] copied worker files to ${out}`);
