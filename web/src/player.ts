/* Wrapper fino sobre a YouTube IFrame API (modo MVP: seekTo + +/-2s). */
declare global {
  interface Window {
    YT?: {
      Player: new (
        el: string | HTMLElement,
        opts: {
          videoId: string;
          playerVars?: Record<string, unknown>;
          events?: { onReady?: (e: { target: YTPlayer }) => void };
        },
      ) => YTPlayer;
    };
    onYouTubeIframeAPIReady?: () => void;
  }
}

export interface YTPlayer {
  seekTo(sec: number, allowSeekAhead: boolean): void;
  getCurrentTime(): number;
  getDuration(): number;
  playVideo(): void;
}

export class YTController {
  private player: YTPlayer | null = null;
  private pendingSeek: number | null = null;
  private readyWatchdog: number | null = null;

  constructor(
    private videoId: string,
    private mountId = "yt-player",
  ) {}

  mount(): void {
    // div fresca a cada montagem: a API do YT substitui a div por iframe,
    // entao remontar sobre o iframe antigo quebra o seek.
    const old = document.getElementById(this.mountId);
    if (old) {
      const fresh = document.createElement("div");
      fresh.id = this.mountId;
      fresh.className = old.className;
      const w = old.style.width;
      if (w) fresh.style.width = w;
      old.replaceWith(fresh);
    }
    if (this.readyWatchdog != null) clearTimeout(this.readyWatchdog);
    if (window.YT?.Player) {
      this.create();
      return;
    }
    window.onYouTubeIframeAPIReady = () => this.create();
    this.readyWatchdog = window.setTimeout(() => {
      if (!this.player) this.complain("YT API nao carregou (bloqueador de ads? offline?)");
    }, 12000);
  }

  private complain(msg: string): void {
    const label = document.getElementById("chap-label");
    if (label) label.textContent = `# erro player: ${msg}`;
  }

  private create(): void {
    try {
      this.player = new window.YT!.Player(this.mountId, {
        videoId: this.videoId,
        playerVars: { rel: 0 },
        events: {
          onReady: () => {
            if (this.readyWatchdog != null) {
              clearTimeout(this.readyWatchdog);
              this.readyWatchdog = null;
            }
            if (this.pendingSeek != null) {
              this.seek(this.pendingSeek);
              this.pendingSeek = null;
            }
          },
        },
      });
    } catch {
      this.complain("falha ao criar player YT");
    }
  }

  seek(sec: number): void {
    if (!this.player) {
      this.pendingSeek = sec;
      return;
    }
    this.player.seekTo(Math.max(0, sec), true);
    this.player.playVideo();
  }

  nudge(delta: number): void {
    if (!this.player) return;
    this.seek(this.player.getCurrentTime() + delta);
  }

  now(): number | null {
    try {
      return this.player ? this.player.getCurrentTime() : null;
    } catch {
      return null;
    }
  }
}

export function fmt(sec: number | null): string {
  if (sec == null) return "--:--";
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = Math.floor(sec % 60);
  const mm = h > 0 ? String(m).padStart(2, "0") : String(m);
  return `${h > 0 ? h + ":" : ""}${mm}:${String(s).padStart(2, "0")}`;
}
