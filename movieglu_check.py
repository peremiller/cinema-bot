"""Validate MovieGlu credentials.

Run after pasting your MovieGlu keys into .env:
    python movieglu_check.py "Manila, Philippines"

Confirms the credentials work and that showtimes come back for a location.
MovieGlu is the OPTIONAL upgrade that prints exact per-cinema timeslots
(and distances) inside the Telegram chat. The bot works without it.
"""
from __future__ import annotations

import sys

import config
import geocode
import showtimes


def main():
    if not config.MOVIEGLU_ENABLED:
        print("MovieGlu is NOT configured.")
        print("Fill these in .env, then re-run:")
        for k in ("MOVIEGLU_CLIENT", "MOVIEGLU_API_KEY",
                  "MOVIEGLU_AUTHORIZATION", "MOVIEGLU_TERRITORY"):
            print(f"  - {k}")
        print("\nGet credentials at https://developer.movieglu.com/ (approval required).")
        sys.exit(1)

    place = sys.argv[1] if len(sys.argv) > 1 else (config.DEFAULT_LOCATION or "Manila, Philippines")
    loc = geocode.geocode(place)
    print(f"Testing MovieGlu near {loc['city']}, {loc['country']} "
          f"({loc['lat']:.3f},{loc['lon']:.3f})\n")

    # filmsNowShowing is the cheapest endpoint that exercises auth + geolocation.
    try:
        data = showtimes._movieglu_get(
            "filmsNowShowing/", {"n": 5}, loc["lat"], loc["lon"]
        )
    except Exception as exc:  # noqa: BLE001
        print(f"❌ MovieGlu request failed: {exc}")
        print("Check the 4 credentials, the territory code, and api-version in .env.")
        sys.exit(2)

    films = data.get("films") or []
    print(f"✅ Credentials work. {len(films)} films now showing returned.")
    for f in films[:5]:
        print(f"   • {f.get('film_name')}")
    print("\nThe Telegram bot will now show exact per-cinema timeslots + distances "
          "in movie cards.")


if __name__ == "__main__":
    main()
