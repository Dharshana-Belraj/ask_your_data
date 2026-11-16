import { useEffect, useRef, useState } from "react";
import { ask, execute, uploadDataset } from "./api.js";
import ChartCard from "./components/ChartCard.jsx";
import FilterPanel from "./components/FilterPanel.jsx";
import KPICard from "./components/KPICard.jsx";

const STARTERS = [
  "Give me an overview of this dataset",
  "Compare monthly revenue across regions",
  "Which categories perform best?",
  "How do sales compare to the previous year?",
];

export default function App() {
  const [dataset, setDataset] = useState(null);
  const [spec, setSpec] = useState(null);
  const [results, setResults] = useState(null);
  const [filters, setFilters] = useState([]);
  const [history, setHistory] = useState([]);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const fileRef = useRef();

  async function onUpload(file) {
    if (!file) return;
    setBusy("Reading and profiling your file…");
    setError("");
    try {
      const ds = await uploadDataset(file);
      setDataset(ds); setSpec(null); setResults(null); setFilters([]); setHistory([]);
    } catch (e) { setError(e.message); }
    setBusy("");
  }

  async function onAsk(text) {
    const q = (text ?? question).trim();
    if (!q || !dataset || busy) return;
    setBusy("Building your dashboard…");
    setError("");
    try {
      const r = await ask({ dataset_id: dataset.dataset_id, question: q, current_spec: spec, history, filters });
      setSpec(r.spec); setResults(r.results); setHistory((h) => [...h, q]); setQuestion("");
    } catch (e) { setError(e.message); }
    setBusy("");
  }

  // Filters changed -> re-run the existing spec (no LLM call)
  useEffect(() => {
    if (!dataset || !spec) return;
    const t = setTimeout(async () => {
      try { setResults((await execute(dataset.dataset_id, spec, filters)).results); }
      catch (e) { setError(e.message); }
    }, 300);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters]);

  // Cross-filtering: clicking a chart element toggles a filter on its column
  const onPick = (column, value) => {
    const info = dataset.columns.find((c) => c.name === column);
    if (!info) return;
    setFilters((fs) => {
      const ex = fs.find((f) => f.column === column);
      const others = fs.filter((f) => f.column !== column);
      if (ex?.op === "in" && ex.value.length === 1 && String(ex.value[0]) === String(value)) return others;
      return [...others, { column, op: "in", value: [info.type === "number" ? Number(value) : String(value)] }];
    });
  };

  return (
    <div className="app">
      <header className="top">
        <h1>Ask your data</h1>
        {dataset && <span className="file">{dataset.name} · {dataset.rows.toLocaleString()} rows · {dataset.columns.length} columns</span>}
        <input ref={fileRef} type="file" hidden accept=".csv,.xlsx,.xls,.parquet" onChange={(e) => onUpload(e.target.files[0])} />
        <button className="ghost" onClick={() => fileRef.current.click()}>{dataset ? "Upload another file" : "Upload a file"}</button>
      </header>

      {error && <div className="banner" role="alert">{error}</div>}

      {!dataset ? (
        <main className="landing">
          <h2>Upload a spreadsheet, then ask a question.</h2>
          <p>Drop in a CSV, Excel or Parquet file. Describe what you want to see in plain English and get an interactive dashboard you can filter, cross-filter and refine with follow-up questions.</p>
          <div
            className="drop"
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => { e.preventDefault(); onUpload(e.dataTransfer.files[0]); }}
            onClick={() => fileRef.current.click()}
          >
            {busy || "Drop a file here or click to browse"}
          </div>
        </main>
      ) : (
        <div className="workspace">
          <FilterPanel columns={dataset.columns} filters={filters} setFilters={setFilters} />
          <main className="board">
            {!spec ? (
              <div className="intro">
                <h2>What do you want to know about {dataset.name}?</h2>
                <div className="chips">{STARTERS.map((s) => <button key={s} onClick={() => onAsk(s)}>{s}</button>)}</div>
                <details className="preview">
                  <summary>Preview columns</summary>
                  <ul>{dataset.columns.map((c) => <li key={c.name}><b>{c.name}</b> {c.type}{c.nulls ? `, ${c.nulls} missing` : ""}</li>)}</ul>
                </details>
              </div>
            ) : (
              <>
                <div className="heading">
                  <h2>{spec.title}</h2>
                  {spec.summary && <p>{spec.summary}</p>}
                </div>
                {filters.length > 0 && (
                  <div className="active">
                    {filters.map((f) => (
                      <button key={f.column} className="pill" onClick={() => setFilters((fs) => fs.filter((x) => x.column !== f.column))}>
                        {f.column}: {f.op === "in" ? f.value.join(", ") : `${f.value[0] || "…"} to ${f.value[1] || "…"}`} ×
                      </button>
                    ))}
                  </div>
                )}
                {spec.kpis.length > 0 && (
                  <div className="kpis">{spec.kpis.map((k) => <KPICard key={k.id} kpi={k} result={results?.kpis?.[k.id]} />)}</div>
                )}
                <div className="grid">
                  {spec.charts.map((c) => <ChartCard key={c.id + c.sql} chart={c} result={results?.charts?.[c.id]} onPick={onPick} />)}
                </div>
                {spec.followups?.length > 0 && (
                  <div className="chips">{spec.followups.map((s) => <button key={s} onClick={() => onAsk(s)}>{s}</button>)}</div>
                )}
              </>
            )}
          </main>
        </div>
      )}

      {dataset && (
        <form className="promptbar" onSubmit={(e) => { e.preventDefault(); onAsk(); }}>
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder={spec ? "Refine it: “now only the South”, “compare with last year”…" : "Ask a question about your data…"}
            disabled={!!busy}
          />
          <button type="submit" disabled={!!busy || !question.trim()}>{busy ? "Working…" : spec ? "Update dashboard" : "Build dashboard"}</button>
        </form>
      )}
    </div>
  );
}
