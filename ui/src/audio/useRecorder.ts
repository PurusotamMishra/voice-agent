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

  const start = useCallback(async () => {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
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
  }, []);

  const stop = useCallback(
    () =>
      new Promise<Recording | null>((resolve) => {
        const rec = recorder.current;
        if (!rec) return resolve(null);
        const speechEndMs = Date.now();
        rec.onstop = () => {
          rec.stream.getTracks().forEach((t) => t.stop());
          recorder.current = null;
          setRecording(false);
          const blob = new Blob(chunks.current, { type: rec.mimeType || "audio/webm" });
          resolve({ blob, durationMs: speechEndMs - startedAt.current, speechEndMs });
        };
        rec.stop();
      }),
    [],
  );

  return { recording, start, stop };
}
