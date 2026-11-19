"""
C9 Fearless Draft Engine - AI & Statistical Recommendation Engine
Generates optimal pick and ban suggestions based on player mastery, team synergy,
counter-matchups, and Fearless Draft champion lockout availability.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from engine.data_loader import GridDataLoader, ROLE_CHAMPION_HINTS
from engine.fearless_rules import ActionType, DraftState, Side


@dataclass
class Recommendation:
    champion: str
    role: str
    score: float
    reason: str
    win_rate: float
    games_played: int
    synergy_score: float
    counter_score: float
    choke_point_flag: bool = False


class DraftRecommender:
    """Calculates tactical pick and ban recommendations for active draft turns."""

    def __init__(self, loader: GridDataLoader):
        self.loader = loader

    def recommend(
        self,
        draft: DraftState,
        top_n: int = 5
    ) -> List[Recommendation]:
        """
        Returns top `top_n` champion recommendations for the current step in `draft`.
        """
        step = draft.current_step
        if not step:
            return []

        acting_side = step.side
        acting_team_name = draft.team_blue if acting_side == Side.BLUE else draft.team_red
        enemy_team_name = draft.team_red if acting_side == Side.BLUE else draft.team_blue

        acting_team = self.loader.find_team_by_name(acting_team_name)
        enemy_team = self.loader.find_team_by_name(enemy_team_name)

        if step.action == ActionType.BAN:
            return self._recommend_bans(draft, acting_side, enemy_team, top_n)
        else:
            return self._recommend_picks(draft, acting_side, acting_team, enemy_team, top_n)

    def _recommend_bans(
        self,
        draft: DraftState,
        acting_side: Side,
        enemy_team: Optional[Any],
        top_n: int
    ) -> List[Recommendation]:
        """Recommends bans targeted at opponent comfort picks and pool bottlenecks."""
        current_taken = set(draft.blue_bans + draft.red_bans + draft.blue_picks + draft.red_picks)
        enemy_locked = draft.get_locked_champions(draft.team_red if acting_side == Side.BLUE else draft.team_blue)

        recommendations: List[Recommendation] = []

        if not enemy_team:
            # Fallback to general pro meta bans if enemy team not found in historical data
            for champ_name in ["Azir", "Orianna", "Vi", "Gnar", "Varus", "Rell", "Ahri"]:
                if champ_name not in current_taken and champ_name not in enemy_locked:
                    recommendations.append(
                        Recommendation(
                            champion=champ_name,
                            role="Meta Priority",
                            score=75.0,
                            reason="High-priority competitive staple.",
                            win_rate=55.0,
                            games_played=50,
                            synergy_score=0.0,
                            counter_score=0.0,
                        )
                    )
            return recommendations[:top_n]

        # Scan each enemy player's champion pool
        for player in enemy_team.players.values():
            comfort_picks = player.comfort_picks(min_games=2)
            available_comfort = [
                c for c in comfort_picks
                if c.name not in current_taken and c.name not in enemy_locked
            ]

            # Choke point warning: if opponent has <= 2 viable comfort champions left
            is_choke = len(available_comfort) <= 2 and len(comfort_picks) >= 2

            for c in available_comfort:
                # Ban score = enemy win rate * games played + choke bonus
                score = (c.win_rate * 0.6) + (min(c.games, 20) * 2.0)
                if is_choke:
                    score += 35.0  # Heavy bonus for suffocating opponent's narrow champion pool

                reason = (
                    f"Target ban against {player.name} ({player.role}): "
                    f"{c.games} games with {c.win_rate:.1f}% WR"
                )
                if is_choke:
                    reason += f" ⚠️ CHOKE POINT: {player.name} only has {len(available_comfort)} comfort picks remaining!"

                recommendations.append(
                    Recommendation(
                        champion=c.name,
                        role=player.role,
                        score=score,
                        reason=reason,
                        win_rate=c.win_rate,
                        games_played=c.games,
                        synergy_score=0.0,
                        counter_score=0.0,
                        choke_point_flag=is_choke,
                    )
                )

        # De-duplicate by champion name taking the highest score
        deduped: Dict[str, Recommendation] = {}
        for r in recommendations:
            if r.champion not in deduped or r.score > deduped[r.champion].score:
                deduped[r.champion] = r

        return sorted(deduped.values(), key=lambda r: r.score, reverse=True)[:top_n]

    def _recommend_picks(
        self,
        draft: DraftState,
        acting_side: Side,
        acting_team: Optional[Any],
        enemy_team: Optional[Any],
        top_n: int
    ) -> List[Recommendation]:
        """Recommends picks optimizing player mastery, role coverage, ally synergy, and enemy counters."""
        current_taken = set(draft.blue_bans + draft.red_bans + draft.blue_picks + draft.red_picks)
        my_team_name = draft.team_blue if acting_side == Side.BLUE else draft.team_red
        my_locked = draft.get_locked_champions(my_team_name)

        my_picks = draft.blue_picks if acting_side == Side.BLUE else draft.red_picks
        enemy_picks = draft.red_picks if acting_side == Side.BLUE else draft.blue_picks

        # Determine which roles are still unfilled in current game
        filled_roles: Set[str] = set()
        for p_champ in my_picks:
            for role, hint_set in ROLE_CHAMPION_HINTS.items():
                if p_champ in hint_set:
                    filled_roles.add(role)

        unfilled_roles = [r for r in ["Top", "Jungle", "Mid", "Bot", "Support"] if r not in filled_roles]

        recommendations: List[Recommendation] = []

        if not acting_team:
            # Fallback
            for champ_name, cid in self.loader.character_ids.items():
                if champ_name not in current_taken and champ_name not in my_locked:
                    recommendations.append(
                        Recommendation(
                            champion=champ_name,
                            role="Flex",
                            score=50.0,
                            reason="Available competitive champion.",
                            win_rate=50.0,
                            games_played=10,
                            synergy_score=0.0,
                            counter_score=0.0,
                        )
                    )
            return recommendations[:top_n]

        # Iterate over team players
        for player in acting_team.players.values():
            # Prioritize unfilled roles
            role_priority = 25.0 if player.role in unfilled_roles else 0.0

            for c_name, c_stat in player.champions.items():
                if c_name in current_taken or c_name in my_locked:
                    continue

                # 1. Base mastery score
                mastery = (c_stat.win_rate * 0.4) + (min(c_stat.games, 25) * 1.5)

                # 2. Synergy with current ally picks
                synergy_bonus = 0.0
                for ally_champ in my_picks:
                    pair = tuple(sorted([c_name, ally_champ]))
                    if pair in self.loader.synergies:
                        syn_data = self.loader.synergies[pair]
                        if syn_data["games"] >= 3:
                            syn_wr = syn_data["wins"] / syn_data["games"]
                            synergy_bonus += (syn_wr - 0.5) * 20.0

                # 3. Counter against enemy picks
                counter_bonus = 0.0
                for enemy_champ in enemy_picks:
                    matchup = (c_name, enemy_champ)
                    if matchup in self.loader.counters:
                        c_data = self.loader.counters[matchup]
                        if c_data["games"] >= 2:
                            cntr_wr = c_data["wins"] / c_data["games"]
                            counter_bonus += (cntr_wr - 0.5) * 25.0

                total_score = mastery + role_priority + synergy_bonus + counter_bonus

                reason_parts = [f"{player.name}'s {c_name} ({c_stat.games}G, {c_stat.win_rate:.0f}% WR)"]
                if player.role in unfilled_roles:
                    reason_parts.append(f"Fills {player.role}")
                if synergy_bonus > 3.0:
                    reason_parts.append("High ally synergy")
                if counter_bonus > 3.0:
                    reason_parts.append("Favorable enemy matchup")

                recommendations.append(
                    Recommendation(
                        champion=c_name,
                        role=player.role,
                        score=round(total_score, 1),
                        reason=" | ".join(reason_parts),
                        win_rate=c_stat.win_rate,
                        games_played=c_stat.games,
                        synergy_score=round(synergy_bonus, 1),
                        counter_score=round(counter_bonus, 1),
                    )
                )

        deduped: Dict[str, Recommendation] = {}
        for r in recommendations:
            if r.champion not in deduped or r.score > deduped[r.champion].score:
                deduped[r.champion] = r

        return sorted(deduped.values(), key=lambda r: r.score, reverse=True)[:top_n]
