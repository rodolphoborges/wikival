"""Crawler do circuito VCT 2026 completo (15 eventos: 4 kickoffs, 2 masters,
4 stage-1, 4 stage-2, champions). Com cache em D:\\wikival-work\\events\\.

Uso: python worker/crawl_events.py        # baixa tudo (~30 req, educado)
       python worker/crawl_events.py --build # so reconstroi o catalogo do cache
Saida: web/public/data/catalog.json {events: [{eventId, eventName, matches}]}
"""
from __future__ import annotations
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from build_catalog import parse_groups, parse_bracket, FULL

WORK = Path("D:/wikival-work/events")
OUT = HERE / ".." / "web" / "public" / "data" / "catalog.json"

EVENTS = [
    ("2682", "vct-2026-americas-kickoff"), ("2683", "vct-2026-pacific-kickoff"),
    ("2684", "vct-2026-emea-kickoff"), ("2685", "vct-2026-china-kickoff"),
    ("2760", "valorant-masters-santiago-2026"), ("2765", "valorant-masters-london-2026"),
    ("2766", "valorant-champions-2026"),
    ("2775", "vct-2026-pacific-stage-1"), ("2860", "vct-2026-americas-stage-1"),
    ("2863", "vct-2026-emea-stage-1"), ("2864", "vct-2026-china-stage-1"),
    ("2776", "vct-2026-pacific-stage-2"), ("2976", "vct-2026-emea-stage-2"),
    ("2977", "vct-2026-americas-stage-2"), ("2978", "vct-2026-china-stage-2"),
]

PROCESSED = {"660370": "data/match.piloto.json"}


def get(url: str, dest: Path) -> str:
    if dest.exists():
        return dest.read_text(encoding="utf-8")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    data = urllib.request.urlopen(req, timeout=60).read().decode("utf-8")
    dest.write_text(data, encoding="utf-8")
    time.sleep(2)  # educado com o vlr.gg
    return data


def event_name(slug: str) -> str:
    return " ".join({"vct": "VCT", "emea": "EMEA"}.get(w, w.title())
                    for w in slug.replace("2026-", "2026 ").split("-"))


def event_meta(slug: str) -> tuple[str, str, int]:
    """-> (region, stage, order). region: americas|pacific|emea|china|intl."""
    region = "intl"
    for r in ("americas", "pacific", "emea", "china"):
        if f"-{r}-" in slug or slug.endswith(f"-{r}"):
            region = r
    if "kickoff" in slug:
        stage, order = "kickoff", 0
    elif "stage-1" in slug:
        stage, order = "stage-1", 1
    elif "masters" in slug:
        stage, order = "masters", 2
    elif "stage-2" in slug:
        stage, order = "stage-2", 3
    elif "champions" in slug:
        stage, order = "champions", 4
    else:
        stage, order = "other", 9
    return region, stage, order


def group_url(eid: str, slug: str, html: str) -> str | None:
    m = re.search(r'href="([^"]*group-stage[^"]*)"', html)
    if not m:
        return None
    u = m.group(1)
    return u if u.startswith("http") else f"https://www.vlr.gg{u}"


def main() -> int:
    build_only = "--build" in sys.argv
    WORK.mkdir(parents=True, exist_ok=True)
    events = []
    for eid, slug in EVENTS:
        main_f = WORK / f"{eid}.html"
        if not build_only:
            html = get(f"https://www.vlr.gg/event/{eid}/{slug}", main_f)
        else:
            html = main_f.read_text(encoding="utf-8") if main_f.exists() else ""
        if not html:
            print(f"{eid}: sem cache, pulando")
            continue
        matches = parse_bracket(html)
        gu = group_url(eid, slug, html)
        if gu and not build_only:
            gh = get(gu, WORK / f"{eid}_group.html")
        else:
            gf = WORK / f"{eid}_group.html"
            gh = gf.read_text(encoding="utf-8") if gf.exists() else ""
        if gh:
            matches = parse_groups(gh) + matches
        seen, uniq = set(), []
        for m in matches:
            if m["id"] in seen:
                continue
            seen.add(m["id"])
            m["status"] = "processed" if m["id"] in PROCESSED else "pending"
            m["dataFile"] = PROCESSED.get(m["id"])
            uniq.append(m)
        events.append({"eventId": eid, "eventName": event_name(slug),
                       "region": event_meta(slug)[0], "stage": event_meta(slug)[1],
                       "order": event_meta(slug)[2], "matches": uniq})
        print(f"{eid} {slug}: {len(uniq)} partidas")
    OUT.write_text(json.dumps({"events": events}, ensure_ascii=False, indent=1), encoding="utf-8")
    total = sum(len(e["matches"]) for e in events)
    print(f"TOTAL: {total} partidas em {len(events)} eventos -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
