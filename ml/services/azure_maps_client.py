"""Azure Maps Route Matrix 2025-01-01 client.

Replaces the haversine-based time matrix in RouteOptimizer with real road
travel times for walk and drive modes. bike/transit are not supported by the
API and always fall back to haversine in the caller.
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import time
from datetime import datetime

import httpx
from cachetools import TTLCache

logger = logging.getLogger(__name__)


# ── exceptions ────────────────────────────────────────────────────────────────

class AzureMapsError(Exception):
    pass


class UnsupportedTravelModeError(AzureMapsError):
    pass


# ── constants ─────────────────────────────────────────────────────────────────

_BASE_URL = "https://atlas.microsoft.com/route/matrix"
_API_VER = "2025-01-01"
_TIMEOUT = httpx.Timeout(connect=30.0, read=90.0, write=30.0, pool=30.0)

# Modes supported by Azure Maps Route Matrix 2025-01-01.
PLANIT_TO_AZURE: dict[str, str] = {
    "walk":  "walking",
    "drive": "driving",
}

# Duplicated from route_optimizer to avoid a circular import.
_TRAVEL_SPEED_KMH: dict[str, float] = {
    "walk":    4.5,
    "bike":   15.0,
    "transit": 25.0,
    "drive":   30.0,
}

# Module-level TTL cache. TTL read from env at import time.
_CACHE: TTLCache = TTLCache(
    maxsize=128,
    ttl=int(os.getenv("AZURE_MATRIX_CACHE_TTL_SECONDS", "3600")),
)


# ── public interface ──────────────────────────────────────────────────────────

def build_time_matrix(
    coords: list[tuple[float, float]],
    travel_mode: str,
    depart_at: datetime | None = None,
) -> list[list[int]]:
    """Return an n×n travel-time matrix in integer minutes.

    coords      (lat, lon) pairs in PlanIt order; index 0 is the VRPTW depot.
    travel_mode PlanIt mode — walk, drive, bike, or transit.
    depart_at   optional departure datetime; respected only for driving ≤2500 cells.

    Returns list[list[int]]: diagonal=0, all other cells max(1, round(minutes)).
    Raises UnsupportedTravelModeError for bike/transit.
    Raises AzureMapsError on auth, network, or parse failures.
    """
    _validate_coords(coords)

    azure_mode = PLANIT_TO_AZURE.get(travel_mode)
    if azure_mode is None:
        raise UnsupportedTravelModeError(
            f"{travel_mode!r} is not supported by Azure Maps Route Matrix 2025-01-01 "
            f"(supported PlanIt modes: walk, drive)."
        )

    api_key = os.getenv("AZURE_MAPS_KEY", "")
    if not api_key:
        raise AzureMapsError("AZURE_MAPS_KEY not set")

    cache_key = _make_cache_key(coords, travel_mode, depart_at)
    if cache_key in _CACHE:
        logger.info(
            "azure_maps_matrix cache_hit=True matrix_size_cells=%d "
            "planit_travel_mode=%s transactions_billed=0",
            len(coords) ** 2, travel_mode,
        )
        return _CACHE[cache_key]

    n = len(coords)
    cells = n * n

    # Sync vs async routing and traffic constraint per API spec size tiers.
    force_historical = False
    use_async = False
    if azure_mode == "walking" and cells > 200:
        use_async = True
    elif azure_mode == "driving" and cells > 2500:
        use_async = True
    elif azure_mode == "driving" and 100 < cells <= 2500:
        force_historical = True

    effective_depart = None if force_historical else depart_at
    body = _build_request_body(coords, azure_mode, effective_depart)

    t0 = time.monotonic()
    if use_async:
        response_json = _post_async_and_poll(body, api_key)
        endpoint_type = "async"
    else:
        response_json = _post_sync(body, api_key)
        endpoint_type = "sync"
    duration_ms = round((time.monotonic() - t0) * 1000)

    matrix, failed_cells = _parse_response(
        response_json, n, coords, travel_mode)
    transactions_billed = math.ceil(cells / 4)

    logger.info(
        "azure_maps_matrix cache_hit=False matrix_size_cells=%d planit_travel_mode=%s "
        "azure_travel_mode=%s sync_or_async=%s duration_ms=%d "
        "transactions_billed=%d failed_cells_count=%d",
        cells, travel_mode, azure_mode, endpoint_type,
        duration_ms, transactions_billed, failed_cells,
    )

    _CACHE[cache_key] = matrix
    return matrix


# ── internal helpers ──────────────────────────────────────────────────────────

def _validate_coords(coords: list[tuple[float, float]]) -> None:
    for i, (lat, lon) in enumerate(coords):
        if not math.isfinite(lat) or not math.isfinite(lon):
            raise AzureMapsError(
                f"Non-finite coordinate at index {i}: ({lat}, {lon})"
            )
        if not -90.0 <= lat <= 90.0:
            raise AzureMapsError(
                f"Latitude {lat} out of range [-90, 90] at index {i}"
            )
        if not -180.0 <= lon <= 180.0:
            raise AzureMapsError(
                f"Longitude {lon} out of range [-180, 180] at index {i}"
            )


def _make_cache_key(
    coords: list[tuple[float, float]],
    travel_mode: str,
    depart_at: datetime | None,
) -> str:
    depart_str = depart_at.date().isoformat() if depart_at else None
    payload = json.dumps(
        {"coords": [list(c) for c in coords],
         "mode": travel_mode, "depart": depart_str},
        sort_keys=True,
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def _build_request_body(
    coords: list[tuple[float, float]],
    azure_mode: str,
    depart_at: datetime | None,
) -> dict:
    geo_coords = [[lon, lat]
                  for lat, lon in coords]  # GeoJSON order: [lon, lat]
    body: dict = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "MultiPoint", "coordinates": geo_coords},
                "properties": {"pointType": "origins"},
            },
            {
                "type": "Feature",
                "geometry": {"type": "MultiPoint", "coordinates": geo_coords},
                "properties": {"pointType": "destinations"},
            },
        ],
        "travelMode": azure_mode,
        "optimizeRoute": "fastest",
        "traffic": "historical",
    }
    if depart_at is not None:
        body["departAt"] = depart_at.isoformat()
    return body


def _post_sync(body: dict, api_key: str) -> dict:
    resp = httpx.post(
        _BASE_URL,
        params={"api-version": _API_VER, "subscription-key": api_key},
        json=body,
        headers={"Content-Type": "application/geo+json"},
        timeout=_TIMEOUT,
    )
    _raise_for_status(resp)
    return resp.json()


def _post_async_and_poll(body: dict, api_key: str) -> dict:
    resp = httpx.post(
        f"{_BASE_URL}:async",
        params={"api-version": _API_VER, "subscription-key": api_key},
        json=body,
        headers={"Content-Type": "application/geo+json"},
        timeout=_TIMEOUT,
    )
    if resp.status_code != 202:
        _raise_for_status(resp)

    operation_url = resp.headers.get("operation-location")
    if not operation_url:
        raise AzureMapsError(
            "Async 202 response missing operation-location header")

    delay = 1.0
    deadline = time.monotonic() + 60.0
    attempt = 0

    while time.monotonic() < deadline:
        attempt += 1
        time.sleep(delay)
        delay = min(delay * 2, 5.0)

        poll = httpx.get(
            operation_url,
            params={"subscription-key": api_key},
            timeout=_TIMEOUT,
        )
        poll.raise_for_status()
        status_body = poll.json()
        status = status_body.get("status", "")
        logger.info("azure_maps_async poll attempt=%d status=%s",
                    attempt, status)

        if status == "Succeeded":
            logger.debug("polling response body on Succeeded: %s", json.dumps(status_body))

            result_url = status_body.get("resultUrl")
            if not result_url:
                from urllib.parse import urlparse, urlunparse
                parsed = urlparse(operation_url)
                new_path = parsed.path.rstrip("/") + "/result"
                result_url = str(urlunparse(parsed._replace(path=new_path, query="")))
                logger.warning(
                    "resultUrl missing from polling response body, "
                    "constructed from operation URL: %s", result_url,
                )

            result = httpx.get(
                result_url,
                params={"api-version": _API_VER, "subscription-key": api_key},
                timeout=_TIMEOUT,
            )
            if result.status_code != 200:
                raise AzureMapsError(
                    f"Failed to fetch async result (HTTP {result.status_code}): "
                    f"{result.text[:200]}"
                )
            return result.json()

        if status in ("Failed", "Canceled"):
            raise AzureMapsError(
                f"Azure Maps async operation {status}: {status_body}"
            )

    raise AzureMapsError("Azure Maps async operation timed out after 60 s")


def _parse_response(
    response_json: dict,
    n: int,
    coords: list[tuple[float, float]],
    travel_mode: str,
) -> tuple[list[list[int]], int]:
    matrix: list[list[int]] = [[0] * n for _ in range(n)]
    failed_cells = 0

    # uses originIndex/destinationIndex.
    for cell in response_json.get("properties", {}).get("matrix", []):
        i = cell["originIndex"]
        j = cell["destinationIndex"]

        if i == j:
            matrix[i][j] = 0
            continue

        if cell.get("statusCode") == 200:
            matrix[i][j] = max(1, round(cell.get("durationInSeconds", 0) / 60))
        else:
            failed_cells += 1
            logger.warning(
                "azure_maps cell failure originIndex=%d destinationIndex=%d "
                "statusCode=%s coord_a=%s coord_b=%s — haversine fill",
                i, j, cell.get("statusCode"), coords[i], coords[j],
            )
            matrix[i][j] = _haversine_minutes(
                coords[i], coords[j], travel_mode)

    return matrix, failed_cells


def _haversine_minutes(
    coord_a: tuple[float, float],
    coord_b: tuple[float, float],
    travel_mode: str,
) -> int:
    """Haversine travel time in integer minutes. Mirrors route_optimizer._travel_minutes()."""
    lat1, lon1 = coord_a
    lat2, lon2 = coord_b
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    dist_km = R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    speed = _TRAVEL_SPEED_KMH.get(travel_mode, 25.0)
    return max(1, round((dist_km / speed) * 60))


def _raise_for_status(resp: httpx.Response) -> None:
    sc = resp.status_code
    if sc < 400:
        return
    if sc in (401, 403):
        raise AzureMapsError(f"auth failed (HTTP {sc})")
    if sc == 429:
        raise AzureMapsError("rate limited (HTTP 429)")
    if sc >= 500:
        raise AzureMapsError(f"upstream error (HTTP {sc}): {resp.text[:200]}")
    raise AzureMapsError(f"bad request (HTTP {sc}): {resp.text[:200]}")
