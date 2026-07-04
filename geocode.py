"""Free, global geocoding via OpenStreetMap Nominatim.

Turns a free-text place ("Cebu City, Philippines") into coordinates plus an
ISO 3166-1 alpha-2 country code, which TMDB uses to scope "now playing".
Also reverse-geocodes a shared GPS location and computes great-circle distance.
"""
from math import asin, cos, radians, sin, sqrt

import requests

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"
# Nominatim's usage policy requires an identifying User-Agent.
USER_AGENT = "cinema-bot/1.0 (personal movie showtimes assistant)"


class GeocodeError(Exception):
    pass


def geocode(query: str) -> dict:
    """Resolve a place string to a location dict.

    Returns: {city, display_name, lat, lon, country, country_code}
    Raises GeocodeError if nothing is found.
    """
    query = (query or "").strip()
    if not query:
        raise GeocodeError("Please provide a place, e.g. 'Manila, Philippines'.")

    resp = requests.get(
        NOMINATIM_URL,
        params={
            "q": query,
            "format": "jsonv2",
            "limit": 1,
            "addressdetails": 1,
        },
        headers={"User-Agent": USER_AGENT},
        timeout=15,
    )
    resp.raise_for_status()
    results = resp.json()
    if not results:
        raise GeocodeError(f"Couldn't find a place matching '{query}'.")

    top = results[0]
    address = top.get("address", {})
    city = (
        address.get("city")
        or address.get("town")
        or address.get("village")
        or address.get("municipality")
        or address.get("state")
        or query
    )
    country_code = (address.get("country_code") or "").upper()
    return {
        "city": city,
        "display_name": top.get("display_name", query),
        "lat": float(top["lat"]),
        "lon": float(top["lon"]),
        "country": address.get("country", ""),
        "country_code": country_code,
    }


def reverse(lat: float, lon: float) -> dict:
    """Turn a shared GPS point into the same location dict shape as geocode()."""
    resp = requests.get(
        NOMINATIM_REVERSE_URL,
        params={"lat": lat, "lon": lon, "format": "jsonv2", "addressdetails": 1},
        headers={"User-Agent": USER_AGENT},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    address = data.get("address", {})
    city = (
        address.get("city")
        or address.get("town")
        or address.get("village")
        or address.get("municipality")
        or address.get("state")
        or "Your location"
    )
    return {
        "city": city,
        "display_name": data.get("display_name", city),
        "lat": float(lat),
        "lon": float(lon),
        "country": address.get("country", ""),
        "country_code": (address.get("country_code") or "").upper(),
    }


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points, in kilometers."""
    r = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = (
        sin(dlat / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    )
    return 2 * r * asin(sqrt(a))
