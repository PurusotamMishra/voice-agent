import type { SearchEvent } from "../api/types";

const inr = (n: number) => `₹${n.toLocaleString("en-IN")}`;

export function ResultsPanel({ s }: { s: SearchEvent | null }) {
  return (
    <section className="panel">
      <h2>Top results (score breakdown)</h2>
      {!s && <p>No search yet.</p>}
      {s && s.results.length === 0 && (
        <p>
          No matches.
          {s.relaxation &&
            ` Suggested: ${s.relaxation.slot} ${String(s.relaxation.old)} → ${String(s.relaxation.new)} (${s.relaxation.count} found)`}
        </p>
      )}
      {s?.results.map((r) => (
        <div key={r.listing.listing_id} className="turn">
          <b>
            #{r.rank} {r.listing.year} {r.listing.make} {r.listing.model}
          </b>{" "}
          · {r.listing.city} · {inr(r.listing.price_inr)} · {r.listing.km_driven.toLocaleString("en-IN")} km ·{" "}
          {r.listing.payload_kg} kg · score {r.score.toFixed(3)}
          <table>
            <tbody>
              {Object.entries(r.contributions).map(([k, v]) => (
                <tr key={k}>
                  <td>{k}</td>
                  <td>{v.toFixed(3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}
    </section>
  );
}
