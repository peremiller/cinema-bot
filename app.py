"""Terminal app — the same engine as the Telegram bot, in your shell.

Usage:
  python app.py "Cebu City, Philippines"          # now playing near a place
  python app.py "Berlin, Germany" "Dune"          # details for one film there
"""
from __future__ import annotations

import sys
import textwrap

import geocode
import showtimes
import tmdb


def line(char="─", n=60):
    print(char * n)


def show(details: dict, city: str | None):
    title = details.get("title", "Untitled")
    year = (details.get("release_date") or "")[:4]
    rating = details.get("vote_average") or 0
    runtime = details.get("runtime") or 0
    genres = ", ".join(g["name"] for g in (details.get("genres") or [])[:3])
    overview = details.get("overview") or "No synopsis available."

    line()
    print(f"🎬 {title}" + (f" ({year})" if year else ""))
    facts = []
    if rating:
        facts.append(f"⭐ {rating:.1f}/10")
    if runtime:
        facts.append(f"⏱ {runtime // 60}h {runtime % 60}m")
    if genres:
        facts.append(f"🎭 {genres}")
    if facts:
        print("   " + " · ".join(facts))
    print()
    print(textwrap.fill(overview, width=60, initial_indent="   ",
                        subsequent_indent="   "))
    trailer = tmdb.trailer_url(details)
    if trailer:
        print(f"\n   ▶️  Trailer: {trailer}")
    print(f"   🎟  Showtimes & tickets: "
          f"{showtimes.google_showtimes_link(title, city)}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    place = sys.argv[1]
    loc = geocode.geocode(place)
    print(f"📍 {loc['city']}, {loc['country']}")

    if len(sys.argv) >= 3:
        title = sys.argv[2]
        hit = tmdb.search_movie(title)
        if not hit:
            print(f"No movie found for '{title}'.")
            return
        show(tmdb.movie_details(hit["id"]), loc.get("city"))
        return

    movies = tmdb.now_playing(loc.get("country_code") or None, 6)
    if not movies:
        print("No 'now playing' titles for this region right now.")
        return
    for m in movies:
        show(tmdb.movie_details(m["id"]), loc.get("city"))
    line()


if __name__ == "__main__":
    main()
