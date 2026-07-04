"""Find real cinemas near a point — free, global, no API key.

Uses the OpenStreetMap Overpass API to list nearby `amenity=cinema` venues
with their coordinates, so we can show the distance from the user's current
location and a booking/showtimes link — in any country, with no signup.
(Overpass gives cinema *locations*, not schedules; for exact per-film timeslots
the optional MovieGlu path is used instead.)
"""
from __future__ import annotations

from urllib.parse import quote_plus

import requests

import geocode

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
USER_AGENT = "cinema-bot/1.0 (personal movie showtimes assistant)"


def _query(lat: float, lon: float, radius_m: int) -> str:
    return f"""
    [out:json][timeout:25];
    (
      node["amenity"="cinema"](around:{radius_m},{lat},{lon});
      way["amenity"="cinema"](around:{radius_m},{lat},{lon});
      relation["amenity"="cinema"](around:{radius_m},{lat},{lon});
    );
    out center tags;
    """


def nearby_cinemas(lat: float, lon: float, radius_km: float = 15, limit: int = 8) -> list[dict]:
    """Cinemas near (lat, lon), nearest-first.

    Each item: {name, lat, lon, distance_km, website, brand}.
    Automatically widens the search radius if nothing is found nearby.
    """
    radii = [radius_km, radius_km * 2, radius_km * 4]
    elements = []
    for r in radii:
        resp = requests.post(
            OVERPASS_URL,
            data={"data": _query(lat, lon, int(r * 1000))},
            headers={"User-Agent": USER_AGENT},
            timeout=40,
        )
        resp.raise_for_status()
        elements = resp.json().get("elements", [])
        if elements:
            break

    out = []
    seen = set()
    for el in elements:
        tags = el.get("tags", {})
        name = tags.get("name") or tags.get("brand")
        if not name:
            continue
        c_lat = el.get("lat") or (el.get("center") or {}).get("lat")
        c_lon = el.get("lon") or (el.get("center") or {}).get("lon")
        if c_lat is None or c_lon is None:
            continue
        key = name.lower().strip()
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "name": name,
                "lat": float(c_lat),
                "lon": float(c_lon),
                "distance_km": geocode.haversine_km(lat, lon, float(c_lat), float(c_lon)),
                "website": tags.get("website") or tags.get("contact:website"),
                "brand": tags.get("brand"),
            }
        )

    out.sort(key=lambda x: x["distance_km"])
    return out[:limit]


def cinema_link(cinema: dict) -> str:
    """Best link for a cinema: its own site if known, else a Google search
    that surfaces that cinema's showtimes + online booking."""
    if cinema.get("website"):
        return cinema["website"]
    return f"https://www.google.com/search?q={quote_plus(cinema['name'] + ' showtimes tickets')}"
