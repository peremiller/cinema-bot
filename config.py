"""Configuration loaded from environment (.env)."""
import os

from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TMDB_API_KEY = os.getenv("TMDB_API_KEY", "").strip()
DEFAULT_LOCATION = os.getenv("DEFAULT_LOCATION", "").strip()

# A v4 token is a long JWT starting with "eyJ"; a v3 key is a short hex string.
TMDB_IS_V4_TOKEN = TMDB_API_KEY.startswith("eyJ")

# MovieGlu (optional)
MOVIEGLU_API_BASE = os.getenv("MOVIEGLU_API_BASE", "https://api-gate2.movieglu.com").strip()
MOVIEGLU_CLIENT = os.getenv("MOVIEGLU_CLIENT", "").strip()
MOVIEGLU_API_KEY = os.getenv("MOVIEGLU_API_KEY", "").strip()
MOVIEGLU_AUTHORIZATION = os.getenv("MOVIEGLU_AUTHORIZATION", "").strip()
MOVIEGLU_TERRITORY = os.getenv("MOVIEGLU_TERRITORY", "").strip()
MOVIEGLU_API_VERSION = os.getenv("MOVIEGLU_API_VERSION", "v201").strip()

MOVIEGLU_ENABLED = all(
    [MOVIEGLU_CLIENT, MOVIEGLU_API_KEY, MOVIEGLU_AUTHORIZATION, MOVIEGLU_TERRITORY]
)

# Where per-chat location preferences are stored.
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
STORE_PATH = os.path.join(DATA_DIR, "locations.json")


def require(value: str, name: str) -> str:
    if not value:
        raise SystemExit(
            f"Missing required config: {name}. Copy .env.example to .env and fill it in."
        )
    return value
