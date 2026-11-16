"""Query engine: DuckDB dataset wrapper, SQL safety validation, interactive filters, spec execution."""
import json
import re

import duckdb
import pandas as pd

FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|attach|detach|copy|pragma|install|load|export|import|"
    r"call|vacuum|truncate|read_csv|read_csv_auto|read_parquet|read_json|read_json_auto|read_text|"
    r"read_blob|glob|httpfs|parquet_scan|sniff_csv)\b",
    re.I,
)


def validate_sql(sql: str) -> str:
    s = (sql or "").strip().rstrip(";").strip()
    if not s:
        raise ValueError("Empty SQL")
    if ";" in s:
        raise ValueError("Multiple statements are not allowed")
    if "--" in s or "/*" in s:
        raise ValueError("SQL comments are not allowed")
    if not re.match(r"^(select|with)\b", s, re.I):
        raise ValueError("Only SELECT queries are allowed")
    if FORBIDDEN.search(s):
        raise ValueError("Query contains a forbidden keyword")
    return s


def _lit(v) -> str:
    return "'" + str(v).replace("'", "''") + "'"


class Dataset:
    def __init__(self, dataset_id: str, name: str, df: pd.DataFrame, profile: list):
        self.id, self.name, self.profile = dataset_id, name, profile
        self.cols = {c["name"]: c for c in profile}
        self.rows = len(df)
        self.con = duckdb.connect(":memory:")
        self.con.register("df_in", df)
        self.con.execute("CREATE TABLE raw_data AS SELECT * FROM df_in")
        self.con.unregister("df_in")
        try:  # defence in depth: block file/network access from SQL
            self.con.execute("SET enable_external_access=false")
            self.con.execute("SET lock_configuration=true")
        except Exception:
            pass

    # ---- interactive filters (global / cross-filter) -> WHERE clause
    def _where(self, filters) -> str:
        parts = []
        for f in filters or []:
            info = self.cols.get(f.get("column"))
            if not info:
                continue
            q = '"' + info["name"].replace('"', '""') + '"'
            op, v, t = f.get("op"), f.get("value"), info["type"]
            if op == "in" and isinstance(v, list) and v:
                if t == "number":
                    parts.append(f"{q} IN ({','.join(str(float(x)) for x in v)})")
                else:
                    parts.append(f"CAST({q} AS VARCHAR) IN ({','.join(_lit(x) for x in v)})")
            elif op == "between" and isinstance(v, list) and len(v) == 2:
                lo, hi = v
                if t == "number":
                    if lo not in (None, ""):
                        parts.append(f"{q} >= {float(lo)}")
                    if hi not in (None, ""):
                        parts.append(f"{q} <= {float(hi)}")
                elif t == "date":
                    if lo:
                        parts.append(f"CAST({q} AS DATE) >= CAST({_lit(lo)} AS DATE)")
                    if hi:
                        parts.append(f"CAST({q} AS DATE) <= CAST({_lit(hi)} AS DATE)")
        return (" WHERE " + " AND ".join(parts)) if parts else ""

    def run(self, sql: str, filters=None, limit: int = 1000):
        s = validate_sql(sql)
        cur = self.con.cursor()  # separate connection => private TEMP view per request
        try:
            cur.execute("CREATE OR REPLACE TEMP VIEW data AS SELECT * FROM raw_data" + self._where(filters))
            df = cur.execute(f"SELECT * FROM ({s}) AS q LIMIT {int(limit)}").fetchdf()
        finally:
            cur.close()
        return list(df.columns), json.loads(df.to_json(orient="records", date_format="iso"))


def _run_item(ds: Dataset, item: dict, filters, repair, is_kpi: bool):
    for attempt in range(2):
        try:
            cols, rows = ds.run(item["sql"], filters, 1 if is_kpi else 1000)
            if is_kpi:
                return {"value": rows[0][cols[0]] if rows else None}
            return {"columns": cols, "rows": rows}
        except Exception as e:  # noqa: BLE001
            err = str(e)
            if repair and attempt == 0:
                try:
                    item["sql"] = repair(item["sql"], err)
                    continue
                except Exception:  # noqa: BLE001
                    pass
            return {"error": err[:300]}


def execute_spec(ds: Dataset, spec: dict, filters=None, repair=None) -> dict:
    out = {"kpis": {}, "charts": {}}
    for k in spec.get("kpis", []):
        out["kpis"][k["id"]] = _run_item(ds, k, filters, repair, True)
    for c in spec.get("charts", []):
        out["charts"][c["id"]] = _run_item(ds, c, filters, repair, False)
    return out
