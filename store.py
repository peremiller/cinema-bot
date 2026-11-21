"""Tiny JSON-file store for per-chat location preferences."""
import json
import os
import re
import threading
import time
import tempfile

import config

_lock = threading.Lock()


class StoreCorruptedError(RuntimeError):
    """Existing preferences could not be read; do not replace them with defaults."""


def _load(*, for_write: bool = False) -> dict:
    try:
        with open(config.STORE_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return {}
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        if for_write:
            raise StoreCorruptedError("Saved cinema preferences are unreadable; write refused.") from exc
        return {}
    if not isinstance(data, dict):
        if for_write:
            raise StoreCorruptedError("Saved cinema preferences must be a JSON object; write refused.")
        return {}
    return data


def _save(data: dict) -> None:
    """Write a complete new snapshot before atomically replacing existing data."""
    os.makedirs(config.DATA_DIR, exist_ok=True)
    tmp = None
    try:
        # Unique same-directory temporary files avoid clobbering another writer's
        # draft file; a failed serialization/replacement must preserve the original.
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=config.DATA_DIR,
            prefix=".locations-", suffix=".tmp", delete=False,
        ) as fh:
            tmp = fh.name
            json.dump(data, fh, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, config.STORE_PATH)
    finally:
        if tmp is not None and os.path.exists(tmp):
            os.unlink(tmp)


def get_location(chat_id: int):
    """Return the saved location dict for a chat, or None."""
    with _lock:
        rec = _load().get(str(chat_id))
        return rec if isinstance(rec, dict) else None


def set_location(chat_id: int, location: dict) -> None:
    with _lock:
        data = _load(for_write=True)
        key = str(chat_id)
        existing = data.get(key)
        # A malformed saved record must never be silently replaced with a new
        # location. Leave its bytes intact so the owner can recover the data.
        if key in data and not isinstance(existing, dict):
            raise StoreCorruptedError("Saved chat preferences are not a JSON object; write refused.")
        existing = existing or {}
        # Preserve a daily-digest subscription across location updates.
        if existing.get("daily"):
            location = {**location, "daily": existing["daily"]}
        # Stamp when this position was captured, so we can tell the user when
        # we're working off an old one-time share.
        location = {**location, "updated": time.time()}
        data[key] = location
        _save(data)


def subscribe(chat_id: int, hhmm: str) -> bool:
    """Save a daily-digest time (HH:MM). Returns False if no location yet."""
    with _lock:
        data = _load(for_write=True)
        rec = data.get(str(chat_id))
        if not isinstance(rec, dict) or not rec:
            return False
        rec["daily"] = hhmm
        data[str(chat_id)] = rec
        _save(data)
        return True


def unsubscribe(chat_id: int) -> None:
    with _lock:
        data = _load(for_write=True)
        rec = data.get(str(chat_id))
        if isinstance(rec, dict) and "daily" in rec:
            rec.pop("daily")
            _save(data)


def all_subscriptions() -> list:
    """Return [(chat_id, 'HH:MM', location_record), ...] for daily subscribers."""
    with _lock:
        data = _load()
    # One malformed record must not stop everyone else's scheduled digest.
    # This is a read-only filter: keep all unknown entries on disk for recovery.
    subscriptions = []
    for cid, rec in data.items():
        if not isinstance(rec, dict):
            continue
        daily = rec.get("daily")
        if not isinstance(daily, str) or not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", daily):
            continue
        try:
            chat_id = int(cid)
        except (TypeError, ValueError):
            continue
        subscriptions.append((chat_id, daily, rec))
    return subscriptions
