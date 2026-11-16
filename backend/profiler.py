"""Data intelligence: load an uploaded file, clean column names, detect types, profile columns."""
import io
import math
import re
import warnings

import numpy as np
import pandas as pd


def _num(x):
    """float or None (NaN/inf are not valid JSON)."""
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _clean_name(name, used):
    n = re.sub(r"[^0-9a-zA-Z]+", "_", str(name).strip()).strip("_").lower() or "col"
    if n[0].isdigit():
        n = "c_" + n
    base, i = n, 2
    while n in used:
        n = f"{base}_{i}"
        i += 1
    used.add(n)
    return n


def _try_dates(s: pd.Series) -> pd.Series:
    nn = s.dropna().astype(str)
    if nn.empty:
        return s
    sample = nn.head(200)
    if sample.str.len().between(6, 30).mean() < 0.95:
        return s
    if sample.str.contains(r"\d").mean() < 0.95 or sample.str.contains(r"[-/:\s]").mean() < 0.95:
        return s
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        parsed = pd.to_datetime(sample, errors="coerce")
        if parsed.notna().mean() < 0.95:
            return s
        return pd.to_datetime(s, errors="coerce")


def load_dataframe(content: bytes, filename: str) -> pd.DataFrame:
    ext = filename.lower().rsplit(".", 1)[-1]
    buf = io.BytesIO(content)
    if ext in ("csv", "txt"):
        try:
            df = pd.read_csv(buf)
        except UnicodeDecodeError:
            buf.seek(0)
            df = pd.read_csv(buf, encoding="latin-1")
    elif ext in ("xlsx", "xlsm", "xls"):
        df = pd.read_excel(buf)
    elif ext == "parquet":
        df = pd.read_parquet(buf)
    else:
        raise ValueError("Unsupported file type. Upload a CSV, Excel (.xlsx) or Parquet file.")
    if df.empty:
        raise ValueError("The file has no rows.")
    used = set()
    df.columns = [_clean_name(c, used) for c in df.columns]
    for c in df.columns:
        if df[c].dtype == object or pd.api.types.is_string_dtype(df[c]):
            df[c] = _try_dates(df[c])
    return df


def profile_df(df: pd.DataFrame) -> list:
    cols = []
    for c in df.columns:
        s = df[c]
        nn = s.dropna()
        uniq = int(nn.nunique())
        if pd.api.types.is_bool_dtype(s):
            t = "boolean"
        elif pd.api.types.is_numeric_dtype(s):
            t = "number"
        elif pd.api.types.is_datetime64_any_dtype(s):
            t = "date"
        else:
            t = "category" if uniq <= 50 else "text"
        info = {"name": c, "type": t, "dtype": str(s.dtype), "nulls": int(s.isna().sum()), "unique": uniq}
        if len(nn):
            if t == "number":
                fin = pd.to_numeric(nn, errors="coerce").astype("float64")
                fin = fin[np.isfinite(fin)]
                if len(fin):
                    info.update(min=_num(fin.min()), max=_num(fin.max()), mean=_num(round(float(fin.mean()), 4)))
            elif t == "date":
                info.update(min=nn.min().strftime("%Y-%m-%d"), max=nn.max().strftime("%Y-%m-%d"))
            elif t in ("category", "boolean"):
                info["values"] = [str(v) for v in nn.astype(str).value_counts().head(50).index]
            info["samples"] = [str(x)[:40] for x in nn.head(3)]
        cols.append(info)
    return cols