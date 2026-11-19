"""
C9 Fearless Draft Engine - Data Loader
Parses official GRID esports metadata for pro League of Legends matches.
"""

from __future__ import annotations

import csv
import os
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple


@dataclass
class ChampionStats:
    name: str
    character_id: str
    games: int = 0
    wins: int = 0

    @property
    def win_rate(self) -> float:
        return (self.wins / self.games * 100.0) if self.games > 0 else 0.0


@dataclass
class PlayerProfile:
    player_id: str
    name: str
    team_id: str
    team_name: str
    role: str = "Unknown"  # Top, Jungle, Mid, Bot, Support
    champions: Dict[str, ChampionStats] = field(default_factory=dict)

    def total_games(self) -> int:
        return sum(c.games for c in self.champions.values())

    def comfort_picks(self, min_games: int = 2) -> List[ChampionStats]:
        """Returns champions sorted by mastery score (games * win rate)."""
        picks = [c for c in self.champions.values() if c.games >= min_games]
        return sorted(picks, key=lambda c: (c.games * (c.win_rate / 100.0), c.games), reverse=True)


@dataclass
class TeamProfile:
    team_id: str
    name: str
    series_count: int
    players: Dict[str, PlayerProfile] = field(default_factory=dict)
    bans_faced: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    total_games: int = 0
    total_wins: int = 0

    @property
    def win_rate(self) -> float:
        return (self.total_wins / self.total_games * 100.0) if self.total_games > 0 else 0.0


# Standard pro role mappings based on historical champion assignments in LoL
ROLE_CHAMPION_HINTS = {
    "Top": {
        "Aatrox", "Gnar", "Renekton", "Jax", "Camille", "K'Sante", "Rumble", "Ornn",
        "Jayce", "Sion", "Gragas", "Fiora", "Gwen", "Kennen", "Poppy", "Malphite",
        "Ambessa", "Sett", "Cho'Gath", "Urgot", "Mordekaiser"
    },
    "Jungle": {
        "Vi", "Sejuani", "Wukong", "Skarner", "Jarvan IV", "Xin Zhao", "Nocturne",
        "Lee Sin", "Viego", "Maokai", "Poppy", "Elise", "Nidalee", "Graves", "Ivern",
        "Kindred", "Pantheon", "Volibear", "Karthus", "Taliyah", "Zac", "Brand"
    },
    "Mid": {
        "Azir", "Orianna", "Syndra", "Ahri", "Corki", "Tristana", "Yone", "Jayce",
        "LeBlanc", "Akali", "Viktor", "Hwei", "Smolder", "Sylas", "Galio", "Taliyah",
        "Karma", "Ryze", "Zoe", "Kassadin", "Twisted Fate", "Aurelion Sol", "Anivia"
    },
    "Bot": {
        "Varus", "Ashe", "Jinx", "Kai'Sa", "Kalista", "Lucian", "Senna", "Aphelios",
        "Xayah", "Ezreal", "Jhin", "Miss Fortune", "Zeri", "Draven", "Sivir",
        "Caitlyn", "Kog'Maw", "Smolder", "Ziggs"
    },
    "Support": {
        "Nautilus", "Rell", "Leona", "Alstar", "Thresh", "Braum", "Rakan", "Lulu",
        "Nami", "Karma", "Tahm Kench", "Renata Glasc", "Poppy", "Bard", "Blitzcrank",
        "Milio", "Taric", "Soraka", "Janna", "Pyke"
    }
}


class GridDataLoader:
    """Loads and indexes official GRID metadata files."""

    def __init__(self, meta_dir: Optional[str] = None):
        if not meta_dir:
            meta_dir = os.environ.get(
                "STL_DATA_DIR",
                os.path.join(os.path.dirname(__file__), "..", "..", "c9-grid-starter", "meta")
            )
            if not os.path.exists(meta_dir):
                alt_dir = r"D:\c9-grid-starter\meta"
                if os.path.exists(alt_dir):
                    meta_dir = alt_dir

        self.meta_dir = os.path.abspath(meta_dir)
        self.teams: Dict[str, TeamProfile] = {}
        self.players: Dict[str, PlayerProfile] = {}
        self.characters: Dict[str, str] = {}  # id -> name
        self.character_ids: Dict[str, str] = {}  # name -> id
        self.games: Dict[str, Dict[str, Any]] = {}
        self.synergies: Dict[Tuple[str, str], Dict[str, int]] = defaultdict(lambda: {"games": 0, "wins": 0})
        self.counters: Dict[Tuple[str, str], Dict[str, int]] = defaultdict(lambda: {"games": 0, "wins": 0})
        self.loaded: bool = False

    def load(self) -> None:
        """Parses the CSV metadata files into memory."""
        if not os.path.exists(self.meta_dir):
            raise FileNotFoundError(f"GRID meta directory not found at: {self.meta_dir}")

        self._load_characters()
        self._load_games()
        self._load_teams()
        self._load_rosters()
        self._infer_player_roles()
        self.loaded = True

    def _load_characters(self) -> None:
        chars_path = os.path.join(self.meta_dir, "characters.csv")
        if not os.path.exists(chars_path):
            return
        with open(chars_path, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("title") == "lol":
                    cid = row["character_id"]
                    name = row["name"].strip()
                    self.characters[cid] = name
                    self.character_ids[name] = cid

    def _load_games(self) -> None:
        games_path = os.path.join(self.meta_dir, "games.csv")
        if not os.path.exists(games_path):
            return
        with open(games_path, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("title") == "lol":
                    self.games[row["game_id"]] = row

    def _load_teams(self) -> None:
        teams_path = os.path.join(self.meta_dir, "teams.csv")
        if not os.path.exists(teams_path):
            return
        with open(teams_path, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("title") == "lol":
                    tid = row["team_id"]
                    self.teams[tid] = TeamProfile(
                        team_id=tid,
                        name=row["name"].strip(),
                        series_count=int(row.get("series_count", 0)),
                    )

    def _load_rosters(self) -> None:
        rosters_path = os.path.join(self.meta_dir, "rosters.csv")
        if not os.path.exists(rosters_path):
            return

        # Track composition per game for synergy and counter calculations
        game_teams: Dict[str, Dict[str, List[Tuple[str, str]]]] = defaultdict(lambda: defaultdict(list))

        with open(rosters_path, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("title") != "lol":
                    continue

                gid = row["game_id"]
                tid = row["team_id"]
                tname = row["team_name"].strip()
                pid = row["player_id"]
                pname = row["player_name"].strip()
                cid = row["character_id"]
                cname = row["character_name"].strip()

                if not pname or not cname or gid not in self.games:
                    continue

                game = self.games[gid]
                won = (game.get("winner_team_id") == tid)

                if tid not in self.teams:
                    self.teams[tid] = TeamProfile(team_id=tid, name=tname, series_count=1)

                team = self.teams[tid]
                team.total_games += 1
                if won:
                    team.total_wins += 1

                if pid not in self.players:
                    self.players[pid] = PlayerProfile(
                        player_id=pid,
                        name=pname,
                        team_id=tid,
                        team_name=tname,
                    )

                player = self.players[pid]
                team.players[pid] = player

                if cname not in player.champions:
                    player.champions[cname] = ChampionStats(name=cname, character_id=cid)

                c_stat = player.champions[cname]
                c_stat.games += 1
                if won:
                    c_stat.wins += 1

                game_teams[gid][tid].append((cname, won))

        # Build pairwise synergies and counters
        for gid, t_dict in game_teams.items():
            team_ids = list(t_dict.keys())
            for tid, champs_won in t_dict.items():
                # Synergy: all pairs within same team
                n = len(champs_won)
                for i in range(n):
                    c1, w = champs_won[i]
                    for j in range(i + 1, n):
                        c2, _ = champs_won[j]
                        pair = tuple(sorted([c1, c2]))
                        self.synergies[pair]["games"] += 1
                        if w:
                            self.synergies[pair]["wins"] += 1

            if len(team_ids) == 2:
                t1, t2 = team_ids[0], team_ids[1]
                t1_champs = t_dict[t1]
                t2_champs = t_dict[t2]
                for c1, w1 in t1_champs:
                    for c2, w2 in t2_champs:
                        # c1 vs c2
                        self.counters[(c1, c2)]["games"] += 1
                        if w1:
                            self.counters[(c1, c2)]["wins"] += 1

    def _infer_player_roles(self) -> None:
        """Assigns the most probable primary role to each player based on champion pool."""
        for player in self.players.values():
            role_scores: Dict[str, int] = defaultdict(int)
            for champ_name, stats in player.champions.items():
                for role, hint_set in ROLE_CHAMPION_HINTS.items():
                    if champ_name in hint_set:
                        role_scores[role] += stats.games

            if role_scores:
                best_role = max(role_scores.items(), key=lambda x: x[1])[0]
                player.role = best_role

    def get_cloud9_profile(self) -> Optional[TeamProfile]:
        """Returns the primary Cloud9 League of Legends team profile."""
        for team in self.teams.values():
            if "cloud9" in team.name.lower():
                return team
        return None

    def find_team_by_name(self, query: str) -> Optional[TeamProfile]:
        """Case-insensitive substring search for team."""
        q = query.lower()
        for team in self.teams.values():
            if q in team.name.lower():
                return team
        return None
