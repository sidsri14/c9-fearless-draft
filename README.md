# Cloud9 Fearless Draft & Macro Scouting Engine

> **Category 2:** *League of Legends Macro Scouting & Draft Management System*  
> **Hackathon:** [Cloud9 x JetBrains: Sky's The Limit Hackathon 2026](https://cloud9.devpost.com) ($25,000 Cash Pool)  
> **Official Esports Data:** Powered by [GRID Esports Data Platform](https://grid.gg)

---

## 🏆 Overview

With the global adoption of **Fearless Draft** in professional League of Legends (LCK Cup, LEC, LTA, and LPL), the traditional approach to draft preparation is obsolete. In Fearless Draft, once a champion is selected in earlier games of a Best-of-3 or Best-of-5 series, that champion is **permanently locked out** for subsequent games.

The **Cloud9 Fearless Draft & Macro Scouting Engine** provides a pro-grade scouting and real-time draft assistant tailored specifically for **Cloud9 Kia**. It analyzes official GRID match data across 745 pro series, tracks champion pool depletion in real time, automatically blocks illegal locked picks, detects opponent choke points, and provides AI-assisted draft recommendations.

---

## ✨ Core Capabilities

### 1. Pro Fearless Draft State Machine
- **Hard Fearless (Mutual Lockout)**: Once any champion is picked by either team in Game $N$, it cannot be picked by *either* team in Games $N+1$ through 5.
- **Soft Fearless (Team Lockout)**: Champions picked by Team A are locked out only for Team A; the opposing team may still draft them unless they previously selected them.
- **Strict Turn Enforcement**: Implements the official 10-ban / 10-pick pro sequence (Ban 1, Pick 1, Ban 2, Pick 2) with automated turn transitions and validation.
- **Illegal Pick Prevention**: Instant runtime rejection (`FearlessLockoutError`) if an analyst or coach attempts to lock a champion restricted by series history.

### 2. Opponent Choke Point & Vulnerability Detection
- Evaluates opponent champion pool depth for every role (Top, Jungle, Mid, Bot, Support) using historical pro series.
- Flags **Choke Point Warnings** when an opponent player has $\le 2$ comfort champions remaining in their pool for upcoming games, recommending target bans to completely suffocate the opponent's strategy.

### 3. AI & Statistical Recommendation Engine
Generates multi-objective recommendations for active turns:
$$\text{Score} = w_1 \cdot \text{Mastery}(p, c) + w_2 \cdot \text{Synergy}(c, \text{Allies}) - w_3 \cdot \text{Counter}(c, \text{Enemies}) + w_4 \cdot \text{ChokeBonus}$$
- **Player Mastery**: Historical pro win rate weighted by games played.
- **Composition Synergy**: Pairwise champion co-occurrence win rate from GRID match history.
- **Counter Advantage**: Head-to-head win rate differentials against locked opponent picks.

### 4. Official GRID Data Compliance
- Adheres strictly to the hackathon license rules: **Zero proprietary match data is committed to git**.
- Reads official metadata dynamically from `STL_DATA_DIR` (defaulting to `../c9-grid-starter/meta` or `D:/c9-grid-starter/meta`).

---

## 🏗️ Architecture

```
D:\c9-fearless-draft/
├── engine/
│   ├── __init__.py
│   ├── data_loader.py       # GRID pro metadata parser & role/synergy profiler
│   ├── fearless_rules.py    # Official Fearless Draft 20-step state machine
│   ├── recommender.py       # Multi-objective AI recommendation engine
│   └── api_server.py        # High-performance async aiohttp REST & static server
├── static/
│   └── index.html           # Dark-themed responsive C9 interactive draft canvas
├── tests/
│   ├── test_draft_engine.py # Unit tests for rules, lockouts, and recommender
│   └── test_api_server.py   # Integration tests for all REST endpoints
├── .gitignore               # Strict exclusion of .zst, .jsonl, and meta files
└── README.md
```

---

## 🚀 Quick Start

### 1. Requirements
- Python 3.10+
- `aiohttp` and `pytest`

### 2. Run Automated Test Suite
```bash
python -m pytest tests/ -v
```
All **11 unit and integration tests** verify data loading, rule enforcement, Hard/Soft Fearless lockouts, and API endpoints:
```
tests/test_api_server.py::TestFearlessDraftAPI::test_draft_lifecycle PASSED
tests/test_api_server.py::TestFearlessDraftAPI::test_get_teams_endpoint PASSED
tests/test_api_server.py::TestFearlessDraftAPI::test_health_endpoint PASSED
tests/test_api_server.py::TestFearlessDraftAPI::test_scout_team_endpoint PASSED
tests/test_draft_engine.py::test_grid_data_loader_counts PASSED
tests/test_draft_engine.py::test_cloud9_roster_and_comfort_picks PASSED
tests/test_draft_engine.py::test_draft_state_initialization PASSED
tests/test_draft_engine.py::test_draft_progression_and_duplicate_rejection PASSED
tests/test_draft_engine.py::test_hard_fearless_series_lockout PASSED
tests/test_draft_engine.py::test_soft_fearless_series_lockout PASSED
tests/test_draft_engine.py::test_recommender_bans_and_picks PASSED
============================= 11 passed in 1.62s =============================
```

### 3. Launch Interactive Web Dashboard
```bash
python -m engine.api_server
```
Open [http://localhost:8090](http://localhost:8090) in any browser to launch the live Cloud9 Fearless Draft canvas.

---

## 📡 REST API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/api/health` | `GET` | Health check and total loaded teams/players count |
| `/api/teams` | `GET` | List all 45 pro teams indexed from GRID data |
| `/api/teams/{id}` | `GET` | Team profile, active roster, and champion comfort pools |
| `/api/scout/{id}` | `GET` | Scouting dossier with choke point vulnerabilities |
| `/api/draft/new` | `POST` | Initialize a new series draft (Bo3/Bo5, Hard/Soft Fearless) |
| `/api/draft/{id}` | `GET` | Get active draft state and series lockouts |
| `/api/draft/{id}/action` | `POST` | Lock in a pick or ban with Fearless validation |
| `/api/draft/{id}/recommend` | `GET` | Top 5 AI recommendations for the active turn |
| `/api/draft/{id}/finish-game` | `POST` | Finish current game and advance to Game $N+1$ |

---

## 🔒 License & Disclaimer
Match data provided by [GRID](https://grid.gg) under the Sky's The Limit 2026 Hackathon agreement. League of Legends is a registered trademark of Riot Games, Inc. This project is not affiliated with or endorsed by Riot Games.

## Paid services (fixed scope)

Bounded software services via no-signup Contra checkout: multi-repo CI reliability sprint (up to 5 repos, USD5,000 for one agreed milestone), checkout-link consistency gate (USD100), token-2022 CI/fee-math repair (USD150), BullMQ token-budget retrofit (USD300), one bounded OSS issue plus regression PR (USD75), and web3 starter CI harness (USD150).

All offers: https://sidsri14.github.io/implementation-packages.html | Request work (no signup): https://sidsri14.github.io/request-work.html

Proof: 25 merged upstream PRs / 30 total merged GitHub PRs; 201 passing tests across 15 owned repos. Independent, AI-assisted work; BCA student at Manipal University Jaipur, expected 2027, Lucknow, India. Advertised offers only, not received income; scope and written terms are agreed before any work starts.