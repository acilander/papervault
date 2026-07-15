import re
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def vite_proxies():
    """Return the set of proxy paths configured in vite.config.ts."""
    vite_config = (ROOT / "frontend" / "vite.config.ts").read_text()
    match = re.search(r"proxy:\s*\{(.*?)\}", vite_config, re.DOTALL)
    assert match, "No proxy block found in vite.config.ts"
    return set(re.findall(r"['\"](/[a-z]+)['\"]\s*:", match.group(1)))


def _collect_routes(route, prefix=""):
    """Recursively collect all API route paths from FastAPI app."""
    from fastapi.routing import APIRoute
    routes = set()
    if isinstance(route, APIRoute):
        full_path = prefix + route.path
        if full_path.startswith("/"):
            routes.add(full_path)
    elif hasattr(route, "routes"):
        sub_prefix = prefix + getattr(route, "path", "")
        for r in route.routes:
            routes.update(_collect_routes(r, sub_prefix))
    return routes


@pytest.fixture
def backend_routes():
    """Return the API routes registered in the backend app."""
    import sys
    sys.path.insert(0, str(ROOT / "backend"))
    import api.main as main
    routes = set()
    for route in main.app.routes:
        routes.update(_collect_routes(route))
    return routes


def test_all_api_routes_are_proxied(vite_proxies, backend_routes):
    """Ensure every backend route is reachable through the Vite dev proxy.

    This would have caught the missing /chat proxy that caused the
    'Fehler bei der Anfrage. Ist der Server erreichbar?' error.
    """
    skip = {"/", "/favicon.ico", "/docs", "/docs/oauth2-redirect", "/redoc", "/openapi.json", "/{path:path}"}
    missing = set()
    for route in backend_routes:
        if route in skip:
            continue
        if not any(route.startswith(p) for p in vite_proxies):
            missing.add(route)
    assert not missing, f"Routes not proxied in vite.config.ts: {missing}"
