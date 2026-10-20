import { useCallback, useRef, useState } from "react";

export interface Recording {
  blob: Blob;
  durationMs: number;
  speechEndMs: number; // epoch ms at button release (J4 t_speech_end)
}

/** Push-to-talk recorder (C3): start on press, stop on release. */
export function useRecorder() {
  const [recording, setRecording] = useState(false);
  const recorder = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);
  const startedAt = useRef(0);
  const pendingStart = useRef<Promise<void> | null>(null); // set while start() awaits the mic
  const stopRequested = useRef(false); // release arrived before the mic was ready

  const start = useCallback((): Promise<void> => {
    if (pendingStart.current) return pendingStart.current; // double press: reuse, no second stream
    if (recorder.current) return Promise.resolve();
    stopRequested.current = false;
    const run = async () => {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (stopRequested.current) {
        stream.getTracks().forEach((t) => t.stop());
        return;
      }
      try {
        const mime = MediaRecorder.isTypeSupported("audio/webm;codecs=opus") ? "audio/webm;codecs=opus" : "";
        const rec = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
        chunks.current = [];
        rec.ondataavailable = (e) => {
          if (e.data.size > 0) chunks.current.push(e.data);
        };
        rec.start();
        recorder.current = rec;
        startedAt.current = Date.now();
        setRecording(true);
      } catch (err) {
        stream.getTracks().forEach((t) => t.stop());
        throw err;
      }
    };
    const p = run().finally(() => {
      pendingStart.current = null;
    });
    pendingStart.current = p;
    return p;
  }, []);

  const stop = useCallback(async (): Promise<Recording | null> => {
    if (pendingStart.current) {
      stopRequested.current = true;
      await pendingStart.current.catch(() => undefined); // start() reports its own error
    }
    const rec = recorder.current;
    if (!rec) return null;
    const speechEndMs = Date.now();
    return new Promise<Recording | null>((resolve) => {
      rec.onstop = () => {
        rec.stream.getTracks().forEach((t) => t.stop());
        recorder.current = null;
        setRecording(false);
        const blob = new Blob(chunks.current, { type: rec.mimeType || "audio/webm" });
        resolve({ blob, durationMs: speechEndMs - startedAt.current, speechEndMs });
      };
      rec.stop();
    });
  }, []);

  return { recording, start, stop };
}
