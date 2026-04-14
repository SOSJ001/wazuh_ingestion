# Appendix: Complete Laboratory Setup and Operations Guide

**Wazuh Integration Layer** — end-to-end instructions for reproducing the research artifact (ingestion middleware, SQLite system of record, FastAPI API, SvelteKit dashboard).

This document consolidates material from the repository [README.md](../README.md) (conceptual overview and cross-platform commands) and [SETUP_RUNBOOK.md](../SETUP_RUNBOOK.md) (Windows PowerShell, certificates, and troubleshooting). Use it as a **single appendix** for dissertation submission or as the **primary runbook** when onboarding a new machine.

**Laboratory assumptions (adjust to your environment):**

- Wazuh Manager and Indexer run on a VM reachable at `192.168.56.103` (VirtualBox host-only network).
- SSH user `wazuh-user` can reach the VM; Manager API uses `WAZUH_USER` / `WAZUH_PASS`; Indexer uses `WAZUH_INDEXER_USER` / `WAZUH_INDEXER_PASS`.
- Middleware host runs Windows with PowerShell (commands below match [SETUP_RUNBOOK.md](../SETUP_RUNBOOK.md)).

---

## A. System overview (what you are building)

| Layer | Component | Role |
|-------|-----------|------|
| Source | Wazuh Manager (55000), Wazuh Indexer (9200) | Alerts stored in OpenSearch; APIs not exposed without SSH |
| Ingestion | `wazuh_ingestion.py` | Task-specific SSH tunnels; startup JWT to Manager; per-poll `_search` to Indexer; Pydantic normalization; HMAC-SHA256 on `full_log`; SQLite insert |
| Persistence | `wazuh_alerts.db` | System of record; columns include `log_hmac`, `hmac_algo`, `hmac_created_at`, `is_verified`, `verified_by`, `verified_at` |
| API | `api.py` (FastAPI) | JWT login; verification-on-read (`integrity_status`); `POST /verify/{alert_id}` |
| UI | `dashboard-ui` (SvelteKit) | Human-in-the-loop review; login at `/login` |
| Telemetry | `ingestion_status.json` | Poll status, insert counts, validation reject count |

**Recommended runtime order:** ingestion (Terminal A) → API (Terminal B) → dashboard (Terminal C).

---

## B. Prerequisites

- Windows with PowerShell 5+ or 7+ (or adapt paths/commands for Linux/macOS).
- Python 3.x on `PATH`.
- Node.js and npm (for the dashboard).
- SSH client; network path from middleware host to Wazuh VM.

Verify:

```powershell
python --version
node --version
npm --version
ssh -V
```

---

## C. Step 1 — Clone repository and set paths

```powershell
$Project = "C:\path\to\wazuh_ingestion"
$CertDir = "$Project\certs"
$SshDir = "$Project\.ssh"
mkdir $CertDir -Force | Out-Null
mkdir $SshDir -Force | Out-Null
cd $Project
```

Copy `.env.example` to `.env` in the project root if you do not already have `.env`.

---

## D. Step 2 — Collect TLS trust material from the Wazuh VM

Run from the **middleware host** (paths below assume `$Project`, `$CertDir` from Step 1). Replace `192.168.56.103` and `wazuh-user` if your lab differs.

### D.1 Manager API certificate (port 55000)

```powershell
ssh wazuh-user@192.168.56.103 "echo | openssl s_client -connect 127.0.0.1:55000 -showcerts 2>/dev/null | sed -ne '/-BEGIN CERTIFICATE-/,/-END CERTIFICATE-/p'" | Set-Content -Encoding ascii "$CertDir\wazuh-api-55000.pem"
```

### D.2 Indexer certificate (port 9200)

```powershell
ssh wazuh-user@192.168.56.103 "sudo cat /etc/wazuh-indexer/certs/wazuh-indexer.pem" | Set-Content -Encoding ascii "$CertDir\wazuh-indexer-9200.pem"
```

### D.3 Combined bundle for `WAZUH_CA_CERT_PATH`

```powershell
Get-Content "$CertDir\wazuh-api-55000.pem","$CertDir\wazuh-indexer-9200.pem" | Set-Content -Encoding ascii "$CertDir\wazuh-endpoints-bundle.pem"
```

### D.4 SSH host key (`known_hosts`)

```powershell
ssh-keyscan -H -t rsa,ecdsa 192.168.56.103 | Set-Content -Encoding ascii "$SshDir\known_hosts"
```

---

## E. Step 3 — Generate secrets

```powershell
$hmacSecret = [Convert]::ToBase64String((1..64 | ForEach-Object { Get-Random -Max 256 }))
$jwtSecret  = [Convert]::ToBase64String((1..64 | ForEach-Object { Get-Random -Max 256 }))
$hmacSecret
$jwtSecret
```

Store these in `.env` as `ALERT_HMAC_SECRET` and `API_JWT_SECRET`. Do not commit `.env` to version control.

---

## F. Step 4 — Configure environment files

### F.1 Project root `.env`

Edit `.env` (see [`.env.example`](../.env.example) for all keys). Minimum set:

| Variable | Purpose |
|----------|---------|
| `WAZUH_IP` | Wazuh VM address |
| `WAZUH_USER` / `WAZUH_PASS` | Manager API (JWT at startup via tunnel) |
| `WAZUH_INDEXER_USER` / `WAZUH_INDEXER_PASS` | Indexer Basic Auth for `_search` |
| `WAZUH_SSH_USER` / `WAZUH_SSH_PASS` (or `WAZUH_SSH_KEY`) | SSH to VM |
| `WAZUH_SSH_KNOWN_HOSTS_PATH` | e.g. `.ssh/known_hosts` under project |
| `WAZUH_CA_CERT_PATH` | e.g. `certs/wazuh-endpoints-bundle.pem` |
| `ALERT_HMAC_SECRET` | HMAC key for `full_log` |
| `API_JWT_SECRET` | Signs dashboard/API JWTs |
| `DASHBOARD_AUTH_USER` / `DASHBOARD_AUTH_PASS` | Login for `POST /auth/token` |

Optional: `WAZUH_POLL_INTERVAL` (default 30), `WAZUH_DB_PATH`, `API_TOKEN_TTL_SECONDS`.

Ingestion **fails closed** at startup if the CA file, known_hosts file, or HMAC secret is missing.

### F.2 Dashboard `dashboard-ui/.env`

```env
VITE_DASHBOARD_AUTH_USER=admin
```

Optional: `VITE_DASHBOARD_BEARER_TOKEN` (usually leave unset; use `/login`).

---

## G. Step 5 — Install dependencies

```powershell
cd $Project
python -m pip install -r requirements.txt

cd "$Project\dashboard-ui"
npm install
```

---

## H. Step 6 — Run the stack

### H.1 Terminal A — Ingestion

```powershell
cd $Project
python wazuh_ingestion.py
```

Expected: authentication via SSH tunnel to Manager (55000), then recurring cycles with SSH tunnel to Indexer (9200), fetch, normalize, insert, and `Waiting … seconds for next sync…`.

### H.2 Terminal B — API

```powershell
cd $Project
python api.py
```

Or: `uvicorn api:app --host 127.0.0.1 --port 8000`

### H.3 Terminal C — Dashboard

```powershell
cd "$Project\dashboard-ui"
npm run dev
```

- Dashboard: `http://localhost:5173` (sign in at `/login`).
- API base: `http://127.0.0.1:8000`

**Cross-platform quick reference (from README):**

```bash
python wazuh_ingestion.py
python api.py
cd dashboard-ui && npm run dev
```

---

## I. Step 7 — Functional validation (acceptance checks)

### I.1 API returns 401 without token

```powershell
curl http://127.0.0.1:8000/alerts
```

Expect HTTP **401**.

### I.2 Obtain JWT and call protected route

```powershell
$body = @{ username = "admin"; password = "<DASHBOARD_AUTH_PASS>" } | ConvertTo-Json
$tokenResponse = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/auth/token" -ContentType "application/json" -Body $body
$tok = $tokenResponse.access_token
curl -H "Authorization: Bearer $tok" http://127.0.0.1:8000/alerts
```

Expect HTTP **200** and JSON array of alerts.

### I.3 Integrity and observability

- In the UI, confirm per-alert **integrity** status (API recomputes HMAC vs stored `log_hmac`).
- Call with token: `GET /system/health`, `GET /system/config` — expect metrics including validation reject count; without token expect **401**.

### I.4 Tamper-evidence spot check (optional)

1. With ingestion + API + UI running, confirm an alert shows valid integrity.
2. In SQLite, change `full_log` for one row **without** updating `log_hmac`.
3. Refresh UI or re-query API — that alert should show **invalid** integrity.

---

## J. Evaluation and reproducibility scripts

### J.1 Indexer-to-middleware lag (Method A)

Measures `hmac_created_at` minus `alerts.timestamp` for rows in SQLite:

```powershell
cd $Project
python scripts/ingestion_lag_report.py --limit 50
```

Options: `--csv lag_report.csv`, `--verified` / `--unverified`, `--db path\to\wazuh_alerts.db`. Reads `WAZUH_DB_PATH` and `WAZUH_POLL_INTERVAL` from `.env` when set.

### J.2 Raw alert vs normalized record (documentation / Figure 4 style output)

Uses the same normalization as `wazuh_ingestion.py`:

```powershell
cd $Project
python scripts/show_normalization_diff.py --from-indexer
```

Or from a saved JSON file:

```powershell
python scripts/show_normalization_diff.py --raw-file sample_alert.json
```

Optional: `--output-json comparison.json`

`--from-indexer` requires the same SSH, TLS, and indexer credentials as live ingestion.

---

## K. Troubleshooting (summary)

| Symptom | Action |
|---------|--------|
| `Set WAZUH_CA_CERT_PATH … file exists` | Verify `Test-Path` to bundle PEM; rebuild bundle (Section D). |
| `Invalid known hosts entry` | Regenerate `known_hosts` with `ssh-keyscan` (Section D.4). |
| TLS verify / hostname errors | Ensure tunnel + bundle include certs for the endpoint in use. |
| Indexer errors | Test indexer HTTPS and auth; see extended curl examples in [SETUP_RUNBOOK.md](../SETUP_RUNBOOK.md) §9. |
| `Schema validation rejected alert` | Inspect logged payload; event may not match `NormalizedAlert` schema. |

Full error-specific commands: [SETUP_RUNBOOK.md](../SETUP_RUNBOOK.md) Section 9.

---

## L. Migration to another device

1. Clone repository on new host.
2. Install Python, Node, SSH client.
3. Recollect VM certificates and rebuild `wazuh-endpoints-bundle.pem`.
4. Regenerate `known_hosts` for the VM IP/hostname.
5. Generate **new** `ALERT_HMAC_SECRET` and `API_JWT_SECRET` (do not reuse across environments).
6. Update `.env` paths for the new machine; configure `dashboard-ui/.env`.
7. `pip install -r requirements.txt` and `npm install` in `dashboard-ui`.
8. Run ingestion → API → UI; repeat Section I acceptance checks.

---

## M. Document map

| Document | Use when |
|----------|----------|
| This appendix | Single-file lab procedure + dissertation appendix |
| [README.md](../README.md) | Quick orientation, bash-friendly snippets, feature summary |
| [SETUP_RUNBOOK.md](../SETUP_RUNBOOK.md) | Deep Windows PowerShell steps and troubleshooting detail |

---

*End of appendix.*
