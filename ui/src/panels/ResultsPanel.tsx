import type { SearchEvent } from "../api/types";
import { FEATURE, inr, slotLabel, slotValue } from "../format";

// Score = sum of weighted feature contributions (E2); the weights sum to 1, so the bar's full
// width is a perfect score. The legend carries the exact numbers (colour is never alone).
export function ResultsPanel({ s }: { s: SearchEvent | null }) {
  return (
    <section>
      <h2>
        Top results<span>score breakdown from the ranker</span>
      </h2>
      {!s && <p className="empty">Results appear after the first search.</p>}
      {s && s.results.length === 0 && (
        <div className="relax">
          No listing matches every filter.
          {s.relaxation
            ? ` Loosening one: ${slotLabel(s.relaxation.slot)} ${slotValue(s.relaxation.slot, s.relaxation.old)} → ${slotValue(s.relaxation.slot, s.relaxation.new)} finds ${s.relaxation.count}.`
            : " No single change finds any."}
        </div>
      )}
      <div className="results">
        {s?.results.map((r) => {
          const l = r.listing;
          const parts = Object.entries(r.contributions);
          return (
            <article className="car" key={l.listing_id}>
              <div className="rank">{r.rank}</div>
              <div>
                <div className="title">
                  {l.year} {l.make} {l.model}
                </div>
                <div className="facts">
                  <span>{inr(l.price_inr)}</span>
                  <span>{l.km_driven.toLocaleString("en-IN")} km</span>
                  <span>{l.payload_kg.toLocaleString("en-IN")} kg payload</span>
                  <span>{slotValue("fuel", l.fuel)}</span>
                  <span>{slotValue("city", l.city)}</span>
                  <span>{l.papers_verified ? "Papers verified" : "Papers not verified"}</span>
                </div>
              </div>
              <div className="score">
                {r.score.toFixed(2)}
                <small>score</small>
              </div>
              <div className="why">
                <div className="bar" role="img" aria-label={`score ${r.score.toFixed(2)} of 1`}>
                  {parts
                    .filter(([, v]) => v > 0)
                    .map(([k, v]) => (
                      <i
                        key={k}
                        style={{ width: `${v * 100}%`, background: `var(--f-${k}, var(--ink-3))` }}
                        title={`${FEATURE[k] ?? k}: ${v.toFixed(3)}`}
                      />
                    ))}
                </div>
                <ul className="legend">
                  {parts.map(([k, v]) => (
                    <li key={k} className={v > 0 ? undefined : "zero"}>
                      <span className="sw" style={{ background: `var(--f-${k}, var(--ink-3))` }} />
                      {FEATURE[k] ?? k} {v.toFixed(2)}
                    </li>
                  ))}
                </ul>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
