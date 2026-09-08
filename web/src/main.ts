import "./style.css";
import { YTController, fmt } from "./player";
import type { Match, GameMap, Catalog, CatalogEntry, EventCatalog } from "./types";

let match: Match;
let currentMap: GameMap;
let currentEventId: string | null = null;
let yt: YTController;
let ticker: number | null = null;

function route(): void {
  const h = location.hash;
  let m = h.match(/^#\/r\/([\w-]+)/);
  if (m) { void loadRegion(m[1]).catch(routeError); return; }
  m = h.match(/^#\/e\/([\w-]+)/);
  if (m) { void loadEvent(m[1]).catch(routeError); return; }
  m = h.match(/^#\/m\/([\w-]+)/);
  if (m) void loadDetail(m[1]).catch(routeError);
  else void loadCatalog().catch(routeError);
}

function routeError(e: unknown): void {
  const msg = (e as Error)?.message ?? String(e);
  const el = document.getElementById("match-sub");
  if (el) el.innerHTML = `<span class="err"># erro: ${msg} — <a href="#/">$ cd ..</a></span>`;
}

async function fetchCatalog(): Promise<Catalog> {
  const res = await fetch("./data/catalog.json", { cache: "no-store" });
  if (!res.ok) throw new Error(`falha ao carregar catalogo: ${res.status}`);
  return (await res.json()) as Catalog;
}

function findEntry(cat: Catalog, id: string): { entry: CatalogEntry; event: EventCatalog } | null {
  for (const event of cat.events) {
    const entry = event.matches.find((x) => x.id === id);
    if (entry) return { entry, event };
  }
  return null;
}

async function loadCatalog(): Promise<void> {
  if (ticker != null) { clearInterval(ticker); ticker = null; }
  document.querySelector<HTMLElement>(".player-col")!.style.display = "none";
  document.getElementById("map-tabs")!.innerHTML = "";
  const cat = await fetchCatalog();
  renderCatalog(cat);
}

function renderCatalog(cat: Catalog): void {
  document.querySelector("header h1")!.innerHTML =
    `wikival --vct <span class="tag">2026 worldmap</span>`;
  const total = cat.events.reduce((n, e) => n + e.matches.length, 0);
  const done = cat.events.reduce(
    (n, e) => n + e.matches.filter((m) => m.status === "processed").length, 0);
  document.getElementById("match-sub")!.innerHTML =
    `<strong>VCT 2026 · worldmap</strong> · processadas ` +
    `<span class="ok">[${done}/${total}]</span> · ` +
    `<a href="https://www.vlr.gg/vct/?region=all&stage=all" target="_blank" rel="noreferrer">fonte: vlr.gg</a>`;
  const box = document.getElementById("round-list")!;
  box.innerHTML = "";
  const h = document.createElement("h2");
  h.textContent = "$ worldmap --regions";
  box.appendChild(h);

  const regs = ["americas", "emea", "china", "pacific"];
  const info = (r: string) => {
    const evs = cat.events.filter((e) => e.region === r);
    const nm = evs.reduce((n, e) => n + e.matches.length, 0);
    const nd = evs.reduce((n, e) => n + e.matches.filter((m) => m.status === "processed").length, 0);
    return { n: nm, d: nd, ne: evs.length };
  };
  const pad = (s: string, w: number) => s.padEnd(w).slice(0, w);
  const W = 15;
  const top = regs.map(() => "┌" + "─".repeat(W) + "┐").join("──▶");
  const mid1 = regs.map((r) => "│" + pad(` ${r.toUpperCase()}`, W) + "│").join("   ");
  const mid2 = regs.map((r) => {
    const i = info(r);
    return "│" + pad(` ${i.n}m ${i.d}ok ${i.ne}ev`, W) + "│";
  }).join("   ");
  const bot = regs.map(() => "└" + "─".repeat(W) + "┘").join("   ");
  const intl = cat.events.filter((e) => e.region === "intl");
  const intlLine = intl.map((e) => `[${e.stage} ${e.matches.length}m]`).join(" ");
  const pre = document.createElement("pre");
  pre.className = "worldmap";
  pre.textContent =
    `lon -170      -90       -10       +70      +170\n${top}\n${mid1}\n${mid2}\n${bot}\n` +
    `  circuit: kickoff ▸ stage-1 ▸ masters ▸ stage-2 ▸ champions\n` +
    `┌─ INTL LANS ─${"─".repeat(58)}\n│ ${intlLine}\n└${"─".repeat(68)}`;
  box.appendChild(pre);

  const ul = document.createElement("ol");
  ul.className = "rounds";
  const mkRow = (label: string, sub: string, go: () => void, mark: string) => {
    const li = document.createElement("li");
    li.innerHTML = `${mark} <span class="res">${label}</span> <span class="ts">${sub}</span>`;
    const b = document.createElement("button");
    b.textContent = "[open]";
    b.onclick = go;
    li.appendChild(b);
    ul.appendChild(li);
  };
  for (const r of regs) {
    const i = info(r);
    mkRow(`region/${r}`, `${i.n} partidas · ${i.d} ok · circuito kickoff▸s1▸s2`,
      () => { location.hash = `#/r/${r}`; },
      i.d > 0 ? `<span class="ok">[${i.d}]</span>` : `<span class="dim">[--]</span>`);
  }
  mkRow("region/intl (LANs)", `${intl.reduce((n, e) => n + e.matches.length, 0)} partidas · masters + champions`,
    () => { location.hash = `#/r/intl`; }, `<span class="dim">[--]</span>`);
  box.appendChild(ul);
}

async function loadRegion(region: string): Promise<void> {
  if (ticker != null) { clearInterval(ticker); ticker = null; }
  document.querySelector<HTMLElement>(".player-col")!.style.display = "none";
  document.getElementById("map-tabs")!.innerHTML = "";
  const cat = await fetchCatalog();
  const evs = cat.events.filter((e) => e.region === region).sort((a, b) => a.order - b.order);
  if (evs.length === 0) { location.hash = "#/"; return; }
  renderRegion(region, evs);
}

function renderRegion(region: string, evs: EventCatalog[]): void {
  document.querySelector("header h1")!.innerHTML =
    `wikival --region <span class="tag">${region}</span>`;
  const total = evs.reduce((n, e) => n + e.matches.length, 0);
  const done = evs.reduce((n, e) => n + e.matches.filter((m) => m.status === "processed").length, 0);
  document.getElementById("match-sub")!.innerHTML =
    `<a href="#/">$ cd ..</a> · <strong>region/${region}</strong> · ` +
    `processadas <span class="ok">[${done}/${total}]</span>`;
  const box = document.getElementById("round-list")!;
  box.innerHTML = "";
  const h = document.createElement("h2");
  h.textContent = `$ circuit ${evs.map((e) => e.stage).join(" ▸ ")}`;
  box.appendChild(h);
  const ul = document.createElement("ol");
  ul.className = "rounds";
  for (const e of evs) {
    const d = e.matches.filter((m) => m.status === "processed").length;
    const li = document.createElement("li");
    li.innerHTML =
      (d > 0 ? `<span class="ok">[${d}]</span>` : `<span class="dim">[--]</span>`) +
      ` <span class="res">${e.eventName}</span> ` +
      `<span class="ts">${e.stage} · ${e.matches.length} partidas</span>`;
    const b = document.createElement("button");
    b.textContent = "[open]";
    b.onclick = () => { location.hash = `#/e/${e.eventId}`; };
    li.appendChild(b);
    ul.appendChild(li);
  }
  box.appendChild(ul);
}

async function loadEvent(eventId: string): Promise<void> {
  if (ticker != null) { clearInterval(ticker); ticker = null; }
  document.querySelector<HTMLElement>(".player-col")!.style.display = "none";
  document.getElementById("map-tabs")!.innerHTML = "";
  const cat = await fetchCatalog();
  const event = cat.events.find((e) => e.eventId === eventId);
  if (!event) { location.hash = "#/"; return; }
  renderEvent(event);
}

function renderEvent(event: EventCatalog): void {
  document.querySelector("header h1")!.innerHTML =
    `wikival --event <span class="tag">${event.eventId}</span>`;
  const done = event.matches.filter((m) => m.status === "processed").length;
  document.getElementById("match-sub")!.innerHTML =
    `<a href="#/r/${event.region}">$ cd ..</a> · <strong>${event.eventName}</strong> · ` +
    `processadas <span class="ok">[${done}/${event.matches.length}]</span>`;
  const box = document.getElementById("round-list")!;
  box.innerHTML = "";
  if (event.matches.length === 0) {
    box.innerHTML = `<p class="empty">[--] nenhuma partida listada ainda (evento futuro ou sem dados no vlr.gg).</p>`;
    return;
  }
  const stages: string[] = [...new Set(event.matches.map((m) => m.stage))];
  for (const st of stages) {
    const h = document.createElement("h2");
    h.textContent = `$ ls ${st}`;
    box.appendChild(h);
    const ul = document.createElement("ol");
    ul.className = "rounds";
    for (const m of event.matches.filter((x) => x.stage === st)) {
      const li = document.createElement("li");
      const badge = m.status === "processed"
        ? `<span class="ok">[ok]</span>`
        : `<span class="dim">[--]</span>`;
      li.innerHTML =
        `${badge} <span class="rn">${m.date}</span> ` +
        `<span class="res">${m.teamA} ${m.scoreA}-${m.scoreB} ${m.teamB}</span> ` +
        `<span class="ts">${m.format}</span>`;
      if (m.status === "processed") {
        const b = document.createElement("button");
        b.textContent = "[open]";
        b.onclick = () => { location.hash = `#/m/${m.id}`; };
        li.appendChild(b);
      } else {
        const a = document.createElement("a");
        a.href = m.vlrUrl; a.target = "_blank"; a.rel = "noreferrer";
        a.textContent = "[vlr]";
        li.appendChild(a);
      }
      ul.appendChild(li);
    }
    box.appendChild(ul);
  }
}

function renderPending(entry: CatalogEntry, eventId: string | null): void {
  document.querySelector<HTMLElement>(".player-col")!.style.display = "none";
  document.getElementById("map-tabs")!.innerHTML = "";
  document.querySelector("header h1")!.innerHTML =
    `wikival --match <span class="tag">pendente</span>`;
  document.getElementById("match-sub")!.innerHTML =
    `<a href="#/${eventId ? `e/${eventId}` : ""}">$ cd ..</a> · <strong>${entry.teamA} ${entry.scoreA}-${entry.scoreB} ${entry.teamB}</strong> · ${entry.stage}`;
  const box = document.getElementById("round-list")!;
  box.innerHTML =
    `<h2>$ status ${entry.id}</h2>` +
    `<p class="empty">[--] partida ainda nao processada.<br>` +
    `rode o worker: <code>python worker/scan.py --run</code> apos cadastrar VOD + verdade de chao.<br>` +
    `<a href="${entry.vlrUrl}" target="_blank" rel="noreferrer">ver no vlr.gg</a></p>`;
}

async function loadDetail(id: string): Promise<void> {
  const cat = await fetchCatalog();
  const found = findEntry(cat, id);
  if (!found) { location.hash = "#/"; return; }
  const { entry, event } = found;
  currentEventId = event.eventId;
  if (!entry.dataFile) { renderPending(entry, event.eventId); return; }
  const r2 = await fetch(`./${entry.dataFile}`);
  if (!r2.ok) throw new Error(`falha ao carregar ${entry.dataFile}: ${r2.status}`);
  match = (await r2.json()) as Match;
  currentMap = match.maps[0];
  document.querySelector<HTMLElement>(".player-col")!.style.display = "";
  document.querySelector("header h1")!.innerHTML =
    `wikival --match <span class="tag">${entry.slug.split("-vct-")[0].slice(0, 24)}</span>`;
  yt = new YTController(match.youtubeVideoId);
  yt.mount();
  renderHeader();
  renderTabs();
  renderRounds();
  renderChapters();
  wireControls();
  if (ticker != null) clearInterval(ticker);
  ticker = window.setInterval(tickChapter, 1000);
}

async function load(): Promise<void> {
  route();
}

function teamName(key: string): string {
  return key === "teamA" ? match.meta.teams.teamA : key === "teamB" ? match.meta.teams.teamB : key;
}

function renderHeader(): void {
  const el = document.getElementById("match-sub")!;
  const { teamA, teamB } = match.meta.teams;
  const logo = (f: string, alt: string) =>
    `<img class="tlogo" src="icons/${f}" alt="${alt}" onerror="this.remove()" />`;
  el.innerHTML =
    `<a href="#/${currentEventId ? `e/${currentEventId}` : ""}">$ cd ..</a> · ` +
    `${logo("team-g2.png", teamA)}<strong>${teamA} ${match.meta.finalScore ?? ""} ${teamB}</strong>${logo("team-100t.png", teamB)} · ` +
    `${match.meta.tournament} — ${match.meta.stage ?? ""} · ` +
    `<span class="status">${match.meta.enrichmentStatus}</span> · ` +
    `<a href="https://www.youtube.com/watch?v=${match.youtubeVideoId}" target="_blank" rel="noreferrer">VOD</a>` +
    (match.vlrUrl ? ` · <a href="${match.vlrUrl}" target="_blank" rel="noreferrer">vlr.gg</a>` : "");
}

function renderTabs(): void {
  const nav = document.getElementById("map-tabs")!;
  nav.innerHTML = "";
  for (const m of match.maps) {
    const b = document.createElement("button");
    b.className = "tab" + (m.mapIndex === currentMap.mapIndex ? " active" : "");
    b.textContent = `[${m.mapIndex}] ${m.mapName.toLowerCase()} ${m.score ?? "x"}${m.status !== "verified" && m.status !== "detected" ? "*" : ""}`;
    b.onclick = () => {
      currentMap = m;
      renderTabs();
      renderRounds();
      renderChapters();
      if (m.anchorApproxSec != null) yt.seek(m.anchorApproxSec);
    };
    nav.appendChild(b);
  }
}

function renderRounds(): void {  const box = document.getElementById("round-list")!;
  box.innerHTML = "";
  const title = document.createElement("h2");
  title.textContent = `map_${currentMap.mapIndex} ${currentMap.mapName.toLowerCase()} [${currentMap.score ?? "?"}] pick=${currentMap.pickBy ?? "?"}`;
  box.appendChild(title);

  if (currentMap.rounds.length === 0) {
    const p = document.createElement("p");
    p.className = "empty";
    p.innerHTML =
      `Rounds ainda <strong>pendentes de detecção</strong> (status: ${currentMap.status}).<br>` +
      `Rode o worker para preencher: <code>python worker/detect.py --section "HH:MM:SS-HH:MM:SS"</code><br>` +
      `Verdade de chão vlr.gg: <strong>${currentMap.score ?? "?"} pró ${teamName(currentMap.winner)}</strong>.`;
    box.appendChild(p);
    if (currentMap.anchorApproxSec != null) {
      const go = document.createElement("button");
      go.textContent = `▶ Ir para início do mapa (${fmt(currentMap.anchorApproxSec)})`;
      go.onclick = () => yt.seek(currentMap.anchorApproxSec!);
      box.appendChild(go);
    }
    return;
  }

  const ul = document.createElement("ol");
  ul.className = "rounds";
  for (const r of currentMap.rounds) {
    const li = document.createElement("li");
    const t = r.timestamps.roundStart;
    if (r.timestamps.buyPhaseStart != null && r.timestamps.roundEnd != null) {
      li.dataset.start = String(r.timestamps.buyPhaseStart);
      li.dataset.end = String(r.timestamps.roundEnd);
      li.dataset.n = String(r.roundNumber);
    }
    li.innerHTML =
      `<span class="rn">r${String(r.roundNumber).padStart(2, "0")}</span> ` +
      (r.result.endKind && r.result.endKind !== "unknown"
        ? `<img class="rk" src="icons/round-${r.result.endKind}.webp" alt="${r.result.endKind}" title="${endKindLabel(r.result.endKind)}" /> `
        : "") +
      `<span class="res">${r.result.scoreAfterRound} ${teamName(r.result.winner)}</span> ` +
      `<span class="ts">${fmt(t)}</span>`;
    if (t != null) {
      const go = () => yt.seek(t + 0.5);
      const btn = document.createElement("button");
      btn.textContent = "[watch]";
      btn.onclick = (e) => { e.stopPropagation(); go(); };
      li.appendChild(btn);
      li.classList.add("seekable");
      li.onclick = go;
      li.title = `pular para ${fmt(t)}`;
    }
    if (r.layer1Enriched && r.events.length > 0) {
      const ev = document.createElement("div");
      ev.className = "events";
      ev.textContent = r.events.map((e) => `${fmt(e.timestamp)} ${e.type}`).join(" · ");
      li.appendChild(ev);
    }
    ul.appendChild(li);
  }
  box.appendChild(ul);
}

function endKindLabel(k: string): string {
  return { elim: "eliminação", defuse: "defuse", boom: "spike explodiu", time: "tempo esgotado" }[k] ?? k;
}

function renderChapters(): void {
  const bar = document.getElementById("chapters")!;
  bar.innerHTML = "";
  const rs = currentMap.rounds.filter(
    (r) => r.timestamps.buyPhaseStart != null && r.timestamps.roundEnd != null,
  );
  for (const r of rs) {
    const span = (r.timestamps.roundEnd! - r.timestamps.buyPhaseStart!) || 1;
    const d = document.createElement("div");
    d.className = "ch " + (r.result.winner === "teamA" ? "won-a" : "won-b");
    d.style.flexGrow = String(Math.max(1, Math.round(span)));
    d.title = `r${r.roundNumber} ${r.result.scoreAfterRound} ${teamName(r.result.winner)} [${fmt(r.timestamps.roundStart)}]${r.result.endKind && r.result.endKind !== "unknown" ? " · " + endKindLabel(r.result.endKind) : ""}`;
    d.dataset.start = String(r.timestamps.buyPhaseStart);
    d.dataset.end = String(r.timestamps.roundEnd);
    d.dataset.n = String(r.roundNumber);
    d.onclick = () => yt.seek((r.timestamps.roundStart ?? 0) + 0.5);
    bar.appendChild(d);
  }
  tickChapter();
}

function tickChapter(): void {
  const now = yt.now();
  const label = document.getElementById("chap-label")!;
  const blocks = [...document.querySelectorAll<HTMLElement>("#chapters .ch")];
  if (now == null || blocks.length === 0) return;
  let cur: HTMLElement | null = null;
  let pct = 0;
  for (const b of blocks) {
    const s = parseFloat(b.dataset.start!);
    const e = parseFloat(b.dataset.end!);
    const hit = now >= s && now <= e;
    b.classList.toggle("cur", hit);
    if (hit) {
      cur = b;
      pct = Math.min(100, Math.max(0, ((now - s) / Math.max(1, e - s)) * 100));
      b.style.setProperty("--p", `${pct.toFixed(1)}%`);
    } else {
      b.style.removeProperty("--p");
    }
  }
  const rows = [...document.querySelectorAll<HTMLElement>(".rounds li[data-start]")];
  let curRow: HTMLElement | null = null;
  for (const li of rows) {
    const s = parseFloat(li.dataset.start!);
    const e = parseFloat(li.dataset.end!);
    const hit = now >= s && now <= e;
    li.classList.toggle("cur", hit);
    if (hit) {
      curRow = li;
      li.style.setProperty("--p", `${pct.toFixed(1)}%`);
    } else {
      li.style.removeProperty("--p");
    }
  }
  label.textContent = cur
    ? `# agora: r${cur.dataset.n} [${fmt(parseFloat(cur.dataset.start!))} → ${fmt(parseFloat(cur.dataset.end!))}] ${pct.toFixed(0)}%`
    : "# fora de round (intervalo / outro mapa)";
}

function wireControls(): void {
  document.getElementById("btn-back")!.onclick = () => yt.nudge(-2);
  document.getElementById("btn-fwd")!.onclick = () => yt.nudge(2);
  const frame = document.getElementById("yt-player")!;
  const sizeBtns = [...document.querySelectorAll<HTMLButtonElement>(".size-btns [data-w]")];
  const wideBtn = document.getElementById("btn-wide")!;
  const main = document.querySelector("main")!;
  const mark = (active: HTMLElement | null) => sizeBtns.forEach((b) => b.classList.toggle("on", b === active));
  sizeBtns.forEach((b) => {
    b.onclick = () => {
      main.classList.remove("theater");
      wideBtn.classList.remove("on");
      frame.style.width = `${b.dataset.w}px`;
      frame.style.maxWidth = "100%";
      mark(b);
    };
  });
  wideBtn.onclick = () => {
    const on = main.classList.toggle("theater");
    wideBtn.classList.toggle("on", on);
    frame.style.width = on ? "100%" : "720px";
    mark(on ? null : sizeBtns[1]);
  };
}

window.addEventListener("hashchange", () => {
  document.getElementById("round-list")!.innerHTML = "";
  document.getElementById("map-tabs")!.innerHTML = "";
  document.getElementById("match-sub")!.textContent = "carregando…";
  route();
});

load().catch((e) => {
  document.getElementById("match-sub")!.textContent = `Erro: ${(e as Error).message}`;
});
