import type { DoneEvent, TranscriptEvent } from "../api/types";

export function VerdictPanel({ done, transcript }: { done: DoneEvent | null; transcript: TranscriptEvent | null }) {
  return (
    <section>
      <h2>
        Checks<span>validator and fallbacks</span>
      </h2>
      {!done ? (
        <p className="empty">Shown after each answer.</p>
      ) : (
        <div className="checks">
          {done.verdict && (
            <span className={`tag ${done.verdict.ok ? "ok" : "bad"}`}>
              {done.verdict.ok ? "✓ Every fact matches the listing" : "✗ Validator rejected the reply"}
              {done.verdict.source === "template" && " (template reply)"}
            </span>
          )}
          {transcript?.source === "stt" && (
            <span className="tag">
              Heard by {transcript.provider ?? "no STT"}
              {transcript.confidence !== null && `, confidence ${transcript.confidence}`}
            </span>
          )}
          {done.fallback_used.map((f, i) => (
            <span className="tag fallback" key={i}>
              Fallback: {f}
            </span>
          ))}
          {done.verdict?.violations.map((v, i) => (
            <div key={i} className="violation">
              {v.kind}: {v.detail}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
