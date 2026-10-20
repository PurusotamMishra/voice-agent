import type { SearchEvent } from "../api/types";

export function SqlPanel({ s }: { s: SearchEvent | null }) {
  return (
    <section className="panel">
      <h2>Executed filters &amp; SQL</h2>
      {!s?.sql ? (
        <p>No search this turn.</p>
      ) : (
        <>
          <pre>{JSON.stringify(s.filters, null, 1)}</pre>
          <pre>{s.sql}</pre>
          <pre>params: {JSON.stringify(s.params)}</pre>
        </>
      )}
    </section>
  );
}
