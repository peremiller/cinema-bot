"""TMDB (The Movie Database) client — global movie data + 'now playing'.

Works in every country via the `region` parameter (ISO 3166-1 alpha-2).
Supports both a v3 API key (query param) and a v4 read token (Bearer header).
"""
from __future__ import annotations

import requests

import config

BASE = "https://api.themoviedb.org/3"
IMG_BASE = "https://image.tmdb.org/t/p/w500"


def _request(path: str, params: dict | None = None) -> dict:
    params = dict(params or {})
    headers = {"accept": "application/json"}
    if config.TMDB_IS_V4_TOKEN:
        headers["Authorization"] = f"Bearer {config.TMDB_API_KEY}"
    else:
        params["api_key"] = config.TMDB_API_KEY
    resp = requests.get(f"{BASE}{path}", params=params, headers=headers, timeout=20)
    resp.raise_for_status()
    return resp.json()


def now_playing(region: str | None = None, limit: int = 8) -> list[dict]:
    """Movies currently in theaters, optionally scoped to a country."""
    params = {"language": "en-US", "page": 1}
    if region:
        params["region"] = region
    data = _request("/movie/now_playing", params)
    results = data.get("results", [])
    # Keep titles actually released on/before today for the region.
    return results[:limit]


def search_movie(query: str) -> dict | None:
    data = _request("/search/movie", {"query": query, "language": "en-US", "page": 1})
    results = data.get("results", [])
    return results[0] if results else None


def movie_details(movie_id: int) -> dict:
    """Full details incl. genres, runtime, trailer and IMDb id."""
    return _request(
        f"/movie/{movie_id}",
        {"language": "en-US", "append_to_response": "videos,external_ids"},
    )


def poster_url(poster_path: str | None) -> str | None:
    return f"{IMG_BASE}{poster_path}" if poster_path else None


def trailer_url(details: dict) -> str | None:
    videos = (details.get("videos") or {}).get("results", [])
    # Prefer an official YouTube trailer.
    best = None
    for v in videos:
        if v.get("site") != "YouTube":
            continue
        if v.get("type") == "Trailer":
            if v.get("official") or best is None:
                best = v
    if best:
        return f"https://www.youtube.com/watch?v={best['key']}"
    return None
