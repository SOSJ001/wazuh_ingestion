import os
import sqlite3
import hmac
import hashlib
import base64
import json
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from dotenv import load_dotenv

# Same DB path as wazuh_ingestion.py
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_SCRIPT_DIR, ".env"))
DATABASE = os.environ.get("WAZUH_DB_PATH", os.path.join(_SCRIPT_DIR, "wazuh_alerts.db"))
ALERT_HMAC_SECRET = os.environ.get("ALERT_HMAC_SECRET", "")
API_JWT_SECRET = os.environ.get("API_JWT_SECRET", "")
AUTH_USER = os.environ.get("DASHBOARD_AUTH_USER", "admin")
AUTH_PASS = os.environ.get("DASHBOARD_AUTH_PASS", os.environ.get("WAZUH_PASS", ""))
TOKEN_TTL_SECONDS = int(os.environ.get("API_TOKEN_TTL_SECONDS", "28800"))
STATUS_PATH = os.environ.get("WAZUH_STATUS_PATH", os.path.join(_SCRIPT_DIR, "ingestion_status.json"))
POLL_INTERVAL = int(os.environ.get("WAZUH_POLL_INTERVAL", "30"))
WAZUH_CA_CERT_PATH = os.environ.get("WAZUH_CA_CERT_PATH", "")
WAZUH_SSH_KNOWN_HOSTS_PATH = os.environ.get("WAZUH_SSH_KNOWN_HOSTS_PATH", "")
security = HTTPBearer(auto_error=False)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _issue_token(username: str) -> str:
    now = int(datetime.now(timezone.utc).timestamp())
    payload = {"sub": username, "iat": now, "exp": now + TOKEN_TTL_SECONDS}
    header = {"alg": "HS256", "typ": "JWT"}
    header_part = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_part = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_part}.{payload_part}".encode("utf-8")
    sig = hmac.new(API_JWT_SECRET.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{header_part}.{payload_part}.{_b64url_encode(sig)}"


def _verify_bearer_token(token: str) -> dict:
    parts = token.split(".")
    if len(parts) != 3:
        raise HTTPException(status_code=401, detail="Invalid token format")
    if not API_JWT_SECRET:
        raise HTTPException(status_code=500, detail="Server auth is not configured")

    signing_input = f"{parts[0]}.{parts[1]}".encode("utf-8")
    expected_sig = hmac.new(
        API_JWT_SECRET.encode("utf-8"), signing_input, hashlib.sha256
    ).digest()
    try:
        token_sig = _b64url_decode(parts[2])
        payload = json.loads(_b64url_decode(parts[1]).decode("utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid token encoding") from exc

    if not hmac.compare_digest(expected_sig, token_sig):
        raise HTTPException(status_code=401, detail="Invalid token signature")

    exp = payload.get("exp")
    if exp is not None and isinstance(exp, (int, float)):
        now_ts = datetime.now(timezone.utc).timestamp()
        if now_ts >= float(exp):
            raise HTTPException(status_code=401, detail="Token expired")

    return payload


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> str:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Missing bearer token")

    payload = _verify_bearer_token(credentials.credentials)
    user = payload.get("sub") or payload.get("username")
    if not user or not isinstance(user, str):
        raise HTTPException(status_code=401, detail="Token missing user claim")
    return user


def _ensure_alert_columns() -> None:
    conn = sqlite3.connect(DATABASE)
    try:
        exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='alerts'"
        ).fetchone()
        if not exists:
            return
        cols = {
            row[1]
            for row in conn.execute("PRAGMA table_info(alerts)").fetchall()
        }
        if "verified_by" not in cols:
            conn.execute("ALTER TABLE alerts ADD COLUMN verified_by TEXT")
        if "verified_at" not in cols:
            conn.execute("ALTER TABLE alerts ADD COLUMN verified_at TEXT")
        conn.commit()
    finally:
        conn.close()


def _compute_hmac(full_log: str) -> str:
    payload = (full_log or "").encode("utf-8")
    secret = ALERT_HMAC_SECRET.encode("utf-8")
    return hmac.new(secret, payload, hashlib.sha256).hexdigest()


def _with_integrity_status(row_dict: dict) -> dict:
    checked_at = datetime.now(timezone.utc).isoformat()
    full_log = row_dict.get("full_log") or ""
    stored_hmac = row_dict.get("log_hmac")
    stored_algo = row_dict.get("hmac_algo")
    if not ALERT_HMAC_SECRET or not stored_hmac or stored_algo != "HMAC-SHA256":
        row_dict["integrity_status"] = "missing"
        row_dict["integrity_checked_at"] = checked_at
        return row_dict

    expected_hmac = _compute_hmac(full_log)
    row_dict["integrity_status"] = (
        "valid" if hmac.compare_digest(expected_hmac, str(stored_hmac)) else "invalid"
    )
    row_dict["integrity_checked_at"] = checked_at
    return row_dict


def _read_ingestion_status() -> dict:
    default = {
        "last_poll_started_at": None,
        "last_poll_completed_at": None,
        "last_poll_status": "unknown",
        "last_error": None,
        "last_inserted_count": 0,
        "last_validation_reject_count": 0,
    }
    if not os.path.isfile(STATUS_PATH):
        return default
    try:
        with open(STATUS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return default
        default.update(data)
        return default
    except Exception:
        return default


class LoginRequest(BaseModel):
    username: str
    password: str


@app.on_event("startup")
def _startup_migrations() -> None:
    _ensure_alert_columns()


@app.post("/auth/token")
def create_auth_token(payload: LoginRequest):
    if not API_JWT_SECRET:
        raise HTTPException(status_code=500, detail="Server auth is not configured")
    if not AUTH_PASS:
        raise HTTPException(status_code=500, detail="Auth password is not configured")
    if payload.username != AUTH_USER or payload.password != AUTH_PASS:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = _issue_token(payload.username)
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": TOKEN_TTL_SECONDS,
        "username": payload.username,
    }


@app.get("/alerts")
def get_alerts(_user: str = Depends(get_current_user)):
    """Return unverified alerts for the live dashboard."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    rows = cur.execute(
        "SELECT * FROM alerts WHERE is_verified = 0 ORDER BY timestamp DESC"
    ).fetchall()
    conn.close()
    return [_with_integrity_status(dict(row)) for row in rows]


@app.get("/alerts/verified")
def get_verified_alerts(_user: str = Depends(get_current_user)):
    """Return human-verified alerts."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    rows = cur.execute(
        "SELECT * FROM alerts WHERE is_verified = 1 ORDER BY timestamp DESC"
    ).fetchall()
    conn.close()
    return [_with_integrity_status(dict(row)) for row in rows]


@app.post("/verify/{alert_id}")
def verify_alert(alert_id: str, current_user: str = Depends(get_current_user)):
    """Mark an alert as human-verified."""
    conn = sqlite3.connect(DATABASE)
    cur = conn.cursor()
    cur.execute(
        "UPDATE alerts SET is_verified = 1, verified_by = ?, verified_at = datetime('now') WHERE id = ?",
        (current_user, alert_id),
    )
    conn.commit()
    updated = cur.rowcount
    conn.close()
    if updated == 0:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"status": "success", "id": alert_id}


@app.get("/system/health")
def get_system_health(current_user: str = Depends(get_current_user)):
    status = _read_ingestion_status()
    return {
        "api_status": "ok",
        "api_time": datetime.now(timezone.utc).isoformat(),
        "current_user": current_user,
        "ingestion": status,
    }


@app.get("/system/config")
def get_system_config(current_user: str = Depends(get_current_user)):
    return {
        "current_user": current_user,
        "poll_interval_seconds": POLL_INTERVAL,
        "security_mode": {
            "hmac_enabled": bool(ALERT_HMAC_SECRET),
            "bearer_required": True,
            "tls_verify_enabled": bool(WAZUH_CA_CERT_PATH),
            "ssh_host_verification_enabled": bool(WAZUH_SSH_KNOWN_HOSTS_PATH),
        },
        "paths": {
            "status_path": STATUS_PATH,
            "ca_cert_path": WAZUH_CA_CERT_PATH,
            "ssh_known_hosts_path": WAZUH_SSH_KNOWN_HOSTS_PATH,
        },
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
