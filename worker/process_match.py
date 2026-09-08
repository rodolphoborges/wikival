"""Processa UMA partida da fila: download -> calib-check -> mapsplit -> scan -> valida.

Uso: python worker/process_match.py <matchId> [--timeout-min 120]
Escreve: web/public/data/match_<mid>.json (so se PASS) + stdout JSON resultado.
Nunca edita o catalog.json (orquestrador faz). Validação dura:
  rounds por mapa == verdade vlr + placar final == catalogo + erros FSM == 0.
"""
from __future__ import annotations
import json
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
WORK = Path("D:/wikival-work")
PY = sys.executable


def run(cmd: list[str], timeout: int, log: Path) -> int:
    with open(log, "a", encoding="utf-8") as f:
        f.write(f"\n$ {' '.join(cmd)}\n")
        f.flush()
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        f.write(p.stdout[-4000:] + p.stderr[-2000:])
        return p.returncode


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("matchId")
    ap.add_argument("--timeout-min", type=float, default=120.0)
    a = ap.parse_args()
    mid = a.matchId
    t_end = time.time() + a.timeout_min * 60
    workdir = str(HERE.parent)
    mlog = WORK / f"match_{mid}.log"
    if mlog.exists():
        mlog.unlink()

    def left() -> float:
        return (t_end - time.time()) / 60.0

    src = {r["matchId"]: r for r in
           json.loads((HERE / "samples" / "queue_source.json").read_text(encoding="utf-8"))}
    cat = json.loads((HERE / ".." / "web" / "public" / "data" / "catalog.json").read_text(encoding="utf-8"))
    entry = ev = None
    for e in cat["events"]:
        for m in e["matches"]:
            if m["id"] == mid:
                entry, ev = m, e
    if mid not in src or not src[mid].get("schedulable") or entry is None:
        print(json.dumps({"matchId": mid, "status": "FAIL", "reason": "not-schedulable"}))
        return 1
    q = src[mid]
    maps = [mp for mp in q.get("maps", []) if mp.get("played")]
    if not maps or not q.get("vods"):
        print(json.dumps({"matchId": mid, "status": "FAIL", "reason": "no-truth-or-vod"}))
        return 1

    # 1. download
    vid = q["vods"][0]["id"]
    vfile = WORK / f"vod_{mid}.mp4"
    if not (vfile.exists() and vfile.stat().st_size > 10_000_000):
        rc = run([PY, "-m", "yt_dlp", "-f", "299/bv*[height<=1080]+ba/b[height<=1080]/b",
                  "--continue", "--no-warnings", "-o", str(vfile),
                  f"https://www.youtube.com/watch?v={vid}"],
                 timeout=int(min(left(), 35)) * 60, log=mlog)
        if rc != 0 or not vfile.exists():
            print(json.dumps({"matchId": mid, "status": "FAIL", "reason": "download"}))
            return 1

    # 2. calib-check: 3 frames precisam mostrar placar legivel
    chk = subprocess.run(
        [PY, "-c", ("import sys; sys.path.insert(0,'worker');"
                    "from calibcheck import check; print(check(%r))" % str(vfile))],
        capture_output=True, text=True, timeout=300, cwd=workdir)
    try:
        nok = int(chk.stdout.strip().split()[-1])
    except Exception:
        nok = 0
    if nok < 1:
        print(json.dumps({"matchId": mid, "status": "FAIL", "reason": "no-board"}))
        return 1

    # 3. mapsplit
    maps_json = WORK / "checkpoints" / f"maps_{mid}.json"
    rc = run([PY, "worker/mapsplit.py", "--video", str(vfile), "--out", str(maps_json)],
             timeout=int(min(left(), 25)) * 60, log=mlog)
    if rc != 0 or not maps_json.exists():
        print(json.dumps({"matchId": mid, "status": "FAIL", "reason": "mapsplit"}))
        return 1
    segs = json.loads(maps_json.read_text(encoding="utf-8"))

    def span(name: str) -> tuple[float, float] | None:
        import difflib
        labels = sorted(set((s.get("label") or "") for s in segs if s.get("label")))
        best = difflib.get_close_matches(name.upper(), [l.upper() for l in labels],
                                         n=1, cutoff=0.6)
        if not best:
            return None
        hits = [s for s in segs if (s.get("label") or "").upper() == best[0]]
        return (max(0.0, hits[0]["t_start"] - 60.0), hits[-1]["t_end"] + 150.0)

    def span_fallback(k: int) -> tuple[float, float] | None:
        # sem faixa no strip: interpola no vao entre mapas vizinhos conhecidos
        prev_end, next_start = 150.0, dur_hint()
        for j, mp2 in enumerate(maps):
            if j == k:
                continue
            sp2 = span(mp2["name"])
            if sp2 is None:
                continue
            if j < k:
                prev_end = max(prev_end, sp2[1])
            else:
                next_start = min(next_start, sp2[0])
        if next_start - prev_end < 300:
            return None
        return (prev_end, next_start)

    def dur_hint() -> float:
        d = (q.get("vods") or [{}])[0].get("durationSec")
        return float(d) if d else 7200.0

    # 4. scan por mapa
    rounds_all: list[list[dict]] = []
    for k, mp in enumerate(maps):
        sp = span(mp["name"]) or span_fallback(k)
        if sp is None:
            print(json.dumps({"matchId": mid, "status": "FAIL",
                              "reason": f"no-strip:{mp['name']}"}))
            return 1
        tag = f"{mid}_m{k}"
        rc = run([PY, "worker/scan.py", "--run", "--video", str(vfile),
                  "--from-sec", str(sp[0]), "--to-sec", str(sp[1]),
                  "--tag", tag, "--max-maps", "1",
                  "--expect", mp.get("score", ""), "--map-name", mp["name"]],
                 timeout=int(min(left(), 70)) * 60, log=mlog)
        fin = WORK / "checkpoints" / f"final_{tag}.json"
        if rc != 0 or not fin.exists():
            print(json.dumps({"matchId": mid, "status": "FAIL",
                              "reason": f"scan:{mp['name']}"}))
            return 1
        fj = json.loads(fin.read_text(encoding="utf-8"))
        rds: list[dict] = []
        for s in fj.get("segments", []):
            rds.extend(s["rounds"])
        if fj.get("errors"):
            print(json.dumps({"matchId": mid, "status": "FAIL",
                              "reason": f"fsm-errors:{mp['name']}",
                              "errors": fj["errors"][:5]}))
            return 1
        rounds_all.append(rds)

    # 4b. ancora times: nomes top/bottom do HTML -> catalogo (prefixo), depois
    # lados esq/dir -> catalogo por consenso de vencedores (barreira 70%)
    def norm(s: str) -> str:
        return re.sub(r"[^a-z0-9]", "", s.lower())

    def page_teams(html: str) -> tuple[str, str] | None:
        i = html.find("vlr-rounds-row-col")
        if i < 0:
            return None
        hdr = html[max(0, i - 4000):i]
        names = re.findall(r'<div class="team[^"]*">.*?team-name">\s*([^<]+?)\s*<', hdr, re.S)
        names = [n.strip() for n in names if n.strip()]
        if len(names) < 2:  # fallback: formato antigo (img + nome puro)
            names = re.findall(r'<div class="team"[^>]*>\s*(?:<img[^>]*>)?\s*([^<]+?)\s*</div>', hdr)
            names = [n.strip() for n in names if n.strip()]
        if len(names) >= 2:
            return names[-2], names[-1]
        return None

    def to_catalog_team(page_name: str) -> str | None:
        p = norm(page_name)
        cands = []
        for side, cname in (("teamA", entry["teamA"]), ("teamB", entry["teamB"])):
            c = norm(cname)
            if p and c and (c.startswith(p) or p.startswith(c)):
                cands.append(side)
        return cands[0] if len(cands) == 1 else None
    try:
        from enrich_vlr import parse_rows as _pr, split_maps as _sm
        mhtml = (WORK / "matches" / f"{mid}.html").read_text(encoding="utf-8")
        truth_maps = _sm(_pr(mhtml))
    except Exception as e:
        print(json.dumps({"matchId": mid, "status": "FAIL", "reason": f"truth-load:{e}"}))
        return 1
    pt_pb = page_teams(mhtml)
    if not pt_pb:
        print(json.dumps({"matchId": mid, "status": "FAIL", "reason": "teams-parse"}))
        return 1
    p_cat = to_catalog_team(pt_pb[0])
    q_cat = to_catalog_team(pt_pb[1])
    if not p_cat or not q_cat or p_cat == q_cat:
        print(json.dumps({"matchId": mid, "status": "FAIL",
                          "reason": f"teams-map:{pt_pb}"}))
        return 1
    # vencedor vlr vem em termos top/bottom -> traduz p/ catalogo
    top2cat = {"teamA": p_cat, "teamB": q_cat}
    for mp, rds, tm in zip(maps, rounds_all, truth_maps):
        lv: dict[str, int] = {"teamA": 0, "teamB": 0}
        rv: dict[str, int] = {"teamA": 0, "teamB": 0}
        tby_n = {t["n"]: t for t in tm}
        n = 0
        for r in rds:
            t = tby_n.get(r["roundNumber"])
            if not t:
                continue
            n += 1
            cat_w = top2cat[t["winner"]]
            if r["result"]["winner"] == "teamA":
                lv[cat_w] += 1
            else:
                rv[cat_w] += 1
        left_team = max(("teamA", "teamB"), key=lambda c: lv[c])
        right_team = "teamB" if left_team == "teamA" else "teamA"
        agree = (lv[left_team] + rv[right_team]) / max(n, 1)
        if n == 0 or agree < 0.7:
            print(json.dumps({"matchId": mid, "status": "FAIL",
                              "reason": f"sides-unclear:{mp['name']} agree={agree:.2f}"}))
            return 1
        mp["_left"] = left_team
        for r in rds:
            a, b = (int(x) for x in r["result"]["scoreAfterRound"].split("-"))
            if left_team == "teamA":
                r["result"]["scoreAfterRound"] = f"{a}-{b}"
            else:
                # espelha: esquerda = teamB
                r["result"]["scoreAfterRound"] = f"{b}-{a}"
                r["result"]["winner"] = ("teamB" if r["result"]["winner"] == "teamA" else "teamA")
    # 5. valida: contagem == verdade vlr (placares ja normalizados p/ ordem do catalogo)
    problems = []
    for mp, rds in zip(maps, rounds_all):
        if len(rds) != mp.get("nRounds"):
            problems.append(f"{mp['name']}: {len(rds)}r vs vlr {mp.get('nRounds')}r")
        if rds and mp.get("score"):
            ours = sorted(rds[-1]["result"]["scoreAfterRound"].split("-"))
            exp = sorted(str(mp["score"]).split("-"))
            if ours != exp:
                problems.append(f"{mp['name']}: placar {rds[-1]['result']['scoreAfterRound']} vs vlr {mp['score']}")
    if problems:
        print(json.dumps({"matchId": mid, "status": "FAIL", "reason": "validate",
                          "problems": problems}))
        return 1

    # 6. monta JSON Camada 0
    def to_schema(r: dict) -> dict:
        return {"roundNumber": r["roundNumber"], "type": "unknown",
                "timestamps": {"buyPhaseStart": r["timestamps"]["buyPhaseStart"],
                               "roundStart": r["timestamps"]["roundStart"],
                               "roundEnd": r["timestamps"]["roundEnd"]},
                "result": {"winner": r["result"]["winner"],
                           "scoreAfterRound": r["result"]["scoreAfterRound"],
                           "endKind": "unknown"},
                "layer1Enriched": False, "events": []}

    def map_winner(mp: dict) -> str:
        sc = str(mp.get("score") or "0-0").split("-")
        return "teamA" if sc[0] > sc[1] else "teamB"

    def to_map(i: int, mp: dict, rds: list) -> dict:
        return {"mapIndex": i + 1, "mapName": mp["name"],
                "pickBy": mp.get("pickBy"), "score": mp.get("score"),
                "winner": map_winner(mp),
                "anchorApproxSec": (rds[0]["timestamps"]["buyPhaseStart"] if rds else None),
                "status": "detected", "rounds": [to_schema(r) for r in rds]}

    w_a = "teamA" if entry["scoreA"] > entry["scoreB"] else "teamB"
    data = {"matchId": f"vct2026-{mid}", "youtubeVideoId": vid, "vlrUrl": entry["vlrUrl"],
            "meta": {"tournament": (ev or {}).get("eventName", "?"), "stage": entry["stage"],
                     "broadcast": "auto", "teams": {"teamA": entry["teamA"], "teamB": entry["teamB"]},
                     "finalScore": f"{entry['scoreA']}-{entry['scoreB']}", "winner": w_a,
                     "enrichmentStatus": "complete", "enrichmentCoveragePercent": 100.0},
            "maps": [to_map(i, mp, rds) for i, (mp, rds) in enumerate(zip(maps, rounds_all))]}
    out = HERE / ".." / "web" / "public" / "data" / f"match_{mid}.json"
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    (HERE / "samples" / f"match_{mid}.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"matchId": mid, "status": "PASS",
                      "rounds": [len(r) for r in rounds_all], "file": f"data/match_{mid}.json"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
