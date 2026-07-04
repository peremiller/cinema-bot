"""Cinema bot — what's playing in nearby cinemas, with details + ticket links.

Run with:  python bot.py
Commands:
  /start, /help            – intro
  /setlocation <place>     – set your city (works in any country)
  /where                   – show your current location
  /movies                  – what's now playing near you + how to decide + tickets
  /movie <title>           – details + showtimes for one film
  /subscribe [HH:MM]       – daily "what's playing near you" push (default 09:00)
  /unsubscribe             – stop the daily push
You can also just send a movie title as a plain message.
"""
from __future__ import annotations

import asyncio
import html
import logging
from datetime import time as dtime

from telegram import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from telegram.constants import ParseMode
from telegram.ext import (
    AIORateLimiter,
    Application,
    CommandHandler,
    ContextTypes,
    Defaults,
    MessageHandler,
    filters,
)
from tzlocal import get_localzone

import cinemas
import clickthecity
import config
import geocode
import mallgeo
import postcard
import providers
import store

# Host-local timezone, so /subscribe HH:MM means the user's local clock time.
LOCAL_TZ = get_localzone()

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.INFO
)
log = logging.getLogger("cinema-bot")

def location_keyboard() -> ReplyKeyboardMarkup:
    """One-tap button that asks the device to share its current GPS location."""
    return ReplyKeyboardMarkup(
        [[KeyboardButton("📍 Share my location", request_location=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder="Tap the button to auto-detect your location",
    )


NEED_LOCATION = (
    "I need your location first 📍\n\n"
    "Tap <b>📍 Share my location</b> below to auto-detect it, or send "
    "<code>/setlocation City, Country</code>."
)


# Cache for the env DEFAULT_LOCATION so we geocode it only once.
_default_location_cache: dict | None = None


def get_effective_location(chat_id: int):
    """Saved per-chat location, else the env default, else None."""
    loc = store.get_location(chat_id)
    if loc:
        return loc
    global _default_location_cache
    if config.DEFAULT_LOCATION:
        if _default_location_cache is None:
            try:
                _default_location_cache = geocode.geocode(config.DEFAULT_LOCATION)
            except Exception as exc:  # noqa: BLE001
                log.warning("Default location geocode failed: %s", exc)
                _default_location_cache = {}
        return _default_location_cache or None
    return None


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------
def _truncate(text: str, limit: int) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def render_caption(m: dict) -> str:
    """Build a movie card caption from a normalized movie dict (see providers)."""
    title = html.escape(m.get("title") or "Untitled")
    year = m.get("year") or ""
    overview = html.escape(m.get("overview") or "No synopsis available.")

    header = f"<b>{title}</b>"
    if year:
        header += f" ({year})"

    facts = []
    rating = m.get("rating10")
    if rating:
        votes = m.get("votes") or 0
        facts.append(f"⭐ {rating:.1f}/10" + (f" ({votes:,} votes)" if votes else ""))
    if m.get("runtime_text"):
        facts.append(f"⏱ {html.escape(m['runtime_text'])}")
    if m.get("genres_text"):
        facts.append(f"🎭 {html.escape(m['genres_text'])}")
    if m.get("mtrcb"):
        facts.append(f"🔖 {html.escape(m['mtrcb'])}")

    parts = [header]
    if facts:
        parts.append(" · ".join(facts))
    parts.append("")
    parts.append(_truncate(overview, 600))

    for block in (m.get("showtimes") or [])[:4]:
        if block is m["showtimes"][0]:
            parts.append("")
            parts.append("🕐 <b>Showtimes today:</b>")
        detail = f" — {block['detail']}" if block.get("detail") else ""
        shown = ", ".join(block["times"][:8])
        parts.append(
            f"• <b>{html.escape(block['name'])}</b>{html.escape(detail)}\n"
            f"  {html.escape(shown)}"
        )

    return _truncate("\n".join(parts), 1024)


def render_buttons(m: dict) -> InlineKeyboardMarkup:
    rows = []
    if m.get("buy_url"):
        rows.append([InlineKeyboardButton(m.get("buy_label") or "🎟 Tickets", url=m["buy_url"])])
    second = []
    if m.get("trailer_url"):
        second.append(InlineKeyboardButton("▶️ Trailer", url=m["trailer_url"]))
    if m.get("info_url"):
        second.append(InlineKeyboardButton(m.get("info_label") or "ℹ️ Info", url=m["info_url"]))
    if second:
        rows.append(second)
    return InlineKeyboardMarkup(rows)


async def deliver_movie(bot, chat_id: int, m: dict):
    """Send one rich movie card to a chat (used by commands and the daily job)."""
    caption = render_caption(m)
    buttons = render_buttons(m)
    poster = m.get("poster_url")
    if poster:
        try:
            await bot.send_photo(
                chat_id=chat_id, photo=poster, caption=caption,
                parse_mode=ParseMode.HTML, reply_markup=buttons,
            )
            return
        except Exception as exc:  # noqa: BLE001 — poster host can reject hotlinks
            log.warning("Poster send failed (%s), falling back to text: %s",
                        m.get("title"), exc)
    await bot.send_message(
        chat_id=chat_id, text=caption, parse_mode=ParseMode.HTML,
        reply_markup=buttons, disable_web_page_preview=True,
    )


async def send_now_playing(bot, chat_id: int, movies: list, loc: dict,
                           headline: str = "🎬 Now playing near"):
    """Send the postcard collage FIRST, then one rich detail card per film.

    The postcard and the detail cards render the SAME list (`shown`) so there is
    never a film on the postcard that's missing from the messages below it."""
    city = loc.get("city", "")
    shown = movies[: postcard.MAX]
    caption = (
        f"{headline} <b>{html.escape(city)}</b> — {len(shown)} films to choose from. "
        f"Full details below 👇\n"
        f"<i>📍 Not in {html.escape(city)}? Share your location to update.</i>"
    )
    try:
        bio = await asyncio.to_thread(postcard.build_postcard, shown, city)
        await bot.send_photo(
            chat_id=chat_id, photo=bio, caption=caption, parse_mode=ParseMode.HTML
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("Postcard build failed: %s", exc)
        await bot.send_message(
            chat_id=chat_id, text=caption, parse_mode=ParseMode.HTML
        )
    for m in shown:
        # One card per postcard film; retry once so a transient send error never
        # leaves a gap between the postcard and the list.
        for attempt in (1, 2):
            try:
                await deliver_movie(bot, chat_id, m)
                break
            except Exception as exc:  # noqa: BLE001
                log.warning("Card send failed (%s, attempt %d): %s",
                            m.get("title"), attempt, exc)


# --------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------
WELCOME = (
    "🎬 <b>Cinema Bot</b>\n\n"
    "I tell you what's playing in cinemas near you — with ratings, plot, runtime "
    "and a trailer to help you decide, plus a link to buy tickets online.\n\n"
    "<b>Get started:</b>\n"
    "1. 📍 Tap <b>Share my location</b> below to auto-detect where you are "
    "— or send <code>/setlocation Manila, Philippines</code> for any city.\n"
    "2. <code>/cinemas</code> — cinemas near you, with distance\n"
    "3. <code>/movies</code> — see what's on near you\n"
    "4. <code>/movie Dune</code> — details + showtimes for one film\n\n"
    "📅 <code>/subscribe 09:00</code> — get a daily push of what's playing near you.\n"
    "Tip: you can also just send me a movie title."
)


async def cmd_start(update: Update, _ctx: ContextTypes.DEFAULT_TYPE):
    # Offer the one-tap location button straight away unless we already know where they are.
    markup = None if get_effective_location(update.effective_chat.id) else location_keyboard()
    await update.message.reply_html(WELCOME, reply_markup=markup)


async def cmd_setlocation(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = " ".join(ctx.args).strip()
    if not query:
        await update.message.reply_html(
            "Usage: <code>/setlocation City, Country</code>\n"
            "e.g. <code>/setlocation Cebu City, Philippines</code>"
        )
        return
    await update.effective_chat.send_action("typing")
    try:
        loc = await asyncio.to_thread(geocode.geocode, query)
    except Exception as exc:  # noqa: BLE001
        await update.message.reply_text(f"Couldn't set location: {exc}")
        return
    store.set_location(update.effective_chat.id, loc)
    await update.message.reply_html(
        f"📍 Location set to <b>{html.escape(loc['city'])}, "
        f"{html.escape(loc['country'])}</b>.\nNow try <code>/movies</code>."
    )


# Only re-run (rate-limited) reverse geocoding once the user has moved this far;
# coordinates are always updated so cinema distances stay exact in between.
LIVE_REFRESH_KM = 5


async def on_location(update: Update, _ctx: ContextTypes.DEFAULT_TYPE):
    """Handle a shared location — one-time, or a continuously-updating live share.

    Telegram delivers the first share as a normal message and each subsequent
    live update as an *edited* message. We update the stored coordinates on every
    tick (silently) so distances track the user, and only reverse-geocode the
    city label when they've moved far enough to matter.
    """
    msg = update.effective_message
    loc_msg = msg.location if msg else None
    if loc_msg is None:
        return
    chat_id = update.effective_chat.id
    is_live = loc_msg.live_period is not None
    is_tick = update.edited_message is not None  # a live-location update, not the first share

    prev = store.get_location(chat_id)
    moved_km = None
    if prev and prev.get("lat") is not None:
        moved_km = geocode.haversine_km(
            prev["lat"], prev["lon"], loc_msg.latitude, loc_msg.longitude
        )

    # Reverse-geocode (rate-limited) only when we don't yet have a real city
    # label or the user has moved meaningfully; otherwise just refresh coords.
    need_geocode = (
        prev is None
        or prev.get("city") in (None, "", "Your location")
        or moved_km is None
        or moved_km >= LIVE_REFRESH_KM
    )
    if need_geocode:
        if not is_tick:
            await update.effective_chat.send_action("typing")
        try:
            loc = await asyncio.to_thread(
                geocode.reverse, loc_msg.latitude, loc_msg.longitude
            )
        except Exception:  # noqa: BLE001
            loc = {
                "city": (prev or {}).get("city") or "Your location",
                "country": (prev or {}).get("country", ""),
                "country_code": (prev or {}).get("country_code", ""),
                "lat": loc_msg.latitude,
                "lon": loc_msg.longitude,
            }
    else:
        loc = {**prev, "lat": loc_msg.latitude, "lon": loc_msg.longitude}

    store.set_location(chat_id, loc)

    # Live ticks update silently — no chat spam every few seconds.
    if is_tick:
        return

    where = html.escape(loc.get("city", "your location"))
    if is_live:
        text = (
            f"🛰️ <b>Live location on</b> — tracking near <b>{where}</b>.\n"
            f"I'll keep cinema distances accurate as you move (updated silently). "
            f"Stop anytime from the location message in Telegram."
        )
    else:
        text = (
            f"📍 Detected your location near <b>{where}</b>. Cinema distances "
            f"measured from here.\nTry <code>/movies</code> or <code>/cinemas</code>."
        )
    await msg.reply_html(text, reply_markup=ReplyKeyboardRemove())


async def cmd_cinemas(update: Update, _ctx: ContextTypes.DEFAULT_TYPE):
    """List cinemas near the user. In PH: real cinemas + what's playing + times
    (ClickTheCity), with distance when matchable. Elsewhere: nearby cinemas with
    distance (OpenStreetMap)."""
    loc = get_effective_location(update.effective_chat.id)
    if not loc:
        await update.message.reply_html(NEED_LOCATION, reply_markup=location_keyboard())
        return

    if _is_ph(loc):
        await update.effective_chat.send_action("typing")
        try:
            found, scope = await asyncio.to_thread(
                clickthecity.cinemas_now_showing, loc.get("city", "")
            )
        except Exception as exc:  # noqa: BLE001
            await update.message.reply_text(f"Couldn't fetch cinemas: {exc}")
            return
        if not found:
            await update.message.reply_text("No cinema schedules found for your area right now.")
            return
        # Attach real distances by geocoding each cinema's mall (cached), then
        # put the nearest cinemas first; any without a known distance follow.
        if loc.get("lat") is not None:
            try:
                await asyncio.to_thread(mallgeo.attach_distances, found, loc["lat"], loc["lon"])
            except Exception as exc:  # noqa: BLE001
                log.warning("Mall distance lookup failed: %s", exc)
            found.sort(key=lambda c: (c.get("distance_km") is None,
                                      c.get("distance_km", 9e9), -len(c["movies"])))
        lines = [f"🏢 <b>Cinemas {html.escape(scope)}</b> — what's playing today:", ""]
        for c in found[:8]:
            link = c.get("url")
            name = html.escape(c["name"])
            head = f"<a href=\"{html.escape(link)}\"><b>{name}</b></a>" if link else f"<b>{name}</b>"
            dist = c.get("distance_km")
            dist_str = f" · {dist:.1f} km" if dist is not None else ""
            lines.append(f"📍 {head} — {html.escape(c['city'])}{dist_str}")
            for title, times in c["movies"][:4]:
                lines.append(f"   • {html.escape(title)} — {html.escape(', '.join(times[:3]))}")
            lines.append("")
        lines.append("Tap a cinema name to buy tickets online.")
        await update.message.reply_html("\n".join(lines), disable_web_page_preview=True)
        return

    # Non-PH: OpenStreetMap nearby cinemas with distance (needs coordinates).
    if loc.get("lat") is None:
        await update.message.reply_html(NEED_LOCATION, reply_markup=location_keyboard())
        return
    await update.effective_chat.send_action("typing")
    try:
        found = await asyncio.to_thread(cinemas.nearby_cinemas, loc["lat"], loc["lon"])
    except Exception as exc:  # noqa: BLE001
        await update.message.reply_text(f"Couldn't fetch cinemas: {exc}")
        return
    if not found:
        await update.message.reply_text("No cinemas found near you.")
        return
    lines = [f"🏢 <b>Cinemas near {html.escape(loc.get('city',''))}</b> (nearest first):", ""]
    for c in found:
        link = cinemas.cinema_link(c)
        lines.append(
            f"• <a href=\"{html.escape(link)}\"><b>{html.escape(c['name'])}</b></a> "
            f"— {c['distance_km']:.1f} km"
        )
    lines.append("\nTap a name for its showtimes &amp; online tickets.")
    await update.message.reply_html("\n".join(lines), disable_web_page_preview=True)


async def cmd_where(update: Update, _ctx: ContextTypes.DEFAULT_TYPE):
    loc = get_effective_location(update.effective_chat.id)
    if not loc:
        await update.message.reply_html(
            "No location set yet. Use <code>/setlocation City, Country</code>."
        )
        return
    await update.message.reply_html(
        f"📍 <b>{html.escape(loc.get('city',''))}, "
        f"{html.escape(loc.get('country',''))}</b>"
    )


TMDB_MISSING_MSG = (
    "⚙️ Movie data isn't configured yet — the bot owner needs to add a free "
    "<code>TMDB_API_KEY</code> to <code>.env</code> "
    "(themoviedb.org → Settings → API)."
)


def _is_ph(loc: dict | None) -> bool:
    return bool(loc) and (loc.get("country_code") or "").upper() == "PH"


async def cmd_movies(update: Update, _ctx: ContextTypes.DEFAULT_TYPE):
    loc = get_effective_location(update.effective_chat.id)
    if not loc:
        await update.message.reply_html(NEED_LOCATION, reply_markup=location_keyboard())
        return
    # PH uses ClickTheCity (no TMDB needed); other regions need a TMDB key.
    if not _is_ph(loc) and not config.TMDB_API_KEY:
        await update.message.reply_html(TMDB_MISSING_MSG)
        return
    await update.effective_chat.send_action("typing")
    try:
        movies = await asyncio.to_thread(providers.get_now_showing, loc, postcard.MAX)
    except Exception as exc:  # noqa: BLE001
        await update.message.reply_text(f"Couldn't fetch movies: {exc}")
        return
    if not movies:
        await update.message.reply_text(
            "No 'now showing' titles found for your area right now."
        )
        return
    await send_now_playing(update.get_bot(), update.effective_chat.id, movies, loc)


async def _show_title(update: Update, title: str):
    if not config.TMDB_API_KEY:
        await update.message.reply_html(TMDB_MISSING_MSG)
        return
    loc = get_effective_location(update.effective_chat.id)
    await update.effective_chat.send_action("typing")
    try:
        movie = await asyncio.to_thread(providers.search_one, title, loc)
        if not movie:
            await update.message.reply_text(f"No movie found for '{title}'.")
            return
        await deliver_movie(update.get_bot(), update.effective_chat.id, movie)
    except Exception as exc:  # noqa: BLE001
        await update.message.reply_text(f"Something went wrong: {exc}")


async def cmd_movie(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    title = " ".join(ctx.args).strip()
    if not title:
        await update.message.reply_html("Usage: <code>/movie Title</code>")
        return
    await _show_title(update, title)


async def on_text(update: Update, _ctx: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    if text:
        await _show_title(update, text)


# --------------------------------------------------------------------------
# Daily digest ("what's playing near you" push)
# --------------------------------------------------------------------------
DEFAULT_DAILY_TIME = "09:00"


def _parse_hhmm(s: str) -> tuple[int, int]:
    parts = s.strip().split(":")
    h = int(parts[0])
    m = int(parts[1]) if len(parts) > 1 else 0
    if not (0 <= h < 24 and 0 <= m < 60):
        raise ValueError("out of range")
    return h, m


def schedule_daily(job_queue, chat_id: int, hhmm: str) -> None:
    """(Re)schedule the daily digest for a chat at HH:MM local time."""
    name = f"daily-{chat_id}"
    for job in job_queue.get_jobs_by_name(name):
        job.schedule_removal()
    h, m = _parse_hhmm(hhmm)
    job_queue.run_daily(
        daily_digest_job,
        time=dtime(hour=h, minute=m, tzinfo=LOCAL_TZ),
        chat_id=chat_id,
        name=name,
    )


async def daily_digest_job(context: ContextTypes.DEFAULT_TYPE):
    """Push the day's now-showing movies to one subscriber."""
    chat_id = context.job.chat_id
    loc = store.get_location(chat_id)
    if not loc:
        return
    if not _is_ph(loc) and not config.TMDB_API_KEY:
        return
    try:
        movies = await asyncio.to_thread(providers.get_now_showing, loc, 5)
    except Exception as exc:  # noqa: BLE001
        log.warning("Daily digest fetch failed for %s: %s", chat_id, exc)
        return
    if not movies:
        return
    await send_now_playing(
        context.bot, chat_id, movies, loc, headline="🍿 Today in cinemas near"
    )


async def cmd_subscribe(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    arg = " ".join(ctx.args).strip() or DEFAULT_DAILY_TIME
    try:
        h, m = _parse_hhmm(arg)
    except (ValueError, IndexError):
        await update.message.reply_html(
            "Usage: <code>/subscribe HH:MM</code> (24-hour), e.g. "
            "<code>/subscribe 09:00</code>."
        )
        return
    hhmm = f"{h:02d}:{m:02d}"
    if not store.subscribe(update.effective_chat.id, hhmm):
        await update.message.reply_html(NEED_LOCATION, reply_markup=location_keyboard())
        return
    schedule_daily(ctx.job_queue, update.effective_chat.id, hhmm)
    await update.message.reply_html(
        f"✅ You'll get a daily \"what's playing near you\" push at <b>{hhmm}</b> "
        f"({LOCAL_TZ.key if hasattr(LOCAL_TZ, 'key') else LOCAL_TZ} time).\n"
        f"Stop anytime with /unsubscribe."
    )


async def cmd_unsubscribe(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    store.unsubscribe(update.effective_chat.id)
    for job in ctx.job_queue.get_jobs_by_name(f"daily-{update.effective_chat.id}"):
        job.schedule_removal()
    await update.message.reply_html("🛑 Daily push stopped. Re-enable with /subscribe.")


BOT_COMMANDS = [
    BotCommand("movies", "What's playing in cinemas near you"),
    BotCommand("cinemas", "Cinemas near you, with distance"),
    BotCommand("movie", "Details + showtimes for one film"),
    BotCommand("setlocation", "Set your city (any country)"),
    BotCommand("where", "Show your saved location"),
    BotCommand("subscribe", "Daily push of what's playing (e.g. /subscribe 09:00)"),
    BotCommand("unsubscribe", "Stop the daily push"),
    BotCommand("help", "How to use the bot"),
]


async def post_init(app: Application) -> None:
    """Register the / command menu and re-arm daily jobs on startup."""
    try:
        await app.bot.set_my_commands(BOT_COMMANDS)
    except Exception as exc:  # noqa: BLE001
        log.warning("Couldn't set command menu: %s", exc)

    count = 0
    for chat_id, hhmm, _rec in store.all_subscriptions():
        try:
            schedule_daily(app.job_queue, chat_id, hhmm)
            count += 1
        except Exception as exc:  # noqa: BLE001
            log.warning("Couldn't reschedule daily for %s: %s", chat_id, exc)
    log.info("Re-armed %d daily subscription(s).", count)


def main():
    config.require(config.TELEGRAM_BOT_TOKEN, "TELEGRAM_BOT_TOKEN")
    if not config.TMDB_API_KEY:
        log.warning("TMDB_API_KEY not set — movie commands will prompt to add it.")

    app = (
        Application.builder()
        .token(config.TELEGRAM_BOT_TOKEN)
        .defaults(Defaults(tzinfo=LOCAL_TZ))
        .rate_limiter(AIORateLimiter())  # pace sends + auto-retry on flood control
        .post_init(post_init)
        .build()
    )
    app.add_handler(CommandHandler(["start", "help"], cmd_start))
    app.add_handler(CommandHandler("setlocation", cmd_setlocation))
    app.add_handler(CommandHandler("where", cmd_where))
    app.add_handler(CommandHandler("cinemas", cmd_cinemas))
    app.add_handler(CommandHandler("movies", cmd_movies))
    app.add_handler(CommandHandler("movie", cmd_movie))
    app.add_handler(CommandHandler("subscribe", cmd_subscribe))
    app.add_handler(CommandHandler("unsubscribe", cmd_unsubscribe))
    app.add_handler(MessageHandler(filters.LOCATION, on_location))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    mg = "ON" if config.MOVIEGLU_ENABLED else "off (Google deep-links)"
    log.info("Cinema bot starting. MovieGlu in-chat showtimes: %s", mg)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
