import { useState } from "react";
import ReactECharts from "echarts-for-react";
import { compact, label } from "../format.js";

const PALETTE = ["#3b5bdb", "#12a594", "#f08c00", "#e5484d", "#8e4ec6", "#0ea5e9", "#65a30d", "#d6409f"];
const TYPES = ["bar", "line", "area", "pie", "table"];

function resolve(chart, columns, rows) {
  const x = columns.includes(chart.x) ? chart.x : columns[0];
  let ys = (chart.y || []).filter((c) => columns.includes(c));
  if (!ys.length) ys = columns.filter((c) => c !== x && rows.some((r) => typeof r[c] === "number")).slice(0, 1);
  const series = chart.series && columns.includes(chart.series) ? chart.series : null;
  return { x, ys, series };
}

function buildOption(type, chart, columns, rows) {
  const { x, ys, series } = resolve(chart, columns, rows);
  if (!ys.length) return null;
  const base = { color: PALETTE, textStyle: { fontFamily: "IBM Plex Sans, sans-serif" } };

  if (type === "pie") {
    return {
      ...base,
      tooltip: { trigger: "item" },
      legend: { type: "scroll", bottom: 0 },
      series: [{ type: "pie", radius: ["42%", "70%"], center: ["50%", "45%"], label: { formatter: "{b}" },
        data: rows.map((r) => ({ name: label(r[x]), value: r[ys[0]] })) }],
    };
  }

  if (chart.type === "scatter" && type === "scatter") {
    const groups = series ? [...new Set(rows.map((r) => label(r[series])))] : [null];
    return {
      ...base,
      tooltip: { trigger: "item" },
      legend: series ? { type: "scroll", top: 0 } : undefined,
      grid: { left: 8, right: 16, top: series ? 36 : 16, bottom: 8, containLabel: true },
      xAxis: { type: "value", name: x, scale: true, axisLabel: { formatter: compact } },
      yAxis: { type: "value", name: ys[0], scale: true, axisLabel: { formatter: compact } },
      series: groups.map((g) => ({
        type: "scatter", name: g ?? ys[0],
        data: rows.filter((r) => g === null || label(r[series]) === g).map((r) => [r[x], r[ys[0]]]),
      })),
    };
  }

  const cats = [...new Set(rows.map((r) => label(r[x])))];
  const byCat = new Map();
  rows.forEach((r) => { const k = label(r[x]); if (!byCat.has(k)) byCat.set(k, r); });

  let list;
  if (series) {
    const names = [...new Set(rows.map((r) => label(r[series])))];
    const cell = new Map(rows.map((r) => [`${label(r[x])}||${label(r[series])}`, r[ys[0]]]));
    list = names.map((n) => ({ name: n, data: cats.map((c) => cell.get(`${c}||${n}`) ?? null) }));
  } else {
    list = ys.map((y) => ({ name: y, data: cats.map((c) => byCat.get(c)?.[y] ?? null) }));
  }
  const t = type === "scatter" ? "bar" : type;
  return {
    ...base,
    tooltip: { trigger: "axis" },
    legend: list.length > 1 ? { type: "scroll", top: 0 } : undefined,
    grid: { left: 8, right: 16, top: list.length > 1 ? 36 : 16, bottom: 8, containLabel: true },
    xAxis: { type: "category", data: cats, axisLabel: { hideOverlap: true } },
    yAxis: { type: "value", axisLabel: { formatter: compact }, splitLine: { lineStyle: { color: "#e6e8ef" } } },
    series: list.map((s) => ({
      ...s, type: t === "area" ? "line" : t, smooth: t !== "bar", showSymbol: cats.length < 40,
      areaStyle: t === "area" ? { opacity: 0.18 } : undefined, barMaxWidth: 36,
    })),
  };
}

function downloadCsv(name, columns, rows) {
  const esc = (v) => (v == null ? "" : `"${String(v).replace(/"/g, '""')}"`);
  const csv = [columns.join(","), ...rows.map((r) => columns.map((c) => esc(r[c])).join(","))].join("\n");
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
  a.download = `${name.replace(/\W+/g, "_")}.csv`;
  a.click();
}

export default function ChartCard({ chart, result, onPick }) {
  const [type, setType] = useState(chart.type);
  const [showSql, setShowSql] = useState(false);
  const { columns = [], rows = [], error } = result || {};
  const options = [...new Set([chart.type === "scatter" ? "scatter" : null, ...TYPES].filter(Boolean))];
  const option = type !== "table" && rows.length ? buildOption(type, chart, columns, rows) : null;

  return (
    <section className={`card ${chart.width === "full" ? "full" : ""}`}>
      <header>
        <h3>{chart.title}</h3>
        <div className="tools">
          <select value={type} onChange={(e) => setType(e.target.value)} aria-label="Chart type">
            {options.map((t) => <option key={t}>{t}</option>)}
          </select>
          <button onClick={() => setShowSql((s) => !s)} aria-pressed={showSql}>SQL</button>
          <button disabled={!rows.length} onClick={() => downloadCsv(chart.title, columns, rows)}>CSV</button>
        </div>
      </header>
      {error ? (
        <p className="error">This chart failed: {error}</p>
      ) : !rows.length ? (
        <p className="empty">No data for the current filters.</p>
      ) : type === "table" || !option ? (
        <div className="table-wrap">
          <table>
            <thead><tr>{columns.map((c) => <th key={c}>{c}</th>)}</tr></thead>
            <tbody>
              {rows.slice(0, 200).map((r, i) => (
                <tr key={i}>{columns.map((c) => <td key={c}>{typeof r[c] === "number" ? r[c].toLocaleString() : label(r[c])}</td>)}</tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <ReactECharts
          option={option}
          style={{ height: 300 }}
          notMerge
          onEvents={{ click: (p) => chart.filter_column && p.name != null && onPick(chart.filter_column, p.name) }}
        />
      )}
      {chart.filter_column && !error && rows.length > 0 && type !== "table" && (
        <p className="hint">Click a {type === "pie" ? "slice" : "bar or point"} to filter by {chart.filter_column}.</p>
      )}
      {showSql && <pre className="sql">{chart.sql}</pre>}
    </section>
  );
}
