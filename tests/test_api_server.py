"""
Integration Tests for C9 Fearless Draft REST API Server
Verifies HTTP routes, health checks, team scouting, draft lifecycle, and recommendation endpoints.
"""

import pytest
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase

from engine.api_server import FearlessDraftApp
from engine.data_loader import GridDataLoader


class TestFearlessDraftAPI(AioHTTPTestCase):
    async def get_application(self):
        loader = GridDataLoader()
        loader.load()
        server = FearlessDraftApp(loader=loader)
        return server.create_app()

    async def test_health_endpoint(self):
        resp = await self.client.request("GET", "/api/health")
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "healthy"
        assert data["teams_loaded"] >= 40

    async def test_get_teams_endpoint(self):
        resp = await self.client.request("GET", "/api/teams")
        assert resp.status == 200
        data = await resp.json()
        assert "teams" in data
        assert len(data["teams"]) >= 40
        c9_team = next(t for t in data["teams"] if t["is_c9"])
        assert c9_team["name"] == "Cloud9 Kia"

    async def test_scout_team_endpoint(self):
        resp = await self.client.request("GET", "/api/scout/47351")
        assert resp.status == 200
        data = await resp.json()
        assert data["target_team"] == "Cloud9 Kia"
        assert len(data["roster_scout"]) >= 5

    async def test_draft_lifecycle(self):
        # 1. Create Draft
        resp = await self.client.request(
            "POST",
            "/api/draft/new",
            json={
                "series_id": "api-test-series",
                "team_blue": "Cloud9 Kia",
                "team_red": "100 Thieves",
                "fearless_mode": "hard",
            },
        )
        assert resp.status == 201
        draft = await resp.json()
        assert draft["series_id"] == "api-test-series"
        assert draft["current_game"] == 1

        # 2. Get recommendations
        rec_resp = await self.client.request("GET", "/api/draft/api-test-series/recommend")
        assert rec_resp.status == 200
        rec_data = await rec_resp.json()
        assert len(rec_data["recommendations"]) > 0

        # 3. Execute action (Ban 1)
        action_resp = await self.client.request(
            "POST",
            "/api/draft/api-test-series/action",
            json={"champion": "Rumble"},
        )
        assert action_resp.status == 200
        action_data = await action_resp.json()
        assert action_data["success"] is True
        assert "Rumble" in action_data["draft"]["blue_bans"]
