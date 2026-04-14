#!/usr/bin/env python3
"""
Method A: measure indexer-to-middleware lag per alert.

Lag = hmac_created_at (normalization time in middleware) - timestamp (Wazuh @timestamp in DB).

Bounded roughly by WAZUH_POLL_INTERVAL plus SSH/HTTP/validation/HMAC overhead.
"""
from __future__ import annotations

import argparse
import csv
import os
import sqlite3
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _load_env() -> None:
    if load_dotenv:
        load_dotenv(_repo_root() / ".env")


def _default_db_path() -> str:
    return str(_repo_root() / "wazuh_alerts.db")


def parse_iso_utc(s: str | None) -> datetime | None:
    if not s or not str(s).strip():
        return None
    text = str(s).strip()
    if text.endswith("Z") or text.endswith("z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Report ingestion lag: hmac_created_at minus Wazuh timestamp (SQLite alerts)."
    )
    parser.add_argument(
        "--db",
        default=None,
        help="Path to SQLite DB (default: WAZUH_DB_PATH from .env or ./wazuh_alerts.db)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=500,
        help="Max rows to analyse (default: 500)",
    )
    parser.add_argument(
        "--csv",
        metavar="FILE",
        help="Write per-row results to CSV",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--verified",
        action="store_true",
        help="Only rows with is_verified = 1",
    )
    group.add_argument(
        "--unverified",
        action="store_true",
        help="Only rows with is_verified = 0",
    )
    args = parser.parse_args()

    _load_env()
    db_path = args.db or os.environ.get("WAZUH_DB_PATH") or _default_db_path()

    if not os.path.isfile(db_path):
        print(f"Database not found: {db_path}", file=sys.stderr)
        return 1

    poll_interval = os.environ.get("WAZUH_POLL_INTERVAL", "30")

    conditions = [
        "timestamp IS NOT NULL",
        "TRIM(timestamp) != ''",
        "hmac_created_at IS NOT NULL",
        "TRIM(hmac_created_at) != ''",
    ]
    if args.verified:
        conditions.append("is_verified = 1")
    elif args.unverified:
        conditions.append("is_verified = 0")

    where_sql = " AND ".join(conditions)
    sql = f"""
        SELECT id, timestamp, hmac_created_at, is_verified
        FROM alerts
        WHERE {where_sql}
        ORDER BY hmac_created_at DESC
        LIMIT ?
    """

    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(sql, (args.limit,)).fetchall()
    finally:
        conn.close()

    parsed: list[tuple[str, float, str, str]] = []
    parse_failures = 0
    negative_count = 0
    for row_id, ts_raw, hmac_raw, _verified in rows:
        ts = parse_iso_utc(ts_raw)
        hmac_ts = parse_iso_utc(hmac_raw)
        if ts is None or hmac_ts is None:
            parse_failures += 1
            continue
        lag = (hmac_ts - ts).total_seconds()
        if lag < 0:
            negative_count += 1
        parsed.append((row_id, lag, str(ts_raw), str(hmac_raw)))

    print("Metric: indexer event time (alerts.timestamp) -> middleware hmac_created_at (normalization).")
    print(f"DB: {db_path}")
    print(f"WAZUH_POLL_INTERVAL from env (reference): {poll_interval}s")
    print(f"Rows fetched (limit {args.limit}): {len(rows)}")
    print(f"Successfully parsed: {len(parsed)}  |  parse failures: {parse_failures}")
    if negative_count:
        print(f"Negative lag rows (possible clock skew): {negative_count}")

    non_negative = [p[1] for p in parsed if p[1] >= 0]
    all_lags = [p[1] for p in parsed]

    if args.csv and parsed:
        with open(args.csv, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(
                ["id", "lag_seconds", "timestamp_raw", "hmac_created_at_raw", "negative_lag"]
            )
            for row_id, lag, ts_r, h_r in parsed:
                w.writerow([row_id, f"{lag:.6f}", ts_r, h_r, "yes" if lag < 0 else "no"])
        print(f"Wrote CSV: {args.csv}")

    if not parsed:
        print("No rows to summarise.")
        return 0

    def stats_line(label: str, values: list[float]) -> None:
        if not values:
            print(f"{label}: (no values)")
            return
        print(
            f"{label}: n={len(values)}  min={min(values):.3f}s  max={max(values):.3f}s  "
            f"mean={statistics.mean(values):.3f}s  median={statistics.median(values):.3f}s"
        )

    stats_line("All parsed lags", all_lags)
    if negative_count > 0 and non_negative:
        stats_line("Non-negative lags only (excludes clock-skew suspects)", non_negative)

    # Compact preview table
    preview_n = min(15, len(parsed))
    print(f"\nFirst {preview_n} rows (by hmac_created_at DESC):")
    print(f"{'id':<36} {'lag_s':>10}")
    print("-" * 48)
    for row_id, lag, _, _ in parsed[:preview_n]:
        short_id = row_id[:36] if len(row_id) > 36 else row_id
        print(f"{short_id:<36} {lag:10.3f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
