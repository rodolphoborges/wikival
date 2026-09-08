# wikival — Wikipédia de VCT com Camada 0 navegável

Catálogo estilo terminal das partidas do VCT 2026 (15 eventos, 488 partidas via vlr.gg),
com rounds clicáveis que pulam direto ao momento no VOD do YouTube.

- Piloto processado: G2 2-0 100T (Upper R1, Americas Stage 1) — 37/37 rounds validados.
- Worker local (Python + OpenCV + Tesseract, 100% CPU): `worker/scan.py`, `mapsplit.py`, `assemble.py`.
- Frontend (Vite + TS, tema terminal): `web/` — `npm install && npm run dev`.

Ver `docs/decisoes.md` e `schemas/match.v1.json`.
