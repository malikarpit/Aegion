"""
Startup route uniqueness validator.

Called during FastAPI startup to ensure no duplicate method+path
registrations exist across the application's 56+ routers.
"""

from fastapi import FastAPI
from ..core.logging import logger


class DuplicateRouteError(RuntimeError):
    """Raised when two routers register the same method+path pair."""
    pass


def validate_route_uniqueness(app: FastAPI) -> None:
    """
    Scan all registered routes and raise on any duplicate method+path pair.

    Must be called AFTER all routers are included in the app.
    """
    seen: dict[tuple[str, str], str] = {}
    duplicates: list[str] = []

    for route in app.routes:
        if not hasattr(route, "methods") or not hasattr(route, "path"):
            continue  # skip Mount, WebSocket etc.

        for method in route.methods:
            key = (method, route.path)
            endpoint_name = getattr(route, "name", "unknown")

            if key in seen:
                msg = (
                    f"Duplicate route: {method} {route.path} "
                    f"('{endpoint_name}' collides with '{seen[key]}')"
                )
                duplicates.append(msg)
                logger.error(msg)
            else:
                seen[key] = endpoint_name

    if duplicates:
        raise DuplicateRouteError(
            f"{len(duplicates)} duplicate route(s) detected:\n"
            + "\n".join(f"  - {d}" for d in duplicates)
        )

    logger.info(f"Route uniqueness validated: {len(seen)} unique endpoints OK")
