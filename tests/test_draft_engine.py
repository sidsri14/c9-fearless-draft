"""
Unit and Integration Tests for C9 Fearless Draft & Scouting Engine
Verifies Fearless Draft rule enforcement, data loading, and recommendation scoring.
"""

import os
import pytest

from engine.data_loader import GridDataLoader
from engine.fearless_rules import (
    ActionType,
    DraftFinishedError,
    DraftState,
    DuplicateActionError,
    FearlessLockoutError,
    FearlessMode,
    Side,
)
from engine.recommender import DraftRecommender


@pytest.fixture(scope="session")
def loader():
    """Initializes and loads official GRID esports metadata."""
    dl = GridDataLoader()
    dl.load()
    return dl


@pytest.fixture
def recommender(loader):
    return DraftRecommender(loader)


def test_grid_data_loader_counts(loader):
    """Verifies that GRID pro metadata was parsed successfully."""
    assert len(loader.teams) >= 40
    assert len(loader.players) >= 200
    assert len(loader.characters) >= 140

    c9 = loader.get_cloud9_profile()
    assert c9 is not None
    assert "cloud9" in c9.name.lower()
    assert c9.total_games > 500
    assert c9.win_rate > 50.0


def test_cloud9_roster_and_comfort_picks(loader):
    """Verifies Cloud9 player profiles and champion comfort pools."""
    c9 = loader.get_cloud9_profile()
    player_names = {p.name for p in c9.players.values()}
    assert "Blaber" in player_names
    assert "Thanatos" in player_names
    assert "Vulcan" in player_names

    blaber = next(p for p in c9.players.values() if p.name == "Blaber")
    assert blaber.role == "Jungle"
    top_champs = [c.name for c in blaber.comfort_picks(min_games=5)]
    assert "Vi" in top_champs or "Wukong" in top_champs or "Sejuani" in top_champs


def test_draft_state_initialization():
    """Verifies initial state of a competitive draft."""
    draft = DraftState(
        series_id="test-series-1",
        team_blue="Cloud9 Kia",
        team_red="100 Thieves",
        fearless_mode=FearlessMode.HARD,
        max_games=3,
    )

    assert draft.current_game == 1
    assert draft.current_step_index == 0
    assert not draft.is_current_game_draft_complete
    assert draft.current_step.phase_label == "Blue Ban 1"
    assert draft.current_step.side == Side.BLUE
    assert draft.current_step.action == ActionType.BAN


def test_draft_progression_and_duplicate_rejection():
    """Verifies that draft steps advance and duplicates are rejected."""
    draft = DraftState(
        series_id="test-series-2",
        team_blue="Cloud9 Kia",
        team_red="100 Thieves",
    )

    step1 = draft.execute_action("Aatrox")
    assert step1.phase_label == "Blue Ban 1"
    assert "Aatrox" in draft.blue_bans

    # Attempting to ban Aatrox again should raise DuplicateActionError
    with pytest.raises(DuplicateActionError):
        draft.execute_action("Aatrox")


def test_hard_fearless_series_lockout():
    """Verifies that in Hard Fearless mode, ANY picked champion is banned in subsequent games."""
    draft = DraftState(
        series_id="test-series-hard",
        team_blue="Cloud9 Kia",
        team_red="100 Thieves",
        fearless_mode=FearlessMode.HARD,
    )

    # Execute 20 draft actions for Game 1
    champs = [
        "Aatrox", "Renekton", "Vi", "Sejuani", "Azir", "Orianna",
        "Gnar", "Wukong", "Sylas", "Varus", "Ezreal", "Alistar",
        "Rakan", "Nautilus", "Corki", "Jinx", "Leona", "Jax",
        "Kai'Sa", "Braum"
    ]
    for c in champs:
        draft.execute_action(c)

    assert draft.is_current_game_draft_complete
    draft.finish_current_game(winner=Side.BLUE)

    # Now on Game 2
    assert draft.current_game == 2
    assert len(draft.series_lockout_history) == 10  # 5 blue + 5 red picks

    # Bans can still be executed in Game 2
    for b in ["Skarner", "Jarvan IV", "Xin Zhao", "Nocturne", "Lee Sin", "Viego"]:
        draft.execute_action(b)

    # First pick of Game 2 (Blue Pick 1): attempting to pick Gnar (picked in Game 1) must fail
    with pytest.raises(FearlessLockoutError) as exc_info:
        draft.execute_action("Gnar")
    assert "Fearless Draft Violation" in str(exc_info.value)
    assert exc_info.value.champion == "Gnar"

    # Blue picks a fresh champion: Ambessa
    draft.execute_action("Ambessa")
    assert "Ambessa" in draft.blue_picks


def test_soft_fearless_series_lockout():
    """Verifies that in Soft Fearless mode, only the team that picked the champion is locked out."""
    draft = DraftState(
        series_id="test-series-soft",
        team_blue="Cloud9 Kia",
        team_red="100 Thieves",
        fearless_mode=FearlessMode.SOFT,
    )

    champs = [
        "Aatrox", "Renekton", "Vi", "Sejuani", "Azir", "Orianna",
        "Gnar", "Wukong", "Sylas", "Varus", "Ezreal", "Alistar",
        "Rakan", "Nautilus", "Corki", "Jinx", "Leona", "Jax",
        "Kai'Sa", "Braum"
    ]
    for c in champs:
        draft.execute_action(c)

    # In Game 1:
    # Blue picks: Gnar, Sylas, Ezreal, Corki, Leona
    # Red picks: Wukong, Varus, Alistar, Jax, Kai'Sa
    draft.finish_current_game(winner=Side.BLUE)

    # Advance bans in Game 2
    for b in ["Skarner", "Jarvan IV", "Xin Zhao", "Nocturne", "Lee Sin", "Viego"]:
        draft.execute_action(b)

    # Blue Pick 1: Blue cannot pick Gnar (picked by Blue in G1)
    with pytest.raises(FearlessLockoutError):
        draft.execute_action("Gnar")

    # Blue CAN pick Wukong in Soft Fearless (picked by Red in G1, not by Blue)
    step = draft.execute_action("Wukong")
    assert "Wukong" in draft.blue_picks


def test_recommender_bans_and_picks(recommender):
    """Verifies AI recommendations for both bans and picks."""
    draft = DraftState(
        series_id="test-recs",
        team_blue="Cloud9 Kia",
        team_red="100 Thieves",
        fearless_mode=FearlessMode.HARD,
    )

    # Step 1: Blue Ban 1
    ban_recs = recommender.recommend(draft, top_n=3)
    assert len(ban_recs) == 3
    for r in ban_recs:
        assert r.score > 0
        assert r.champion

    # Fast forward to pick phase (step 7)
    for b in ["Rumble", "Akali", "Ryze", "Aatrox", "Jax", "Sejuani"]:
        draft.execute_action(b)

    assert draft.current_step.action == ActionType.PICK
    pick_recs = recommender.recommend(draft, top_n=3)
    assert len(pick_recs) == 3
    for r in pick_recs:
        assert r.score > 0
        assert r.champion
