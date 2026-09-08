"""Calib-check rapido: 3 frames amostrais precisam mostrar placar legivel.

Uso: from calibcheck import check; check("D:/x.mp4") -> n pares validos (0..3)
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from scan import Reader
from rois import ROIS_1080P, crop

SCORE_RE = re.compile(r"^\d{1,2}$")


def check(video: str) -> int:
    import cv2
    cap = cv2.VideoCapture(video)
    if not cap.isOpened():
        return 0
    fps = cap.get(cv2.CAP_PROP_FPS) or 60.0
    dur = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) / fps
    r = Reader()
    ok = 0
    for frac in (0.1, 0.3, 0.5):
        cap.set(cv2.CAP_PROP_POS_MSEC, dur * frac * 1000)
        good, frame = cap.read()
        if not good:
            continue
        la = r.ocr(crop(frame, ROIS_1080P["score_left"]), 8)
        ra = r.ocr(crop(frame, ROIS_1080P["score_right"]), 8)
        if SCORE_RE.match(la) and SCORE_RE.match(ra):
            ok += 1
    cap.release()
    return ok


if __name__ == "__main__":
    print(check(sys.argv[1]))
