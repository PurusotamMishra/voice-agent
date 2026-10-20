import { useEffect, useRef } from "react";

export interface ChatTurn {
  you: string;
  source: "stt" | "typed";
  bot: string;
}

export function Conversation({ turns }: { turns: ChatTurn[] }) {
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => {
    // Block body on purpose: newer browsers return a Promise from scrollIntoView, and React
    // would call an implicitly returned value as the effect's cleanup.
    end.current?.scrollIntoView({ block: "end" });
  }, [turns]);
  return (
    <div className="log" aria-live="polite">
      {turns.length === 0 && (
        <p className="hint">
          Hold the mic and ask, for example
          <br />
          <em>“Chhota truck chahiye, 5 lakh ke andar, Pune mein”</em>
        </p>
      )}
      {turns.map((t, i) => (
        <div key={i} style={{ display: "contents" }}>
          <div className="msg you">
            <span className="via">{t.source === "stt" ? "You said" : "You typed"}</span>
            {t.you || "…"}
          </div>
          {t.bot && <div className="msg bot">{t.bot}</div>}
        </div>
      ))}
      <div ref={end} />
    </div>
  );
}
