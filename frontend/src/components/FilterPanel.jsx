export default function FilterPanel({ columns, filters, setFilters }) {
  const get = (c) => filters.find((f) => f.column === c);
  const put = (c, f) => setFilters((fs) => [...fs.filter((x) => x.column !== c), ...(f ? [f] : [])]);

  const cats = columns.filter((c) => (c.type === "category" || c.type === "boolean") && c.unique > 1 && c.values);
  const dates = columns.filter((c) => c.type === "date");
  const nums = columns.filter((c) => c.type === "number" && c.unique > 12 && !/(^|_)id$/.test(c.name)).slice(0, 3);

  const toggle = (col, v) => {
    const cur = get(col)?.value || [];
    const next = cur.includes(v) ? cur.filter((x) => x !== v) : [...cur, v];
    put(col, next.length ? { column: col, op: "in", value: next } : null);
  };
  const range = (col, i, v) => {
    const cur = get(col)?.value || ["", ""];
    const next = [...cur];
    next[i] = v;
    put(col, next[0] || next[1] ? { column: col, op: "between", value: next } : null);
  };

  return (
    <aside className="filters">
      <div className="filters-head">
        <h2>Filters</h2>
        {filters.length > 0 && <button className="link" onClick={() => setFilters([])}>Clear all</button>}
      </div>
      {dates.map((c) => (
        <div className="filter" key={c.name}>
          <div className="filter-name">{c.name}</div>
          <div className="range">
            <input type="date" min={c.min} max={c.max} value={get(c.name)?.value?.[0] || ""} onChange={(e) => range(c.name, 0, e.target.value)} />
            <input type="date" min={c.min} max={c.max} value={get(c.name)?.value?.[1] || ""} onChange={(e) => range(c.name, 1, e.target.value)} />
          </div>
        </div>
      ))}
      {cats.map((c) => (
        <details className="filter" key={c.name} open={cats.length <= 4 || !!get(c.name)}>
          <summary>
            <span className="filter-name">{c.name}</span>
            {get(c.name) && <span className="count">{get(c.name).value.length}</span>}
          </summary>
          <div className="options">
            {c.values.map((v) => (
              <label key={v}>
                <input type="checkbox" checked={!!get(c.name)?.value?.includes(v)} onChange={() => toggle(c.name, v)} />
                <span>{v}</span>
              </label>
            ))}
          </div>
        </details>
      ))}
      {nums.map((c) => (
        <div className="filter" key={c.name}>
          <div className="filter-name">{c.name}</div>
          <div className="range">
            <input type="number" placeholder={String(Math.floor(c.min))} value={get(c.name)?.value?.[0] ?? ""} onChange={(e) => range(c.name, 0, e.target.value)} />
            <input type="number" placeholder={String(Math.ceil(c.max))} value={get(c.name)?.value?.[1] ?? ""} onChange={(e) => range(c.name, 1, e.target.value)} />
          </div>
        </div>
      ))}
    </aside>
  );
}
