"""Config central do worker Camada 0 — piloto G2 vs 100T (BR VOD HA87ODmnHLI)."""
from __future__ import annotations

MATCH_ID = "vct-2026-americas-s1-ur1-g2-vs-100t"
YOUTUBE_VIDEO_ID = "HA87ODmnHLI"
YOUTUBE_URL = f"https://www.youtube.com/watch?v={YOUTUBE_VIDEO_ID}"
VLR_URL = "https://www.vlr.gg/660370/g2-esports-vs-100-thieves-vct-2026-americas-stage-1-ur1"
VIDEO_DURATION_SEC = 5715  # via yt-dlp (VALORANT Esports BR)
TOURNAMENT = "VCT 2026 Americas Stage 1"
STAGE = "Playoffs — Upper Round 1 (Bo3)"
BROADCAST = "VALORANT Esports BR (PT-BR)"
TEAM_A = "G2 Esports"
TEAM_B = "100 Thieves"
FINAL_SCORE = "2-0"
WINNER = "teamA"

# Verdade de chao vinda do vlr.gg (Bo3 2-0 G2)
MAPS_GROUND_TRUTH = [
    {"mapIndex": 1, "mapName": "Pearl", "pickBy": "100T", "score": "13-4", "winner": "G2"},
    {"mapIndex": 2, "mapName": "Lotus", "pickBy": "G2",   "score": "13-7", "winner": "G2"},
]

# ROIs relativas (x0,y0,x1,y1 em 0..1) calibradas no VOD BR 1080p (Stage 2).
# Revalidar no Stage 1: layout do HUD pode diferir levemente.
ROIS_720P = {
    "scoreboard": (0.42, 0.005, 0.58, 0.055),
    "timer": (0.478, 0.055, 0.522, 0.095),
    "killfeed": (0.72, 0.06, 0.99, 0.30),
    "round_banner": (0.25, 0.30, 0.75, 0.55),  # "G2 WINS" / faixa de round
}

SAMPLE_FPS = 1.0          # amostragem p/ deteccao macro (barato)
MAX_ROUND_SEC = 100.0     # janela ativa maxima por round
BUY_PHASE_SEC = 30.0      # buy phase padrao antes do roundStart
TIMESTAMP_TOL_SEC = 2.0   # tolerancia alvo do MVP (Fase 4 aperta p/ 0.6s)
