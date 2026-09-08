"""Pass A (v3): fronteiras de mapa via faixa CURRENT: X a cada 10s.

Uso: python worker/mapsplit.py  ->  D:\\wikival-work\\checkpoints\\maps.json
[{label, t_start, t_end}] com histerese (2 leituras p/ trocar).
"""
from __future__ import annotations
import json
import subprocess
import sys
import time
from pathlib import Path

WORK = Path("D:/wikival-work")
VIDEO = WORK / "vod_1080p.mp4"
OUT = WORK / "checkpoints" / "maps.json"
sys.path.insert(0, str(Path(__file__).parent))

MAPS_KNOWN = ["PEARL", "LOTUS", "BREEZE", "SPLIT", "SUNSET", "ASCENT", "HAVEN", "SUMMIT"]


def strip_label(img) -> str | None:
    import cv2
    from rois import ROIS_1080P, crop, TESSERACT_EXE
    s = crop(img, ROIS_1080P["map_strip"])
    g = cv2.cvtColor(s, cv2.COLOR_BGR2GRAY)
    g = cv2.resize(g, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    _, buf = cv2.imencode(".png", g)
    p = subprocess.run([TESSERACT_EXE, "stdin", "stdout", "--psm", "6"],
                       input=buf.tobytes(), capture_output=True)
    txt = p.stdout.decode("utf-8", "ignore").upper()
    cur = None
    for m in MAPS_KNOWN:
        if f"CURRENT: {m}" in txt or f"CURRENT:{m}" in txt:
            cur = m
    return cur


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", type=str, default="")
    ap.add_argument("--out", type=str, default="")
    a = ap.parse_args()
    global VIDEO, OUT
    if a.video:
        VIDEO = Path(a.video)
    if a.out:
        OUT = Path(a.out)
    import cv2
    from scan import write_progress
    cap = cv2.VideoCapture(str(VIDEO))
    dur = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) / (cap.get(cv2.CAP_PROP_FPS) or 60.0)
    segs: list[dict] = []
    cur: str | None = None
    cur_start = 0.0
    pending: str | None = None
    pending_n = 0
    t = 0.0
    while t < dur:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, frame = cap.read()
        label = strip_label(frame) if ok else None
        if label != cur:
            if label == pending:
                pending_n += 1
            else:
                pending, pending_n = label, 1
            if pending_n >= 2:
                if cur is not None or True:
                    segs.append({"label": cur, "t_start": cur_start, "t_end": t})
                cur, cur_start = label, t
                pending, pending_n = None, 0
                print(f"  [{t:.0f}s] -> {label}", flush=True)
        else:
            pending, pending_n = None, 0
        if int(t) % 120 == 0:
            write_progress(stage="passA", t_sec=round(t), dur_sec=round(dur),
                           pct=round(100 * t / dur, 1))
        t += 10.0
    segs.append({"label": cur, "t_start": cur_start, "t_end": dur})
    # filtra Nones curtos (intervalos) e mescla adjacentes iguais
    merged: list[dict] = []
    for s in segs:
        if merged and merged[-1]["label"] == s["label"]:
            merged[-1]["t_end"] = s["t_end"]
        else:
            merged.append(dict(s))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(merged, ensure_ascii=False, indent=1), encoding="utf-8")
    print("MAPAS:")
    for s in merged:
        print(f"  {s['label']}: {s['t_start']:.0f}s - {s['t_end']:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
