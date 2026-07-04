"""Tiny JSON-file store for per-chat location preferences."""
import json
import os
import threading

import config

_lock = threading.Lock()


def _load() -> dict:
    try:
        with open(config.STORE_PATH, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save(data: dict) -> None:
    os.makedirs(config.DATA_DIR, exist_ok=True)
    tmp = config.STORE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    os.replace(tmp, config.STORE_PATH)


def get_location(chat_id: int):
    """Return the saved location dict for a chat, or None."""
    with _lock:
        return _load().get(str(chat_id))


def set_location(chat_id: int, location: dict) -> None:
    with _lock:
        data = _load()
        existing = data.get(str(chat_id)) or {}
        # Preserve a daily-digest subscription across location updates.
        if existing.get("daily"):
            location = {**location, "daily": existing["daily"]}
        data[str(chat_id)] = location
        _save(data)


def subscribe(chat_id: int, hhmm: str) -> bool:
    """Save a daily-digest time (HH:MM). Returns False if no location yet."""
    with _lock:
        data = _load()
        rec = data.get(str(chat_id))
        if not rec:
            return False
        rec["daily"] = hhmm
        data[str(chat_id)] = rec
        _save(data)
        return True


def unsubscribe(chat_id: int) -> None:
    with _lock:
        data = _load()
        rec = data.get(str(chat_id))
        if rec and "daily" in rec:
            rec.pop("daily")
            _save(data)


def all_subscriptions() -> list:
    """Return [(chat_id, 'HH:MM', location_record), ...] for daily subscribers."""
    with _lock:
        data = _load()
    return [(int(cid), rec["daily"], rec) for cid, rec in data.items() if rec.get("daily")]
