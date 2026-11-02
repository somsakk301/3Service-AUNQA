"""Verify a completed production job through the public Gateway.

This performs one explicit download, so the Generator creates one immutable
Document History version exactly as the web UI does.

Usage: python deploy/verify_completed_generation.py JOB_ID
"""
from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path
from zipfile import is_zipfile

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("job_id")
parser.add_argument("--base", default="http://localhost")
parser.add_argument(
    "--reuse-version",
    type=int,
    help="reuse a previously downloaded test artifact instead of creating another history version",
)
args = parser.parse_args()

env = dict(
    line.split("=", 1)
    for line in (ROOT / ".env").read_text(encoding="utf-8-sig").splitlines()
    if "=" in line and not line.startswith("#")
)
jar = CookieJar()
client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def request(path: str, data: dict | None = None, method: str | None = None):
    encoded = json.dumps(data).encode() if data is not None else None
    headers = {"Accept": "application/json"}
    if encoded is not None:
        headers.update({"Content-Type": "application/json", "Origin": args.base})
    req = urllib.request.Request(args.base + path, data=encoded, headers=headers, method=method)
    try:
        with client.open(req, timeout=60) as response:
            return response.status, response.read(), response.headers
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(), exc.headers


status, _, _ = request(
    "/api/auth/login",
    {"username": env["PORTAL_ADMIN_USERNAME"], "password": env["PORTAL_ADMIN_PASSWORD"]},
    "POST",
)
if status != 200:
    raise SystemExit(f"FAIL login HTTP {status}")

status, raw, _ = request(f"/api/generator/generate/{args.job_id}/status")
job = json.loads(raw or b"{}")
if status != 200 or job.get("status") != "completed":
    raise SystemExit(f"FAIL completed status HTTP {status}: {job}")
print("PASS completed job status is available after container restart")

if args.reuse_version is None:
    status, content, headers = request(f"/api/generator/generate/{args.job_id}/download")
    version = headers.get("X-Document-Version")
    if status != 200 or not version:
        raise SystemExit(f"FAIL download HTTP {status}: {content[:300]!r}")
    artifact = ROOT / "artifacts" / f"SAR_v{version}_{args.job_id}.docx"
    artifact.parent.mkdir(exist_ok=True)
    artifact.write_bytes(content)
else:
    version = str(args.reuse_version)
    artifact = ROOT / "artifacts" / f"SAR_v{version}_{args.job_id}.docx"
    if not artifact.exists():
        raise SystemExit(f"FAIL reusable artifact is missing: {artifact}")
    content = artifact.read_bytes()
if not content.startswith(b"PK") or not is_zipfile(artifact):
    raise SystemExit("FAIL downloaded result is not a valid DOCX package")
print(f"PASS public download produced valid DOCX version {version} ({len(content)} bytes)")

status, raw, _ = request("/api/generator/history")
history = json.loads(raw or b"[]")
versions = history.get("versions", []) if isinstance(history, dict) else history
if status != 200 or not any(
    isinstance(item, dict) and str(item.get("version")) == str(version)
    for item in versions
):
    raise SystemExit(f"FAIL downloaded version {version} missing from Document History")
print(f"PASS Document History contains version {version} for the completed job")
