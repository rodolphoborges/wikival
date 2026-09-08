export interface RoundTimestamps {
  buyPhaseStart: number | null;
  roundStart: number | null;
  roundEnd: number | null;
  confidence?: number;
}

export interface RoundResult {
  winner: string;
  scoreAfterRound: string;
  endKind?: string;
}

export interface Round {
  roundNumber: number;
  type?: string;
  timestamps: RoundTimestamps;
  result: RoundResult;
  layer1Enriched: boolean;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  events: any[];
}

export interface CatalogEntry {
  id: string;
  slug: string;
  teamA: string;
  teamB: string;
  tagA: string;
  tagB: string;
  scoreA: number;
  scoreB: number;
  winner: string;
  stage: string;
  format: string;
  date: string;
  vlrUrl: string;
  status: "processed" | "pending";
  dataFile: string | null;
}

export interface EventCatalog {
  eventId: string;
  eventName: string;
  region: string;
  stage: string;
  order: number;
  matches: CatalogEntry[];
}

export interface Catalog {
  events: EventCatalog[];
}

export interface GameMap {

  mapIndex: number;
  mapName: string;
  pickBy?: string;
  score: string | null;
  winner: string;
  anchorApproxSec: number | null;
  status: string;
  rounds: Round[];
}

export interface Match {
  matchId: string;
  youtubeVideoId: string;
  vlrUrl?: string;
  meta: {
    tournament: string;
    stage?: string;
    broadcast?: string;
    videoDurationSec?: number;
    teams: { teamA: string; teamB: string };
    finalScore?: string;
    winner?: string;
    enrichmentStatus: string;
    enrichmentCoveragePercent: number;
  };
  maps: GameMap[];
}
