# 🎬 Cinema Bot

Tells you **what's playing in cinemas near you — in any country** — with the
details you need to decide (rating, plot, runtime, genres, trailer) and a link
to **buy tickets online**.

Comes in two forms that share one engine:

- **Telegram bot** (`bot.py`) — chat `/movies` and get a card per film with a
  "🎟 Showtimes & tickets" button.
- **Terminal app** (`app.py`) — the same thing in your shell.

## How "any country" works

| Need | Source | Cost |
| --- | --- | --- |
| What's playing now — **Philippines** | **ClickTheCity** API (accurate local slate + real showtimes + buy links) | Free, no key |
| What's playing now — other countries | [TMDB](https://www.themoviedb.org/) `now_playing?region=XX` | Free key |
| Movie details (rating, plot, runtime, trailer, IMDb) | TMDB | Free key |
| "Nearby" / your city | [OpenStreetMap Nominatim](https://nominatim.org/) geocoding | Free, no key |
| Showtimes + buy-ticket links | **Google Showtimes** deep-link (universal) | Free |
| *(optional)* exact timeslots **inside the chat** | [MovieGlu](https://developer.movieglu.com/) global API | Free dev tier |

> **Why the Google deep-link?** There is no free global API that returns exact
> per-cinema timeslots in every country. Google's showtimes panel does cover
> nearly every country, showing real nearby cinemas, times, and "Book tickets"
> partners. Add MovieGlu credentials and the bot will *also* print exact times
> directly in the chat.

## Setup

```bash
cd ~/cinema-bot
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env       # then fill it in
```

Fill `.env`:

1. **`TELEGRAM_BOT_TOKEN`** — message [@BotFather](https://t.me/BotFather),
   send `/newbot`, copy the token.
2. **`TMDB_API_KEY`** — sign up at TMDB → Settings → API. A v3 key *or* a v4
   "API Read Access Token" both work.
3. *(optional)* **`DEFAULT_LOCATION`** — e.g. `Manila, Philippines`, used until
   a user sets their own.
4. *(optional)* **MovieGlu** keys for in-chat exact timeslots.

## Run

**Telegram bot:**
```bash
python bot.py
```
Then in Telegram (the bot is **@pelikula_finder_bot**):
```
📍 Tap "Share my location" button   ← auto-detects your current GPS (one tap)
/setlocation Cebu City, Philippines  ← or set any city by name
/cinemas                                       ← cinemas near you + distance
/movies
/movie Dune
/subscribe 09:00                               ← daily "what's playing" push
/unsubscribe                                    ← stop the daily push
```

### Movie overview postcard
`/movies` (and the daily push) now lead with a single **postcard image** — a
poster collage of the films now playing near you, each with title + ★ rating,
under a "NOW PLAYING in cinemas near {city}" header. It's sent *first*, as an
at-a-glance overview, before the individual detail cards. Built on the fly with
Pillow (`postcard.py`); falls back to a text header if image building ever fails.

### Daily push
`/subscribe HH:MM` schedules a once-a-day message with the films now playing
near you (rich cards: rating, plot, runtime, trailer, showtimes/tickets). Times
are in the **host machine's local timezone** (currently `Asia/Manila`). The
schedule survives restarts — the bot re-arms all subscriptions on startup via
its `post_init` hook and an in-process APScheduler job queue. `/unsubscribe`
stops it.
(You can also just send a movie title.)

### Location auto-detect
On `/start` (and whenever a location is needed) the bot shows a one-tap
**📍 Share my location** button that pulls the device's current GPS and
reverse-geocodes it. Telegram can't read a user's location without this explicit
tap — that's a privacy guarantee, not a limitation of the bot. `/setlocation
City, Country` remains the manual fallback for any city worldwide.

**Live location** is supported too: share a *live* location (Telegram: attach →
Location → Share Live Location) and the bot tracks you as you move. Each update
arrives as an edited message; the bot refreshes the stored coordinates **silently
on every tick** (so cinema distances stay exact) and only re-resolves the city
label after you've moved >= 5 km, to respect the geocoder's rate limits. You get
one "Live location on" confirmation, then no further chat noise until you stop.

### Cinema distance
When you **share your location** (or `/setlocation`), the bot measures the
great-circle distance from you to each cinema and lists them **nearest-first**,
e.g. `• Ayala Malls Cinemas — 2.7 km`.

`/cinemas` adapts to where you are:
- **Philippines** — real cinemas from **ClickTheCity**, grouped and showing
  **what's playing at each, with today's timeslots**, a **distance** (from
  geocoding each mall — cached in `data/mall_coords.json`, so nearest-first),
  and a buy-tickets link. Scoped to your city → province (e.g. Metro Manila) →
  nationwide.
- **Other countries** — real nearby cinemas from **OpenStreetMap** (free, no
  key), each with **distance** + a booking/showtimes link.

Movie-card distances also appear two ways:
- **Movie cards** — if **MovieGlu** keys are set, each film lists the cinemas
  showing it *with exact timeslots and distance*. Without MovieGlu, cards still
  give the universal Google Showtimes link.

### Optional: MovieGlu (exact in-chat timeslots)
MovieGlu is an approval-gated developer API. After you're approved at
[developer.movieglu.com](https://developer.movieglu.com/), paste the four values
into `.env` (`MOVIEGLU_CLIENT`, `MOVIEGLU_API_KEY`, `MOVIEGLU_AUTHORIZATION`,
`MOVIEGLU_TERRITORY`) and validate them:
```bash
python movieglu_check.py "Manila, Philippines"
```
A ✅ means the bot will start printing exact per-cinema times + distances.

## Running in the background (auto-start)
The bot is installed as a macOS **LaunchAgent** so it starts at login and
restarts if it crashes:
```
~/Library/LaunchAgents/com.cinemabot.plist   → runs .venv/bin/python bot.py
logs/bot.log, logs/bot.err.log               → its output
```
Manage it:
```bash
launchctl list | grep cinemabot                 # status (shows PID)
launchctl unload ~/Library/LaunchAgents/com.cinemabot.plist   # stop
launchctl load -w ~/Library/LaunchAgents/com.cinemabot.plist  # start
```
⚠️ Only one instance may poll a bot token at a time (Telegram returns
`409 Conflict` otherwise). Don't run `python bot.py` manually while the
LaunchAgent is loaded.

**Terminal app:**
```bash
python app.py "Berlin, Germany"            # what's on near Berlin
python app.py "Tokyo, Japan" "Godzilla"    # one film's details + tickets
```

## Files

| File | Purpose |
| --- | --- |
| `bot.py` | Telegram bot (commands, message cards) |
| `app.py` | Terminal version |
| `postcard.py` | Pillow collage of nearby films (sent first on `/movies`) |
| `make_icons.py` | Renders the logo to PNG (`web/logo-512.png`, `web/icon-512.png`) |
| `web/logo.svg`, `web/icon.svg` | App logo (pin + play mark) and square badge |
| `tmdb.py` | TMDB client — now-playing + details |
| `geocode.py` | City → coords + country code, reverse-geocode, haversine distance |
| `cinemas.py` | Nearby cinemas + distance via OpenStreetMap (free, no key) |
| `showtimes.py` | Google deep-link + optional MovieGlu timeslots/distance |
| `movieglu_check.py` | Validate MovieGlu credentials |
| `store.py` | Per-chat saved location (JSON) |
| `config.py` | Loads `.env` |

## Notes
- Keep it running (`python bot.py`) for the bot to respond; or deploy it as a
  worker (Render/railway/a small VPS) the same way as your other projects.
- Nominatim asks for light usage; the bot only geocodes when you `/setlocation`.
