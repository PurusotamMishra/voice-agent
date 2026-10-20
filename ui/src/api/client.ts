import type { TurnEvent } from "./types";

export async function createSession(): Promise<string> {
  const res = await fetch("/api/session", { method: "POST" });
  if (!res.ok) throw new Error(`session: HTTP ${res.status}`);
  return ((await res.json()) as { session_id: string }).session_id;
}

/** POST one turn and call onEvent for each NDJSON line as it arrives. */
export async function sendTurn(form: FormData, onEvent: (e: TurnEvent) => void): Promise<void> {
  const res = await fetch("/api/turn", { method: "POST", body: form });
  if (!res.ok || !res.body) throw new Error(`turn: HTTP ${res.status}`);
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let newline = buffer.indexOf("\n");
    while (newline >= 0) {
      const line = buffer.slice(0, newline).trim();
      buffer = buffer.slice(newline + 1);
      if (line) onEvent(JSON.parse(line) as TurnEvent);
      newline = buffer.indexOf("\n");
    }
  }
  if (buffer.trim()) onEvent(JSON.parse(buffer) as TurnEvent);
}

export async function postClientTimings(
  turnId: string,
  body: { t_speech_end: number | null; t_first_audio: number },
): Promise<void> {
  await fetch(`/api/turn/${turnId}/client-timings`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}
