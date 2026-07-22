# Testing-Toolkit v3.60.0 Exhaustive Codebase Audit Report

**Date:** 2026-07-22
**Scope:** 283 source files, ~75,000 lines (Python + TypeScript)
**Method:** 11 work packages (module audit) + cross-cutting analysis + documentation review
**Auditor:** Automated multi-agent sweep with manual synthesis

---

## Executive Summary

The Testing-Toolkit codebase has **25 critical** and **57 high-severity** findings across security, correctness, and architecture. The most urgent clusters are:

1. **Security vulnerabilities (11 critical):** SSRF with PAT exfiltration, path traversals, XSS via dangerouslySetInnerHTML, open LLM proxy, zip traversal in installer
2. **Agentic E2E defects (4 critical):** Credential substitution missing, multi-tool crash, dialog freeze, None page yield
3. **Memory safety (4 critical):** OOM in PDF processing, KB bundle building, N+1 fetches, and RAM accumulation
4. **Documentation decay:** All specs reference v3.44.0 or earlier; E2E_SPEC.md mandates a dead architecture

---

## Findings by Severity

| Severity | Count | Action Required |
|----------|-------|-----------------|
| Critical | 25 | Must fix before production use |
| High | 57 | Should fix before panel review |
| Medium | 55 | Fix or document as accepted risk |
| Low | 23 | Backlog (cosmetic/minor) |
| Cosmetic | 12 | Optional cleanup |
| **Total** | **146** | |

---

## Findings by Category

| Category | Count | Worst Severity |
|----------|-------|----------------|
| Vulnerability | 28 | Critical |
| Defect | 52 | Critical |
| Dead Code | 13 | Medium |
| Contract Mismatch | 14 | Critical |
| Documentation Stale | 15 | High |
| Architecture | 7 | High |
| Structural Duplication | 5 | High |
| Config Drift | 4 | Medium |
| Cosmetic | 12 | Cosmetic |

---

## Critical Findings Summary

### Security (must-fix)

| ID | File | Issue |
|----|------|-------|
| AUDIT-001 | sources.py | SSRF: azure.com allowlist bypassable, PAT sent to attacker |
| AUDIT-002 | boards.py | Path traversal in push-xlsx (../../ in filename) |
| AUDIT-003/4 | DetailPane.tsx | XSS via dangerouslySetInnerHTML (comments + descriptions) |
| AUDIT-009 | encryption.py | XOR fallback = trivially reversible encryption |
| AUDIT-011 | legacy_docs.py | XXE in XML parsing (2 instances) |
| AUDIT-014/15 | llm/route.ts | Open relay + SSRF when PROXY_TOKEN unset |
| AUDIT-019 | boards.py | Authenticated SSRF via blob fetch (PAT to internal) |
| AUDIT-021/22 | install.py | Zip traversal + VBScript injection |
| AUDIT-023/24 | agent-client.ts | Unsafe cast + XSS trust chain |

### Correctness (must-fix)

| ID | File | Issue |
|----|------|-------|
| AUDIT-005 | agentic_tools.py | {{username}}/{{password}} substitution MISSING |
| AUDIT-006 | agentic_tools.py | multi_tool_use content block crashes executor |
| AUDIT-007 | agentic_tools.py | browser_session yields None page |
| AUDIT-008 | agentic_tools.py | Dialog auto-dismiss freezes page |
| AUDIT-010 | ssl_config.py | Thread-unsafe SSL context mutation |
| AUDIT-012/13 | kb/ | OOM on large PDFs and bundle builds |
| AUDIT-016/17/18 | automation/ | Legacy path crashes (script_generator, video, status) |
| AUDIT-020 | boards.py | Unbounded N+1 (500K HTTP calls possible) |
| AUDIT-025 | settings.py | TS/Python contract mismatch on tls_mode |

---

## Module Health Summary

| Module | Critical | High | Assessment |
|--------|----------|------|------------|
| Core Infrastructure | 2 | 8 | Fragile (thread safety, encryption) |
| Agent Server & Routes | 2 | 6 | Exposed (no auth, CORS, path traversal) |
| Agentic E2E | 4 | 6 | Unstable (just deployed, multiple crashes) |
| Legacy Automation | 3 | 6 | Dead (superseded, crashes if invoked) |
| Knowledge Base | 4 | 4 | OOM-prone (no streaming, no page limits) |
| TestGen + ADO/JIRA | 2 | 6 | N+1 bombs, path traversal |
| Installer | 2 | 5 | Path traversal, no integrity checks |
| Frontend Lib | 2 | 5 | Type safety gaps, memory leaks |
| Frontend Components | 2 | 5 | XSS, race conditions |
| Frontend App + API | 2 | 6 | Open relay, no CSP |

---

## Dependency Graph Highlights

- **209 nodes**, 627 edges, 1 cycle
- **44 unreachable files** (13 non-trivial production modules)
- Cycle: `defects/jira_uploader.py` <-> `defects/uploader.py` (safe due to deferred import)
- Key dead modules: parallel_runner, bug_tracker, dashboard_report, diff_engine, protocols, source_registry, prefs_store

---

## API Contract Mismatches (TS <-> Python)

| Severity | Issue | Impact |
|----------|-------|--------|
| Critical | SettingsResponse missing tls_mode | Frontend shows undefined |
| High | DefectModel drops images field | Uploaded defects lose screenshots |
| High | /sources/verify response too narrow in TS | Hides source diagnostics |
| High | TagRequest.wi_id str vs int | Potential 422 on tag operations |
| Medium | E2E result missing on partial stop | Undefined access crash |
| Medium | E2E wi_ids str vs generate wi_ids int | Type confusion |

---

## Documentation Status

| Document | Status | Key Issues |
|----------|--------|------------|
| CODEBASE.md | Severely stale | Says v3.44.0, wrong REQUIRED_AGENT_VERSION, dead architecture |
| E2E_SPEC.md | Stale | Mandates dead compile-then-execute path |
| E2E_RUNNER_V3.40.md | Stale | References non-existent qa_agent.py |
| E2E_V340_PROGRESS.md | Stale | Lists 3.40.0 bump as pending |
| DEPLOYMENT.md | Incomplete | Missing agentic_runner verification |
| RUN_LOG.md | Adequate | No version tag |
| CODEBASE_MAP.md | **NEW** | Accurate v3.60.0 reference (this audit) |

---

## Structural Duplication

| Pattern | Impact | Recommendation |
|---------|--------|----------------|
| Triple retry implementation | Behavioral drift between copies | Consolidate to core/http_retry |
| ADO/JIRA boards parallel structure | Bug fixes not propagated | Extract BoardProvider protocol |
| _safe_name() duplicated 3x | Unicode edge cases missed | Single core/utils.safe_filename() |
| 12 dialog components identical boilerplate | Pattern changes require 12 edits | useDialog hook or DialogWrapper |
| Model names hardcoded in 3 files | Model change requires find/replace | Central MODEL_REGISTRY |

---

## Residual Risks & Assumptions

1. **Confidence levels:** 139 findings are "confirmed" (code-path traced), 7 are "plausible" (requires runtime verification)
2. **Test coverage not measured:** No coverage tool run; test suite quality audit (WP11) deferred
3. **Runtime behavior untested:** Audit is static; concurrency issues and OOM findings need load testing to confirm thresholds
4. **Credential substitution (AUDIT-005):** Marked critical based on code reading; the actual tool executor may handle this in a code path not visible in the audited snapshot
5. **XSS (AUDIT-003/4):** Confirmed dangerouslySetInnerHTML exists; actual exploitability depends on whether ADO/JIRA sanitize their output before our app receives it (defense-in-depth says don't rely on this)
6. **Dead code modules:** Some "unreachable" modules may be invoked via dynamic imports or CLI scripts not captured in the static import graph

---

## Recommended Priority Order

**Immediate (before any demo/review):**
1. Fix credential substitution in agentic_tools.py (AUDIT-005)
2. Sanitize dangerouslySetInnerHTML inputs (AUDIT-003/4)
3. Add URL validation to SSRF-prone endpoints (AUDIT-001, 019)
4. Guard LLM proxy with mandatory token (AUDIT-014)
5. Fix multi_tool_use crash (AUDIT-006)

**Short-term (before production):**
6. Add path traversal guards to all file-write endpoints
7. Replace XOR encryption fallback with proper error
8. Add page-limit to PDF processing
9. Implement N+1 fetch caps
10. Update all documentation to v3.60.0

**Medium-term (technical debt):**
11. Remove dead legacy modules
12. Consolidate retry implementations
13. Add rate limiting
14. Implement locator caching for cost reduction
15. Add CSP and tighten CORS

---

## Deliverables

| Artifact | Path | Description |
|----------|------|-------------|
| Issue Ledger | `ISSUE_LEDGER.json` | 146 findings, severity-ranked, deduplicated |
| Dependency Graph | `DEPENDENCY_GRAPH.json` | 209 nodes, 627 edges, cycles, unreachable |
| Codebase Map | `CODEBASE_MAP.md` | Accurate v3.60.0 architecture reference |
| This Report | `AUDIT_REPORT.md` | Summary, analysis, recommendations |

---

## What Was NOT Checked

- Runtime performance profiling (only static analysis)
- Actual test execution (suite was not run)
- WP11 test suite quality (coverage gaps, vacuous assertions) -- deferred
- Third-party dependency CVE scan (beyond surface review)
- Accessibility compliance of frontend components
- Phase 6 competitive landscape assessment (deferred per user request)

---

*This audit surfaces residual risk honestly. 25 critical findings require immediate attention before any panel review or production deployment. The agentic E2E architecture (v3.60.0) is architecturally sound but has implementation gaps that will cause runtime failures in its current state.*
