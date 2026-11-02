"""Runtime settings. Infrastructure only: no PS configuration lives here."""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    source_db_uri: str
    source_db_name: str
    config_db_uri: str
    config_db_name: str
    results_db_uri: str
    results_db_name: str
    cors_origins: tuple[str, ...]
    year_offset: int  # runtime year -> the calendar of the stored years
    session_secret: str       # signs the session cookie (app/services/auth.py) — set a real value in production
    session_ttl_seconds: int  # how long a session stays valid after login
    cookie_secure: bool       # the session cookie's Secure flag — true once served over HTTPS, else the
                              # browser never sends it back and login silently never "sticks"

    @staticmethod
    def from_env() -> "Settings":
        env = os.environ.get
        uri, name = env("MORNITOR_DB_URI", "mongodb://localhost:27017"), env("MORNITOR_DB_NAME", "mornitor_source")
        origins = env("MORNITOR_CORS_ORIGINS", "http://localhost:5173")
        return Settings(
            source_db_uri=uri, source_db_name=name,
            # Configuration may live in a different database; defaults to the source one.
            config_db_uri=env("MORNITOR_CONFIG_DB_URI", uri), config_db_name=env("MORNITOR_CONFIG_DB_NAME", name),
            # Monitor-owned `monitoring_results` likewise; defaults to the source one. The `users` collection
            # (app/adapters/auth.py) lives in this same database: one more Monitor-owned collection, not a new
            # database to configure.
            results_db_uri=env("MORNITOR_RESULTS_DB_URI", uri), results_db_name=env("MORNITOR_RESULTS_DB_NAME", name),
            cors_origins=tuple(o.strip() for o in origins.split(",") if o.strip()),
            year_offset=int(env("MORNITOR_YEAR_OFFSET", "543")),
            # No safe default for production: MORNITOR_SESSION_SECRET must be set there, or every session
            # token is forgeable by anyone who reads this source. Local dev without it still works.
            session_secret=env("MORNITOR_SESSION_SECRET", "dev-only-insecure-secret-set-MORNITOR_SESSION_SECRET"),
            session_ttl_seconds=int(env("MORNITOR_SESSION_TTL_SECONDS", str(8 * 3600))),
            # Default false: today's deployment (compose.yaml, Vite dev) is plain HTTP, and a Secure cookie
            # would simply never come back over HTTP — login would silently stop working. Set true once a real
            # TLS front end serves the app.
            cookie_secure=env("MORNITOR_COOKIE_SECURE", "false").strip().lower() == "true",
        )
