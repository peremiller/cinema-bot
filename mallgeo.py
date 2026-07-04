"""Distance for ClickTheCity cinemas by geocoding their mall (name + city).

ClickTheCity doesn't expose cinema coordinates, and OpenStreetMap cinema names
in Metro Manila are too generic to match reliably. Geocoding the mall itself
(e.g. "Ayala Malls Manila Bay, Parañaque City, Philippines") gives an accurate
location. Results are cached to disk (hits AND misses) so it's a one-time cost
per mall, and live lookups are throttled to respect Nominatim's usage policy.
"""
from __future__ import annotations

import json
import os
import threading
import time

import config
import geocode

CACHE_PATH = os.path.join(config.DATA_DIR, "mall_coords.json")
# Committed seed (ships in the repo) so a fresh machine starts warm and the
# cinema list is nearest-first from the very first call.
SEED_PATH = os.path.join(os.path.dirname(__file__), "mall_coords.seed.json")
_MIN_INTERVAL = 1.1  # seconds between live geocodes (Nominatim politeness)

_lock = threading.Lock()
_last_call = [0.0]
_seed = None


def _load_seed() -> dict:
    global _seed
    if _seed is None:
        try:
            with open(SEED_PATH, "r", encoding="utf-8") as fh:
                _seed = json.load(fh)
        except (FileNotFoundError, json.JSONDecodeError):
            _seed = {}
    return _seed


def _load_runtime() -> dict:
    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _load() -> dict:
    """Merged view: committed seed as base, runtime cache wins on conflict."""
    return {**_load_seed(), **_load_runtime()}


def _save(data: dict) -> None:
    os.makedirs(config.DATA_DIR, exist_ok=True)
    tmp = CACHE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh)
    os.replace(tmp, CACHE_PATH)


def _cached(key: str):
    """Return (present, value) — value is [lat,lon] or None (a known miss)."""
    with _lock:
        cache = _load()
        return (key in cache), cache.get(key)


def _geocode_live(mall: str, city: str, key: str):
    query = ", ".join(x for x in [mall, city, "Philippines"] if x)
    wait = _MIN_INTERVAL - (time.monotonic() - _last_call[0])
    if wait > 0:
        time.sleep(wait)
    _last_call[0] = time.monotonic()
    try:
        loc = geocode.geocode(query)
        val = [loc["lat"], loc["lon"]]
    except Exception:
        val = None
    with _lock:
        rt = _load_runtime()
        rt[key] = val
        _save(rt)
    return val


def attach_distances(cinemas: list, lat: float, lon: float, max_new: int = 10) -> None:
    """Attach 'distance_km' to each cinema (in-place) via its geocoded mall.

    Cached malls are always resolved for free; up to `max_new` uncached malls are
    geocoded live this call (the rest fill in on later calls as the cache warms)."""
    new = 0
    for c in cinemas:
        name = c.get("mall") or c.get("name")
        key = f"{(name or '').strip()}|{(c.get('city') or '').strip()}".lower()
        present, val = _cached(key)
        if not present:
            if new >= max_new:
                continue
            val = _geocode_live(name, c.get("city", ""), key)
            new += 1
        if val:
            c["distance_km"] = geocode.haversine_km(lat, lon, val[0], val[1])
