"""Livro-razao das acoes: D:\\wikival-work\\ledger.json.

Cada acao: {id, kind, label, status, started_at, ended_at, detail, log}.
status: planned | running | done | failed | skipped.
Escrita atomica (tmp + replace). Sem dependencias.
"""
from __future__ import annotations
import datetime
import json
import os
from pathlib import Path

LEDGER = Path("D:/wikival-work/ledger.json")


def _now() -> str:
    return datetime.datetime.now().strftime("%H:%M:%S")


def _load() -> list[dict]:
    try:
        return json.loads(LEDGER.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save(jobs: list[dict]) -> None:
    tmp = LEDGER.with_suffix(".tmp")
    tmp.write_text(json.dumps(jobs, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, LEDGER)


def log_job(kind: str, label: str, status: str = "planned",
            detail: str = "", log: str = "") -> str:
    jobs = _load()
    jid = f"{_now().replace(':', '')}-{len(jobs) + 1:03d}"
    jobs.append({"id": jid, "kind": kind, "label": label, "status": status,
                 "started_at": _now() if status in ("running", "done", "failed") else "",
                 "ended_at": _now() if status in ("done", "failed", "skipped") else "",
                 "detail": detail, "log": log})
    _save(jobs)
    return jid


def set_status(jid: str, status: str, detail: str = "") -> None:
    jobs = _load()
    for j in jobs:
        if j["id"] == jid:
            j["status"] = status
            if detail:
                j["detail"] = detail
            if status == "running" and not j["started_at"]:
                j["started_at"] = _now()
            if status in ("done", "failed", "skipped"):
                j["ended_at"] = _now()
    _save(jobs)


def find(label_part: str, status: str = "") -> dict | None:
    for j in reversed(_load()):
        if label_part in j["label"] and (not status or j["status"] == status):
            return j
    return None
