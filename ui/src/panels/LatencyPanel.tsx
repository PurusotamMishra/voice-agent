const ORDER = ["stt", "nlu", "search", "rank", "relax", "compose", "pipeline", "first_audio_ready", "tts", "server_total"];
const NAME: Record<string, string> = {
  stt: "Speech to text",
  nlu: "Understanding",
  search: "Search + rank",
  compose: "Compose reply",
  other: "Other pipeline",
  first_tts: "First sentence voice",
};

// The server's path to the first audio, as sequential stages. first_audio_ready is measured
// from turn start, so the first TTS call is what remains after STT and the pipeline.
// "Other pipeline" is pipeline time outside the named stages (state checkpoint, graph glue).
function stages(t: Record<string, number>): [string, number][] {
  const search = (t.search ?? 0) + (t.rank ?? 0) + (t.relax ?? 0);
  const other = Math.max(0, (t.pipeline ?? 0) - (t.nlu ?? 0) - search - (t.compose ?? 0));
  const before = (t.stt ?? 0) + (t.pipeline ?? 0);
  const firstTts = t.first_audio_ready !== undefined ? Math.max(0, t.first_audio_ready - before) : 0;
  const out: [string, number][] = [
    ["stt", t.stt ?? 0],
    ["nlu", t.nlu ?? 0],
    ["search", search],
    ["compose", t.compose ?? 0],
    ["other", other],
    ["first_tts", firstTts],
  ];
  return out.filter(([, ms]) => ms > 0);
}

const sec = (ms: number) => `${(ms / 1000).toFixed(1)} s`;

export function LatencyPanel({ timings, firstAudioMs }: { timings: Record<string, number>; firstAudioMs: number | null }) {
  const keys = [...ORDER.filter((k) => k in timings), ...Object.keys(timings).filter((k) => !ORDER.includes(k))];
  const parts = stages(timings);
  const total = parts.reduce((a, [, ms]) => a + ms, 0);
  const topKey = parts.length ? parts.reduce((a, b) => (b[1] > a[1] ? b : a))[0] : null; // dominant stage
  return (
    <section>
      <h2>
        Latency<span>this turn</span>
      </h2>
      {keys.length === 0 ? (
        <p className="empty">Timings appear after the first turn.</p>
      ) : (
        <div className="latency">
          <div className="headline">
            <b>{firstAudioMs === null ? "–" : sec(firstAudioMs)}</b>
            <span>from releasing the mic (or pressing Send) to the first audio, measured in the browser</span>
          </div>
          {total > 0 && (
            <div className="timeline" role="img" aria-label="server stages to first audio">
              {parts.map(([k, ms]) => (
                <div
                  key={k}
                  className={k === topKey ? "top-stage" : undefined}
                  style={{ flexGrow: ms, flexBasis: 0 }}
                  title={`${NAME[k]}: ${Math.round(ms)} ms`}
                >
                  {ms / total > 0.12 ? NAME[k] : ""}
                </div>
              ))}
            </div>
          )}
          <table className="stages">
            <tbody>
              {keys.map((k) => (
                <tr key={k} className={k === topKey ? "top-stage" : undefined}>
                  <td>{k}</td>
                  <td>{Math.round(timings[k])} ms</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
