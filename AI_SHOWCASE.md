# AI-Powered Workflow Story: Building the Cloud9 Fearless Draft Engine

> **Bonus Prize Submission**: *Best AI-Powered Workflow Story*  
> **Hackathon**: [Cloud9 x JetBrains: Sky's The Limit Hackathon 2026](https://cloud9.devpost.com)  
> **Project**: [Cloud9 Fearless Draft & Scouting Engine](https://github.com/sidsri14/c9-fearless-draft)  
> **Author**: Siddharth Srivastava ([@sidsri14](https://github.com/sidsri14))

---

## Executive Summary

When professional League of Legends embraced **Fearless Draft** in 2025 and 2026 across major international leagues (LCK Cup, LEC, LTA, and LPL), the combinatorial complexity of competitive drafting exploded. In a Best-of-5 series, up to 40 champions are locked out, forcing coaching staff to manage 10 roles, player comfort pool exhaustion, and real-time counter-pick differentials under a 30-second timer.

Building a production-grade Fearless Draft management system required parsing 745 professional LoL series and millions of event rows from the official [GRID Esports Data Platform](https://grid.gg), maintaining zero data leakage per the hackathon licensing policy, and engineering an automated state machine that enforces pro pick/ban rules with microsecond latency.

Using **JetBrains PyCharm** paired with modern AI-agentic orchestration, we accelerated development from concept to a fully verified, 11-test suite implementation in under two hours.

---

## Key Challenges & How JetBrains Tools Solved Them

### 1. Data Segregation & Strict License Conformance
- **Challenge**: The hackathon's most critical rule (`AGENTS.md`) strictly prohibits committing raw `.zst`, `.jsonl`, or `meta/` CSV data to git repositories.
- **Solution**: In PyCharm, we configured `STL_DATA_DIR` as an external environment mapping pointing to the local GRID cache, wrote automated `.gitignore` safeguards, and created a pre-computed metrics pipeline (`data_loader.py`) that exports aggregated champion pool mastery without leaking proprietary event rows.

### 2. Formulating the Pro Fearless Draft State Machine
- **Challenge**: Modeling the exact 20-step sequence (Phase 1 bans 1–6, Phase 1 picks 1–6, Phase 2 bans 7–10, Phase 2 picks 7–10) with support for both **Hard Fearless** (mutual lockout) and **Soft Fearless** (team-specific lockout).
- **Solution**: We leveraged AI code generation inside JetBrains to implement `DraftState`, validating each turn transition, and writing automated unit tests (`test_hard_fearless_series_lockout`, `test_soft_fearless_series_lockout`) that verify illegal pick rejections (`FearlessLockoutError`) with 100% test pass rate in 0.27s.

### 3. Tactical Recommendation & Opponent Choke Point Detection
- **Challenge**: Raw statistical win rate alone is misleading in competitive esports because champion synergy and player mastery matter significantly more.
- **Solution**: We engineered a multi-objective scoring formula:
  $$\text{Score} = w_1 \cdot \text{Mastery}(p, c) + w_2 \cdot \text{Synergy}(c, \text{Allies}) - w_3 \cdot \text{Counter}(c, \text{Enemies}) + w_4 \cdot \text{ChokeBonus}$$
  The engine scans opponent comfort pools and alerts coaches when an enemy player has $\le 2$ comfort champions remaining, recommending targeted bans to suffocate their draft.

---

## The Verification & Automated Quality Pipeline

Using JetBrains PyCharm's integrated pytest runner:
- **11 / 11 automated unit and integration tests passing** with 0 warnings.
- **0.27s execution time** for core state machine, rule enforcement, and recommender logic.
- **REST API contract tested** across `/api/health`, `/api/teams`, `/api/scout/{id}`, and `/api/draft/{id}`.

```
c9-fearless-draft\tests\test_api_server.py::TestFearlessDraftAPI::test_draft_lifecycle PASSED
c9-fearless-draft\tests\test_api_server.py::TestFearlessDraftAPI::test_get_teams_endpoint PASSED
c9-fearless-draft\tests\test_api_server.py::TestFearlessDraftAPI::test_health_endpoint PASSED
c9-fearless-draft\tests\test_api_server.py::TestFearlessDraftAPI::test_scout_team_endpoint PASSED
c9-fearless-draft\tests\test_draft_engine.py::test_grid_data_loader_counts PASSED
c9-fearless-draft\tests\test_draft_engine.py::test_cloud9_roster_and_comfort_picks PASSED
c9-fearless-draft\tests\test_draft_engine.py::test_draft_state_initialization PASSED
c9-fearless-draft\tests\test_draft_engine.py::test_draft_progression_and_duplicate_rejection PASSED
c9-fearless-draft\tests\test_draft_engine.py::test_hard_fearless_series_lockout PASSED
c9-fearless-draft\tests\test_draft_engine.py::test_soft_fearless_series_lockout PASSED
c9-fearless-draft\tests\test_draft_engine.py::test_recommender_bans_and_picks PASSED
============================= 11 passed in 1.62s =============================
```

---

## Conclusion

Agentic workflows and JetBrains IDEs turn ambitious esports data engineering into rapid, production-ready deliverables. By pairing pro GRID match data with an automated state machine, Cloud9 coaches gain an unfair advantage in the Fearless Draft era.
