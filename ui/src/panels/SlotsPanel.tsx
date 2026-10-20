import type { UnderstandingEvent } from "../api/types";

export function SlotsPanel({ u }: { u: UnderstandingEvent | null }) {
  return (
    <section className="panel">
      <h2>Active slots</h2>
      {!u ? (
        <p>None yet.</p>
      ) : (
        <>
          <p>
            intent <b>{u.intent ?? "?"}</b> · route <b>{u.route}</b> · language <b>{u.language ?? "?"}</b>
          </p>
          <table>
            <tbody>
              {Object.entries(u.slots).map(([k, v]) => (
                <tr key={k} className={k in u.slot_diff ? "diff" : undefined}>
                  <td>{k}</td>
                  <td>{String(v)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {Object.keys(u.slot_diff).length > 0 && (
            <p className="diff">
              changed:{" "}
              {Object.entries(u.slot_diff)
                .map(([k, [a, b]]) => `${k}: ${String(a)} → ${String(b)}`)
                .join(", ")}
            </p>
          )}
          {u.pending_confirmation && (
            <p>
              waiting for yes/no: {u.pending_confirmation.slot} = {u.pending_confirmation.candidate}?
            </p>
          )}
        </>
      )}
    </section>
  );
}
