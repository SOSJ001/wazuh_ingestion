import os
import sqlite3

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# Same DB path as wazuh_ingestion.py
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.environ.get("WAZUH_DB_PATH", os.path.join(_SCRIPT_DIR, "wazuh_alerts.db"))

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/alerts")
def get_alerts():
    """Return unverified alerts for the live dashboard."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    rows = cur.execute(
        "SELECT * FROM alerts WHERE is_verified = 0 ORDER BY timestamp DESC"
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


@app.get("/alerts/verified")
def get_verified_alerts():
    """Return human-verified alerts."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    rows = cur.execute(
        "SELECT * FROM alerts WHERE is_verified = 1 ORDER BY timestamp DESC"
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


@app.post("/verify/{alert_id}")
def verify_alert(alert_id: str):
    """Mark an alert as human-verified."""
    conn = sqlite3.connect(DATABASE)
    cur = conn.cursor()
    cur.execute("UPDATE alerts SET is_verified = 1 WHERE id = ?", (alert_id,))
    conn.commit()
    updated = cur.rowcount
    conn.close()
    if updated == 0:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"status": "success", "id": alert_id}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
