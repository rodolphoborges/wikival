"""Turno da madrugada: miner -> agenda -> site -> 2 partidas -> revisao -> docs -> push.

Uso: python worker/overnight.py [--max-matches 2]
Tudo com timeout e try/except por etapa (nunca trava). Log: D:/wikival-work/overnight.log
Progresso visivel no dashboard via progress.json. Ao final: WAKEUP.md p/ leitura matinal.
"""
from __future__ import annotations
import datetime
import json
import subprocess
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent
WORK = Path("D:/wikival-work")
LOG = WORK / "overnight.log"
PY = sys.executable
START = time.time()
DEADLINE = START + 7 * 3600
MAX_MATCHES = 2
sys.path.insert(0, str(HERE))
try:
    from ledger import set_status, find, log_job
except ImportError:  # pragma: no cover
    set_status = lambda *a, **k: None
    find = lambda *a, **k: None
    log_job = lambda *a, **k: ""


def log(msg: str) -> None:
    line = f"[{datetime.datetime.now():%H:%M:%S}] {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def progress(**kw) -> None:
    try:
        (WORK / "progress.json").write_text(json.dumps(
            {"updated_at": datetime.datetime.now().strftime("%H:%M:%S"), **kw},
            ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        pass


def sh(cmd: list[str], timeout_min: float, cwd: str = "") -> tuple[int, str]:
    log("$ " + " ".join(cmd[:6]) + (" ..." if len(cmd) > 6 else ""))
    try:
        p = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=int(timeout_min * 60),
                           cwd=cwd or str(ROOT))
        tail = (p.stdout + p.stderr)[-1500:]
        return p.returncode, tail
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT"


def wait_miner(timeout_min: float = 180.0) -> bool:
    log("etapa 0: aguardando minerador (Fase A)")
    t0 = time.time()
    while time.time() - t0 < timeout_min * 60:
        try:
            src = json.loads((HERE / "samples" / "queue_source.json").read_text(encoding="utf-8"))
            done = sum(1 for r in src if r.get("done"))
            log(f"miner: {done}/{len(src)}")
            progress(stage="overnight:miner", pct=round(100 * done / max(len(src), 1), 1))
            if done >= len(src) and len(src) >= 400:
                return True
        except Exception as e:
            log(f"miner: aguardando arquivo ({e})")
        time.sleep(120)
    return False


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-matches", type=int, default=MAX_MATCHES)
    a = ap.parse_args()
    report: list[str] = [f"# Turno da madrugada — {datetime.date.today().isoformat()}", ""]
    try:
        progress(stage="overnight:start")
        ok_miner = wait_miner()
        report.append(f"- minerador: {'completo' if ok_miner else 'incompleto (seguindo com o que ha)'}")

        progress(stage="overnight:agenda")
        rc, _ = sh([PY, "worker/plan_queue.py", "--replan"], 10)
        sched = json.loads((ROOT / "web" / "public" / "data" / "schedule.json").read_text(encoding="utf-8"))
        report.append(f"- agenda: {len(sched['slots'])} slots, ETA {sched['funnel']['totalEtaMin']:.0f}min")

        progress(stage="overnight:build")
        rc, out = sh(["cmd", "/c", "npm run build"], 10, cwd=str(ROOT / "web"))
        report.append(f"- build site: {'OK' if rc == 0 else 'FAIL'}")

        # partidas: piloto travado nos vizinhos do validado (mesmo broadcast BR),
        # depois fila geral por preferencia de evento
        planned = [s for s in sched["slots"] if s["status"] == "planned"]
        by_id = {s["matchId"]: s for s in planned}
        picks = [by_id[m] for m in ("660369", "660371") if m in by_id]
        pref = [s for s in planned if s.get("eventId") == "2860" and s not in picks]
        rest = [s for s in planned if s.get("eventId") != "2860"]
        slots = (picks + pref + rest)[:a.max_matches]
        results = []
        for s in slots:
            if time.time() > DEADLINE - 3600:
                log("deadline proximo: pulando partidas restantes")
                break
            mid = s["matchId"]
            progress(stage="overnight:match", detail=f"{mid} {s['teams']}")
            log(f"processando {mid} {s['teams']} (~{s['etaMin']}min)")
            rc, out = sh([PY, "worker/process_match.py", mid, "--timeout-min", "100"], 115)
            try:
                last = [ln for ln in out.splitlines() if ln.strip().startswith("{")]
                res = json.loads(last[-1]) if last else {"status": "FAIL", "reason": "no-output"}
            except Exception:
                res = {"status": "FAIL", "reason": "parse"}
            res["matchId"] = mid
            results.append(res)
            log(f"{mid}: {res.get('status')} {res.get('reason', '')}")
            progress(stage="overnight:match-done", detail=f"{mid} {res.get('status')}")
        passed = [r for r in results if r.get("status") == "PASS"]
        failed = [r for r in results if r.get("status") != "PASS"]
        for r in results:
            j = find(r["matchId"], "running") or find(r["matchId"], "planned")
            if j:
                set_status(j["id"], "done" if r.get("status") == "PASS" else "failed",
                           f"{r.get('status')} {r.get('reason', '')} {r.get('rounds', '')}")
        # varredura final: resultados PASS externos (ex.: paralelo manual) em proc*.out
        for out in sorted(WORK.glob("proc*.out")):
            try:
                lines = out.read_text(encoding="utf-8").splitlines()
                last = [ln for ln in lines if ln.strip().startswith("{")]
                if not last:
                    continue
                res = json.loads(last[-1])
                if res.get("status") == "PASS" and res.get("matchId") not in [r["matchId"] for r in results]:
                    res["matchId"] = res.get("matchId")
                    results.append(res)
                    passed.append(res)
                    log(f"sweep: {res['matchId']} PASS externo incorporado")
                    j = find(res["matchId"], "running") or find(res["matchId"])
                    if j:
                        set_status(j["id"], "done", f"PASS {res.get('rounds', '')}")
            except Exception as e:
                log(f"sweep {out.name}: {e}")
        report.append(f"- partidas: {len(passed)} PASS, {len(failed)} FAIL")
        for r in results:
            report.append(f"  - {r['matchId']}: {r.get('status')} {r.get('reason', '')} {r.get('rounds', '')}")

        # catalogo: marca processadas
        if passed:
            cat_p = ROOT / "web" / "public" / "data" / "catalog.json"
            cat = json.loads(cat_p.read_text(encoding="utf-8"))
            for r in passed:
                for ev in cat["events"]:
                    for m in ev["matches"]:
                        if m["id"] == r["matchId"]:
                            m["status"] = "processed"
                            m["dataFile"] = r.get("file", f"data/match_{r['matchId']}.json")
            cat_p.write_text(json.dumps(cat, ensure_ascii=False, indent=1), encoding="utf-8")
            sh(["cmd", "/c", "npm run build"], 10, cwd=str(ROOT / "web"))
            report.append("- catalogo atualizado + rebuild")
            j = find("revisao")
            if j:
                set_status(j["id"], "done", f"{len(passed)} PASS / {len(failed)} FAIL")

        # docs + commit/push
        stamp = datetime.date.today().isoformat()
        (ROOT / "docs" / f"overnight_{stamp}.md").write_text("\n".join(report) + "\n", encoding="utf-8")
        sh(["git", "add", "-A"], 2)
        sh(["git", "commit", "-m", f"turno madrugada {stamp}: agenda + {len(passed)} partida(s)"], 2)
        rc, _ = sh(["git", "push", "origin", "main"], 5)
        report.append(f"- push: {'OK' if rc == 0 else 'FAIL (ver log)'}")
        j = find("documentacao")
        if j:
            set_status(j["id"], "done" if rc == 0 else "failed", f"push {'OK' if rc == 0 else 'FAIL'}")

        progress(stage="overnight:done", detail=f"{len(passed)} PASS / {len(failed)} FAIL")
    except Exception:
        log("ERRO FATAL:\n" + traceback.format_exc())
        report.append("- ERRO FATAL (ver overnight.log)")
    wake = ["# Bom dia — resumo do turno", "",
            f"duracao: {(time.time() - START) / 3600:.1f}h", ""] + report + [
            "", "ver: docs/overnight_*.md, D:/wikival-work/overnight.log, dashboard :8000"]
    (WORK / "WAKEUP.md").write_text("\n".join(wake), encoding="utf-8")
    j = find("relatorio matinal")
    if j:
        set_status(j["id"], "done", "WAKEUP.md")
    log("WAKEUP.md escrito. Fim do turno.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
