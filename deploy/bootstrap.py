"""Seed missing configuration and an optional initial user; never overwrite team data."""
import json
import os
from pathlib import Path
from pymongo import MongoClient
from app.settings import Settings
from app.services.auth import hash_password

s = Settings.from_env()
if len(s.session_secret) < 32 or s.session_secret.startswith("dev-only"):
    raise RuntimeError("MORNITOR_SESSION_SECRET must be a random secret of at least 32 characters")
db = MongoClient(s.config_db_uri)[s.config_db_name]
configuration = json.loads(Path("portal-config.json").read_text(encoding="utf-8"))
if not isinstance(configuration, list):
    raise RuntimeError("Expected the approved PS configuration array")
for record in configuration:
    db.ps_requirements.update_one({"psCode": record["psCode"]}, {"$setOnInsert": record}, upsert=True)
readiness = json.loads(Path("portal-readiness.json").read_text(encoding="utf-8"))
db.ps_requirements.update_one({"configType": "generationReadiness"}, {"$setOnInsert": readiness}, upsert=True)
username = os.environ.get("PORTAL_ADMIN_USERNAME", "admin")
password = os.environ.get("PORTAL_ADMIN_PASSWORD", "")
users = MongoClient(s.results_db_uri)[s.results_db_name].users
if not users.find_one({"username": username}):
    if len(password) < 12:
        raise RuntimeError("Set PORTAL_ADMIN_PASSWORD (12+ characters) for the first startup")
    users.insert_one({"username": username, "name": os.environ.get("PORTAL_ADMIN_NAME", "Portal Administrator"),
                      "passwordHash": hash_password(password)})
print("Portal configuration and account ready (existing records preserved)")

