"""
C9 Fearless Draft Engine - Fearless Rules & Draft State Machine
Implements pro-level Fearless Draft rulesets for League of Legends Bo3 and Bo5 series.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple


class FearlessMode(str, Enum):
    HARD = "hard"  # Mutual lockout: picked champion cannot be played by either team in later games
    SOFT = "soft"  # Team lockout: picked champion cannot be played by the same team again


class Side(str, Enum):
    BLUE = "blue"
    RED = "red"


class ActionType(str, Enum):
    BAN = "ban"
    PICK = "pick"


@dataclass
class DraftStep:
    step_number: int
    side: Side
    action: ActionType
    phase_label: str  # e.g. "B1 Ban", "R1 Pick"


# Standard competitive 10-ban / 10-pick order
OFFICIAL_DRAFT_SEQUENCE: List[DraftStep] = [
    # Phase 1: 3 bans each
    DraftStep(1, Side.BLUE, ActionType.BAN, "Blue Ban 1"),
    DraftStep(2, Side.RED, ActionType.BAN, "Red Ban 1"),
    DraftStep(3, Side.BLUE, ActionType.BAN, "Blue Ban 2"),
    DraftStep(4, Side.RED, ActionType.BAN, "Red Ban 2"),
    DraftStep(5, Side.BLUE, ActionType.BAN, "Blue Ban 3"),
    DraftStep(6, Side.RED, ActionType.BAN, "Red Ban 3"),
    # Phase 2: Pick 1 (1-2-2-1)
    DraftStep(7, Side.BLUE, ActionType.PICK, "Blue Pick 1"),
    DraftStep(8, Side.RED, ActionType.PICK, "Red Pick 1"),
    DraftStep(9, Side.RED, ActionType.PICK, "Red Pick 2"),
    DraftStep(10, Side.BLUE, ActionType.PICK, "Blue Pick 2"),
    DraftStep(11, Side.BLUE, ActionType.PICK, "Blue Pick 3"),
    DraftStep(12, Side.RED, ActionType.PICK, "Red Pick 3"),
    # Phase 3: 2 bans each (Red starts)
    DraftStep(13, Side.RED, ActionType.BAN, "Red Ban 4"),
    DraftStep(14, Side.BLUE, ActionType.BAN, "Blue Ban 4"),
    DraftStep(15, Side.RED, ActionType.BAN, "Red Ban 5"),
    DraftStep(16, Side.BLUE, ActionType.BAN, "Blue Ban 5"),
    # Phase 4: Pick 2 (1-2-1)
    DraftStep(17, Side.RED, ActionType.PICK, "Red Pick 4"),
    DraftStep(18, Side.BLUE, ActionType.PICK, "Blue Pick 4"),
    DraftStep(19, Side.BLUE, ActionType.PICK, "Blue Pick 5"),
    DraftStep(20, Side.RED, ActionType.PICK, "Red Pick 5"),
]


class FearlessError(Exception):
    """Base exception for fearless draft rule violations."""
    pass


class FearlessLockoutError(FearlessError):
    """Raised when an attempt is made to pick a champion locked out by Fearless Draft rules."""
    def __init__(self, champion: str, game_picked: int, team_picked: str, mode: FearlessMode):
        super().__init__(
            f"Fearless Draft Violation: '{champion}' was already picked in Game {game_picked} by {team_picked}. "
            f"Under {mode.value.upper()} Fearless rules, it cannot be picked again in this series."
        )
        self.champion = champion
        self.game_picked = game_picked
        self.team_picked = team_picked
        self.mode = mode


class DuplicateActionError(FearlessError):
    """Raised when a champion is picked or banned twice in the same game."""
    def __init__(self, champion: str, action: str):
        super().__init__(f"Champion '{champion}' has already been {action}ed in the current game.")
        self.champion = champion
        self.action = action


class DraftFinishedError(FearlessError):
    """Raised when an action is attempted on a completed draft."""
    pass


@dataclass
class CompletedGame:
    game_number: int
    blue_team: str
    red_team: str
    blue_picks: List[str]
    red_picks: List[str]
    blue_bans: List[str]
    red_bans: List[str]
    winner: Optional[Side] = None


@dataclass
class DraftState:
    series_id: str
    team_blue: str
    team_red: str
    fearless_mode: FearlessMode = FearlessMode.HARD
    max_games: int = 3  # 3 for Bo3, 5 for Bo5
    current_game: int = 1
    current_step_index: int = 0
    # Current game selections
    blue_bans: List[str] = field(default_factory=list)
    red_bans: List[str] = field(default_factory=list)
    blue_picks: List[str] = field(default_factory=list)
    red_picks: List[str] = field(default_factory=list)
    # Series history (records game number & team that picked each champ)
    # champion_name -> (game_number, team_name)
    series_lockout_history: Dict[str, Tuple[int, str]] = field(default_factory=dict)
    completed_games: List[CompletedGame] = field(default_factory=list)

    @property
    def is_current_game_draft_complete(self) -> bool:
        return self.current_step_index >= len(OFFICIAL_DRAFT_SEQUENCE)

    @property
    def current_step(self) -> Optional[DraftStep]:
        if self.is_current_game_draft_complete:
            return None
        return OFFICIAL_DRAFT_SEQUENCE[self.current_step_index]

    def get_locked_champions(self, for_team: str) -> Set[str]:
        """Returns the set of champion names that cannot be picked by `for_team` due to Fearless rules."""
        locked: Set[str] = set()
        for champ, (game_num, team_name) in self.series_lockout_history.items():
            if self.fearless_mode == FearlessMode.HARD:
                # In hard fearless, ANY team pick locks it out for EVERYONE
                locked.add(champ)
            elif self.fearless_mode == FearlessMode.SOFT:
                # In soft fearless, only the team that picked it is locked out
                if team_name == for_team:
                    locked.add(champ)
        return locked

    def is_champion_available(self, champion: str, for_side: Side) -> Tuple[bool, Optional[str]]:
        """
        Checks whether `champion` can be selected by `for_side` in current turn.
        Returns (is_available, error_reason).
        """
        step = self.current_step
        if not step:
            return False, "Draft for the current game is already complete."

        # Check current game bans and picks
        current_game_taken = set(self.blue_bans + self.red_bans + self.blue_picks + self.red_picks)
        if champion in current_game_taken:
            return False, f"'{champion}' has already been selected or banned in this game."

        # If it's a pick step, enforce Fearless Draft lockouts
        if step.action == ActionType.PICK:
            acting_team = self.team_blue if for_side == Side.BLUE else self.team_red
            if champion in self.series_lockout_history:
                g_num, t_name = self.series_lockout_history[champion]
                if self.fearless_mode == FearlessMode.HARD or t_name == acting_team:
                    return False, f"Fearless Lockout: Picked in Game {g_num} by {t_name}."

        return True, None

    def execute_action(self, champion: str) -> DraftStep:
        """
        Executes the current draft step with `champion`.
        Advances step index and enforces all Fearless validation.
        """
        if self.is_current_game_draft_complete:
            raise DraftFinishedError("All 20 draft steps for this game are already complete.")

        step = self.current_step
        assert step is not None

        acting_team = self.team_blue if step.side == Side.BLUE else self.team_red

        # Validate duplicate within current game
        current_game_taken = set(self.blue_bans + self.red_bans + self.blue_picks + self.red_picks)
        if champion in current_game_taken:
            raise DuplicateActionError(champion, "selected or ban")

        # Validate Fearless Draft lockout for picks
        if step.action == ActionType.PICK:
            if champion in self.series_lockout_history:
                g_num, t_name = self.series_lockout_history[champion]
                if self.fearless_mode == FearlessMode.HARD:
                    raise FearlessLockoutError(champion, g_num, t_name, self.fearless_mode)
                elif self.fearless_mode == FearlessMode.SOFT and t_name == acting_team:
                    raise FearlessLockoutError(champion, g_num, t_name, self.fearless_mode)

            # Record pick
            if step.side == Side.BLUE:
                self.blue_picks.append(champion)
            else:
                self.red_picks.append(champion)
        else:
            # Record ban
            if step.side == Side.BLUE:
                self.blue_bans.append(champion)
            else:
                self.red_bans.append(champion)

        executed_step = step
        self.current_step_index += 1
        return executed_step

    def finish_current_game(self, winner: Optional[Side] = None) -> None:
        """
        Locks in the current game's picks into the series Fearless lockout ledger,
        records the completed game, and advances to the next game in the series.
        """
        if not self.is_current_game_draft_complete:
            raise FearlessError("Cannot finish game: current draft has not completed all 20 steps.")

        # Record all picks into series lockout history
        for champ in self.blue_picks:
            self.series_lockout_history[champ] = (self.current_game, self.team_blue)
        for champ in self.red_picks:
            self.series_lockout_history[champ] = (self.current_game, self.team_red)

        completed = CompletedGame(
            game_number=self.current_game,
            blue_team=self.team_blue,
            red_team=self.team_red,
            blue_picks=list(self.blue_picks),
            red_picks=list(self.red_picks),
            blue_bans=list(self.blue_bans),
            red_bans=list(self.red_bans),
            winner=winner,
        )
        self.completed_games.append(completed)

        # Prepare next game
        self.current_game += 1
        self.current_step_index = 0
        self.blue_bans = []
        self.red_bans = []
        self.blue_picks = []
        self.red_picks = []

    def to_dict(self) -> Dict[str, Any]:
        """Serializes draft state to a clean JSON-ready dictionary."""
        curr_step = self.current_step
        return {
            "series_id": self.series_id,
            "team_blue": self.team_blue,
            "team_red": self.team_red,
            "fearless_mode": self.fearless_mode.value,
            "max_games": self.max_games,
            "current_game": self.current_game,
            "current_step_index": self.current_step_index,
            "is_draft_complete": self.is_current_game_draft_complete,
            "current_step": {
                "step_number": curr_step.step_number,
                "side": curr_step.side.value,
                "action": curr_step.action.value,
                "phase_label": curr_step.phase_label,
            } if curr_step else None,
            "blue_bans": self.blue_bans,
            "red_bans": self.red_bans,
            "blue_picks": self.blue_picks,
            "red_picks": self.red_picks,
            "locked_champions_blue": sorted(list(self.get_locked_champions(self.team_blue))),
            "locked_champions_red": sorted(list(self.get_locked_champions(self.team_red))),
            "series_lockouts": {
                c: {"game": g, "team": t} for c, (g, t) in self.series_lockout_history.items()
            },
            "completed_games": [
                {
                    "game_number": cg.game_number,
                    "blue_team": cg.blue_team,
                    "red_team": cg.red_team,
                    "blue_picks": cg.blue_picks,
                    "red_picks": cg.red_picks,
                    "blue_bans": cg.blue_bans,
                    "red_bans": cg.red_bans,
                    "winner": cg.winner.value if cg.winner else None,
                }
                for cg in self.completed_games
            ],
        }
