# Ask your data — AI natural-language dashboard generator

Upload a CSV / Excel / Parquet file, ask a question in plain English, and get an interactive dashboard
(KPIs, charts, filters, cross-filtering) that you can refine with follow-up questions.

## Run it

Requirements: Python 3.10+ and Node.js 18+.

### 1. Backend (terminal 1)
    cd backend
    python -m venv .venv
    # macOS/Linux:  source .venv/bin/activate
    # Windows:      .venv\Scripts\activate
    pip install -r requirements.txt
    # open backend/.env and paste your key:  OPENAI_API_KEY=sk-...
    python -m uvicorn main:app --reload --port 8000

### 2. Frontend (terminal 2)
    cd frontend
    npm install
    npm run dev

Open http://localhost:5173 and upload `backend/sample_sales.csv` (or any file).
(Regenerate the sample data with `python make_sample_data.py`.)

## How it works
1. `profiler.py`  – data intelligence: cleans column names, detects types/dates, profiles each column.
2. `llm.py`       – analytical + presentation intelligence: question + schema (never the data) -> JSON dashboard spec
                    (KPIs, charts, SQL). Follow-ups send the current spec so the model edits it instead of starting over.
3. `engine.py`    – validates SQL (single read-only SELECT), runs it in DuckDB, applies interactive filters,
                    and auto-repairs failed queries with one LLM retry.
4. `main.py`      – FastAPI: `/api/upload`, `/api/ask` (uses the LLM), `/api/execute` (filters; no LLM, instant).
5. React frontend renders the spec with ECharts. Clicking a bar/slice cross-filters the dashboard.
   Each chart can switch type, show its SQL, and export CSV.

## Notes
- Datasets live in server memory; restart = re-upload. Add PostgreSQL/S3 when you need saved dashboards.
- Change the model with `OPENAI_MODEL` in `backend/.env`.
- Never commit `backend/.env`.
