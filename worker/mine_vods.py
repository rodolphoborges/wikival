"""Fase A: minera VODs + verdade de chao das 488 partidas (com cache + resume).

Para cada partida: pagina vlr -> youtu.be IDs, mapas (nome/pick/vencedor),
rounds (placar pos-round, vencedor, endKind), duracao via yt-dlp (cache).
Saida: worker/samples/queue_source.json
Uso: python worker/mine_vods.py [--no-probe]   (roda em background, ~40min)
"""
from __future__ import annotations
import json
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from enrich_vlr import parse_rows, split_maps

CACHE = Path("D:/wikival-work/matches")
CACHE.mkdir(parents=True, exist_ok=True)
OUT = HERE / "samples" / "queue_source.json"
PROBE_CACHE = CACHE / "_durations.json"

MAPNAV_RE = re.compile(
    r'js-map-switch[^>]*data-game-id="(\d+)"[^>]*>(.*?)</a>', re.S)
VOD_RE = re.compile(r'youtu\.be/([A-Za-z0-9_-]{6,})')


def get(url: str, dest: Path) -> str:
    if dest.exists() and dest.stat().st_size > 10000:
        return dest.read_text(encoding="utf-8")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    data = urllib.request.urlopen(req, timeout=60).read().decode("utf-8")
    dest.write_text(data, encoding="utf-8")
    time.sleep(1.5)
    return data


def probe(vid: str, cache: dict, do_probe: bool) -> int | None:
    if vid in cache:
        return cache[vid]
    if not do_probe:
        return None
    try:
        p = subprocess.run(
            [sys.executable, "-m", "yt_dlp", "--no-warnings", "--skip-download",
             "--print", "%(duration)s", f"https://www.youtube.com/watch?v={vid}"],
            capture_output=True, text=True, timeout=90)
        d = int(float(p.stdout.strip().split()[0]))
        cache[vid] = d
        return d
    except Exception:
        cache[vid] = None
        return None


def maps_of(html: str) -> list[dict]:
    out = []
    for gid, body in MAPNAV_RE.findall(html):
        if gid == "all":
            continue
        txt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body)).strip()
        m = re.search(r"Pick:\s*(\S+)\s*-->\s*(\d+)\s+(\S+)\s+(.*?)(-->|$)", txt)
        if not m:
            continue
        pick, num, name, rest = m.group(1), int(m.group(2)), m.group(3), m.group(4)
        played = "Not played" not in rest
        out.append({"number": num, "name": name, "pickBy": None if pick == "--" else pick,
                    "played": played})
    return out


def main() -> int:
    do_probe = "--no-probe" not in sys.argv
    cat = json.loads((HERE / ".." / "web" / "public" / "data" / "catalog.json").read_text(encoding="utf-8"))
    durs: dict = json.loads(PROBE_CACHE.read_text(encoding="utf-8")) if PROBE_CACHE.exists() else {}
    prev: dict = {}
    if OUT.exists():
        try:
            prev = {m["matchId"]: m for m in json.loads(OUT.read_text(encoding="utf-8"))}
        except Exception:
            pass
    results = []
    total = sum(len(e["matches"]) for e in cat["events"])
    i = 0
    for ev in cat["events"]:
        for m in ev["matches"]:
            i += 1
            mid = m["id"]
            if mid in prev and prev[mid].get("done"):
                results.append(prev[mid])
                continue
            try:
                html = get(m["vlrUrl"], CACHE / f"{mid}.html")
            except Exception as e:
                print(f"[{i}/{total}] {mid} FETCH FAIL: {e}", flush=True)
                results.append({"matchId": mid, "eventId": ev["eventId"], "done": False,
                                "error": "fetch-fail", "schedulable": False})
                continue
            vods = sorted(set(VOD_RE.findall(html)))
            vodinfo = [{"id": v, "durationSec": probe(v, durs, do_probe)} for v in vods]
            maps = maps_of(html)
            rounds = split_maps(parse_rows(html))
            for mp, rr in zip(maps, rounds):
                if rr:
                    mp["score"] = rr[-1]["score"]
                    mp["nRounds"] = len(rr)
            sched = bool(vods) and any(mp.get("played") for mp in maps)
            results.append({"matchId": mid, "eventId": ev["eventId"],
                            "teams": [m["teamA"], m["teamB"]],
                            "vods": vodinfo, "maps": maps,
                            "done": True, "schedulable": sched,
                            "reason": None if sched else ("no-vod" if not vods else "no-maps")})
            if i % 25 == 0:
                PROBE_CACHE.write_text(json.dumps(durs), encoding="utf-8")
                OUT.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
                print(f"[{i}/{total}] checkpoint", flush=True)
            print(f"[{i}/{total}] {mid} vods={len(vods)} maps={len(maps)} sched={sched}", flush=True)
    PROBE_CACHE.write_text(json.dumps(durs), encoding="utf-8")
    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    ok = sum(1 for r in results if r.get("schedulable"))
    print(f"FIM: {ok}/{len(results)} agendaveis")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
