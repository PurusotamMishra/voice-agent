const ORDER = ["stt", "nlu", "search", "rank", "relax", "compose", "pipeline", "first_audio_ready", "tts", "server_total"];

export function LatencyPanel({ timings, firstAudioMs }: { timings: Record<string, number>; firstAudioMs: number | null }) {
  const keys = [...ORDER.filter((k) => k in timings), ...Object.keys(timings).filter((k) => !ORDER.includes(k))];
  return (
    <section className="panel">
      <h2>Latency (ms)</h2>
      <table>
        <tbody>
          {keys.map((k) => (
            <tr key={k}>
              <td>{k}</td>
              <td>{Math.round(timings[k])}</td>
            </tr>
          ))}
          <tr>
            <td>
              <b>speech end → first audio (browser)</b>
            </td>
            <td>
              <b>{firstAudioMs === null ? "–" : Math.round(firstAudioMs)}</b>
            </td>
          </tr>
        </tbody>
      </table>
    </section>
  );
}
