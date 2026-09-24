from typing import Optional, Tuple

import httpx


DEFAULT_COORDINATES: Tuple[float, float] = (17.385044, 78.486671)
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"


def resolve_coordinates(
    street_name: Optional[str],
    lat: Optional[float],
    lng: Optional[float],
) -> Tuple[float, float]:
    """Resolve upload coordinates, falling back to Hyderabad when necessary."""
    if lat is not None and lng is not None:
        return float(lat), float(lng)

    query = street_name.strip() if street_name else ""
    if not query:
        return DEFAULT_COORDINATES

    try:
        response = httpx.get(
            NOMINATIM_URL,
            params={"q": query, "format": "json", "limit": 1},
            headers={"User-Agent": "RoadGuardApp/1.0"},
            timeout=5.0,
        )
        response.raise_for_status()
        results = response.json()
        if results:
            return float(results[0]["lat"]), float(results[0]["lon"])
    except Exception:
        pass

    return DEFAULT_COORDINATES
