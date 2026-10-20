// Mirrors the NDJSON events in src/voice_agent/api/stream.py (architecture §10).
export type Language = "en" | "hi-en";

export interface Listing {
  listing_id: string;
  make: string;
  model: string;
  variant: string;
  body_type: string;
  fuel: string;
  year: number;
  price_inr: number;
  km_driven: number;
  payload_kg: number;
  city: string;
  owners: number;
  seller_type: string;
  papers_verified: boolean;
}

export interface ScoredListing {
  listing: Listing;
  rank: number;
  score: number;
  contributions: Record<string, number>;
}

export interface PendingConfirmation {
  slot: string;
  raw: string;
  candidate: string;
  score: number;
}

export interface Relaxation {
  slot: string;
  old: unknown;
  new: unknown;
  count: number;
}

export interface Usage {
  provider: string;
  input_tokens: number;
  output_tokens: number;
  audio_seconds: number;
  characters: number;
}

export interface Verdict {
  ok: boolean;
  source: "llm" | "template";
  violations: { where: string; kind: string; detail: string }[];
}

export interface TranscriptEvent {
  type: "transcript";
  text: string;
  source: "stt" | "typed";
  provider: string | null;
  confidence: number | null;
  language: string | null;
}

export interface UnderstandingEvent {
  type: "understanding";
  turn: number;
  intent: string | null;
  language: string | null;
  route: string;
  slots: Record<string, unknown>;
  slot_diff: Record<string, [unknown, unknown]>;
  pending_confirmation: PendingConfirmation | null;
}

export interface SearchEvent {
  type: "search";
  filters: Record<string, unknown> | null;
  sql: string | null;
  params: Record<string, unknown>;
  results: ScoredListing[];
  relaxation: Relaxation | null;
}

export interface SentenceEvent {
  type: "sentence";
  index: number;
  text: string;
  audio_b64: string | null;
  tts: "server" | "client";
}

export interface DoneEvent {
  type: "done";
  turn_id: string;
  turn: number | null;
  response_text: string;
  verdict: Verdict | null;
  fallback_used: string[];
  timings_ms: Record<string, number>;
  usage: Usage[];
}

export type TurnEvent =
  | TranscriptEvent
  | UnderstandingEvent
  | SearchEvent
  | SentenceEvent
  | DoneEvent;
