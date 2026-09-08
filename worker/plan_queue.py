"""Agenda da fila: schedule.json com slot/noite, ETA e motivo (ordem cronologica).

Uso:
  python worker/plan_queue.py --replan   # recomputa tudo (barato, sem rede)
  python worker/plan_queue.py --next     # imprime o slot de hoje (matchId ou NADA)
ETA: scan 4.1 amostras/s + download ~60MB/s@1080p + margem 25%.
"""
from __future__ import annotations
import argparse
import datetime
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
SRC = HERE / "samples" / "queue_source.json"
CAT = HERE / ".." / "web" / "public" / "data" / "catalog.json"
OUT = HERE / ".." / "web" / "public" / "data" / "schedule.json"

SCAN_RATE = 4.1      # amostras/s (medido)
DL_MBS = 60.0        # MB/s download 1080p (medido)
V1080P_MBS = 0.55    # MB por segundo de video 1080p60 (medido: 2.86GB/5715s)
MARGIN = 1.25
SLOT_HOUR_UTC = 3


def eta_min(dur_sec: float | None, n_maps: int) -> tuple[float, bool]:
    if not dur_sec:
        dur_sec = n_maps * 2400.0  # fallback Bo3 ~40min/mapa (flag estimado)
        estimated = True
    else:
        estimated = False
    scan = dur_sec / SCAN_RATE / 60.0
    dl = dur_sec * V1080P_MBS / DL_MBS / 60.0
    return round((scan + dl + 6) * MARGIN, 1), estimated


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--replan", action="store_true")
    ap.add_argument("--next", action="store_true")
    a = ap.parse_args()
    if a.next:
        s = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
        today = datetime.date.today().isoformat()
        for slot in s.get("slots", []):
            if slot["date"] >= today and slot["status"] in ("planned",):
                print(slot["matchId"])
                return 0
        print("NADA")
        return 1
    # --replan
    src = json.loads(SRC.read_text(encoding="utf-8"))
    cat = json.loads(CAT.read_text(encoding="utf-8"))
    meta = {}
    for ev in cat["events"]:
        for m in ev["matches"]:
            meta[m["id"]] = {"eventId": ev["eventId"], "eventName": ev["eventName"],
                             "date": m.get("date", "?"), "teams": [m["teamA"], m["teamB"]],
                             "status": m.get("status"), "order": ev.get("order", 9)}
    order_ev = {}
    for ev in cat["events"]:
        order_ev[ev["eventId"]] = ev.get("order", 9)
    rows = [r for r in src if r.get("schedulable") and meta.get(r["matchId"], {}).get("status") != "processed"]
    rows.sort(key=lambda r: (order_ev.get(r["eventId"], 9), r["matchId"]))
    day = datetime.date.today() + datetime.timedelta(days=1)
    slots = []
    for r in rows:
        m = meta.get(r["matchId"], {})
        dur = None
        for v in r.get("vods", []):
            if v.get("durationSec"):
                dur = (dur or 0) + v["durationSec"]
                break
        if dur is None and r.get("vods"):
            dur = None
        nmaps = sum(1 for mp in r.get("maps", []) if mp.get("played"))
        eta, estimated = eta_min(dur, max(nmaps, 1))
        slots.append({"date": day.isoformat(), "matchId": r["matchId"],
                      "eventId": r["eventId"], "teams": m.get("teams", r.get("teams", [])),
                      "etaMin": eta, "etaEstimated": estimated,
                      "vodId": (r.get("vods", [{}])[0].get("id")),
                      "status": "planned"})
        day += datetime.timedelta(days=1)
    unsched = [{"matchId": r["matchId"], "reason": r.get("reason", r.get("error", "?")),
                "teams": r.get("teams", [])}
               for r in src if not r.get("schedulable")]
    total_eta = round(sum(s["etaMin"] for s in slots), 1)
    sched = {"generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
             "slot_hour_utc": SLOT_HOUR_UTC, "perNight": 1,
             "funnel": {"schedulable": len(slots), "unschedulable": len(unsched),
                        "totalEtaMin": total_eta,
                        "totalEtaDays": round(total_eta / 60 / 24 + len(slots), 1)},
             "slots": slots, "unschedulable": unsched}
    OUT.write_text(json.dumps(sched, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"agenda: {len(slots)} slots, ETA total {total_eta:.0f}min, {len(unsched)} fora da fila")
    if slots:
        print(f"primeiro: {slots[0]['date']} {slots[0]['matchId']} {slots[0]['teams']} ~{slots[0]['etaMin']}min")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
