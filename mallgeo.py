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
    """Merged view: committed seed as base + runtime cache. A runtime value wins
    UNLESS it's a null (a past failed geocode) that would clobber a good seed."""
    merged = dict(_load_seed())
    for k, v in _load_runtime().items():
        if v is not None or k not in merged:
            merged[k] = v
    return merged


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


def _geocode_query(query: str, key: str):
    """Geocode `query`, cache the result (hit or miss) under `key`, throttled."""
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


def _mall_coords(mall: str, city: str, allow_live: bool):
    key = f"{(mall or '').strip()}|{(city or '').strip()}".lower()
    present, val = _cached(key)
    if present:
        return tuple(val) if val else None, False
    if allow_live:
        v = _geocode_query(", ".join(x for x in [mall, city, "Philippines"] if x), key)
        return (tuple(v) if v else None), True
    return None, False


def _city_coords(city: str):
    """City-level coordinates — the fallback so every cinema gets a distance.
    Cities almost always geocode, so this closes the 'no distance shown' gap."""
    city = (city or "").strip()
    if not city:
        return None
    key = f"__city__|{city.lower()}"
    present, val = _cached(key)
    if present:
        return tuple(val) if val else None
    v = _geocode_query(f"{city}, Philippines", key)
    return tuple(v) if v else None


def attach_distances(cinemas: list, lat: float, lon: float, max_new: int = 40) -> None:
    """Attach 'distance_km' to EVERY cinema (in-place).

    Resolve each cinema's mall (seed/cache first, then a throttled live lookup,
    up to `max_new` new ones). If the exact mall can't be geocoded, fall back to
    the city's coordinates and mark the distance approximate (`approx=True`)."""
    new = 0
    for c in cinemas:
        mall = c.get("mall") or c.get("name")
        coords, did_live = _mall_coords(mall, c.get("city", ""), allow_live=(new < max_new))
        if did_live:
            new += 1
        approx = False
        if coords is None:
            coords = _city_coords(c.get("city", ""))
            approx = coords is not None
        if coords:
            c["distance_km"] = geocode.haversine_km(lat, lon, coords[0], coords[1])
            c["approx"] = approx
