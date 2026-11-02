"""Access to the Monitor-owned `users` collection (project owner, 2026-10-04: Authentication; logout
revocation, 2026-10-05). An account is created only by scripts/seed_user.py — there is no register or
user-management endpoint, and nothing here adds one. The one write this repository offers
(`record_logout`) sets a single timestamp used only to make a logout immediate (app/services/auth.py);
it is never an account's username, password or name."""
from datetime import datetime
from typing import Protocol

from app.repositories.base import Document


class UserAdapter(Protocol):
    def find_by_username(self, username: str) -> Document | None: ...

    def find_by_id(self, user_id: str) -> Document | None: ...

    def set_sessions_invalid_before(self, user_id: str, at: datetime) -> None: ...


class UserRepository:
    def __init__(self, adapter: UserAdapter) -> None:
        self._adapter = adapter

    def find_by_username(self, username: str) -> Document | None:
        return self._adapter.find_by_username(username)

    def find_by_id(self, user_id: str) -> Document | None:
        return self._adapter.find_by_id(user_id)

    def record_logout(self, user_id: str, at: datetime) -> None:
        self._adapter.set_sessions_invalid_before(user_id, at)
