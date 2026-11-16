export const compact = (n) =>
  typeof n === "number" ? new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 }).format(n) : n;

export function formatKpi(value, format) {
  if (value === null || value === undefined) return "–";
  const n = Number(value);
  if (Number.isNaN(n)) return String(value);
  if (format === "currency")
    return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", notation: "compact", maximumFractionDigits: 1 }).format(n);
  if (format === "percent") return `${n.toLocaleString("en-US", { maximumFractionDigits: 1 })}%`;
  return Math.abs(n) >= 10000 ? compact(n) : n.toLocaleString("en-US", { maximumFractionDigits: 2 });
}

export const label = (v) =>
  v === null || v === undefined ? "–" : /^\d{4}-\d{2}-\d{2}T/.test(String(v)) ? String(v).slice(0, 10) : String(v);
