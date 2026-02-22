import os
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from tmdbv3api import TMDb, Movie, TV


def _to_bool(value: str) -> bool:
    return value.strip().lower() in {'1', 'true', 't', 'yes', 'y', 'on'}


def _normalize_database_url(value: str) -> str:
    if '://' in value:
        return value
    return f"sqlite:///{value}"


def _read_env(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.getenv(name)
    if value is None:
        return default
    value = value.strip()
    return value if value else default


TMDB_API_KEY = _read_env('TMDB_API_KEY')
DATABASE_URL = _normalize_database_url(_read_env('DATABASE_URL', 'media_library.db'))
FLASK_DEBUG = _to_bool(_read_env('FLASK_DEBUG', 'false'))
SCANNER_MEDIA_ROOT = _read_env('SCANNER_MEDIA_ROOT', './media')
MEDIA_ROOT = _read_env('MEDIA_ROOT', SCANNER_MEDIA_ROOT)
TMDB_LANGUAGE = _read_env('TMDB_LANGUAGE', 'en')

ENGINE = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=ENGINE)

TMDB_CLIENT = TMDb()
TMDB_CLIENT.api_key = TMDB_API_KEY
TMDB_CLIENT.language = TMDB_LANGUAGE
MOVIE_API = Movie()
TV_API = TV()


def validate_required_config() -> None:
    missing = []
    if not TMDB_API_KEY:
        missing.append('TMDB_API_KEY')

    if missing:
        missing_str = ', '.join(missing)
        raise RuntimeError(
            f"Missing required environment variable(s): {missing_str}. "
            "Set them before starting the application."
        )
