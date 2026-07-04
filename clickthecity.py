"""ClickTheCity API client — the accurate source of what's actually showing
in Philippine cinemas (TMDB's regional 'now playing' is unreliable for PH).

Public JSON API used by clickthecity.com's own frontend:
  /api/movies/now-showing          -> films currently in PH cinemas
  /api/movies/{id}/showtimes       -> theaters + timeslots for a film
Each now-showing item already carries synopsis, runtime, genre, poster,
trailer and a real buy-ticket page, so no TMDB enrichment is needed for PH.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import requests

BASE = "https://www.clickthecity.com/api"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "application/json",
    "Origin": "https://www.clickthecity.com",
    "Referer": "https://www.clickthecity.com/",
}


def _get(path: str, params: dict | None = None) -> dict:
    r = requests.get(f"{BASE}{path}", params=params, headers=HEADERS, timeout=20)
    r.raise_for_status()
    return r.json()


def now_showing(limit: int = 12) -> list[dict]:
    """Raw list of films currently showing in PH cinemas."""
    data = _get("/movies/now-showing").get("data", []) or []
    return data[:limit]


def showtimes(movie_id: int, city: str | None = None) -> list[dict]:
    """Theaters + schedules for a film. If `city` is given, prefer theaters in
    that city, but fall back to all theaters when the city has no match (city
    labels don't always line up with a user's exact municipality)."""
    try:
        rows = _get(f"/movies/{movie_id}/showtimes").get("data", []) or []
    except Exception:
        return []
    if city:
        cl = city.lower().replace("ñ", "n")
        matched = [t for t in rows if cl in (t.get("city", "").lower().replace("ñ", "n"))]
        if matched:
            return matched
    return rows


def _norm(s: str) -> str:
    return (s or "").lower().replace("ñ", "n").strip()


def cinemas_now_showing(user_city: str, movie_cap: int = 12, max_cinemas: int = 10):
    """Cinema-centric view: nearby cinemas and what's playing at each, with times.

    Aggregates the per-film showtimes of the current now-showing slate into a map
    of theater -> [(movie, times)]. Scopes to the user's city, then their
    province, then nationwide. Returns (cinemas, scope_label).
    Each cinema: {name, city, province, url, movies: [(title, [times])]}.
    """
    movies = now_showing(movie_cap)

    def fetch(mv):
        try:
            return mv["title"], _get(f"/movies/{mv['movie_id']}/showtimes")
        except Exception:
            return mv["title"], {}

    with ThreadPoolExecutor(max_workers=6) as ex:
        results = list(ex.map(fetch, movies))

    # city -> province directory (same for every response; grab from the first).
    city_prov = {}
    for _title, j in results:
        for c in j.get("cities", []) or []:
            city_prov[_norm(c.get("city", ""))] = c.get("province", "")
        if city_prov:
            break

    theaters: dict = {}
    for title, j in results:
        for t in j.get("data", []) or []:
            times = t.get("schedule") or []
            if not times:
                continue
            key = (t.get("theater_name"), t.get("city"))
            ent = theaters.setdefault(
                key,
                {
                    "name": (t.get("theater_name") or t.get("mall_name") or "Cinema").strip(),
                    "mall": (t.get("mall_name") or "").strip(),
                    "city": (t.get("city", "") or "").strip(),
                    "province": city_prov.get(_norm(t.get("city", "")), ""),
                    "url": t.get("url"),
                    "movies": [],
                },
            )
            ent["movies"].append((title, times))

    all_cinemas = list(theaters.values())
    ucl = _norm(user_city)
    busiest = lambda c: (-len(c["movies"]), c["city"], c["name"])

    in_city = sorted([c for c in all_cinemas if ucl and ucl in _norm(c["city"])], key=busiest)
    # User's province: exact directory hit, else a fuzzy city match ("Las Piñas"
    # vs "Las Piñas City"), else inferred from their own city's cinemas.
    user_prov = city_prov.get(ucl, "")
    if not user_prov and ucl:
        for ck, prov in city_prov.items():
            if ucl in ck or ck in ucl:
                user_prov = prov
                break
    if not user_prov and in_city:
        user_prov = in_city[0]["province"]
    city_ids = {id(c) for c in in_city}
    in_prov = sorted(
        [c for c in all_cinemas if user_prov and c["province"] == user_prov and id(c) not in city_ids],
        key=busiest,
    )

    # City cinemas first, then the rest of the province to fill out the list.
    ordered = in_city + in_prov
    if in_city and in_prov:
        scope = f"near {user_city}"
    elif in_city:
        scope = f"in {user_city}"
    elif in_prov:
        scope = f"in {user_prov}"
    else:
        ordered = sorted(all_cinemas, key=busiest)
        scope = "across the Philippines"

    return ordered[:max_cinemas], scope
