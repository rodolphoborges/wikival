"""Enriquece match.piloto.json com endKind + vencedor por round vindos do vlr.gg.

Le D:\\wikival-work\\vlr_660370.html (rows .vlr-rounds-row-col):
  title="0-1" = placar apos o round; img round/<kind>.webp no sq vencedor
  (1o sq = time de cima G2, 2o sq = time de baixo 100T).
Baixa icones + logos p/ web/public/icons/.
Uso: python worker/enrich_vlr.py
"""
from __future__ import annotations
import json
import re
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
HTML = Path("D:/wikival-work/vlr_660370.html")
ICONS = HERE / ".." / "web" / "public" / "icons"
JSON_PATH = HERE / "samples" / "match.piloto.json"
KIND2END = {"elim": "elim", "defuse": "defuse", "boom": "boom", "time": "time"}

ROW_RE = re.compile(
    r'<div class="vlr-rounds-row-col" title="(\d+)-(\d+)">.*?'
    r'<div class="rnd-num">\s*(\d+)\s*</div>(.*?)'
    r'(?=<div class="vlr-rounds-row-col"|$)', re.S)
SQ_RE = re.compile(r'<div class="rnd-sq ([^"]*)">(.*?)</div>', re.S)
IMG_RE = re.compile(r'game/round/(\w+)\.webp')


def parse_rows(html: str) -> list[dict]:
    out = []
    for m in ROW_RE.finditer(html):
        sa, sb, num, body = m.groups()
        sqs = SQ_RE.findall(body)
        kind, winner = None, None
        for i, (cls, inner) in enumerate(sqs):
            im = IMG_RE.search(inner)
            if im:
                kind = im.group(1)
                winner = "teamA" if i == 0 else "teamB"  # cima=G2, baixo=100T
        if kind:
            out.append({"n": int(num), "score": f"{sa}-{sb}",
                        "winner": winner, "endKind": KIND2END.get(kind, "unknown")})
    return out


def split_maps(rows: list[dict]) -> list[list[dict]]:
    maps, cur, last_total = [], [], -1
    for r in rows:
        a, b = (int(x) for x in r["score"].split("-"))
        if a + b < last_total:
            maps.append(cur)
            cur = []
        cur.append(r)
        last_total = a + b
    if cur:
        maps.append(cur)
    return maps


def dl(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        return
    req = urllib.request.Request("https:" + url if url.startswith("//") else url,
                                 headers={"User-Agent": "Mozilla/5.0"})
    dest.write_bytes(urllib.request.urlopen(req, timeout=30).read())
    print("baixado:", dest.name)


def main() -> int:
    html = HTML.read_text(encoding="utf-8")
    rows = parse_rows(html)
    maps = split_maps(rows)
    print("rounds vlr:", [len(m) for m in maps])
    assert [len(m) for m in maps] == [17, 20], "esperava [17, 20]"
    assert maps[0][-1]["score"] == "13-4" and maps[1][-1]["score"] == "13-7"

    base = "https://www.vlr.gg"
    for kind in ["elim", "defuse", "boom", "time"]:
        dl(f"{base}/img/vlr/game/round/{kind}.webp", ICONS / f"round-{kind}.webp")
    # logos vindos do proprio HTML (G2 cima, 100T baixo)
    logos = re.findall(r'<img src="(//owcdn\.net/img/[0-9a-f]+\.png)">\s*(G2|100T)',
                       html)
    seen = {}
    for url, team in logos:
        seen.setdefault(team, url)
    for team, url in seen.items():
        dl(url, ICONS / f"team-{team.lower()}.png")

    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    names = ["Pearl", "Lotus"]
    problems = []
    for entry, vrounds in zip(data["maps"], maps):
        assert entry["mapName"] in names
        for r, v in zip(entry["rounds"], vrounds):
            if r["roundNumber"] != v["n"] or r["result"]["scoreAfterRound"] != v["score"]:
                problems.append(f"{entry['mapName']} R{r['roundNumber']}: auto={r['result']['scoreAfterRound']} vlr={v['score']}")
            if r["result"]["winner"] != v["winner"]:
                problems.append(f"{entry['mapName']} R{r['roundNumber']}: vencedor auto={r['result']['winner']} vlr={v['winner']}")
            r["result"]["endKind"] = v["endKind"]
    JSON_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    webjson = HERE / ".." / "web" / "public" / "data" / "match.piloto.json"
    webjson.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print("discrepancias:", problems if problems else "nenhuma — 37/37 rounds conferem")
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
