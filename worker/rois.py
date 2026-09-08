"""ROIs do HUD para o VOD BR 1080p (1920x1080) — calibrar na Etapa 2.

Coordenadas relativas (0..1); scan.py escala para a resolucao real do frame.
Layout padrao Valorant Champions broadcast:
  - placar: topo-centro (logos + "7 : 13")
  - timer: logo abaixo do placar ("1:32" some no buy phase / aparece no live)
  - banner: faixa central ("100 THIEVES WINS THE ROUND" / inicio de mapa)
"""
from __future__ import annotations

# Calibrado em frames reais do VOD BR 1080p (Etapa 2, 07/09/2026).
# Placar topo-centro: "100T 6 | ROUND 11 1:39 | 4 LOUD".
# Digitos grandes brancos em fundo gradiente -> cinza 3x SEM threshold, PSM 8.
ROIS_1080P: dict[str, tuple[float, float, float, float]] = {
    "scoreboard": (0.32, 0.005, 0.68, 0.07),   # bloco inteiro (debug)
    "score_left": (0.412, 0.004, 0.470, 0.058),  # digito(s) G2 (com padding)
    "score_right": (0.550, 0.004, 0.598, 0.058),  # digito(s) 100T (sem divisoria)
    "timer": (0.472, 0.022, 0.534, 0.062),  # "1:39" (abaixo de ROUND N)
    "round_label": (0.462, 0.004, 0.538, 0.028),  # "ROUND 11" (pequeno, best-effort)
    "map_strip": (0.0, 0.002, 0.33, 0.024),  # "SPLIT 7-13 > CURRENT: SUNSET > ..."
    "banner": (0.25, 0.30, 0.75, 0.55),
}

TESSERACT_EXE = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def crop(frame, roi: tuple[float, float, float, float]):
    """Recorta ROI relativa de um frame OpenCV (h, w, c)."""
    h, w = frame.shape[:2]
    x0, y0, x1, y1 = roi
    return frame[int(y0 * h):int(y1 * h), int(x0 * w):int(x1 * w)]


def clean_score(bgr):
    """Threshold + abertura 3x3 (remove filetes/divisorias) + trim ao digito + 3x.

    Retorna imagem binaria pronta p/ Tesseract ou None se sem conteudo.
    """
    import cv2
    import numpy as np
    g = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    _, th = cv2.threshold(g, 150, 255, cv2.THRESH_BINARY)
    th = cv2.morphologyEx(th, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    ys, xs = np.where(th > 0)
    if len(xs) < 30:
        return None
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    pad = 6
    h, w = th.shape
    roi = th[max(0, y0 - pad):y1 + pad, max(0, x0 - pad):x1 + pad]
    return cv2.resize(roi, None, fx=3, fy=3, interpolation=cv2.INTER_NEAREST)


def trim_to_content(bgr, thresh: int = 150, pad: float = 0.25):
    """Recorta box ao redor dos pixels claros (digitos) — adapta-se a 1-2 digitos."""
    import cv2
    import numpy as np
    g = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    ys, xs = np.where(g > thresh)
    if len(xs) < 50:
        return bgr
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    dx, dy = int((x1 - x0) * pad) + 4, int((y1 - y0) * pad) + 4
    h, w = g.shape
    return bgr[max(0, y0 - dy):y1 + dy, max(0, x0 - dx):x1 + dx]


def preprocess_scoreboard(crop_img):
    """Upscale 2x + cinza + threshold adaptativo p/ digitos do placar."""
    import cv2
    g = cv2.cvtColor(crop_img, cv2.COLOR_BGR2GRAY)
    g = cv2.resize(g, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
    _, th = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return th
