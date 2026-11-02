"""Docker packaging (project owner 2026-09-26): backend + frontend images and compose, for a MongoDB on this computer.

Static checks that keep the Docker files in step with the application's settings and API paths. Building and
running the images is checked by hand (docs/TESTING.md §0.1). No database is involved.
"""
import re
from pathlib import Path

import yaml

from app.main import create_app

ROOT = Path(__file__).resolve().parents[2]
BACKEND, FRONTEND = ROOT / "backend", ROOT / "frontend"
COMPOSE = yaml.safe_load((ROOT / "compose.yaml").read_text())
SERVICES = COMPOSE["services"]
SETTINGS_VARS = set(re.findall(r'env\("(MORNITOR_\w+)"', (BACKEND / "app" / "settings.py").read_text()))
PORT_VARS = {"MORNITOR_WEB_PORT", "MORNITOR_API_PORT"}   # read by compose only
CREDENTIALS = re.compile(r"\w+://[^\s/@:]+:[^\s/@]+@")


def env_example():
    """Every VAR=value line of .env.example, commented out or not."""
    text = (ROOT / ".env.example").read_text()
    return dict(re.findall(r"^#?\s*(MORNITOR_\w+)=(.*)$", text, re.M))


def text_of(*parts):
    return ROOT.joinpath(*parts).read_text()


# --- settings: what the image is given at run time --------------------------------------------------------
def test_the_settings_read_are_the_known_ones():
    assert SETTINGS_VARS == {
        "MORNITOR_DB_URI", "MORNITOR_DB_NAME", "MORNITOR_CONFIG_DB_URI", "MORNITOR_CONFIG_DB_NAME",
        "MORNITOR_RESULTS_DB_URI", "MORNITOR_RESULTS_DB_NAME", "MORNITOR_CORS_ORIGINS", "MORNITOR_YEAR_OFFSET",
        "MORNITOR_SESSION_SECRET", "MORNITOR_SESSION_TTL_SECONDS", "MORNITOR_COOKIE_SECURE"}


def test_env_example_documents_every_setting_and_nothing_else():
    assert set(env_example()) == SETTINGS_VARS | PORT_VARS


def test_env_example_and_compose_hold_no_credentials():
    for name in (".env.example", "compose.yaml"):
        assert not CREDENTIALS.search(text_of(name)), name


def test_the_env_file_is_never_committed_or_built_into_an_image():
    ignored = text_of(".gitignore").splitlines()
    assert ".env" in ignored and "!.env.example" in ignored
    for part in ("backend", "frontend"):
        assert ".env" in text_of(part, ".dockerignore").splitlines(), part


# --- a MongoDB on this computer ------------------------------------------------------------------------------
def test_the_backend_reaches_a_database_on_this_computer_by_default():
    backend = SERVICES["backend"]
    assert backend["environment"]["MORNITOR_DB_URI"] == "${MORNITOR_DB_URI:-mongodb://host.docker.internal:27017}"
    assert env_example()["MORNITOR_DB_URI"] == "mongodb://host.docker.internal:27017"
    assert "host.docker.internal:host-gateway" in backend["extra_hosts"]


def test_the_default_database_name_is_the_applications():
    assert SERVICES["backend"]["environment"]["MORNITOR_DB_NAME"] == "${MORNITOR_DB_NAME:-mornitor_source}"
    assert "MORNITOR_DB_NAME\", \"mornitor_source\"" in text_of("backend", "app", "settings.py")


def test_optional_settings_come_only_from_the_env_file():
    """Settings.from_env falls back to the source database only when a variable is unset: compose must never
    pass an optional one as an empty string."""
    backend = SERVICES["backend"]
    assert set(backend["environment"]) == {"MORNITOR_DB_URI", "MORNITOR_DB_NAME"}
    assert all(not re.search(r":-\}", value) for value in backend["environment"].values())
    assert backend["env_file"] == [{"path": ".env", "required": False}]


# --- images and wiring ---------------------------------------------------------------------------------------
def test_ports_are_published_on_this_computer_only():
    """The API has no authentication (SRS §51 TBD)."""
    for name, service in SERVICES.items():
        assert service["ports"] and all(p.startswith("127.0.0.1:") for p in service["ports"]), name


def test_the_backend_image_serves_the_app_where_nginx_forwards_to():
    dockerfile = text_of("backend", "Dockerfile")
    assert 'CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]' in dockerfile
    assert SERVICES["backend"]["ports"] == ["127.0.0.1:${MORNITOR_API_PORT:-8000}:8000"]
    assert "proxy_pass http://backend:8000;" in text_of("frontend", "nginx.conf")
    assert SERVICES["frontend"]["depends_on"] == ["backend"]


def test_the_backend_image_installs_the_tested_versions_and_runs_as_non_root():
    dockerfile = text_of("backend", "Dockerfile")
    assert "pip install --no-cache-dir -r requirements.txt -c requirements-dev.lock.txt" in dockerfile
    assert re.search(r"^USER mornitor$", dockerfile, re.M)
    assert not re.search(r"^(ENV|ARG) MORNITOR_", dockerfile, re.M)       # no database built into the image


def test_nginx_serves_the_app_and_forwards_the_api():
    conf = text_of("frontend", "nginx.conf")
    assert "location /api/ {" in conf
    assert "try_files $uri $uri/ /index.html;" in conf                       # client-side routes
    assert 'import.meta.env.VITE_API_BASE_URL ?? "/api"' in text_of("frontend", "src", "api", "endpoints.js")
    assert not re.search(r"^(ENV|ARG) VITE_", text_of("frontend", "Dockerfile"), re.M)   # same origin: /api


def test_every_api_route_is_under_the_forwarded_prefix():
    paths = create_app().openapi()["paths"]
    assert paths and all(p.startswith("/api/") for p in paths)
