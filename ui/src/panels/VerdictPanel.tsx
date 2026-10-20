import type { DoneEvent, TranscriptEvent } from "../api/types";

export function VerdictPanel({ done, transcript }: { done: DoneEvent | null; transcript: TranscriptEvent | null }) {
  return (
    <section className="panel">
      <h2>Validator &amp; fallbacks</h2>
      {transcript?.source === "stt" && (
        <p>
          STT: {transcript.provider ?? "none"}
          {transcript.confidence !== null && ` · confidence ${transcript.confidence}`}
        </p>
      )}
      {!done ? (
        <p>–</p>
      ) : (
        <>
          {done.verdict && (
            <span className={`badge ${done.verdict.ok ? "ok" : "bad"}`}>
              validator: {done.verdict.ok ? "pass" : "fail"} ({done.verdict.source})
            </span>
          )}
          {done.fallback_used.map((f, i) => (
            <span className="badge" key={i}>
              {f}
            </span>
          ))}
          {done.verdict?.violations.map((v, i) => (
            <div key={i} className="error">
              {v.kind}: {v.detail}
            </div>
          ))}
        </>
      )}
    </section>
  );
}
