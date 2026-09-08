"""Monta match.piloto.json a partir dos passes B + valida contra verdade de chao.

Uso: python worker/assemble.py
Le: checkpoints/final_pearl.json, final_lotus.json, samples/ground_truth_round1.json
Escreve: samples/match.piloto.json + web/public/data/match.piloto.json
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from cutlist import skeleton

WORK = Path("D:/wikival-work")
TRUTH = {"Pearl": "13-4", "Lotus": "13-7"}
TAGS = [("pearl", "Pearl"), ("lotus", "Lotus")]


def load_rounds(tag: str) -> tuple[list[dict], list[str]]:
    fin = json.loads((WORK / "checkpoints" / f"final_{tag}.json").read_text(encoding="utf-8"))
    rounds: list[dict] = []
    for s in fin.get("segments", []):
        rounds.extend(s["rounds"])
    # NOTA: fin["rounds"] duplica o ultimo segmento (ver scan.py); ignorar aqui.
    rounds.sort(key=lambda r: r["roundNumber"])
    return rounds, fin.get("errors", [])


def to_schema(r: dict) -> dict:
    return {
        "roundNumber": r["roundNumber"],
        "type": "unknown",
        "timestamps": {
            "buyPhaseStart": r["timestamps"]["buyPhaseStart"],
            "roundStart": r["timestamps"]["roundStart"],
            "roundEnd": r["timestamps"]["roundEnd"],
        },
        "result": {
            "winner": r["result"]["winner"],
            "scoreAfterRound": r["result"]["scoreAfterRound"],
            "endKind": "unknown",
        },
        "layer1Enriched": False,
        "events": [],
    }


def main() -> int:
    m = skeleton()
    ok = True
    for tag, name in TAGS:
        rounds, errors = load_rounds(tag)
        entry = next(x for x in m["maps"] if x["mapName"] == name)
        entry["rounds"] = [to_schema(r) for r in rounds]
        entry["status"] = "detected" if rounds else "pending_detection"
        if rounds:
            entry["anchorApproxSec"] = rounds[0]["timestamps"]["buyPhaseStart"]
        final = rounds[-1]["result"]["scoreAfterRound"] if rounds else "?"
        exp = TRUTH[name]
        n_exp = sum(int(x) for x in exp.split("-"))
        flag = "OK " if (final == exp and len(rounds) == n_exp) else "DIVERGE"
        if flag != "OK ":
            ok = False
        print(f"{name}: {len(rounds)} rounds (esperado {n_exp}), placar {final} (esperado {exp}) [{flag}]")
        for e in errors[:5]:
            print(f"  ! {e}")
    # round 1 vs gabarito manual
    gt = json.loads((HERE / "samples" / "ground_truth_round1.json").read_text(encoding="utf-8"))
    r1 = m["maps"][0]["rounds"][0] if m["maps"][0]["rounds"] else None
    if r1:
        for k, gk in [("buyPhaseStart", None), ("roundStart", "round_start"), ("roundEnd", "round_end_banner")]:
            v = r1["timestamps"][k]
            if gk:
                d = (v or -1) - gt[gk]
                mark = "OK " if abs(d) <= 2 else "DIVERGE"
                if mark != "OK ":
                    ok = False
                print(f"R1.{k}: auto={v} manual={gt[gk]} d={d:+.0f}s [{mark}]")
        w = "OK " if r1["result"]["winner"] == gt["winner"] else "DIVERGE"
        print(f"R1.vencedor: auto={r1['result']['winner']} manual={gt['winner']} [{w}]")
    out1 = HERE / "samples" / "match.piloto.json"
    out1.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
    out2 = HERE / ".." / "web" / "public" / "data" / "match.piloto.json"
    out2.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"escrito: {out1} + {out2}")
    print("VALIDACAO GERAL:", "PASS" if ok else "FAIL (ver DIVERGE acima)")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
