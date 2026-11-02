"""Start and follow one production generation job. This makes real Gemini calls.

Usage: python deploy/verify_generation_once.py --run
The script intentionally does not log out because Monitor logout revokes every
active session for the account.
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--run", action="store_true", help="acknowledge that this performs real Gemini requests")
parser.add_argument("--timeout", type=int, default=900)
args = parser.parse_args()
if not args.run:
    parser.error("--run is required because this check performs real Gemini requests")

env = dict(
    line.split("=", 1)
    for line in (ROOT / ".env").read_text(encoding="utf-8-sig").splitlines()
    if "=" in line and not line.startswith("#")
)
base = "http://localhost"
jar = CookieJar()
client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def request(path: str, data: dict | None = None, method: str | None = None):
    headers = {"Accept": "application/json"}
    encoded = None
    if data is not None:
        encoded = json.dumps(data).encode()
        headers.update({"Content-Type": "application/json", "Origin": base})
    req = urllib.request.Request(base + path, data=encoded, headers=headers, method=method)
    try:
        with client.open(req, timeout=30) as response:
            return response.status, json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            body = json.loads(raw)
        except Exception:
            body = {"raw": raw.decode(errors="replace")[:500]}
        return exc.code, body


status, _ = request(
    "/api/auth/login",
    {"username": env["PORTAL_ADMIN_USERNAME"], "password": env["PORTAL_ADMIN_PASSWORD"]},
    "POST",
)
if status != 200:
    raise SystemExit(f"Login failed: HTTP {status}")

status, curricula = request("/api/generator/curriculum")
if status != 200:
    raise SystemExit(f"Curriculum lookup failed: HTTP {status}: {curricula}")
items = curricula if isinstance(curricula, list) else curricula.get("curricula", [])
if isinstance(curricula, dict) and curricula.get("id"):
    items = [curricula]
if len(items) != 1:
    raise SystemExit(f"Expected exactly one curriculum, found {len(items)}")
curriculum_id = items[0].get("curriculum_id") or items[0].get("curriculumId") or items[0].get("id")
if not curriculum_id:
    raise SystemExit(f"Curriculum response has no id: {items[0]}")

status, body = request("/api/generator/generate", {"curriculum_id": curriculum_id}, "POST")
print("START", status, body, flush=True)
if status != 200:
    raise SystemExit(2)
job_id = body["job_id"]
deadline = time.time() + args.timeout
last = None
while time.time() < deadline:
    try:
        status, job = request(f"/api/generator/generate/{job_id}/status")
    except (TimeoutError, urllib.error.URLError) as exc:
        # A transient gateway/backend timeout must not abandon a job which is
        # still running in the background. Production code now moves Gemini
        # calls off the API event loop, but this also makes the verifier robust
        # during container startup or a brief network interruption.
        print(f"POLL RETRY {type(exc).__name__}", flush=True)
        time.sleep(3)
        continue
    if status != 200:
        print(f"POLL RETRY HTTP {status}", flush=True)
        time.sleep(3)
        continue
    snapshot = (job.get("status"), job.get("error"), len(job.get("criteria_progress") or []))
    if snapshot != last:
        print("JOB", job_id, snapshot, flush=True)
        last = snapshot
    if job.get("status") in {"completed", "failed"}:
        print("FINAL", json.dumps(job, ensure_ascii=False)[:5000], flush=True)
        raise SystemExit(0 if job.get("status") == "completed" else 2)
    time.sleep(3)
raise TimeoutError(f"Generation {job_id} did not finish within {args.timeout} seconds")
