"""
C9 Fearless Draft Engine - Web API Server
Provides REST endpoints and interactive web UI for pro-level League of Legends Fearless Draft management.
"""

from __future__ import annotations

import json
import os
from typing import Dict, Optional

from aiohttp import web

from engine.data_loader import GridDataLoader
from engine.fearless_rules import DraftState, FearlessError, FearlessMode, Side
from engine.recommender import DraftRecommender


class FearlessDraftApp:
    def __init__(self, loader: Optional[GridDataLoader] = None):
        if loader is None:
            loader = GridDataLoader()
            loader.load()
        self.loader = loader
        self.recommender = DraftRecommender(self.loader)
        self.active_drafts: Dict[str, DraftState] = {}

    def create_app(self) -> web.Application:
        app = web.Application()
        app.router.add_get("/api/health", self.handle_health)
        app.router.add_get("/api/teams", self.handle_get_teams)
        app.router.add_get("/api/teams/{team_id}", self.handle_get_team_detail)
        app.router.add_get("/api/scout/{team_id}", self.handle_scout_team)
        app.router.add_post("/api/draft/new", self.handle_new_draft)
        app.router.add_get("/api/draft/{series_id}", self.handle_get_draft)
        app.router.add_post("/api/draft/{series_id}/action", self.handle_draft_action)
        app.router.add_get("/api/draft/{series_id}/recommend", self.handle_get_recommendations)
        app.router.add_post("/api/draft/{series_id}/finish-game", self.handle_finish_game)

        # Serve static UI
        static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
        if os.path.exists(static_dir):
            app.router.add_static("/static/", static_dir)
            app.router.add_get("/", self.handle_index)

        return app

    async def handle_health(self, request: web.Request) -> web.Response:
        return web.json_response({
            "status": "healthy",
            "teams_loaded": len(self.loader.teams),
            "players_loaded": len(self.loader.players),
            "characters_loaded": len(self.loader.characters),
            "active_drafts": len(self.active_drafts),
        })

    async def handle_get_teams(self, request: web.Request) -> web.Response:
        teams_list = [
            {
                "team_id": t.team_id,
                "name": t.name,
                "series_count": t.series_count,
                "total_games": t.total_games,
                "win_rate": round(t.win_rate, 1),
                "is_c9": "cloud9" in t.name.lower(),
            }
            for t in self.loader.teams.values()
        ]
        # Sort C9 first, then by series_count descending
        teams_list.sort(key=lambda t: (t["is_c9"], t["series_count"]), reverse=True)
        return web.json_response({"teams": teams_list})

    async def handle_get_team_detail(self, request: web.Request) -> web.Response:
        team_id = request.match_info["team_id"]
        team = self.loader.teams.get(team_id)
        if not team:
            return web.json_response({"error": "Team not found"}, status=404)

        players_list = []
        for p in team.players.values():
            comfort = [
                {
                    "name": c.name,
                    "games": c.games,
                    "wins": c.wins,
                    "win_rate": round(c.win_rate, 1),
                }
                for c in p.comfort_picks(min_games=1)[:6]
            ]
            players_list.append({
                "player_id": p.player_id,
                "name": p.name,
                "role": p.role,
                "total_games": p.total_games(),
                "top_picks": comfort,
            })

        return web.json_response({
            "team_id": team.team_id,
            "name": team.name,
            "series_count": team.series_count,
            "win_rate": round(team.win_rate, 1),
            "players": players_list,
        })

    async def handle_scout_team(self, request: web.Request) -> web.Response:
        team_id = request.match_info["team_id"]
        team = self.loader.teams.get(team_id)
        if not team:
            return web.json_response({"error": "Team not found"}, status=404)

        dossier_players = []
        for p in team.players.values():
            comfort = p.comfort_picks(min_games=2)
            dossier_players.append({
                "name": p.name,
                "role": p.role,
                "pool_depth": len(p.champions),
                "comfort_count": len(comfort),
                "choke_vulnerable": len(comfort) <= 3,
                "comfort_picks": [
                    {"name": c.name, "games": c.games, "win_rate": round(c.win_rate, 1)}
                    for c in comfort[:5]
                ],
            })

        return web.json_response({
            "target_team": team.name,
            "team_id": team.team_id,
            "series_played": team.series_count,
            "overall_win_rate": round(team.win_rate, 1),
            "roster_scout": dossier_players,
        })

    async def handle_new_draft(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
        except Exception:
            data = {}

        series_id = data.get("series_id", f"draft-{len(self.active_drafts)+1}")
        team_blue = data.get("team_blue", "Cloud9 Kia")
        team_red = data.get("team_red", "100 Thieves")
        mode_str = data.get("fearless_mode", "hard").lower()
        fearless_mode = FearlessMode.SOFT if mode_str == "soft" else FearlessMode.HARD
        max_games = int(data.get("max_games", 3))

        draft = DraftState(
            series_id=series_id,
            team_blue=team_blue,
            team_red=team_red,
            fearless_mode=fearless_mode,
            max_games=max_games,
        )
        self.active_drafts[series_id] = draft
        return web.json_response(draft.to_dict(), status=201)

    async def handle_get_draft(self, request: web.Request) -> web.Response:
        series_id = request.match_info["series_id"]
        draft = self.active_drafts.get(series_id)
        if not draft:
            return web.json_response({"error": "Draft not found"}, status=404)
        return web.json_response(draft.to_dict())

    async def handle_draft_action(self, request: web.Request) -> web.Response:
        series_id = request.match_info["series_id"]
        draft = self.active_drafts.get(series_id)
        if not draft:
            return web.json_response({"error": "Draft not found"}, status=404)

        try:
            data = await request.json()
            champion = data.get("champion", "").strip()
            if not champion:
                return web.json_response({"error": "Champion name is required"}, status=400)

            executed_step = draft.execute_action(champion)
            return web.json_response({
                "success": True,
                "executed_step": {
                    "step_number": executed_step.step_number,
                    "side": executed_step.side.value,
                    "action": executed_step.action.value,
                    "phase_label": executed_step.phase_label,
                    "champion": champion,
                },
                "draft": draft.to_dict(),
            })
        except FearlessError as e:
            return web.json_response({"error": str(e), "type": type(e).__name__}, status=400)

    async def handle_get_recommendations(self, request: web.Request) -> web.Response:
        series_id = request.match_info["series_id"]
        draft = self.active_drafts.get(series_id)
        if not draft:
            return web.json_response({"error": "Draft not found"}, status=404)

        recs = self.recommender.recommend(draft, top_n=5)
        return web.json_response({
            "current_step": draft.to_dict()["current_step"],
            "recommendations": [
                {
                    "champion": r.champion,
                    "role": r.role,
                    "score": r.score,
                    "reason": r.reason,
                    "win_rate": r.win_rate,
                    "games_played": r.games_played,
                    "synergy_score": r.synergy_score,
                    "counter_score": r.counter_score,
                    "choke_point_flag": r.choke_point_flag,
                }
                for r in recs
            ],
        })

    async def handle_finish_game(self, request: web.Request) -> web.Response:
        series_id = request.match_info["series_id"]
        draft = self.active_drafts.get(series_id)
        if not draft:
            return web.json_response({"error": "Draft not found"}, status=404)

        try:
            data = await request.json() if request.can_read_body else {}
        except Exception:
            data = {}

        winner_str = data.get("winner")
        winner = Side.BLUE if winner_str == "blue" else (Side.RED if winner_str == "red" else None)

        try:
            draft.finish_current_game(winner=winner)
            return web.json_response({
                "success": True,
                "message": f"Game {draft.current_game - 1} completed and locked. Now on Game {draft.current_game}.",
                "draft": draft.to_dict(),
            })
        except FearlessError as e:
            return web.json_response({"error": str(e)}, status=400)

    async def handle_index(self, request: web.Request) -> web.Response:
        index_path = os.path.join(os.path.dirname(__file__), "..", "static", "index.html")
        if os.path.exists(index_path):
            with open(index_path, "r", encoding="utf-8") as f:
                return web.Response(text=f.read(), content_type="text/html")
        return web.Response(text="<h1>C9 Fearless Draft Engine</h1>", content_type="text/html")


def run_app(host: str = "127.0.0.1", port: int = 8090):
    server = FearlessDraftApp()
    app = server.create_app()
    web.run_app(app, host=host, port=port)


if __name__ == "__main__":
    run_app()
