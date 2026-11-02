"""MongoDB adapter for the Monitor-owned `users` collection (project owner, 2026-10-04: Authentication;
logout revocation, 2026-10-05). An account itself (username/password/name) is written only by
scripts/seed_user.py. `set_sessions_invalid_before` is the one write the running application makes here: a
single timestamp a logout sets so its token (and any other still-open one of the same account) stops
verifying immediately (app/services/auth.py) — never an account's own fields."""
from datetime import datetime
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from pymongo.database import Database
from pymongo.errors import PyMongoError

from app.adapters.mongo import source_error
from app.repositories.base import Document

USERS_COLLECTION = "users"


class MongoUserAdapter:
    def __init__(self, database: Database) -> None:
        self._db = database

    def find_by_username(self, username: str) -> Document | None:
        try:
            return self._db[USERS_COLLECTION].find_one({"username": username})
        except PyMongoError as exc:
            raise source_error(exc) from exc

    def find_by_id(self, user_id: str) -> Document | None:
        try:
            object_id = ObjectId(user_id)
        except (InvalidId, TypeError):
            return None   # a userId a token of ours never produces; fails closed rather than querying
        try:
            return self._db[USERS_COLLECTION].find_one({"_id": object_id})
        except PyMongoError as exc:
            raise source_error(exc) from exc

    def set_sessions_invalid_before(self, user_id: str, at: datetime) -> None:
        try:
            object_id = ObjectId(user_id)
        except (InvalidId, TypeError):
            return   # nothing to invalidate for an id that can never be a real account
        update: dict[str, Any] = {"$set": {"sessionsInvalidBefore": at}}
        try:
            self._db[USERS_COLLECTION].update_one({"_id": object_id}, update)
        except PyMongoError as exc:
            raise source_error(exc) from exc
