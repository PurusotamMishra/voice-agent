import type { SentenceEvent } from "../api/types";

/** Plays sentences in order: server MP3 when present, browser speech otherwise (H5). */
export class AudioQueue {
  private chain: Promise<void> = Promise.resolve();
  private generation = 0;
  private firstPlayed = false;
  private current: HTMLAudioElement | null = null;
  onFirstPlay: ((epochMs: number) => void) | null = null;
  lang = "en-IN";

  reset(): void {
    this.generation += 1;
    this.chain = Promise.resolve();
    this.firstPlayed = false;
    this.current?.pause();
    this.current = null;
    window.speechSynthesis?.cancel();
  }

  enqueue(sentence: SentenceEvent): void {
    const gen = this.generation;
    this.chain = this.chain.then(() => (gen === this.generation ? this.play(sentence) : undefined));
  }

  private markFirst(): void {
    if (!this.firstPlayed) {
      this.firstPlayed = true;
      this.onFirstPlay?.(Date.now());
    }
  }

  private play(s: SentenceEvent): Promise<void> {
    return new Promise((resolve) => {
      if (s.audio_b64) {
        const audio = new Audio(`data:audio/mpeg;base64,${s.audio_b64}`);
        this.current = audio;
        audio.onplaying = () => {
          if (this.current === audio) this.markFirst();
        };
        audio.onended = () => resolve();
        audio.onerror = () => resolve();
        audio.play().catch(() => resolve());
        return;
      }
      if (!window.speechSynthesis) return resolve();
      const u = new SpeechSynthesisUtterance(s.text.replace(/₹/g, "rupees "));
      u.lang = this.lang;
      u.onstart = () => this.markFirst();
      u.onend = () => resolve();
      u.onerror = () => resolve();
      window.speechSynthesis.speak(u);
    });
  }
}
