# Wikival — decisões (piloto 100T vs LOUD)

## Piloto
- VOD: https://www.youtube.com/watch?v=oJ92wNAm270 (VALORANT Esports BR, PT-BR, 18342s ≈ 5h05)
- Vlr.gg: https://www.vlr.gg/734308 (GF Bo5, 100T 3-2 LOUD)
- Mapas: Split 7-13 (L) · Sunset 13-11 (W) · Ascent 14-12 (W) · Summit 1-13 (L) · Haven 14-12 (W)

## Decisões do MVP (com o usuário)
1. Só YouTube via IFrame `seekTo` — sem hospedar fatias (evita CORS/custo).
2. Sem backend — JSON estático em `web/public/data/`.
3. Visão: OCR clássico + template-matching primeiro; ONNX/WebGPU só Fase 3.
4. Escopo: 1 VOD piloto.

## Rodar
- Worker dry-run (valida FSM, 20 rounds Split): `python worker/detect.py --dry-run`
- Gerar esqueleto: `python worker/cutlist.py`
- Teste rápido 2min de vídeo: `python worker/detect.py --section "00:10:00-00:12:00"`
- Frontend: `cd web && npm install && npm run dev` → http://localhost:5173

## Próximos passos (Camada 0 real)
1. Baixar trecho e calibrar ROIs 720p em `worker/config.py` (placar/timer/banner BR).
2. Ligar OCR (PaddleOCR opcional) em `detect.py::try_ocr`.
3. Preencher `rounds[]` mapa a mapa, validar placar contínuo, marcar `status: detected`.
4. Só então Fase 3 (WebGPU) / Fase 4 (consenso 2/3, ±0.6s, honey-pot).
