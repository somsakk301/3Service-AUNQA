from functools import lru_cache

from fastapi import Cookie, Depends, HTTPException

from app.adapters.auth import MongoUserAdapter
from app.adapters.mongo import MongoConfigurationAdapter, MongoSourceDataAdapter, connect
from app.adapters.monitoring_results import MongoMonitoringResultAdapter
from app.models.auth import AuthenticatedUser
from app.references.runtime import RuntimeReferences
from app.repositories.auth import UserRepository
from app.repositories.configuration import ConfigurationRepository
from app.repositories.monitoring_results import MonitoringResultRepository
from app.repositories.source_data import SourceDataRepository
from app.services.auth import AuthService
from app.services.monitoring_service import MonitoringService
from app.settings import Settings

SESSION_COOKIE = "mornitor_session"


@lru_cache
def get_service() -> MonitoringService:
    s = Settings.from_env()
    configuration = ConfigurationRepository(MongoConfigurationAdapter(connect(s.config_db_uri, s.config_db_name)))
    source = SourceDataRepository(MongoSourceDataAdapter(connect(s.source_db_uri, s.source_db_name)))
    results = MonitoringResultRepository(MongoMonitoringResultAdapter(connect(s.results_db_uri, s.results_db_name)))
    return MonitoringService(configuration, source, RuntimeReferences(s.year_offset), results=results)


@lru_cache
def get_auth_service() -> AuthService:
    s = Settings.from_env()
    users = UserRepository(MongoUserAdapter(connect(s.results_db_uri, s.results_db_name)))
    return AuthService(users, s.session_secret, s.session_ttl_seconds)


def get_current_user(
    mornitor_session: str | None = Cookie(default=None),
    auth: AuthService = Depends(get_auth_service),
) -> AuthenticatedUser:
    """The session cookie's identity, or 401 when it is missing, invalid, expired or revoked by a logout. Used
    by every route that records who did something (the review routes); a route that only reads needs no
    identity at all."""
    user = auth.verify_token(mornitor_session) if mornitor_session else None
    if user is None:
        raise HTTPException(status_code=401, detail="Login required")
    return user


def get_current_user_optional(
    mornitor_session: str | None = Cookie(default=None),
    auth: AuthService = Depends(get_auth_service),
) -> AuthenticatedUser | None:
    """Like get_current_user, but None instead of 401 when there is no valid session — logout is the one route
    that still has to succeed (there is nothing left to revoke) even when the cookie it was sent is already
    missing, invalid or expired."""
    return auth.verify_token(mornitor_session) if mornitor_session else None
