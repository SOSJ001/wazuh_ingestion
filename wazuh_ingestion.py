import asyncio
import os
import sqlite3
import time
import requests
import urllib3

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
SSH_HOST = WAZUH_IP
SSH_PORT = int(os.environ.get("WAZUH_SSH_PORT", "22"))
# Live ingestion: poll interval in seconds (default 30)
POLL_INTERVAL = int(os.environ.get("WAZUH_POLL_INTERVAL", "30"))
# SQLite system of record (default: wazuh_alerts.db in script directory)
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("WAZUH_DB_PATH", os.path.join(_SCRIPT_DIR, "wazuh_alerts.db"))


def get_connection():
    """Authenticate to Wazuh manager API; returns token or None."""
    url = f"https://{WAZUH_IP}:55000/security/user/authenticate"
    print(f"Authenticating as {USER!r} to {WAZUH_IP} ...")
    try:
        r = requests.get(url, auth=(USER, PASS), verify=False)
        if r.status_code == 200:
            token = r.json()["data"]["token"]
            print(f"Success! API token: {token[:20]}...")
            return token
        print(f"Failed. Status: {r.status_code}")
        try:
            print(r.json())
        except Exception:
            print(r.text[:200])
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
            is_verified INTEGER NOT NULL DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()


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
    return (
        aid,
        ts,
        agent.get("name", ""),
        agent.get("id", ""),
        int(rule.get("level", 0)) if rule.get("level") is not None else 0,
        rule.get("description", ""),
        str(rule.get("id", "")) if rule.get("id") is not None else "",
        _get_full_log(raw),
    )


def _insert_alerts(conn, normalized_rows):
    """Insert rows into alerts table. Deduplication by primary key. Returns number of new rows inserted."""
    if not normalized_rows:
        return 0
    before = conn.total_changes
    conn.executemany(
        """INSERT OR IGNORE INTO alerts (
            id, timestamp, agent_name, agent_id, rule_level, rule_description, rule_id, full_log
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        normalized_rows,
    )
    conn.commit()
    return conn.total_changes - before


def _fetch_alerts_from_indexer(host, port, auth, timeout=15):
    """Query indexer _search; returns (True, list) or (False, None)."""
    url = f"https://{host}:{port}/wazuh-alerts*/_search"
    body = {"size": 10, "sort": [{"@timestamp": {"order": "desc"}}]}
    try:
        r = requests.post(url, json=body, auth=auth, verify=False, timeout=timeout)
        if r.status_code != 200:
            return False, None
        hits = r.json().get("hits", {}).get("hits", [])
        return True, [h.get("_source", {}) for h in hits]
    except Exception:
        return False, None


async def _tunnel_and_fetch(auth):
    """SSH tunnel via asyncssh, then fetch alerts from indexer. Returns (ok, alerts) or raises."""
    import asyncssh
    kwargs = {
        "host": SSH_HOST,
        "port": SSH_PORT,
        "username": SSH_USER,
        "known_hosts": None,
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


def get_recent_alerts(_token):
    """Fetch recent alerts from indexer via SSH tunnel and write to SQLite."""
    auth = (INDEXER_USER, INDEXER_PASS)
    print("Fetching recent security alerts (SSH tunnel to indexer)...")
    try:
        ok, alerts = asyncio.run(_tunnel_and_fetch(auth))
        if ok:
            print(f"Success! Fetched {len(alerts)} raw alerts.")
            rows = []
            for a in alerts:
                row = _normalize_alert(a)
                if row is not None:
                    rows.append(row)
            conn = sqlite3.connect(DB_PATH)
            try:
                _init_db(conn)
                inserted = _insert_alerts(conn, rows)
                print(f"{inserted} new alerts written to database.")
            finally:
                conn.close()
            return
        print("Indexer request failed (check WAZUH_INDEXER_USER and WAZUH_INDEXER_PASS in .env).")
    except Exception as e:
        print(f"SSH tunnel or indexer failed: {e}")


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
    token = get_connection()
    if token:
        start_live_ingestion(token)
