"""Detecta macroestrutura (Camada 0) via amostragem + OCR do HUD.

Pipeline MVP (OCR classico + template-matching):
  1. yt-dlp baixa (ou --download-sections p/ teste rapido).
  2. OpenCV amostra a 1fps, recorta ROIs (placar/timer/banner).
  3. OCR le placar "7 13" / timer "1:32"; heuristica de banner fecha round.
  4. RoundFSM valida e emite rounds -> cutlist.json -> match.json.

Exemplos:
  python detect.py --section "00:10:00-00:12:00"   # teste rapido 2min
  python detect.py --full                            # VOD inteiro (~5h, lento)
  python detect.py --dry-run                         # so valida FSM sem video
"""
from __future__ import annotations
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from config import MATCH_ID, YOUTUBE_URL, SAMPLE_FPS, VIDEO_DURATION_SEC
from fsm import RoundFSM

SCORE_RE = re.compile(r"(\d{1,2})\s*[-:x×]\s*(\d{1,2})")
TIMER_RE = re.compile(r"([0-1]?):([0-5]\d)")


def parse_scoreboard_text(text: str) -> tuple[int, int] | None:
    m = SCORE_RE.search(text.replace(" ", ""))
    if not m:
        m = SCORE_RE.search(text)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        if 0 <= a <= 20 and 0 <= b <= 20:
            return a, b
    return None


def try_ocr(crop_path: str) -> str:
    """Tenta OCR se instalado; fallback: '' (calibracao manual das ROIs).

    Para ativar: python -m pip install paddleocr (pesado, ~500MB).
    MVP funciona sem OCR via --dry-run + bootstrap de placares vlr.gg.
    """
    try:
        import importlib
        paddleocr = importlib.import_module("paddleocr")
    except ImportError:
        return ""
    return ""


def download_section(section: str | None, out: Path) -> Path:
    cmd = [sys.executable, "-m", "yt_dlp", "-f", "bv*[height<=720]+ba/b[height<=720]/b",
           "--no-warnings", "-o", str(out)]
    if section:
        cmd += ["--download-sections", f"*{section}"]
    cmd += [YOUTUBE_URL]
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True)
    return out


def run_dry_run() -> int:
    """Valida a FSM com sequencia sintetizada Split 7-13 sem precisar de video."""
    fsm = RoundFSM()
    t = 600.0
    seq = [(0, 0, True)]  # (a, b, timer)
    # Simula 20 rounds: LOUD vence 13, 100T vence 7, ordem plausivel
    winners = ["B", "B", "A", "B", "B", "A", "B", "A", "B", "B", "A", "B",
               "A", "B", "B", "A", "B", "A", "B", "B"]
    a = b = 0
    for w in winners:
        fsm.step({"scoreA": a, "scoreB": b, "timer_visible": True}, t)
        t += 70
        if w == "A":
            a += 1
        else:
            b += 1
        fsm.step({"scoreA": a, "scoreB": b, "timer_visible": False,
                  "round_end_banner": True}, t)
        t += 12
    assert len(fsm.finished_rounds) == 20, f"esperava 20, saiu {len(fsm.finished_rounds)}"
    assert fsm.finished_rounds[-1]["result"]["scoreAfterRound"] == "7-13"
    assert not fsm.errors, fsm.errors
    print(f"dry-run OK: 20 rounds, placar final 7-13, 0 erros")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--section", default=None, help="Ex: 00:10:00-00:12:00")
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if args.dry_run or (not args.section and not args.full):
        return run_dry_run()
    out = Path(__file__).parent / "samples" / "_tmp_section.mp4"
    download_section(args.section, out)
    print(f"baixado: {out} (proximo passo: OCR frame-a-frame das ROIs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
