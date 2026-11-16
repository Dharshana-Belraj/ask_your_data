import { formatKpi } from "../format.js";

export default function KPICard({ kpi, result }) {
  return (
    <div className="kpi">
      <div className="kpi-label">{kpi.label}</div>
      {result?.error ? (
        <div className="kpi-error" title={result.error}>Couldn’t calculate</div>
      ) : (
        <div className="kpi-value">{formatKpi(result?.value, kpi.format)}</div>
      )}
    </div>
  );
}
