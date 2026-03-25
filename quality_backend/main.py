"""
Entrypoint for running the Quality Defect Tracking FastAPI backend.

The preview environment sometimes launches the app with the system Python instead of the
project's virtualenv, which can cause import errors (e.g., `ModuleNotFoundError: fastapi`)
and prevent the container from binding to the expected port.

This script:
- Adds the project root to sys.path so `src.api.main:app` can be imported.
- If a local `./venv` exists, adds its site-packages to sys.path as a fallback.
- Reads HOST/PORT from environment (defaults: 0.0.0.0 / 3001).
- Runs uvicorn to serve the FastAPI `app`.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _maybe_add_venv_site_packages(project_root: Path) -> None:
    """
    Add venv site-packages to sys.path if present.

    This is a best-effort fallback for environments that do not activate the venv
    before launching the service.
    """
    py_ver = f"python{sys.version_info.major}.{sys.version_info.minor}"
    candidate = project_root / "venv" / "lib" / py_ver / "site-packages"
    if candidate.exists() and candidate.is_dir():
        sys.path.insert(0, str(candidate))


# PUBLIC_INTERFACE
def main() -> None:
    """Run the FastAPI backend with uvicorn using HOST/PORT env vars."""
    project_root = Path(__file__).resolve().parent
    sys.path.insert(0, str(project_root))
    _maybe_add_venv_site_packages(project_root)

    host = os.getenv("UVICORN_HOST") or os.getenv("HOST") or "0.0.0.0"
    port_raw = os.getenv("PORT") or "3001"
    try:
        port = int(port_raw)
    except ValueError:
        port = 3001

    # Import after sys.path adjustments
    import uvicorn  # type: ignore

    uvicorn.run(
        "src.api.main:app",
        host=host,
        port=port,
        log_level=os.getenv("LOG_LEVEL", "info"),
    )


if __name__ == "__main__":
    main()
