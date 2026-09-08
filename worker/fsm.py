"""FSM de rounds: BUY -> LIVE -> END, com validacao continua de placar 0..13+.

Uso:
    from fsm import RoundFSM
    fsm = RoundFSM()
    for obs in observacoes:  # obs = dict(scoreA, scoreB, timer_visible, banner)
        eventos = fsm.step(obs, t_sec=...)
"""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class RoundState:
    phase: str = "BUY"  # BUY | LIVE | END
    scoreA: int = 0
    scoreB: int = 0
    round_number: int = 1  # 1-indexed, = scoreA+scoreB+1
    buy_start: float | None = None
    round_start: float | None = None


@dataclass
class RoundFSM:
    state: RoundState = field(default_factory=RoundState)
    finished_rounds: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def _total(self, a: int, b: int) -> int:
        return a + b

    def step(self, obs: dict, t_sec: float) -> list[dict]:
        """Processa uma observacao amostrada. Retorna lista de eventos (round_end)."""
        events: list[dict] = []
        a, b = int(obs.get("scoreA", self.state.scoreA)), int(obs.get("scoreB", self.state.scoreB))
        timer = bool(obs.get("timer_visible", False))
        banner = bool(obs.get("round_end_banner", False))
        s = self.state

        # --- validacao de placar: nunca anda >1 e nunca regride ---
        da, db = a - s.scoreA, b - s.scoreB
        if da < 0 or db < 0:
            self.errors.append(f"[{t_sec:.0f}s] placar regrediu {s.scoreA}-{s.scoreB} -> {a}-{b}")
            return events
        if da + db > 1:
            self.errors.append(f"[{t_sec:.0f}s] salto de placar {s.scoreA}-{s.scoreB} -> {a}-{b}")
            return events

        if s.phase == "BUY":
            if s.buy_start is None:
                s.buy_start = t_sec
            # buy termina quando timer de round aparece (live) ou placar ja mudou
            if timer or (da + db == 1):
                s.round_start = t_sec
                s.phase = "LIVE"
        elif s.phase == "LIVE":
            if banner or (da + db == 1):
                winner = "teamA" if da == 1 else ("teamB" if db == 1 else "unknown")
                if winner == "unknown":
                    # banner sem mudanca de placar ainda: aguarda confirmacao
                    s.phase = "END"
                    if s.round_start is None:
                        s.round_start = t_sec
                else:
                    events.append(self._close_round(winner, a, b, s.buy_start, s.round_start, t_sec))
                    s.scoreA, s.scoreB = a, b
                    s.round_number = a + b + 1
                    s.phase = "BUY"
                    s.buy_start = None
                    s.round_start = None
        elif s.phase == "END":
            if da + db == 1:
                winner = "teamA" if da == 1 else "teamB"
                events.append(self._close_round(winner, a, b, s.buy_start, s.round_start, t_sec))
                s.scoreA, s.scoreB = a, b
                s.round_number = a + b + 1
                s.phase = "BUY"
                s.buy_start = None
                s.round_start = None
        return events

    def _close_round(self, winner, a, b, buy_start, round_start, round_end):
        rec = {
            "roundNumber": self.state.round_number,
            "timestamps": {"buyPhaseStart": buy_start, "roundStart": round_start, "roundEnd": round_end},
            "result": {"winner": winner, "scoreAfterRound": f"{a}-{b}"},
        }
        self.finished_rounds.append(rec)
        return {"type": "round_end", **rec}
