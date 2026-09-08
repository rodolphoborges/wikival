"""Gera match.json Camada 0 a partir de rounds detectados + verdade de chao vlr.gg.

Uso:
  python cutlist.py   # gera esqueleto com mapas/placares e rounds pendentes
"""
from __future__ import annotations
import json
from pathlib import Path

from config import (MATCH_ID, YOUTUBE_VIDEO_ID, VLR_URL, VIDEO_DURATION_SEC,
                    MAPS_GROUND_TRUTH, TOURNAMENT, STAGE, BROADCAST,
                    TEAM_A, TEAM_B, FINAL_SCORE, WINNER)


def _canon(w: str) -> str:
    if w in ("teamA", "teamB"):
        return w
    if w == TEAM_A or w in ("G2", "G2 Esports"):
        return "teamA"
    return "teamB"


def skeleton() -> dict:
    return {
        "matchId": MATCH_ID,
        "youtubeVideoId": YOUTUBE_VIDEO_ID,
        "vlrUrl": VLR_URL,
        "meta": {
            "tournament": TOURNAMENT,
            "stage": STAGE,
            "broadcast": BROADCAST,
            "videoDurationSec": VIDEO_DURATION_SEC,
            "teams": {"teamA": TEAM_A, "teamB": TEAM_B},
            "finalScore": FINAL_SCORE,
            "winner": WINNER,
            "enrichmentStatus": "in_progress",
            "enrichmentCoveragePercent": 0.0,
        },
        "maps": [
            {
                "mapIndex": m["mapIndex"],
                "mapName": m["mapName"],
                "pickBy": m["pickBy"],
                "score": m["score"],
                "winner": _canon(m["winner"]),
                "anchorApproxSec": None,
                "status": "pending_detection",
                "rounds": [],
            }
            for m in MAPS_GROUND_TRUTH
        ],
    }


if __name__ == "__main__":
    out = Path(__file__).parent / "samples" / "match.piloto.json"
    out.write_text(json.dumps(skeleton(), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"esqueleto escrito em {out}")
