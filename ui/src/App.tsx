import { useEffect, useRef, useState, type FormEvent } from "react";
import { createSession, postClientTimings, sendTurn } from "./api/client";
import type { DoneEvent, Language, SearchEvent, TranscriptEvent, TurnEvent, UnderstandingEvent } from "./api/types";
import { AudioQueue } from "./audio/AudioQueue";
import { useRecorder } from "./audio/useRecorder";
import { Conversation, type ChatTurn } from "./panels/Conversation";
import { LatencyPanel } from "./panels/LatencyPanel";
import { ResultsPanel } from "./panels/ResultsPanel";
import { SlotsPanel } from "./panels/SlotsPanel";
import { SqlPanel } from "./panels/SqlPanel";
import { VerdictPanel } from "./panels/VerdictPanel";

interface Pending {
  speechEnd: number;
  turnId: string | null;
  firstAudio: number | null;
  posted: boolean;
}

export default function App() {
  const [session, setSession] = useState<string | null>(null);
  const [language, setLanguage] = useState<Language>("en");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [typed, setTyped] = useState("");
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [transcript, setTranscript] = useState<TranscriptEvent | null>(null);
  const [understanding, setUnderstanding] = useState<UnderstandingEvent | null>(null);
  const [search, setSearch] = useState<SearchEvent | null>(null);
  const [done, setDone] = useState<DoneEvent | null>(null);
  const [firstAudioMs, setFirstAudioMs] = useState<number | null>(null);
  const queue = useRef(new AudioQueue());
  const pending = useRef<Pending | null>(null);
  const releasing = useRef(false); // pointerup and pointerleave can both fire: send one turn
  const { recording, start, stop } = useRecorder();

  useEffect(() => {
    createSession().then(setSession, (e: Error) => setError(e.message));
  }, []);

  // Post browser timings once both the turn id (done event) and first playback are known (J4).
  const maybePostTimings = () => {
    const p = pending.current;
    if (!p || p.posted || !p.turnId || p.firstAudio === null) return;
    p.posted = true;
    setFirstAudioMs(p.firstAudio - p.speechEnd);
    postClientTimings(p.turnId, { t_speech_end: p.speechEnd, t_first_audio: p.firstAudio }).catch((e) =>
      console.warn("client timings not sent", e),
    );
  };

  const onEvent = (e: TurnEvent) => {
    switch (e.type) {
      case "transcript":
        setTranscript(e);
        setTurns((t) => [...t, { you: e.text, source: e.source, bot: "" }]);
        break;
      case "understanding":
        setUnderstanding(e);
        break;
      case "search":
        setSearch(e);
        break;
      case "sentence":
        queue.current.enqueue(e);
        setTurns((t) => t.map((x, i) => (i === t.length - 1 ? { ...x, bot: `${x.bot} ${e.text}`.trim() } : x)));
        break;
      case "done":
        setDone(e);
        if (pending.current) pending.current.turnId = e.turn_id;
        maybePostTimings();
        break;
    }
  };

  const runTurn = async (form: FormData, speechEnd: number) => {
    if (!session) return;
    form.append("session_id", session);
    form.append("language", language);
    queue.current.reset();
    queue.current.lang = language === "hi-en" ? "hi-IN" : "en-IN";
    pending.current = { speechEnd, turnId: null, firstAudio: null, posted: false };
    queue.current.onFirstPlay = (ms) => {
      if (pending.current) pending.current.firstAudio = ms;
      maybePostTimings();
    };
    setBusy(true);
    setError(null);
    setSearch(null);
    setDone(null);
    setUnderstanding(null);
    setTranscript(null);
    setFirstAudioMs(null);
    try {
      await sendTurn(form, onEvent);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const onPress = async () => {
    if (busy || recording) return;
    queue.current.reset(); // barge-in: stop the previous reply as soon as the buyer presses
    try {
      await start();
    } catch {
      setError("Microphone unavailable: type your request instead.");
    }
  };

  const onRelease = async () => {
    if (releasing.current) return;
    releasing.current = true;
    try {
      const rec = await stop();
      if (!rec || rec.blob.size === 0) return;
      const form = new FormData();
      form.append("audio", rec.blob, "speech.webm");
      form.append("audio_seconds", String(rec.durationMs / 1000));
      await runTurn(form, rec.speechEndMs);
    } finally {
      releasing.current = false;
    }
  };

  const onType = async (ev: FormEvent) => {
    ev.preventDefault();
    const text = typed.trim();
    if (!text || busy) return;
    setTyped("");
    const form = new FormData();
    form.append("text", text);
    await runTurn(form, Date.now());
  };

  return (
    <div className="app">
      <h1>Vyngo voice vehicle search</h1>
      <div className="controls">
        <button
          className={`ptt ${recording ? "recording" : ""}`}
          disabled={!session || busy}
          onPointerDown={onPress}
          onPointerUp={onRelease}
          onPointerLeave={() => recording && onRelease()}
        >
          {recording ? "Listening… release to send" : busy ? "Working…" : "Hold to talk"}
        </button>
        <select value={language} onChange={(e) => setLanguage(e.target.value as Language)}>
          <option value="en">English</option>
          <option value="hi-en">Hinglish</option>
        </select>
        <form onSubmit={onType} style={{ display: "flex", flex: 1, gap: 8 }}>
          <input type="text" value={typed} onChange={(e) => setTyped(e.target.value)} placeholder="…or type here" />
          <button type="submit" disabled={!session || busy}>
            Send
          </button>
        </form>
      </div>
      {error && <p className="error">{error}</p>}
      <div className="grid">
        <Conversation turns={turns} />
        <SlotsPanel u={understanding} />
        <ResultsPanel s={search} />
        <SqlPanel s={search} />
        <LatencyPanel timings={done?.timings_ms ?? {}} firstAudioMs={firstAudioMs} />
        <VerdictPanel done={done} transcript={transcript} />
      </div>
    </div>
  );
}
