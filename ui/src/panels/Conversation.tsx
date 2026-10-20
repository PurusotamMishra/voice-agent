export interface ChatTurn {
  you: string;
  source: "stt" | "typed";
  bot: string;
}

export function Conversation({ turns }: { turns: ChatTurn[] }) {
  return (
    <section className="panel">
      <h2>Conversation</h2>
      {turns.length === 0 && <p>Hold the button and speak, or type below.</p>}
      {turns.map((t, i) => (
        <div className="turn" key={i}>
          <div className="you">
            you{t.source === "stt" ? " (voice)" : ""}: {t.you || "…"}
          </div>
          <div>bot: {t.bot}</div>
        </div>
      ))}
    </section>
  );
}
