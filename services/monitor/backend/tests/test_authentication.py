"""Authentication (project owner, 2026-10-04; logout revocation + cookie Secure + PBKDF2 iterations, 2026-10-05
findings #2/#4): a signed, time-limited, HttpOnly session cookie. No register endpoint and no user-management
API exist — an account is made only by scripts/seed_user.py (never tested here: this file exercises
AuthService/the HTTP routes directly against an in-memory `users` stand-in).

Covered: login success / wrong password / unknown username, GET /api/auth/me with and without a session, logout
(including that it revokes the token itself, not only the browser's cookie — a captured token replayed after
logout is 401 everywhere, and every open token of the account is revoked, not only the one used to log out),
an invalid or expired cookie, a review POST refused without a session (401) and accepted with one, that the
identity recorded on a real review is exactly the signed-in one (never a name the client could send itself),
the cookie's Secure flag following settings, and that raising the PBKDF2 iteration count does not break an
existing, lower-iteration password hash.
"""
import copy

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_auth_service, get_service
from app.main import create_app
from app.models.auth import AuthenticatedUser
from app.repositories.auth import UserRepository
from app.repositories.monitoring_results import MonitoringResultRepository
from app.services.auth import AuthService, hash_password, verify_password
from app.settings import Settings
from tests.support.fixtures import GENERATION_READINESS, make_service
from tests.support.memory_store import InMemoryMonitoringResultAdapter, InMemoryUserAdapter

USERNAME, PASSWORD, NAME = "reviewer1", "correct horse battery staple", "ผู้ตรวจทดสอบ"
REVIEW = "/api/monitor/ps/{}/review"


def auth_service(users=None, ttl_seconds=8 * 3600, secret="test-secret"):
    docs = users if users is not None else {
        USERNAME: {"_id": "u1", "username": USERNAME, "name": NAME, "passwordHash": hash_password(PASSWORD)},
    }
    return AuthService(UserRepository(InMemoryUserAdapter(docs)), secret, ttl_seconds)


def prepared(data):
    data["ps_requirements"].append(copy.deepcopy(GENERATION_READINESS))
    return data


def client_for(data=None, auth=None, ttl_seconds=8 * 3600):
    """A full app: real auth routes (get_auth_service overridden with an in-memory `users` store) and a real
    monitoring service over the standard fixtures, so a review posted after a real login is persisted for real."""
    auth = auth or auth_service(ttl_seconds=ttl_seconds)
    adapter = InMemoryMonitoringResultAdapter()
    service, _ = make_service(prepared(data) if data is not None else prepared(copy_base()), results=MonitoringResultRepository(adapter))
    app = create_app()
    app.dependency_overrides[get_service] = lambda: service
    app.dependency_overrides[get_auth_service] = lambda: auth
    return TestClient(app), adapter


def copy_base():
    from tests.support.fixtures import base_data
    return base_data()


# --- login -------------------------------------------------------------------------------------------------
def test_login_succeeds_and_sets_a_session_cookie():
    c, _ = client_for()
    r = c.post("/api/auth/login", json={"username": USERNAME, "password": PASSWORD})
    assert r.status_code == 200 and r.json() == {"name": NAME}
    assert "mornitor_session" in r.cookies


def test_login_with_the_wrong_password_is_401_and_sets_no_cookie():
    c, _ = client_for()
    r = c.post("/api/auth/login", json={"username": USERNAME, "password": "not-the-password"})
    assert r.status_code == 401 and "mornitor_session" not in r.cookies


def test_login_with_an_unknown_username_is_401():
    c, _ = client_for()
    r = c.post("/api/auth/login", json={"username": "nobody", "password": PASSWORD})
    assert r.status_code == 401


def test_the_401_detail_never_says_which_of_username_or_password_was_wrong():
    c, _ = client_for()
    wrong_user = c.post("/api/auth/login", json={"username": "nobody", "password": PASSWORD}).json()
    wrong_pass = c.post("/api/auth/login", json={"username": USERNAME, "password": "x"}).json()
    assert wrong_user == wrong_pass == {"detail": "Invalid username or password"}


# --- /api/auth/me --------------------------------------------------------------------------------------------
def test_me_without_a_session_is_401():
    c, _ = client_for()
    assert c.get("/api/auth/me").status_code == 401


def test_me_after_login_returns_the_signed_in_name():
    c, _ = client_for()
    c.post("/api/auth/login", json={"username": USERNAME, "password": PASSWORD})
    r = c.get("/api/auth/me")
    assert r.status_code == 200 and r.json() == {"name": NAME}


# --- logout --------------------------------------------------------------------------------------------------
def test_logout_clears_the_session_and_me_is_401_again():
    c, _ = client_for()
    c.post("/api/auth/login", json={"username": USERNAME, "password": PASSWORD})
    assert c.get("/api/auth/me").status_code == 200
    assert c.post("/api/auth/logout").status_code == 200
    assert c.get("/api/auth/me").status_code == 401


# --- invalid / expired session --------------------------------------------------------------------------------
def test_a_garbage_cookie_value_is_401():
    c, _ = client_for()
    c.cookies.set("mornitor_session", "not-a-real-token")
    assert c.get("/api/auth/me").status_code == 401


def test_a_cookie_signed_with_a_different_secret_is_401():
    c, _ = client_for(auth=auth_service(secret="test-secret"))
    other = auth_service(secret="a-different-secret")
    forged = other.issue_token(AuthenticatedUser(user_id="u1", name=NAME))
    c.cookies.set("mornitor_session", forged)
    assert c.get("/api/auth/me").status_code == 401


def test_an_expired_session_is_401():
    auth = auth_service(ttl_seconds=-1)   # issued already expired
    c, _ = client_for(auth=auth)
    c.post("/api/auth/login", json={"username": USERNAME, "password": PASSWORD})
    assert c.get("/api/auth/me").status_code == 401


# --- reviews require a session, and record the real identity --------------------------------------------------
def test_an_unauthenticated_post_review_is_401_and_nothing_is_saved():
    c, adapter = client_for()
    r = c.post(REVIEW.format("PS-03"), json={"status": "PASS"})
    assert r.status_code == 401 and adapter.docs == [] and "set_review" not in adapter.calls


def test_logging_out_then_posting_a_review_is_401_again():
    c, adapter = client_for()
    c.post("/api/auth/login", json={"username": USERNAME, "password": PASSWORD})
    c.post("/api/auth/logout")
    r = c.post(REVIEW.format("PS-03"), json={"status": "PASS"})
    assert r.status_code == 401 and adapter.docs == []


# --- Finding #2: logout revokes the token itself, not only the browser's copy of the cookie ------------------
def _captured_token(client):
    """The raw cookie value from the client's own jar, to replay by hand after a logout the jar itself would
    otherwise silently drop (httpx's cookie jar removes a cookie on seeing its Max-Age=0 deletion)."""
    return client.cookies.get("mornitor_session")


@pytest.mark.parametrize("ps_code, status", [("PS-03", "PASS"), ("PS-06", "PASS")])
def test_a_token_captured_before_logout_cannot_record_a_review_after_it(ps_code, status):
    c, adapter = client_for()
    c.post("/api/auth/login", json={"username": USERNAME, "password": PASSWORD})
    token = _captured_token(c)
    c.post("/api/auth/logout")
    before = copy.deepcopy(adapter.docs)
    r = c.post(REVIEW.format(ps_code), json={"status": status}, headers={"Cookie": f"mornitor_session={token}"})
    assert r.status_code == 401
    assert adapter.docs == before and adapter.docs == []   # MongoDB: unchanged


def test_a_token_captured_before_logout_cannot_read_me_after_it():
    c, _ = client_for()
    c.post("/api/auth/login", json={"username": USERNAME, "password": PASSWORD})
    token = _captured_token(c)
    c.post("/api/auth/logout")
    r = c.get("/api/auth/me", headers={"Cookie": f"mornitor_session={token}"})
    assert r.status_code == 401


def test_logout_revokes_every_open_token_of_the_account_not_only_the_one_used_to_log_out():
    """Two "tabs" logged in as the same account; logging out from one invalidates the other too — there is no
    per-token record, only a per-account cutoff (app/services/auth.py: AuthService.logout)."""
    auth = auth_service()
    tab1, _ = client_for(auth=auth)
    tab1.post("/api/auth/login", json={"username": USERNAME, "password": PASSWORD})
    token_tab1 = _captured_token(tab1)
    tab2, _ = client_for(auth=auth)   # same AuthService/users store, a separate client/cookie jar
    tab2.post("/api/auth/login", json={"username": USERNAME, "password": PASSWORD})
    tab2.post("/api/auth/logout")
    r = tab1.get("/api/auth/me", headers={"Cookie": f"mornitor_session={token_tab1}"})
    assert r.status_code == 401


def test_logging_in_again_after_logout_issues_a_token_that_works():
    c, _ = client_for()
    c.post("/api/auth/login", json={"username": USERNAME, "password": PASSWORD})
    c.post("/api/auth/logout")
    r = c.post("/api/auth/login", json={"username": USERNAME, "password": PASSWORD})
    assert r.status_code == 200
    assert c.get("/api/auth/me").status_code == 200   # the TestClient jar now holds the new, post-logout token


def test_recorded_by_on_a_real_review_is_the_signed_in_identity_never_a_client_supplied_name():
    c, adapter = client_for()
    c.post("/api/auth/login", json={"username": USERNAME, "password": PASSWORD})
    # the body cannot name a reviewer: only `status` is a field of ReviewRequest, extra keys are dropped
    r = c.post(REVIEW.format("PS-03"), json={"status": "PASS", "recordedBy": {"userId": "fake", "name": "ปลอม"}})
    assert r.status_code == 200
    by = r.json()["review"]["recordedBy"]
    assert by == {"userId": "u1", "name": NAME}
    assert adapter.docs[0]["review"]["recordedBy"] == {"userId": "u1", "name": NAME}


def test_a_review_still_follows_the_configured_ps_and_status_rules_when_authenticated():
    """Authentication adds who recorded a review; it changes nothing about which PS or status is allowed."""
    c, adapter = client_for()
    c.post("/api/auth/login", json={"username": USERNAME, "password": PASSWORD})
    assert c.post(REVIEW.format("PS-01"), json={"status": "PASS"}).status_code == 400   # PS-01 takes no review
    assert c.post(REVIEW.format("PS-03"), json={"status": "NOT-A-STATUS"}).status_code == 422
    assert adapter.docs == []


# --- password hashing (unit level) ------------------------------------------------------------------------------
def test_password_is_never_stored_as_plaintext():
    stored = hash_password(PASSWORD)
    assert PASSWORD not in stored and verify_password(PASSWORD, stored)


def test_each_hash_uses_a_fresh_random_salt_so_identical_passwords_differ():
    assert hash_password(PASSWORD) != hash_password(PASSWORD)


def test_verify_password_rejects_the_wrong_password_and_malformed_stored_values():
    stored = hash_password(PASSWORD)
    assert not verify_password("wrong", stored)
    assert not verify_password(PASSWORD, "not-a-valid-stored-value")
    assert not verify_password(PASSWORD, "")


def test_login_rejects_an_account_with_no_usable_password_hash():
    auth = auth_service(users={USERNAME: {"_id": "u1", "username": USERNAME, "name": NAME}})   # no passwordHash
    assert auth.login(USERNAME, PASSWORD) is None


# --- Finding #4: raising the iteration count does not break an existing, lower-iteration hash ------------------
def test_an_old_lower_iteration_hash_still_verifies_after_the_module_default_is_raised():
    import hashlib
    from app.services import auth as auth_module
    salt = b"\x00" * 16
    old_iterations = 100_000
    assert old_iterations != auth_module._PBKDF2_ITERATIONS   # a genuinely different, lower count
    digest = hashlib.pbkdf2_hmac("sha256", PASSWORD.encode("utf-8"), salt, old_iterations).hex()
    low_iteration_hash = f"pbkdf2_sha256${old_iterations}${salt.hex()}${digest}"
    assert verify_password(PASSWORD, low_iteration_hash)       # verified at ITS OWN 100_000, not the module default
    assert not verify_password("wrong-password", low_iteration_hash)


def test_the_stored_hash_always_carries_its_own_iteration_count():
    from app.services import auth as auth_module
    stored = hash_password(PASSWORD)
    assert stored.split("$")[1] == str(auth_module._PBKDF2_ITERATIONS)
    assert auth_module._PBKDF2_ITERATIONS >= 600_000   # current OWASP guidance for PBKDF2-HMAC-SHA256


# --- Finding #4: the session cookie's Secure flag follows settings, not a hardcoded value -----------------------
def test_login_does_not_mark_the_cookie_secure_by_default(monkeypatch):
    monkeypatch.delenv("MORNITOR_COOKIE_SECURE", raising=False)
    assert Settings.from_env().cookie_secure is False
    c, _ = client_for()
    r = c.post("/api/auth/login", json={"username": USERNAME, "password": PASSWORD})
    assert "secure" not in r.headers["set-cookie"].lower()


def test_login_marks_the_cookie_secure_when_configured_to(monkeypatch):
    monkeypatch.setenv("MORNITOR_COOKIE_SECURE", "true")
    assert Settings.from_env().cookie_secure is True
    c, _ = client_for()
    r = c.post("/api/auth/login", json={"username": USERNAME, "password": PASSWORD})
    assert "secure" in r.headers["set-cookie"].lower()
