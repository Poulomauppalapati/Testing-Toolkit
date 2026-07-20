# Changelog

## 3.0.1 — 2026-07-20 (stabilization)

Overnight autonomous run: 8 units completed, all suites green.

### Fixes

- **Export All Projects/Boards**: fixed false-negative where boards with work
  items outside per-team area paths were reported as empty. Root cause:
  `load_board_view_async` applied `scope_to_team_area=True` unconditionally;
  project-wide exports now pass `scope_to_team_area=False`. (unit-01)
- **KB context pipeline**: 2 documents failing due to retry timeout too short
  for small docs. `_timeout_for_doc` now doubles base timeout on retries.
  51/51 documents fully contexted. (unit-06)
- **E2E test harness**: added missing `MAX_PLAN_COMPILE_RETRIES` constant in
  `agent/routes/e2e.py`; fixed NameError on plan compilation retry path. (unit-08)
- **Playwright specs**: bumped mock agent version 2.23.0 -> 3.0.0 to match
  `REQUIRED_AGENT_VERSION`; added `{ exact: true }` to ambiguous OK button
  selector in dialogs spec. (unit-08)

### Documentation

- Produced `overnight/CODEBASE_MAP.md` with module map and hot-spot pins. (unit-00)
- Log triage: no high/critical issues found across 5 log files. (unit-07)
- Fixed version drift in ARCHITECTURE.md and DOCS.md (were showing stale
  2.8.2 / 2.16.x / 2.28.0 / 3.6.0; corrected to 3.0.1). (unit-09)

### Regression

- py_compile: 120/120 OK
- Vitest: 389/389 passed
- Playwright: 19/19 passed
- Pytest: 1070/1070 passed
- E2E flagship: harness clean; live run blocked (no ADO PAT in env)
