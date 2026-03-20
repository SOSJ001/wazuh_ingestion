import asyncio
import hmac
import os
import sqlite3
import time
import hashlib
import json
from datetime import datetime, timezone
import requests
import urllib3
from pydantic import BaseModel, ValidationError

# Load .env from this script's folder so it's always found
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except ImportError:
    pass

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Manager API (port 55000) - for connectivity check
WAZUH_IP = os.environ.get("WAZUH_IP", "192.168.56.103")
USER = os.environ.get("WAZUH_USER", "")
PASS = os.environ.get("WAZUH_PASS", "")
# Indexer (port 9200, reached via SSH tunnel). OVA often uses admin/admin.
INDEXER_USER = os.environ.get("WAZUH_INDEXER_USER", "admin")
INDEXER_PASS = os.environ.get("WAZUH_INDEXER_PASS", "admin")
# SSH tunnel to server (indexer is on server localhost only). OVA: wazuh-user / wazuh
SSH_USER = os.environ.get("WAZUH_SSH_USER", "")
SSH_PASS = os.environ.get("WAZUH_SSH_PASS", "")
SSH_KEY = os.environ.get("WAZUH_SSH_KEY", "")
SSH_KNOWN_HOSTS_PATH = os.environ.get("WAZUH_SSH_KNOWN_HOSTS_PATH", os.path.expanduser("~/.ssh/known_hosts"))
SSH_HOST = WAZUH_IP
SSH_PORT = int(os.environ.get("WAZUH_SSH_PORT", "22"))
WAZUH_CA_CERT_PATH = os.environ.get("WAZUH_CA_CERT_PATH", "")
# Live ingestion: poll interval in seconds (default 30)
POLL_INTERVAL = int(os.environ.get("WAZUH_POLL_INTERVAL", "30"))
# SQLite system of record (default: wazuh_alerts.db in script directory)
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("WAZUH_DB_PATH", os.path.join(_SCRIPT_DIR, "wazuh_alerts.db"))
ALERT_HMAC_SECRET = os.environ.get("ALERT_HMAC_SECRET", "")
STATUS_PATH = os.environ.get("WAZUH_STATUS_PATH", os.path.join(_SCRIPT_DIR, "ingestion_status.json"))


class NormalizedAlert(BaseModel):
    id: str
    timestamp: str
    agent_name: str
    agent_id: str
    rule_level: int
    rule_description: str
    rule_id: str
    full_log: str
    log_hmac: str
    hmac_algo: str
    hmac_created_at: str


def _status_defaults():
    return {
        "last_poll_started_at": None,
        "last_poll_completed_at": None,
        "last_poll_status": "idle",
        "last_error": None,
        "last_inserted_count": 0,
        "last_validation_reject_count": 0,
    }


def _read_status():
    if not os.path.isfile(STATUS_PATH):
        return _status_defaults()
    try:
        with open(STATUS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                return _status_defaults()
            defaults = _status_defaults()
            defaults.update(data)
            return defaults
    except Exception:
        return _status_defaults()


def _write_status(**updates):
    status = _read_status()
    status.update(updates)
    with open(STATUS_PATH, "w", encoding="utf-8") as f:
        json.dump(status, f, indent=2)


def get_connection():
    """Authenticate to Wazuh manager API via SSH tunnel; returns token or None."""
    print(f"Authenticating as {USER!r} to {WAZUH_IP} (via SSH tunnel) ...")
    try:
        token = asyncio.run(_authenticate_manager_via_tunnel())
        if token:
            print(f"Success! API token: {token[:20]}...")
            return token
        print("Failed to authenticate through manager API tunnel.")
    except Exception as e:
        print(f"Error: {e}")
    return None


def _init_db(conn):
    """Create alerts table if it does not exist."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id TEXT PRIMARY KEY,
            timestamp TEXT,
            agent_name TEXT,
            agent_id TEXT,
            rule_level INTEGER,
            rule_description TEXT,
            rule_id TEXT,
            full_log TEXT,
            log_hmac TEXT,
            hmac_algo TEXT,
            hmac_created_at TEXT DEFAULT (datetime('now')),
            is_verified INTEGER NOT NULL DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    _migrate_alerts_table(conn)
    conn.commit()


def _migrate_alerts_table(conn):
    """Add integrity columns for existing databases."""
    cols = {
        row[1]
        for row in conn.execute("PRAGMA table_info(alerts)").fetchall()
    }
    if "log_hmac" not in cols:
        conn.execute("ALTER TABLE alerts ADD COLUMN log_hmac TEXT")
    if "hmac_algo" not in cols:
        conn.execute("ALTER TABLE alerts ADD COLUMN hmac_algo TEXT")
    if "hmac_created_at" not in cols:
        conn.execute("ALTER TABLE alerts ADD COLUMN hmac_created_at TEXT")


def _compute_hmac(full_log):
    """Compute deterministic HMAC-SHA256 digest for a log string."""
    payload = (full_log or "").encode("utf-8")
    secret = ALERT_HMAC_SECRET.encode("utf-8")
    return hmac.new(secret, payload, hashlib.sha256).hexdigest()


def _get_full_log(raw):
    """Extract full log text from Wazuh alert; indexer may use full_log, data, or message."""
    log = raw.get("full_log")
    if isinstance(log, str) and log:
        return log
    log = raw.get("data")
    if isinstance(log, str) and log:
        return log
    if isinstance(log, dict):
        return log.get("log", log.get("message", "")) or ""
    log = raw.get("message") or raw.get("log")
    return log if isinstance(log, str) else ""


def _normalize_alert(raw):
    """Map Wazuh alert dict to a row tuple for alerts table. Returns None if id missing."""
    aid = raw.get("id")
    if not aid:
        return None
    ts = raw.get("@timestamp") or raw.get("timestamp") or ""
    agent = raw.get("agent") or {}
    rule = raw.get("rule") or {}
    full_log = _get_full_log(raw)
    normalized = NormalizedAlert(
        id=aid,
        timestamp=ts,
        agent_name=agent.get("name", ""),
        agent_id=agent.get("id", ""),
        rule_level=int(rule.get("level", 0)) if rule.get("level") is not None else 0,
        rule_description=rule.get("description", ""),
        rule_id=str(rule.get("id", "")) if rule.get("id") is not None else "",
        full_log=full_log,
        log_hmac=_compute_hmac(full_log),
        hmac_algo="HMAC-SHA256",
        hmac_created_at=datetime.now(timezone.utc).isoformat(),
    )
    return (
        normalized.id,
        normalized.timestamp,
        normalized.agent_name,
        normalized.agent_id,
        normalized.rule_level,
        normalized.rule_description,
        normalized.rule_id,
        normalized.full_log,
        normalized.log_hmac,
        normalized.hmac_algo,
        normalized.hmac_created_at,
    )


def _insert_alerts(conn, normalized_rows):
    """Insert rows into alerts table. Deduplication by primary key. Returns number of new rows inserted."""
    if not normalized_rows:
        return 0
    before = conn.total_changes
    conn.executemany(
        """INSERT OR IGNORE INTO alerts (
            id, timestamp, agent_name, agent_id, rule_level, rule_description, rule_id, full_log, log_hmac, hmac_algo, hmac_created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        normalized_rows,
    )
    conn.commit()
    return conn.total_changes - before


def _fetch_alerts_from_indexer(host, port, auth, timeout=15):
    """Query indexer _search; returns (True, list) or (False, None)."""
    url = f"https://{host}:{port}/wazuh-alerts*/_search"
    body = {"size": 10, "sort": [{"@timestamp": {"order": "desc"}}]}
    try:
        r = requests.post(url, json=body, auth=auth, verify=WAZUH_CA_CERT_PATH, timeout=timeout)
        if r.status_code != 200:
            print(f"Indexer request status {r.status_code}: {r.text[:200]}")
            return False, None
        hits = r.json().get("hits", {}).get("hits", [])
        return True, [h.get("_source", {}) for h in hits]
    except Exception as exc:
        print(f"Indexer request error: {exc}")
        return False, None


async def _tunnel_and_fetch(auth):
    """SSH tunnel via asyncssh, then fetch alerts from indexer. Returns (ok, alerts) or raises."""
    import asyncssh
    kwargs = {
        "host": SSH_HOST,
        "port": SSH_PORT,
        "username": SSH_USER,
        "known_hosts": SSH_KNOWN_HOSTS_PATH,
    }
    if SSH_KEY and os.path.isfile(SSH_KEY):
        kwargs["client_keys"] = [SSH_KEY]
    if SSH_PASS:
        kwargs["password"] = SSH_PASS
    conn = await asyncio.wait_for(asyncssh.connect(**kwargs), timeout=15)
    try:
        listener = await conn.forward_local_port("127.0.0.1", 0, "127.0.0.1", 9200)
        if listener is None:
            return False, None
        port = listener.get_port()
        ok, alerts = await asyncio.to_thread(
            _fetch_alerts_from_indexer, "127.0.0.1", port, auth
        )
        return ok, alerts
    finally:
        conn.close()


async def _authenticate_manager_via_tunnel():
    """Authenticate to manager API on 55000 through SSH tunnel."""
    import asyncssh
    kwargs = {
        "host": SSH_HOST,
        "port": SSH_PORT,
        "username": SSH_USER,
        "known_hosts": SSH_KNOWN_HOSTS_PATH,
    }
    if SSH_KEY and os.path.isfile(SSH_KEY):
        kwargs["client_keys"] = [SSH_KEY]
    if SSH_PASS:
        kwargs["password"] = SSH_PASS

    conn = await asyncio.wait_for(asyncssh.connect(**kwargs), timeout=15)
    try:
        listener = await conn.forward_local_port("127.0.0.1", 0, "127.0.0.1", 55000)
        if listener is None:
            return None
        port = listener.get_port()
        url = f"https://localhost:{port}/security/user/authenticate"
        r = await asyncio.to_thread(
            requests.get, url, auth=(USER, PASS), verify=WAZUH_CA_CERT_PATH, timeout=15
        )
        if r.status_code == 200:
            return r.json()["data"]["token"]
        try:
            print(f"Auth failed. Status: {r.status_code} Response: {r.json()}")
        except Exception:
            print(f"Auth failed. Status: {r.status_code} Response: {r.text[:200]}")
        return None
    finally:
        conn.close()


def get_recent_alerts(_token):
    """Fetch recent alerts from indexer via SSH tunnel and write to SQLite."""
    auth = (INDEXER_USER, INDEXER_PASS)
    print("Fetching recent security alerts (SSH tunnel to indexer)...")
    _write_status(
        last_poll_started_at=datetime.now(timezone.utc).isoformat(),
        last_poll_status="running",
        last_error=None,
    )
    try:
        ok, alerts = asyncio.run(_tunnel_and_fetch(auth))
        if ok:
            print(f"Success! Fetched {len(alerts)} raw alerts.")
            rows = []
            reject_count = 0
            for a in alerts:
                try:
                    row = _normalize_alert(a)
                    if row is not None:
                        rows.append(row)
                except ValidationError as exc:
                    reject_count += 1
                    print(f"Schema validation rejected alert: {exc.errors()[:1]}")
            conn = sqlite3.connect(DB_PATH)
            try:
                _init_db(conn)
                inserted = _insert_alerts(conn, rows)
                print(f"{inserted} new alerts written to database.")
                _write_status(
                    last_poll_completed_at=datetime.now(timezone.utc).isoformat(),
                    last_poll_status="ok",
                    last_error=None,
                    last_inserted_count=inserted,
                    last_validation_reject_count=reject_count,
                )
            finally:
                conn.close()
            return
        msg = "Indexer request failed (check indexer connectivity, TLS trust, and credentials)."
        print(msg)
        _write_status(
            last_poll_completed_at=datetime.now(timezone.utc).isoformat(),
            last_poll_status="error",
            last_error=msg,
            last_inserted_count=0,
        )
    except Exception as e:
        print(f"SSH tunnel or indexer failed: {e}")
        _write_status(
            last_poll_completed_at=datetime.now(timezone.utc).isoformat(),
            last_poll_status="error",
            last_error=str(e),
            last_inserted_count=0,
        )


def start_live_ingestion(token):
    """Run ingestion in a loop so new threats are captured every POLL_INTERVAL seconds. Stop with Ctrl+C."""
    print("Integration Layer is now LIVE. Monitoring for threats...")
    try:
        while True:
            get_recent_alerts(token)
            print(f"Waiting {POLL_INTERVAL} seconds for next sync...")
            time.sleep(POLL_INTERVAL)
    except KeyboardInterrupt:
        print("\nLive ingestion stopped by user.")


if __name__ == "__main__":
    if not USER or not PASS:
        print("Set WAZUH_USER and WAZUH_PASS in .env.")
        exit(1)
    if not SSH_USER or not (SSH_PASS or (SSH_KEY and os.path.isfile(SSH_KEY))):
        print("Set WAZUH_SSH_USER and WAZUH_SSH_PASS (or WAZUH_SSH_KEY) in .env.")
        exit(1)
    if not WAZUH_CA_CERT_PATH or not os.path.isfile(WAZUH_CA_CERT_PATH):
        print("Set WAZUH_CA_CERT_PATH in .env and ensure the certificate file exists.")
        exit(1)
    if not SSH_KNOWN_HOSTS_PATH or not os.path.isfile(SSH_KNOWN_HOSTS_PATH):
        print("Set WAZUH_SSH_KNOWN_HOSTS_PATH in .env and ensure the known_hosts file exists.")
        exit(1)
    if not ALERT_HMAC_SECRET:
        print("Set ALERT_HMAC_SECRET in .env.")
        exit(1)
    token = get_connection()
    if token:
        start_live_ingestion(token)
