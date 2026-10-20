import type { SearchEvent } from "../api/types";

export function SqlPanel({ s }: { s: SearchEvent | null }) {
  if (!s?.sql) return null;
  return (
    <details className="sql">
      <summary>Executed SQL and parameters</summary>
      <pre>{s.sql}</pre>
      <pre>{JSON.stringify(s.params, null, 1)}</pre>
    </details>
  );
}
