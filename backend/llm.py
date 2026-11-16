"""Analytical + presentation intelligence: natural language -> dashboard specification (JSON). (Groq)"""
import json
import os

from dotenv import load_dotenv
from fastapi import HTTPException
from openai import OpenAI

load_dotenv()
MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
CHART_TYPES = {"bar", "line", "area", "pie", "scatter", "table"}
KPI_FORMATS = {"number", "currency", "percent"}

SYSTEM = """You are the analytics engine of an AI-powered BI dashboard tool. The user asks questions about one
uploaded dataset. You translate each question into a dashboard specification. Reply with ONE JSON object only.

SPEC FORMAT
{
  "title": "short dashboard title",
  "summary": "1-2 sentences describing what the dashboard shows. Do NOT invent numbers.",
  "kpis": [ {"id":"kpi_1","label":"Total revenue","sql":"SELECT SUM(revenue) AS value FROM data","format":"currency|number|percent"} ],
  "charts": [ {"id":"chart_1","title":"...","type":"bar|line|area|pie|scatter|table",
               "sql":"...","x":"<result column for x axis / category>","y":["<result column(s) with values>"],
               "series":null,"filter_column":null,"width":"half|full"} ],
  "followups": ["3 short follow-up questions the user might ask next"]
}

SQL RULES (DuckDB dialect)
- Query ONLY the table named data. Use only columns listed in the schema, exactly as spelled. Never use another table.
- Exactly one SELECT (or WITH ... SELECT) per item. No semicolons, no comments, no DDL/DML.
- KPI sql returns exactly one row and one column aliased value. For percent KPIs return a percentage number (12.5 means 12.5%).
- Chart sql returns tidy rows. The aliases in sql must equal the names used in x, y and series.
- If "series" is set, the result is long-form (x, series, one value column) and y has exactly one entry.
  Otherwise y lists one or more value columns (wide form).
- Time grouping: strftime(date_trunc('month', col), '%Y-%m') AS month (use quarter/year/day similarly). Always ORDER BY time ascending.
- For "top N" use ORDER BY ... DESC LIMIT N. For "top N per group" use a window function (ROW_NUMBER() OVER (PARTITION BY ...)).
- Year-over-year / previous-period comparisons: use conditional aggregation or window functions (LAG) in one query.
- Round numeric outputs to 2 decimals. Keep chart results under 500 rows.
- The user may apply interactive filters; they are applied to data automatically. Never hardcode them.

CHART RULES
- 3 to 6 charts and 2 to 5 KPIs, each answering part of the question. Pick the chart type that suits the data:
  line/area for trends, bar for category comparison, pie only for <=6 parts of a whole, scatter for two numeric
  measures, table for detailed rows.
- filter_column: if x is a real column of data (e.g. region, category), put that raw column name so clicking a bar filters
  the dashboard; if x is derived (month, bucket) use null.
- width: "full" for time series or wide tables, otherwise "half".

FOLLOW-UPS
- If current_spec is provided and the new question refines or extends it ("now only South", "compare with last year",
  "add a chart of ..."), return the FULL updated spec. Keep unchanged charts/KPIs identical (same id, same sql) and
  change or add only what is needed. If the question is unrelated, build a fresh dashboard.
- If the question cannot be answered with the dataset, still return a spec: empty kpis/charts and a summary
  explaining what is missing."""

_CLIENT = None


def _client() -> OpenAI:
    """Groq exposes an OpenAI-compatible API, so we use the OpenAI SDK with Groq's base URL."""
    global _CLIENT
    if _CLIENT is None:
        key = os.getenv("GROQ_API_KEY", "")
        if not key or "PASTE_YOUR" in key:
            raise HTTPException(400, "GROQ_API_KEY is not set. Add your key to backend/.env and restart the server.")
        _CLIENT = OpenAI(api_key=key, base_url="https://api.groq.com/openai/v1", timeout=60.0)
    return _CLIENT


def _chat_json(messages) -> dict:
    try:
        r = _client().chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=0.2,
            max_completion_tokens=8000,  # reasoning tokens count too; leave room so the JSON isn't cut off
            response_format={"type": "json_object"},
            extra_body={"reasoning_effort": "low"},  # gpt-oss: faster answers, plenty for text-to-SQL
        )
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"Groq request failed: {e}") from e
    try:
        return json.loads(r.choices[0].message.content)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"Groq returned invalid JSON: {e}") from e


def _compact_profile(profile):
    out = []
    for c in profile:
        d = {k: c[k] for k in ("name", "type", "unique", "nulls", "min", "max", "samples") if k in c}
        if "values" in c:
            d["values"] = c["values"][:12]
        out.append(d)
    return out


def _normalize(spec: dict) -> dict:
    spec = spec if isinstance(spec, dict) else {}
    spec["title"] = spec.get("title") or "Dashboard"
    spec["summary"] = spec.get("summary") or ""
    spec["followups"] = [str(x) for x in spec.get("followups", [])][:4]
    kpis = [k for k in spec.get("kpis", []) if isinstance(k, dict) and k.get("sql")][:6]
    for i, k in enumerate(kpis):
        k["id"] = str(k.get("id") or f"kpi_{i + 1}")
        k["label"] = k.get("label") or "Metric"
        k["format"] = k.get("format") if k.get("format") in KPI_FORMATS else "number"
    charts = [c for c in spec.get("charts", []) if isinstance(c, dict) and c.get("sql")][:8]
    for i, c in enumerate(charts):
        c["id"] = str(c.get("id") or f"chart_{i + 1}")
        c["title"] = c.get("title") or "Chart"
        c["type"] = c.get("type") if c.get("type") in CHART_TYPES else "bar"
        y = c.get("y") or []
        c["y"] = [y] if isinstance(y, str) else [str(v) for v in y]
        c["width"] = "full" if c.get("width") == "full" else "half"
    spec["kpis"], spec["charts"] = kpis, charts
    return spec


def generate_spec(profile, row_count, question, current_spec=None, history=None) -> dict:
    payload = {
        "dataset": {"table": "data", "rows": row_count, "columns": _compact_profile(profile)},
        "previous_questions": (history or [])[-6:],
        "current_spec": current_spec,
        "question": question,
    }
    spec = _chat_json([
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": json.dumps(payload, default=str)},
    ])
    return _normalize(spec)


def make_repairer(profile):
    schema = json.dumps(_compact_profile(profile), default=str)

    def repair(sql: str, error: str) -> str:
        r = _chat_json([
            {"role": "system", "content": "Fix the DuckDB SQL. Query only the table `data` and only the listed "
             "columns. Keep the same output column aliases. Reply as JSON: {\"sql\": \"...\"}."},
            {"role": "user", "content": json.dumps({"schema": schema, "sql": sql, "error": error})},
        ])
        return r["sql"]

    return repair