"""Varredura total Camada 0: 1 amostra/s x video inteiro -> placar/timer -> FSM -> JSON.

Estrategia eficiente (calibrada 07/09/2026 no VOD BR 1080p):
  - timer: OCR leve (PSM 7) a cada amostra; live = regex \\d:\\d (colon filtra lixo)
  - placar: OCR so quando diff de pixels do box muda ou a cada 60s (re-sync)
  - mudanca de placar so aceita com 2 leituras iguais seguidas (voto anti-ruido)
  - sem placar (replay/entrevista/facecam): mantem ultimo placar (hold)

Uso:
  python worker/scan.py --calibrate            # ~20 frames p/ Etapa 2
  python worker/scan.py --run                  # varredura total (retomavel)
  python worker/scan.py --run --from-sec 9000  # retoma de ponto especifico
"""
from __future__ import annotations
import argparse
import json
import re
import subprocess
import sys
import time
from collections import deque
from pathlib import Path

WORK = Path("D:/wikival-work")
VIDEO = WORK / "vod_1080p.mp4"
PROGRESS = WORK / "progress.json"
CALIB_DIR = WORK / "frames"
CKPT_DIR = WORK / "checkpoints"

TIMER_RE = re.compile(r"\d:\d")
TIMER_FULL_RE = re.compile(r"(\d):([0-5]\d)")
SCORE_RE = re.compile(r"^\d{1,2}$")
STEP_SEC = 1.0
RESYNC_EVERY_SEC = 60
VOTE_WINDOW = 12
VOTE_MIN = 3  # fantasma precisa vencer 3 leituras em 12 (atraso compensado por backdate)
VOTE_STALL = 8  # par divergente dominante por 8+ leituras = dessinc: ressincroniza com erro
SCORE_EVERY_SEC = 3.0  # OCR de placar periodico (diff sozinho morre de fome em placa estatica)
RESET_HOLD_SEC = 10
LIVE_MEMORY_SEC = 180


def write_progress(**kw) -> None:
    try:
        PROGRESS.write_text(json.dumps(
            {"updated_at": time.strftime("%H:%M:%S"), **kw},
            ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        pass


def calibrate() -> int:
    import cv2
    cap = cv2.VideoCapture(str(VIDEO))
    if not cap.isOpened():
        print(f"ERRO: nao abriu {VIDEO}")
        return 1
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    dur = total / fps
    print(f"video: {dur:.0f}s, {fps:.1f}fps")
    CALIB_DIR.mkdir(parents=True, exist_ok=True)
    for i in range(20):
        t = dur * (i + 0.5) / 20
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, frame = cap.read()
        if ok:
            cv2.imwrite(str(CALIB_DIR / f"calib_{i:02d}_{int(t)}s.jpg"), frame,
                        [cv2.IMWRITE_JPEG_QUALITY, 80])
    cap.release()
    write_progress(stage="calibracao", detail=f"20 frames em {CALIB_DIR}")
    return 0


class Reader:
    def __init__(self) -> None:
        import cv2  # noqa: F401
        from rois import TESSERACT_EXE
        self.exe = TESSERACT_EXE

    def ocr(self, img, psm: int) -> str:
        import cv2
        from rois import clean_score
        if psm == 8:  # placar: limpa filetes + isola digito
            pre = clean_score(img)
            if pre is None:
                return ""
        else:  # timer: cinza 3x direto
            g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            pre = cv2.resize(g, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
        _, buf = cv2.imencode(".png", pre)
        p = subprocess.run(
            [self.exe, "stdin", "stdout", "--psm", str(psm),
             "-c", "tessedit_char_whitelist=0123456789:"],
            input=buf.tobytes(), capture_output=True)
        return p.stdout.decode("utf-8", "ignore").strip()

    @staticmethod
    def changed(a, b, thresh: float = 0.02) -> bool:
        import cv2
        if a is None or b is None or a.shape != b.shape:
            return True
        ga = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY)
        gb = cv2.cvtColor(b, cv2.COLOR_BGR2GRAY)
        diff = (cv2.absdiff(ga, gb) > 25).mean()
        return diff > thresh


def run(from_sec: float = 0.0, to_sec: float | None = None,
        tag: str = "", max_maps: int = 3, expect_end: str = "",
        map_name: str = "") -> int:
    import cv2
    from rois import ROIS_1080P, crop
    from fsm import RoundFSM
    ckpt_prefix = f"{tag}_" if tag else ""
    final_name = f"final_{tag}.json" if tag else "final.json"
    expA = expB = -1
    if "-" in expect_end:
        try:
            expA, expB = (int(x) for x in expect_end.split("-"))
        except ValueError:
            pass

    cap = cv2.VideoCapture(str(VIDEO))
    if not cap.isOpened():
        print(f"ERRO: nao abriu {VIDEO}")
        return 1
    fps = cap.get(cv2.CAP_PROP_FPS) or 60.0
    dur = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) / fps
    if to_sec is not None:
        dur = min(dur, to_sec)
    reader = Reader()
    fsm = RoundFSM()
    segments: list[dict] = []  # [{map_idx, rounds}] — novo segmento a cada reset de placar
    map_idx = 1
    MAX_MAPS = max_maps  # pass B por mapa: max_maps=1 desliga resets
    votes: list[tuple[tuple[int, int], float]] = []  # ((a,b), t) DIVERGENTES
    last_score_ocr = -1e9
    pending_end_backdate: tuple[float, float] | None = None
    last_L = last_R = None
    scoreA = scoreB = 0
    has_board = False  # algum dia viu placar valido (buy so ancora apos isso)
    last_live_t = -1e9
    prev_timer_sec: int | None = None
    reset_streak = 0
    last_resync = -RESYNC_EVERY_SEC
    obs_count = 0

    ckpts = sorted(CKPT_DIR.glob(f"obs_{ckpt_prefix}*.json"))
    t = from_sec
    if ckpts and from_sec == 0.0:
        last = json.loads(ckpts[-1].read_text(encoding="utf-8"))
        t = float(last["t_end"])
        for o in last["obs"]:
            for _ in fsm.step(o, o["_t"]):
                pass
        scoreA, scoreB = fsm.state.scoreA, fsm.state.scoreB
        print(f"retomando de t={t:.0f}s placar {scoreA}-{scoreB}")

    CKPT_DIR.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    last_flush = 0.0
    traj: list[dict] = []
    while t < dur:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, frame = cap.read()
        if not ok:
            t += STEP_SEC
            continue
        tbox = crop(frame, ROIS_1080P["timer"])
        lbox = crop(frame, ROIS_1080P["score_left"])
        rbox = crop(frame, ROIS_1080P["score_right"])
        timer_txt = reader.ocr(tbox, 7)
        m_full = TIMER_FULL_RE.search(timer_txt)
        timer_sec = (int(m_full.group(1)) * 60 + int(m_full.group(2))) if m_full else None
        # freeze time (buy) mostra 0:30->0:00: so conta como live acima de 32s.
        # spike plantada troca o timer por icone (live=False, comportamento mantido).
        live = timer_sec is not None and timer_sec > 32
        if live:
            last_live_t = t
        if timer_sec is not None and prev_timer_sec is not None:
            if timer_sec - prev_timer_sec > 30:
                # salto p/ cima = fim do freeze: inicio real do round (corrige R1: 190->191)
                if fsm.state.phase == "BUY" and has_board:
                    fsm.state.round_start = t
                    fsm.state.phase = "LIVE"
        if timer_sec is not None:
            prev_timer_sec = timer_sec

        force = (t - last_resync) >= RESYNC_EVERY_SEC
        periodic = (t - last_score_ocr) >= SCORE_EVERY_SEC
        if force or periodic or reader.changed(lbox, last_L) or reader.changed(rbox, last_R):
            last_resync = t if force else last_resync
            if force or periodic:
                last_score_ocr = t
            la, ra = reader.ocr(lbox, 8), reader.ocr(rbox, 8)
            ma, mb = SCORE_RE.match(la), SCORE_RE.match(ra)
            if ma and mb:
                na, nb = int(la), int(ra)
                if 0 <= na <= 20 and 0 <= nb <= 20:
                    has_board = True
                    if (na, nb) == (scoreA, scoreB):
                        votes.clear()  # leitura igual ao atual: zera divergentes
                        reset_streak = 0
                    else:
                        votes.append(((na, nb), t))
                        votes = votes[-VOTE_WINDOW:]
                        pairs = [v[0] for v in votes]
                        top, cnt = max(((v, pairs.count(v)) for v in set(pairs)),
                                       key=lambda kv: kv[1])
                        ta, tb = top
                        first_seen = min(v[1] for v in votes if v[0] == top)
                        is_flip = (ta + tb == scoreA + scoreB + 1)
                        is_low = (ta + tb < scoreA + scoreB - 2)
                        # truth-guide: aceita o placar esperado mesmo com lados trocados
                        # (overlay pode inverter; ex.: espera 13-8, le 8-13)
                        is_expected = (expA >= 0 and sorted((ta, tb)) == sorted((expA, expB)))
                        need = VOTE_MIN - 1 if (is_expected and
                                                t - last_live_t < 300) else VOTE_MIN
                        # flip breve mas duplo-consecutivo do placar ESPERADO vale
                        # (closer some rapido do ar; fantasma nunca acerta o placar final)
                        consec = (len(votes) >= 2 and votes[-1][0] == votes[-2][0] == top
                                  and is_expected)
                        if cnt >= need and is_flip and t - last_live_t < LIVE_MEMORY_SEC:
                            accept = True
                        elif consec and is_flip and t - last_live_t < 300:
                            accept = True
                        else:
                            accept = False
                        if accept:
                            scoreA, scoreB = ta, tb  # flip +1 com round vivo
                            votes.clear()
                            reset_streak = 0
                            pending_end_backdate = (first_seen, t)
                        elif is_low:
                            # candidato a reset: exige persistencia (transicoes nao duram 30s)
                            reset_streak += 1
                            if reset_streak >= RESET_HOLD_SEC and cnt >= VOTE_MIN and \
                                    t - last_live_t > 120 and map_idx < MAX_MAPS:
                                segments.append({"map_idx": map_idx,
                                                 "rounds": fsm.finished_rounds,
                                                 "end_score": f"{scoreA}-{scoreB}",
                                                 "t_end": t})
                                map_idx += 1
                                fsm = RoundFSM()
                                fsm.state.scoreA, fsm.state.scoreB = ta, tb
                                fsm.state.round_number = ta + tb + 1
                                fsm.errors.append(
                                    f"[{t:.0f}s] novo mapa #{map_idx}: ancora em {ta}-{tb}")
                                scoreA, scoreB = ta, tb
                                votes.clear()
                                reset_streak = 0
                        elif cnt >= VOTE_STALL:
                            # par divergente domina a janela mas nao eh flip nem reset:
                            # dessinc (fantasma antigo) -> ressincroniza e segue
                            fsm.errors.append(
                                f"[{t:.0f}s] STALL: {scoreA}-{scoreB} -> {ta}-{tb} "
                                f"({cnt}x); ressincronizando")
                            scoreA, scoreB = ta, tb
                            fsm.state.scoreA, fsm.state.scoreB = ta, tb
                            fsm.state.round_number = ta + tb + 1
                            fsm.state.phase = "BUY"
                            fsm.state.buy_start = None
                            fsm.state.round_start = None
                            votes.clear()
                            reset_streak = 0
                            pending_end_backdate = None
                        else:
                            reset_streak = 0
            last_L, last_R = lbox, rbox

        if not has_board:
            t += STEP_SEC  # pre-game sem placar: nao ancora buy em t=0
            continue
        obs = {"scoreA": scoreA, "scoreB": scoreB, "timer_visible": live,
               "round_end_banner": False, "_t": t}
        events = fsm.step({k: v for k, v in obs.items() if not k.startswith("_")}, t)
        if pending_end_backdate is not None:
            first_seen, accepted_at = pending_end_backdate
            if events and t - accepted_at <= 3:
                # fim real = 1a leitura divergente (placar vira no banner, nao no freeze seguinte)
                for ev in events:
                    if ev.get("type") == "round_end":
                        ev["timestamps"]["roundEnd"] = first_seen
            if not events or t - accepted_at > 3:
                pending_end_backdate = None
            elif events:
                pending_end_backdate = None
        traj.append({"t": t, "a": scoreA, "b": scoreB, "live": live})
        obs_count += 1
        t += STEP_SEC

        if time.time() - last_flush > 10:
            last_flush = time.time()
            el = max(time.time() - t0, 0.01)
            rate = (t - (from_sec or 0)) / el
            write_progress(stage="varredura", t_sec=round(t), dur_sec=round(dur),
                           pct=round(100 * t / dur, 1), rounds=len(fsm.finished_rounds),
                           score=f"{scoreA}-{scoreB}", rate_fps=round(rate, 1),
                           eta_min=round((dur - t) / max(rate, 0.01) / 60, 1),
                           errors=len(fsm.errors),
                           tag=tag or None, map=map_name or None,
                           round_now=fsm.state.round_number,
                           phase=fsm.state.phase,
                           detail=(f"{map_name} R{fsm.state.round_number} [{fsm.state.phase}] "
                                   f"{scoreA}-{scoreB}" + (f" · tag {tag}" if tag else "")))
        if int(t) % 300 == 0:
            (CKPT_DIR / f"obs_{ckpt_prefix}{int(t):06d}.json").write_text(
                json.dumps([{"scoreA": o["a"], "scoreB": o["b"],
                             "timer_visible": o["live"],
                             "round_end_banner": False, "_t": o["t"]}
                            for o in traj], ensure_ascii=False), encoding="utf-8")
    cap.release()
    segments.append({"map_idx": map_idx, "rounds": fsm.finished_rounds,
                     "end_score": f"{scoreA}-{scoreB}", "t_end": t})
    total_rounds = sum(len(s["rounds"]) for s in segments)
    (CKPT_DIR / final_name).write_text(json.dumps(
        {"t_end": t, "segments": segments, "rounds": fsm.finished_rounds,
         "errors": fsm.errors, "traj_tail": traj[-50:]},
        ensure_ascii=False, indent=1), encoding="utf-8")
    write_progress(stage="varredura_concluida", pct=100.0,
                   rounds=total_rounds, errors=len(fsm.errors),
                   detail=" | ".join(
                       f"mapa{s['map_idx']}:{s['end_score']}({len(s['rounds'])}r)"
                       for s in segments))
    print(f"FIM: {total_rounds} rounds em {len(segments)} segmentos, "
          f"{len(fsm.errors)} erros")
    for s in segments:
        print(f"  mapa{s['map_idx']}: {s['end_score']} "
              f"({len(s['rounds'])} rounds) t_end={s['t_end']:.0f}s")
    for e in fsm.errors[:30]:
        print("  !", e)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--calibrate", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--from-sec", type=float, default=0.0)
    ap.add_argument("--to-sec", type=float, default=None)
    ap.add_argument("--tag", type=str, default="")
    ap.add_argument("--max-maps", type=int, default=3)
    ap.add_argument("--expect", type=str, default="",
                    help="Placar final esperado vlr.gg (ex: 13-4): aceita com 1 voto a menos")
    ap.add_argument("--map-name", type=str, default="",
                    help="Nome do mapa p/ o dashboard (ex: Pearl)")
    ap.add_argument("--video", type=str, default="",
                    help="Arquivo de video (padrao D:/wikival-work/vod_1080p.mp4)")
    a = ap.parse_args()
    global VIDEO
    if a.video:
        VIDEO = Path(a.video)
    if a.calibrate:
        return calibrate()
    if a.run:
        return run(a.from_sec, a.to_sec, a.tag, a.max_maps, a.expect, a.map_name)
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent))
    raise SystemExit(main())
