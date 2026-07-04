"""Now-showing providers, normalized to one movie shape the bot can render.

Routing:
  • Philippines (country_code == 'PH')  -> ClickTheCity: the *accurate* local
    slate, with real per-cinema showtimes and a real buy-ticket page.
  • Everywhere else                     -> TMDB 'now playing' for the region
    (best globally-available source), with a Google Showtimes link.

Normalized movie dict ("M"):
  title, year, rating10, votes, runtime_text, genres_text, overview,
  poster_url, trailer_url, buy_url, buy_label, info_url, info_label,
  mtrcb, showtimes  (list of {name, detail, times[]})
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import clickthecity
import config
import showtimes
import tmdb

BUY_LABEL = "🎟 Showtimes & tickets"


def _ctc_showtimes_block(movie_id: int, loc: dict | None) -> list[dict]:
    city = (loc or {}).get("city")
    out = []
    for t in clickthecity.showtimes(movie_id, city)[:4]:
        times = t.get("schedule") or []
        if not times:
            continue
        out.append(
            {
                "name": t.get("theater_name") or t.get("mall_name") or "Cinema",
                "detail": t.get("city", ""),
                "times": times,
            }
        )
    return out


def normalize_ctc(item: dict, loc: dict | None, with_showtimes: bool = True) -> dict:
    avg = (item.get("user_rating") or {}).get("average") or 0  # CTC scale is /5
    yt = item.get("youtube_trailer_url")
    return {
        "title": item.get("title") or "Untitled",
        "year": str(item.get("year_released") or (item.get("release_date") or "")[:4]),
        "rating10": round(avg * 2, 1) if avg else None,
        "votes": (item.get("user_rating") or {}).get("total") or 0,
        "runtime_text": item.get("running_time") or None,
        "genres_text": item.get("genre") or None,
        "overview": item.get("synopsis") or "No synopsis available.",
        "poster_url": item.get("poster_2x") or item.get("poster"),
        "trailer_url": f"https://www.youtube.com/watch?v={yt}" if yt else None,
        "buy_url": item.get("url"),
        "buy_label": BUY_LABEL,
        "info_url": None,
        "info_label": None,
        "mtrcb": item.get("mtrcb_rating") or None,
        "showtimes": _ctc_showtimes_block(item["movie_id"], loc) if with_showtimes else None,
    }


def normalize_tmdb(details: dict, loc: dict | None) -> dict:
    runtime = details.get("runtime") or 0
    genres = ", ".join(g["name"] for g in (details.get("genres") or [])[:3])
    imdb_id = (details.get("external_ids") or {}).get("imdb_id")
    title = details.get("title") or "Untitled"
    city = (loc or {}).get("city")

    # Optional in-chat exact showtimes via MovieGlu (if configured).
    st = None
    if loc and loc.get("lat") is not None:
        mg = showtimes.movieglu_showtimes(title, loc["lat"], loc["lon"])
        if mg:
            st = []
            for c in mg[:4]:
                dist = c.get("distance_km")
                st.append(
                    {
                        "name": c["name"],
                        "detail": f"{dist:.1f} km away" if dist is not None else "",
                        "times": c["times"],
                    }
                )

    return {
        "title": title,
        "year": (details.get("release_date") or "")[:4],
        "rating10": details.get("vote_average") or None,
        "votes": details.get("vote_count") or 0,
        "runtime_text": f"{runtime // 60}h {runtime % 60}m" if runtime else None,
        "genres_text": genres or None,
        "overview": details.get("overview") or "No synopsis available.",
        "poster_url": tmdb.poster_url(details.get("poster_path")),
        "trailer_url": tmdb.trailer_url(details),
        "buy_url": showtimes.google_showtimes_link(title, city),
        "buy_label": BUY_LABEL,
        "info_url": f"https://www.imdb.com/title/{imdb_id}/" if imdb_id else None,
        "info_label": "ℹ️ IMDb" if imdb_id else None,
        "mtrcb": None,
        "showtimes": st,
    }


def _enrich_ratings(movies: list[dict]) -> None:
    """Fill in missing ratings from TMDB (matched by title/year), in parallel.
    ClickTheCity user-ratings are usually 0 for new releases, so this surfaces a
    real ⭐ score on the postcard/cards for titles TMDB knows. In-place."""
    if not config.TMDB_API_KEY:
        return
    todo = [m for m in movies if not m.get("rating10")]
    if not todo:
        return

    def fetch(m):
        try:
            m["rating10"] = tmdb.rating_for(m["title"], m.get("year"))
        except Exception:  # noqa: BLE001
            pass

    with ThreadPoolExecutor(max_workers=6) as ex:
        list(ex.map(fetch, todo))


def get_now_showing(loc: dict, limit: int = 8) -> list[dict]:
    """Accurate now-showing list for the user's location, as normalized movies."""
    if (loc.get("country_code") or "").upper() == "PH":
        items = clickthecity.now_showing(limit)
        movies = [normalize_ctc(it, loc) for it in items]
        _enrich_ratings(movies)
        return movies
    region = loc.get("country_code") or None
    out = []
    for m in tmdb.now_playing(region, limit):
        try:
            out.append(normalize_tmdb(tmdb.movie_details(m["id"]), loc))
        except Exception:
            continue
    return out


def search_one(title: str, loc: dict | None) -> dict | None:
    """Look up a single named title (global, via TMDB)."""
    hit = tmdb.search_movie(title)
    if not hit:
        return None
    return normalize_tmdb(tmdb.movie_details(hit["id"]), loc)
