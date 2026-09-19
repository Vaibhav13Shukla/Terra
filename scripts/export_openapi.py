"""Regenerate docs/openapi.json from the live FastAPI app definition.

Run this after any change to app/api/main.py, app/api/schemas.py, or the
domain model that affects the public API shape, so the committed spec never
drifts from the actual code (the frontend team builds against this file).

Usage:
    cd backend && ../.venv/Scripts/python ../scripts/export_openapi.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.api.main import app  # noqa: E402

OUT_PATH = Path(__file__).resolve().parent.parent / "docs" / "openapi.json"


def main() -> None:
    spec = app.openapi()
    OUT_PATH.write_text(json.dumps(spec, indent=2), encoding="utf-8")
    print(f"wrote {OUT_PATH} ({len(spec['paths'])} paths)")


if __name__ == "__main__":
    main()
