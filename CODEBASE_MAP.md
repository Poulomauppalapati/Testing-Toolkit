# Testing-Toolkit Codebase Map v3.60.0

Generated: 2026-07-22 | Audit commit: 638ba62 | 283 source files | ~75,000 lines

---

## Architecture Overview

```
Browser (Next.js 16 / React 19 / Tailwind v4)
    |
    | HTTP (localhost:3000 -> localhost:7842)
    v
FastAPI Agent Server (Python 3.12, uvicorn + TLS)
    |
    +-- /e2e     -> Agentic E2E Runner (observe->decide->act loop)
    +-- /kb      -> Knowledge Base (vector store + embeddings)
    +-- /boards  -> ADO/JIRA Work Item Boards
    +-- /generate -> Test Case Generation (LLM-powered)
    +-- /sources -> Credential & Source Management
    +-- /settings -> Runtime Configuration
    +-- /health  -> Health Check & Version
    +-- /installer -> Self-Update Mechanism
```

---

## Module Map

### Python Backend (`agent-bundle/src/`)

| Module | Files | Lines | Role | Health |
|--------|-------|-------|------|--------|
| `agent/` | 21 | ~4,700 | HTTP server, route handlers, job orchestration | Hotspot |
| `automation/` | 20 | ~8,500 | Agentic E2E runner + legacy compile-execute (dead) | Critical |
| `core/` | 27 | ~5,800 | Config, encryption, LLM clients, MCP bridge | Fragile |
| `kb/` | 18 | ~6,900 | Knowledge base: ingest, embed, search, bundle | OOM-prone |
| `ado/` | 6 | ~3,100 | Azure DevOps integration (boards, test cases) | Hotspot |
| `jira/` | 4 | ~1,200 | JIRA integration (boards, Xray) | Duplicates ADO |
| `testgen/` | 8 | ~3,200 | LLM test case generation | Stable |
| `defects/` | 4 | ~800 | Defect upload to ADO/JIRA | Circular dep |
| `tools/` | 4 | ~1,200 | PDF combine, packaging utilities | Low risk |
| `scripts/` | 3 | ~400 | Maintenance scripts | Low risk |
| `install.py` | 1 | 2,407 | Self-contained installer/updater | Hotspot |

### TypeScript Frontend

| Module | Files | Lines | Role | Health |
|--------|-------|-------|------|--------|
| `lib/` | 18 | ~6,400 | API client, state, utilities | Hotspot |
| `components/` | 34 | ~10,500 | UI components, dialogs, board | XSS risk |
| `app/` | 7 | ~1,500 | Next.js pages, API routes, layout | Proxy risk |

### Tests

| Module | Files | Lines | Coverage |
|--------|-------|-------|----------|
| `tests/` (Python) | 46 | ~10,500 | Moderate (many mocks) |
| `__tests__/` (TS) | 15 | ~2,400 | Low (22 tests total) |

---

## Entry Points

| Entry | Path | Purpose |
|-------|------|---------|
| Agent Server | `agent/server.py` | FastAPI app with TLS, 7842 |
| Agent CLI | `agent/__main__.py` | Direct python -m invocation |
| Installer | `install.py` | Self-contained agent installer |
| Web App | `app/page.tsx` | Next.js main page |
| Web Layout | `app/layout.tsx` | Root layout + providers |
| LLM Proxy | `app/api/llm/route.ts` | Proxy to avoid CORS |
| Installer API | `app/api/installer/route.ts` | Agent install trigger |

---

## Data Flow: Agentic E2E (v3.60.0 Architecture)

```
User clicks "Start E2E" in browser
    |
    v
POST /e2e/start {wi_ids, config}
    |
    v
e2e.py route handler
    |-- Creates job, launches background task
    |-- Resolves test cases from ADO work items
    |-- Builds KB briefings per test case
    |
    v
agentic_runner.run_agentic_suite()
    |
    v
For each test case:
    |
    +---> build_system_prompt() [agentic_prompt.py]
    |         |-- Role definition
    |         |-- Credentials ({{username}}/{{password}} placeholders)
    |         |-- Test case steps
    |         |-- KB briefing
    |
    +---> LOOP (max 500 steps):
    |     |
    |     +---> get_accessibility_tree(page) [page_observer]
    |     |
    |     +---> LLM call (Claude) with tools
    |     |         |-- 35 tools defined in agentic_tools.py
    |     |         |-- Self-healing locator factory
    |     |
    |     +---> AgenticToolExecutor.execute(tool_name, input)
    |     |         |-- Credential substitution happens HERE
    |     |         |-- Returns observation + StepResult
    |     |
    |     +---> History compression (8-turn window)
    |     |
    |     +---> Check: declare_done? declare_stuck? max_steps?
    |
    +---> If stuck: retry with fallback model (Opus)
    |
    v
TestCaseResult collected, streamed via SSE to browser
```

---

## Security Architecture

| Layer | Mechanism |
|-------|-----------|
| Credential Storage | AES-256-GCM encrypted `.env.enc` envelope |
| Key Derivation | DPAPI (Windows) / OS keyring binding |
| Credential Injection | Tool executor substitutes at execution time |
| LLM Redaction | Credentials never in LLM context (placeholders only) |
| Network | TLS on agent server (self-signed + trust) |
| Web Auth | Proxy token for LLM route (when configured) |

**Known gaps:** No auth on agent API (localhost-only assumption), CORS too broad, no CSP header, XOR fallback when AES unavailable.

---

## Dependency Graph Summary

- **209 nodes**, **627 edges**, **1 cycle** (defects/jira_uploader <-> defects/uploader)
- **44 unreachable files** (13 non-trivial production modules)
- **Key dead modules:** parallel_runner, bug_tracker, dashboard_report, prefs_store, protocols, source_registry, diff_engine
- Full graph: `DEPENDENCY_GRAPH.json`

---

## Deployment Chain

```
version.py (AGENT_VERSION) --push--> parts branch (agent-update.json)
                                         |
                                         +--> ref = commit SHA
                                         +--> hash = sha256 of version.py
                                         |
lib/agent-version.ts (REQUIRED_AGENT_VERSION) <-- LAST to update
                                         |
                                         v
                                    Vercel deploys
```

**Invariant:** Parts branch must be pushed BEFORE REQUIRED_AGENT_VERSION is set. Violating this bricks the app with "update required" loop.

---

## Known Technical Debt

1. **Legacy E2E modules still on disk** — e2e_plan.py, script_generator.py, e2e_runner.py (compile-then-execute path) superseded by agentic_runner but not removed
2. **ADO/JIRA duplication** — 80+ lines of shared board logic duplicated between modules
3. **No .env.example** — 29+ env vars consumed with zero documentation
4. **Triple retry implementation** — core/http_retry exists but ado/boards and ado/extract roll their own
5. **All docs reference v3.44.0 or earlier** — CODEBASE.md, E2E_SPEC.md, E2E_RUNNER_V3.40.md severely stale
6. **No rate limiting** — all endpoints exposed without throttling
7. **Continuous LLM loop** — no locator caching, no deterministic replay mode for CI

---

## Audit Coverage

| Phase | Scope | Findings |
|-------|-------|----------|
| Dependency Graph | 209 nodes, full import analysis | 44 unreachable files |
| Module Audit (10 WPs) | All 283 source files | 130 findings |
| Cross-cutting | Contracts + duplication | 27 findings |
| Documentation | 7 spec/doc files | 15 findings |
| **Total (deduplicated)** | | **146 unique findings** |

Severity breakdown: 25 Critical, 57 High, 55 Medium, 23 Low, 12 Cosmetic
