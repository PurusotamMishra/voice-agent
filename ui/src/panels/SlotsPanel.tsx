import type { UnderstandingEvent } from "../api/types";
import { slotLabel, slotValue } from "../format";

// Every hard filter is a yellow commercial plate. A plate re-mounts (and flips) only when its
// value changes, so a one-slot correction shows as exactly one flip. `purpose` only ranks, so
// it is shown as text, not as a plate (hard rule 2).
export function SlotsPanel({ u }: { u: UnderstandingEvent | null }) {
  const walls = Object.entries(u?.slots ?? {}).filter(([k, v]) => k !== "purpose" && v !== null);
  const purpose = u?.slots.purpose;
  const dropped = Object.entries(u?.slot_diff ?? {}).filter(([, [, b]]) => b === null);
  return (
    <>
      <div className="walls" aria-label="Active filters">
        {walls.length === 0 && <span className="walls-empty">No filters yet. Say what you need.</span>}
        {walls.map(([k, v]) => {
          const diff = u?.slot_diff[k];
          const was = diff && diff[0] !== null ? slotValue(k, diff[0]) : null;
          return (
            <div className={`plate${diff ? " changed" : ""}`} key={`${k}:${String(v)}`} title={k}>
              <span className="k">{slotLabel(k)}</span>
              <span className="v">{slotValue(k, v)}</span>
              {was && <span className="was">was {was}</span>}
            </div>
          );
        })}
      </div>
      {u && (
        <div className="meta">
          <span>
            Intent <b>{u.intent ?? "?"}</b>
          </span>
          <span>
            Route <b>{u.route}</b>
          </span>
          <span>
            Language <b>{u.language ?? "?"}</b>
          </span>
          {purpose != null && (
            <span>
              Ranked for <b>{slotValue("purpose", purpose)}</b> (not a filter)
            </span>
          )}
          {dropped.length > 0 && <span>Dropped: {dropped.map(([k]) => slotLabel(k)).join(", ")}</span>}
          {u.pending_confirmation && (
            <span className="confirm">
              Waiting for yes or no: {slotLabel(u.pending_confirmation.slot)} {u.pending_confirmation.candidate}?
            </span>
          )}
        </div>
      )}
    </>
  );
}
