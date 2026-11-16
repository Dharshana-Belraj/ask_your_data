"""FastAPI app: upload -> profile -> ask (LLM spec -> SQL -> results) -> execute (filters/cross-filter)."""
import math
import uuid
from typing import Any, Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import llm
from engine import Dataset, execute_spec
from profiler import load_dataframe, profile_df

app = FastAPI(title="AI Dashboard Generator")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

DATASETS: dict[str, Dataset] = {}  # in-memory; swap for PostgreSQL/S3 when you add accounts


def _clean(o):
    """Recursively replace NaN/inf with None so responses are always valid JSON."""
    if isinstance(o, float):
        return o if math.isfinite(o) else None
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    return o


def _get(dataset_id: str) -> Dataset:
    ds = DATASETS.get(dataset_id)
    if not ds:
        raise HTTPException(404, "Dataset not found. Upload it again.")
    return ds


class AskBody(BaseModel):
    dataset_id: str
    question: str
    current_spec: Optional[dict[str, Any]] = None
    history: list[str] = []
    filters: list[dict[str, Any]] = []


class ExecBody(BaseModel):
    dataset_id: str
    spec: dict[str, Any]
    filters: list[dict[str, Any]] = []


@app.get("/api/health")
def health():
    return {"ok": True}


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    content = await file.read()
    try:
        df = load_dataframe(content, file.filename or "data.csv")
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, str(e)) from e
    profile = profile_df(df)
    ds = Dataset(uuid.uuid4().hex[:12], file.filename, df, profile)
    DATASETS[ds.id] = ds
    sample = df.head(8).astype(str).to_dict(orient="records")  # strings only => always JSON-safe
    return _clean({"dataset_id": ds.id, "name": ds.name, "rows": ds.rows, "columns": profile, "sample": sample})


@app.post("/api/ask")
def ask(body: AskBody):
    ds = _get(body.dataset_id)
    spec = llm.generate_spec(ds.profile, ds.rows, body.question, body.current_spec, body.history)
    results = execute_spec(ds, spec, body.filters, repair=llm.make_repairer(ds.profile))
    return _clean({"spec": spec, "results": results})


@app.post("/api/execute")
def execute(body: ExecBody):
    """Re-run an existing spec with new filters. No LLM call, so filtering is instant and free."""
    ds = _get(body.dataset_id)
    return _clean({"results": execute_spec(ds, body.spec, body.filters)})