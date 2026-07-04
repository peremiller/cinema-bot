"""Showtimes + ticket-buying links.

Two layers, designed to work in ANY country:

1. google_showtimes_link()  — always available. Builds a Google Showtimes
   deep-link scoped to the user's city. Google renders real nearby cinemas,
   timeslots, and "Book tickets" partners (Fandango, local chains, etc.) for
   essentially every country, so this is the universal buy-ticket path.

2. movieglu_showtimes()     — optional. If MovieGlu credentials are present,
   fetch exact per-cinema timeslots and print them inside the chat. Falls back
   silently to the Google link on any error.
"""
from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import quote_plus

import requests

import config
import geocode


def google_showtimes_link(title: str, city: str | None) -> str:
    """A Google search that surfaces showtimes + online booking partners."""
    q = f"{title} showtimes"
    if city:
        q += f" near {city}"
    return f"https://www.google.com/search?q={quote_plus(q)}"


# --------------------------------------------------------------------------
# MovieGlu (optional global showtimes API)
# --------------------------------------------------------------------------
def _movieglu_headers(lat: float, lon: float) -> dict:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    return {
        "client": config.MOVIEGLU_CLIENT,
        "x-api-key": config.MOVIEGLU_API_KEY,
        "authorization": config.MOVIEGLU_AUTHORIZATION,
        "territory": config.MOVIEGLU_TERRITORY,
        "api-version": config.MOVIEGLU_API_VERSION,
        "geolocation": f"{lat:.5f};{lon:.5f}",
        "device-datetime": now,
        "accept": "application/json",
    }


def _movieglu_get(path: str, params: dict, lat: float, lon: float) -> dict:
    url = f"{config.MOVIEGLU_API_BASE.rstrip('/')}/{path.lstrip('/')}"
    resp = requests.get(
        url, params=params, headers=_movieglu_headers(lat, lon), timeout=20
    )
    resp.raise_for_status()
    return resp.json()


def movieglu_showtimes(title: str, lat: float, lon: float, when: datetime | None = None):
    """Showtimes for `title` near (lat, lon), with distance to each cinema.

    Returns a list of dicts sorted nearest-first:
        {"name": str, "times": [HH:MM], "distance_km": float | None}
    or None if MovieGlu is disabled or anything fails (callers then fall back
    to the Google deep-link).
    """
    if not config.MOVIEGLU_ENABLED:
        return None
    when = when or datetime.now()
    date_str = when.strftime("%Y-%m-%d")
    try:
        # 1) Resolve the MovieGlu film id from the title.
        search = _movieglu_get("filmLiveSearch/", {"query": title}, lat, lon)
        films = search.get("films") or []
        if not films:
            return None
        film_id = films[0].get("film_id")
        if not film_id:
            return None

        # 2) Fetch showtimes for that film near the geolocation.
        data = _movieglu_get(
            "filmShowTimes/", {"film_id": film_id, "date": date_str}, lat, lon
        )
        cinemas = data.get("cinemas") or []
        out = []
        for c in cinemas:
            times = []
            showings = c.get("showings") or {}
            for _category, info in showings.items():
                for t in info.get("times", []):
                    if t.get("start_time"):
                        times.append(t["start_time"])
            if not times:
                continue

            # Prefer our own haversine from the cinema's coords (consistent km).
            distance_km = None
            c_lat, c_lon = c.get("lat"), c.get("lng")
            if c_lat is not None and c_lon is not None:
                distance_km = geocode.haversine_km(lat, lon, float(c_lat), float(c_lon))
            elif c.get("distance") is not None:
                # Fall back to MovieGlu's own distance (territory unit, ~miles).
                try:
                    distance_km = float(c["distance"]) * 1.60934
                except (TypeError, ValueError):
                    distance_km = None

            out.append(
                {
                    "name": c.get("cinema_name", "Cinema"),
                    "times": sorted(set(times)),
                    "distance_km": distance_km,
                }
            )

        # Nearest first; cinemas with unknown distance sink to the bottom.
        out.sort(key=lambda x: x["distance_km"] if x["distance_km"] is not None else 9e9)
        return out or None
    except Exception:
        return None
