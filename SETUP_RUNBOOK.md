# Wazuh Ingestion Secure Setup Runbook (Windows PowerShell)

This guide lets you deploy this project on a new device/environment with:
- TLS verification
- SSH host verification
- HMAC integrity checks
- Login-based bearer auth for API access

All commands below are PowerShell.

## 1) Prerequisites

- Windows with PowerShell 5+ or 7+
- Python installed and available in `PATH`
- Node.js/npm for dashboard UI
- SSH access from Windows host to Wazuh VM

Quick checks:

```powershell
python --version
node --version
npm --version
ssh -V
```

## 2) Project paths (adjust if different)

```powershell
$Project = "C:\Users\Michael\Documents\GitHub\wazuh_ingestion"
$CertDir = "$Project\certs"
$SshDir = "$Project\.ssh"
mkdir $CertDir -Force | Out-Null
mkdir $SshDir -Force | Out-Null
```

## 3) Collect trust material from VM

### 3.1 Manager API certificate (port 55000)

```powershell
ssh wazuh-user@192.168.56.103 "echo | openssl s_client -connect 127.0.0.1:55000 -showcerts 2>/dev/null | sed -ne '/-BEGIN CERTIFICATE-/,/-END CERTIFICATE-/p'" | Set-Content -Encoding ascii "$CertDir\wazuh-api-55000.pem"
```

### 3.2 Indexer certificate (port 9200)

```powershell
ssh wazuh-user@192.168.56.103 "sudo cat /etc/wazuh-indexer/certs/wazuh-indexer.pem" | Set-Content -Encoding ascii "$CertDir\wazuh-indexer-9200.pem"
```

### 3.3 Build combined trust bundle

```powershell
Get-Content "$CertDir\wazuh-api-55000.pem","$CertDir\wazuh-indexer-9200.pem" | Set-Content -Encoding ascii "$CertDir\wazuh-endpoints-bundle.pem"
```

### 3.4 Create known_hosts for SSH verification

```powershell
ssh-keyscan -H -t rsa,ecdsa 192.168.56.103 | Set-Content -Encoding ascii "$SshDir\known_hosts"
```

## 4) Generate secrets

### 4.1 Generate strong secrets

```powershell
$hmacSecret = [Convert]::ToBase64String((1..64 | ForEach-Object { Get-Random -Max 256 }))
$jwtSecret  = [Convert]::ToBase64String((1..64 | ForEach-Object { Get-Random -Max 256 }))
$hmacSecret
$jwtSecret
```

## 5) Configure `.env`

Set these values in `.env`:

```env
WAZUH_IP=192.168.56.103
WAZUH_USER=wazuh
WAZUH_PASS=<manager-api-password>

WAZUH_INDEXER_USER=admin
WAZUH_INDEXER_PASS=<indexer-password>

WAZUH_SSH_USER=wazuh-user
WAZUH_SSH_PASS=<ssh-password>
WAZUH_SSH_KNOWN_HOSTS_PATH=.ssh/known_hosts

WAZUH_CA_CERT_PATH=certs/wazuh-endpoints-bundle.pem

ALERT_HMAC_SECRET=<generated-hmac-secret>
API_JWT_SECRET=<generated-jwt-secret>
DASHBOARD_AUTH_USER=admin
DASHBOARD_AUTH_PASS=<strong-password>
# Optional: API_TOKEN_TTL_SECONDS=28800
```

### 5.1 Configure dashboard UI env (`dashboard-ui/.env`)

```env
VITE_DASHBOARD_AUTH_USER=admin
# Optional fallback (normally leave unset and use /login):
# VITE_DASHBOARD_BEARER_TOKEN=
```

## 6) Install dependencies

### Backend

```powershell
cd $Project
python -m pip install -r requirements.txt
```

### Dashboard UI

```powershell
cd "$Project\dashboard-ui"
npm install
```

## 7) Run services (recommended order)

### Terminal A: Ingestion

```powershell
cd $Project
python wazuh_ingestion.py
```

Expected healthy log:
- `Authenticating as ... (via SSH tunnel)`
- `Success! API token: ...`
- `Success! Fetched ... raw alerts.`
- `... new alerts written to database.`

### Terminal B: API

```powershell
cd $Project
python api.py
```

### Terminal C: Dashboard

```powershell
cd "$Project\dashboard-ui"
npm run dev
```

## 8) Validation tests

### 8.1 API auth behavior (401 without token)

```powershell
curl http://127.0.0.1:8000/alerts
```

Expected: `401`

### 8.2 Request token from login endpoint

```powershell
$body = @{
  username = "admin"
  password = "<DASHBOARD_AUTH_PASS>"
} | ConvertTo-Json

$tokenResponse = Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8000/auth/token" `
  -ContentType "application/json" `
  -Body $body

$tok = $tokenResponse.access_token
$tok
```

Expected: JWT string in `$tok`.

### 8.3 API auth behavior (200 with token)

```powershell
curl -H "Authorization: Bearer $tok" http://127.0.0.1:8000/alerts
```

Expected: JSON alerts array.

### 8.4 HMAC integrity check in UI/API

- In dashboard, check integrity badge (`Valid`/`Invalid`/`Missing`).
- Or inspect API response fields:
  - `integrity_status`
  - `integrity_checked_at`

### 8.5 System status/config checks

```powershell
curl -H "Authorization: Bearer $tok" http://127.0.0.1:8000/system/health
curl -H "Authorization: Bearer $tok" http://127.0.0.1:8000/system/config
```

Expected:
- `/system/health` returns poll timestamps, poll status, inserted count, validation reject count.
- `/system/config` returns safe non-secret security/config flags.

Without bearer token, both should return `401`.

## 9) Troubleshooting (common errors)

### Error: `Set WAZUH_CA_CERT_PATH ... file exists`
- Path wrong or file missing.
- Fix by verifying with:
```powershell
Test-Path "$CertDir\wazuh-endpoints-bundle.pem"
```

### Error: `Invalid known hosts entry`
- Recreate known_hosts:
```powershell
ssh-keyscan -H -t rsa,ecdsa 192.168.56.103 | Set-Content -Encoding ascii "$SshDir\known_hosts"
```

### Error: `certificate verify failed: IP address mismatch`
- Use SSH tunnel to manager (already implemented), so TLS sees `localhost`.

### Error: `certificate verify failed: self-signed certificate`
- Bundle missing cert used by that endpoint. Rebuild `wazuh-endpoints-bundle.pem`.

### Error: `Indexer request failed ...`
- Could be TLS/auth/tunnel. Test manually:
```powershell
curl.exe -k -u admin:admin "https://127.0.0.1:9200/wazuh-alerts*/_search?size=1"
```
Then test with bundle:
```powershell
curl.exe --ssl-no-revoke --cacert "$CertDir\wazuh-endpoints-bundle.pem" -u admin:admin "https://127.0.0.1:9200/wazuh-alerts*/_search?size=1"
```

### Error: `Schema validation rejected alert`
- This means the incoming event did not fit the normalized schema.
- Ingestion continues for valid alerts; review the logged error snippet and source event fields.

## 10) Migration checklist for another device/architecture

On the new host:
- Clone project
- Install Python + Node + SSH client
- Copy/collect fresh certs from VM
- Rebuild `.ssh/known_hosts`
- Generate new secrets
- Set `.env` paths for that host
- Set dashboard login credentials
- Install deps
- Run ingestion/API/UI
- Validate login -> token -> API 200, plus ingestion + integrity badges

Do not reuse production secrets across devices. Generate new values per environment.