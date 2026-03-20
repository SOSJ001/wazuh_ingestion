# Wazuh Integration Layer

Ingestion of Wazuh alerts into a SQLite database, with a FastAPI backend and SvelteKit dashboard for human-in-the-loop verification.

## Run order

1. **Ingestion script** (optional but recommended for live data):
   ```bash
   python wazuh_ingestion.py
   ```

2. **API** (backend for the dashboard):
   ```bash
   python api.py
   ```
   Or: `uvicorn api:app --host 127.0.0.1 --port 8000`

3. **Dashboard** (frontend):
   ```bash
   cd dashboard-ui && npm run dev
   ```

- **Dashboard:** http://localhost:5173  
- **API:** http://127.0.0.1:8000 (e.g. http://127.0.0.1:8000/alerts)

## Integrity protection (HMAC)

The ingestion layer stores an `HMAC-SHA256` digest per alert in SQLite:

- Input: `full_log` (empty string when missing)
- Secret: `ALERT_HMAC_SECRET` from `.env`
- Stored fields: `log_hmac`, `hmac_algo`

The API recomputes this digest per alert and returns:

- `integrity_status=valid` when digest matches
- `integrity_status=invalid` when digest mismatch is detected
- `integrity_status=missing` when integrity metadata is unavailable

### Tamper-evidence demo

1. Ingest alerts normally (`python wazuh_ingestion.py`).
2. Start API/dashboard and confirm alerts show `Integrity: Valid`.
3. Manually modify one alert's `full_log` value in SQLite without updating `log_hmac`.
4. Refresh dashboard or query API.
5. Confirm that alert changes to `Integrity: Invalid`.

## API authentication and verifier attribution

API routes are protected with bearer auth:

- `GET /alerts`
- `GET /alerts/verified`
- `POST /verify/{alert_id}`

The token is now issued by the API login endpoint:

- `POST /auth/token`
- Body: `{ "username": "...", "password": "..." }`
- Response: `{ "access_token": "...", "token_type": "bearer", "expires_in": ... }`

The issued token is an HS256 JWT signed with `API_JWT_SECRET` and includes `sub`.

Dashboard auth flow:

- Open `/login` in the UI and sign in.
- The UI stores the returned bearer token in browser storage.
- Protected requests send `Authorization: Bearer <token>` automatically.
- On `401`, the UI clears the stored token and requires login again.

Required API auth env values:

- `API_JWT_SECRET` (JWT signing secret)
- `DASHBOARD_AUTH_USER` (login username, default `admin`)
- `DASHBOARD_AUTH_PASS` (login password; falls back to `WAZUH_PASS` if unset)
- Optional: `API_TOKEN_TTL_SECONDS` (default `28800`, 8 hours)

Optional UI env values:

- `VITE_DASHBOARD_AUTH_USER` (prefill login username)
- `VITE_DASHBOARD_BEARER_TOKEN` (optional fallback token; usually leave empty)

When an alert is verified, the API records verifier attribution in SQLite:

- `verified_by` (from token claim)
- `verified_at` (timestamp)

### Auth/401 proof check

1. Call API without `Authorization` header.
2. Confirm response is `401`.
3. Request token with `POST /auth/token`.
4. Call API again with `Authorization: Bearer <access_token>`.
5. Confirm response succeeds.

## Schema validation and status observability

Ingestion now enforces a strict normalized alert schema before database insert.

- Invalid alerts are rejected (not inserted).
- Rejection count is tracked as `last_validation_reject_count`.
- Runtime ingestion health is written to `ingestion_status.json`.

Protected observability endpoints:

- `GET /system/health` (live status + ingestion metrics)
- `GET /system/config` (safe non-secret configuration summary)

Both endpoints require bearer auth and are shown in the dashboard `Status` tab.

### Validation proof check

1. Start ingestion, API, and dashboard.
2. Open dashboard `Status` tab and confirm:
   - poll status (`ok`/`error`/`running`)
   - inserted count
   - validation reject count
3. Call `/system/health` without bearer token and confirm `401`.

## Transport trust hardening

The ingestion script now validates transport trust and fails closed if trust files are missing.

Required environment settings:

- `WAZUH_CA_CERT_PATH`: CA certificate used for HTTPS verification to manager/indexer.
- `WAZUH_SSH_KNOWN_HOSTS_PATH`: known_hosts file used to verify SSH host keys.

The script will stop at startup unless:

- CA cert file exists, and
- known_hosts file exists, and
- HMAC secret is set.
