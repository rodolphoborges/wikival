"""Constroi web/public/data/catalog.json com as 42 partidas do Stage 1.

Fontes: D:\\wikival-work\\vlr_group.html (30, grupos) + vlr_event2860.html (12, playoffs).
status: processed so p/ 660370 (tem match.piloto.json); resto pending.
Uso: python worker/build_catalog.py
"""
from __future__ import annotations
import json
import re
from pathlib import Path

WORK = Path("D:/wikival-work")
OUT = Path(__file__).parent / ".." / "web" / "public" / "data" / "catalog.json"

FULL = {"sentinels": "Sentinels", "kr-esports": "KR Esports", "g2-esports": "G2 Esports",
        "mibr": "MIBR", "100-thieves": "100 Thieves", "evil-geniuses": "Evil Geniuses",
        "envy": "Envy", "loud": "LOUD", "cloud9": "Cloud9", "leviat-n": "LEVIATÁN",
        "furia": "FURIA", "nrg": "NRG"}


def full_name(slug: str, side: int) -> str:
    parts = slug.split("-vs-")
    side_slug = parts[side] if len(parts) == 2 else slug
    team = re.sub(r"-vct-2026-.*$", "", side_slug)
    team = re.sub(r"-valorant-.*$", "", team)
    return FULL.get(team, team.replace("-", " ").title())


def parse_groups(h: str) -> list[dict]:
    blocks = re.findall(
        r'href="/(\d{6})/([\w-]+)">(.*?)</a>', h, re.S)
    out = []
    for mid, slug, body in blocks:
        if not re.search(r"-w[1-9]$", slug):
            continue
        date = re.search(r"<b>([A-Za-z]+ \d+)</b>", body)
        tags = re.findall(r'<div class="team-name[^>]*>\s*<div>([^<]+)</div>', body)
        scores = re.findall(r'<div class="score-(?:left|right)[^"]*">\s*(\d+)', body)
        stage = re.search(r'<span class="ss-name mod-full">([^<]+)</span>', body)
        fmt = re.search(r">(Bo\d)<", body)
        if len(tags) >= 2 and len(scores) >= 2:
            a, b = int(scores[0]), int(scores[1])
            out.append({"id": mid, "slug": slug, "teamA": full_name(slug, 0),
                        "teamB": full_name(slug, 1), "tagA": tags[0].strip(),
                        "tagB": tags[1].strip(), "scoreA": a, "scoreB": b,
                        "winner": "teamA" if a > b else ("teamB" if b > a else "draw"),
                        "stage": (stage.group(1) if stage else "?") + " · Grupos",
                        "format": fmt.group(1) if fmt else "Bo3",
                        "date": date.group(1) if date else "?",
                        "vlrUrl": f"https://www.vlr.gg/{mid}/{slug}"})
    return out


def parse_bracket(h: str) -> list[dict]:
    labels = [(m.start(), m.group(1).strip())
              for m in re.finditer(r'bracket-col-label">\s*([^<]+?)\s*<', h)]
    out = []
    for m in re.finditer(
            r'<a class="bracket-item[^"]*"[^>]*title="([^"]+)" href="/(\d{6})/([\w-]+)"[^>]*>(.*?)</a>',
            h, re.S):
        title, mid, slug, body = m.groups()
        names = re.findall(r"<span>([^<]+)</span>", body)
        scores = re.findall(r'bracket-item-team-score">\s*(\d+)', body)
        date = re.search(r"data-moment-format[^>]*><div><span></span>([^<]+)", body)
        curlabel = "Playoffs"
        for pos, lab in labels:
            if pos < m.start():
                curlabel = lab
        if len(names) >= 2 and len(scores) >= 2:
            a, b = int(scores[0]), int(scores[1])
            out.append({"id": mid, "slug": slug, "teamA": names[0].strip(),
                        "teamB": names[1].strip(), "tagA": names[0].strip(),
                        "tagB": names[1].strip(), "scoreA": a, "scoreB": b,
                        "winner": "teamA" if a > b else ("teamB" if b > a else "draw"),
                        "stage": "Playoffs · " + curlabel, "format": "Bo3",
                        "date": date.group(1).strip() if date else "?",
                        "vlrUrl": f"https://www.vlr.gg/{mid}/{slug}"})
    return out


def main() -> int:
    g = parse_groups((WORK / "vlr_group.html").read_text(encoding="utf-8"))
    p = parse_bracket((WORK / "vlr_event2860.html").read_text(encoding="utf-8"))
    seen, allm = set(), []
    for m in g + p:
        if m["id"] in seen:
            continue
        seen.add(m["id"])
        m["status"] = "processed" if m["id"] == "660370" else "pending"
        m["dataFile"] = "data/match.piloto.json" if m["id"] == "660370" else None
        allm.append(m)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"event": "VCT 2026 Americas Stage 1",
                               "source": "https://www.vlr.gg/vct/?region=26&stage=45",
                               "matches": allm}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(allm)} partidas ({len(g)} grupos + {len(p)} playoffs)")
    pro = [m for m in allm if m["status"] == "processed"]
    print("processadas:", [(m["id"], m["teamA"], m["scoreA"], "x", m["scoreB"], m["teamB"]) for m in pro])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
