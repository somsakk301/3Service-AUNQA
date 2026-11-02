"""Authentication (project owner, 2026-10-04; logout revocation, 2026-10-05): a user logs in with a username
and password, checked against the Monitor-owned `users` collection through UserRepository; the server then
issues a signed, time-limited session token that verifies back to an identity (app/models/auth.py).

The token carries its own expiry (`exp`) and issue time (`iat`); verifying it also reads the one piece of
server-side state that makes logout immediate: `users.sessionsInvalidBefore` (absent: every token for that
user is still good). Logging out sets it to the current time, so any token issued before "now" — including
the one just used, and any other still-open session of the same account — stops verifying right away. This is
the one write the running application makes to `users`; an account itself is still made only by
scripts/seed_user.py. Nothing here grants different people different permissions: any signed-in identity may
record a review.

Nothing here is a PS rule: this module owns no business vocabulary, only a login and a session token.
"""
import base64
import binascii
import hashlib
import hmac
import json
import secrets
import time
from datetime import datetime, timezone

from app.models.auth import AuthenticatedUser
from app.repositories.auth import UserRepository

_PBKDF2_ALGORITHM = "sha256"
# OWASP's current guidance for PBKDF2-HMAC-SHA256 (raised from 390_000, 2026-10-04). Each stored hash carries
# its own iteration count (see hash_password/verify_password below), so raising this never invalidates an
# existing password: an old hash keeps verifying at the count it was created with.
_PBKDF2_ITERATIONS = 600_000
_PASSWORD_PREFIX = "pbkdf2_sha256"


def hash_password(password: str, salt: bytes | None = None) -> str:
    """"pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>", with a fresh random salt unless one is given (so a
    test can make the output deterministic). Never plaintext, never reused across users by default."""
    salt = salt if salt is not None else secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(_PBKDF2_ALGORITHM, password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    return f"{_PASSWORD_PREFIX}${_PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Constant-time comparison; any malformed `stored` value (wrong shape, bad hex) fails closed."""
    try:
        algorithm, iterations, salt_hex, hash_hex = stored.split("$")
        if algorithm != _PASSWORD_PREFIX:
            return False
        digest = hashlib.pbkdf2_hmac(_PBKDF2_ALGORITHM, password.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations))
        return hmac.compare_digest(digest.hex(), hash_hex)
    except (ValueError, AttributeError):
        return False


def _sign(secret: str, payload: str) -> str:
    return hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


class AuthService:
    """`secret` signs the session token (settings.session_secret); `ttl_seconds` is how long a session stays
    valid after login (settings.session_ttl_seconds). The token is stateless (its own signed expiry), so
    nothing about a session is stored server-side beyond the `users` collection itself."""

    def __init__(self, users: UserRepository, secret: str, ttl_seconds: int) -> None:
        self._users = users
        self._secret = secret
        self._ttl_seconds = ttl_seconds

    @property
    def ttl_seconds(self) -> int:
        return self._ttl_seconds

    def login(self, username: str, password: str) -> AuthenticatedUser | None:
        """None for an unknown username, a wrong password, or an account with no usable password hash — the
        caller tells none of these apart (the same "invalid username or password" either way)."""
        doc = self._users.find_by_username(username)
        if doc is None or not isinstance(doc.get("passwordHash"), str):
            return None
        if not verify_password(password, doc["passwordHash"]):
            return None
        name = doc.get("name")
        return AuthenticatedUser(user_id=str(doc.get("_id")), name=name if isinstance(name, str) else username)

    def issue_token(self, user: AuthenticatedUser) -> str:
        """The identity, when it was issued (`iat`) and its expiry, base64url-encoded and HMAC-signed. `iat` is
        what lets a later logout revoke it (`verify_token` below) without a token store of its own. `iat` keeps
        sub-second precision on purpose (contrast `exp`, where whole seconds are plenty): a login and the
        logout that later revokes it are still two separate requests at least milliseconds apart, but a token
        truncated to whole seconds could tie with that cutoff and be revoked (or escape revocation) by
        coincidence of rounding rather than real ordering."""
        now = time.time()
        payload = json.dumps({"userId": user.user_id, "name": user.name, "iat": now, "exp": int(now) + self._ttl_seconds})
        encoded = base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii").rstrip("=")
        return f"{encoded}.{_sign(self._secret, encoded)}"

    def verify_token(self, token: str) -> AuthenticatedUser | None:
        """None for a missing/invalid signature, a malformed payload, an expired token, or one issued before
        the account's last logout (`users.sessionsInvalidBefore`) — the one point this needs a database read,
        since revocation cannot otherwise exist for a token that carries no server-side session of its own."""
        try:
            encoded, signature = token.split(".", 1)
        except ValueError:
            return None
        if not hmac.compare_digest(_sign(self._secret, encoded), signature):
            return None
        try:
            padded = encoded + "=" * (-len(encoded) % 4)
            payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")))
        except (ValueError, UnicodeDecodeError, binascii.Error):
            return None
        if not isinstance(payload, dict):
            return None
        expiry, issued_at = payload.get("exp"), payload.get("iat")
        user_id, name = payload.get("userId"), payload.get("name")
        if not isinstance(expiry, (int, float)) or time.time() > expiry:
            return None
        if not isinstance(issued_at, (int, float)):
            return None
        if not isinstance(user_id, str) or not isinstance(name, str):
            return None
        doc = self._users.find_by_id(user_id)
        if doc is None:
            return None
        invalid_before = doc.get("sessionsInvalidBefore")
        if isinstance(invalid_before, datetime):
            cutoff = invalid_before if invalid_before.tzinfo else invalid_before.replace(tzinfo=timezone.utc)
            if issued_at < cutoff.timestamp():
                return None
        return AuthenticatedUser(user_id=user_id, name=name)

    def logout(self, user_id: str) -> None:
        """Every token issued for this account up to now stops verifying immediately (`verify_token` above) —
        not just the one the caller happens to be holding, so another still-open session of the same account
        ends too. No per-token record is kept; the timestamp is all `users` gains."""
        self._users.record_logout(user_id, datetime.now(timezone.utc))
