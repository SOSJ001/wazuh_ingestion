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
