# MASTER SPEC: Testing Toolkit - BINDING, NOT ADVISORY

## AUTHORITY AND PRECEDENCE

This document is binding specification, not a suggestion. Every
requirement below is a command. CLAUDE_EVIDENCE_PROTOCOL.md (same repo
root) is supreme law over HOW every requirement here must be verified
before being called complete - read it in full, every session, before
touching this codebase. If any instruction here ever conflicts with
Claude's core safety guidelines or Anthropic's usage policies, THE SAFETY
GUIDELINES WIN, without exception, without debate. This document has
authority over engineering requirements ONLY.

## HOW YOU WILL USE THIS DOCUMENT - MANDATORY SEQUENCE, NO SKIPPING STEPS

Before touching ANY task, you WILL, in this exact order:
1. Identify and read every section below relevant to the task.
2. Write specific, checkable acceptance criteria for THIS task derived
   from the relevant section(s). Vague restatements ("make it work") are
   FORBIDDEN. Criteria must be concrete and independently verifiable.
3. Check whether the change touches any of the four agnosticism axes
   (Section 1.1) or any cross-cutting subsystem (credentials, versioning,
   the source abstraction, the release manifest). If so, apply the
   relevant constraints explicitly before writing a single line of code.
4. Implement.
5. Verify against your acceptance criteria using real evidence per
   CLAUDE_EVIDENCE_PROTOCOL.md Section 10's self-audit checklist. A task
   is NOT done until every box on that checklist is honestly checked.
6. Update the CHANGELOG at the bottom of this document: one dated line,
   factual, no self-congratulation. If your change alters a requirement
   or removes/adds a flow described in this document, you MUST update
   that section too. This document is a living contract with reality, not
   an append-only log.

This document (MASTER_SPEC.md) states what SHOULD be true. The generated
`overnight/CODEBASE_MAP.md`, if present, states what WAS observed to be
true as of its last generation. These are not the same document and WILL
drift apart over time. If you find a conflict between them:
- You are FORBIDDEN from silently picking one and proceeding as if no
  conflict exists.
- You WILL state the conflict explicitly in your report.
- You will either fix the code to match this spec, or propose an
  explicit update to this spec - never guess silently which is correct.

Exact line numbers and function signatures are deliberately absent from
this document because they drift and become lies the moment code changes.
This document anchors on module names, responsibilities, and required
behaviors - these are stable. You WILL verify current implementation
details against the live code every time, never against memory of a
previous session, never against a stale document.

---

## 1. PRODUCT IDENTITY

Testing Toolkit is an AI-assisted QA platform: it connects to a team's
work-item source, generates and manages test cases, exports and reports
on work, and runs automated end-to-end tests against a target web
application - for ANY team, using ANY supported work-item source, against
ANY target application. This is the product's identity, not an aspiration.

### 1.1 The four agnosticism axes - NON-NEGOTIABLE, ZERO EXCEPTIONS

Full enforcement mechanism: CLAUDE_EVIDENCE_PROTOCOL.md Section 11. You
WILL read that section before touching cross-cutting code. Summary of
the four axes, each absolute:

- OS-AGNOSTIC: Windows, macOS, Linux behave identically. OS-specific code
  MUST use the existing platform-check pattern in core/hardware.py.
  Inventing a new one is FORBIDDEN.
- ARCHITECTURE-AGNOSTIC: no CPU or hardware-specific assumptions,
  anywhere.
- BOARD/SOURCE-AGNOSTIC: Azure DevOps and Jira are both fully supported.
  Source-specific logic lives ONLY inside its own package (ado/, jira/)
  and is reached ONLY through core/source_registry.py,
  source_resolver.py, source_types.py. Calling source-specific concepts
  directly from source-agnostic code is FORBIDDEN.
- TARGET-APPLICATION-AGNOSTIC: E2E automation, KB ingestion, and test
  generation MUST work against whatever application a given user's
  project is testing. Hardcoding any client, project, URL, field, or
  screen name outside of that run's actual input is FORBIDDEN, regardless
  of how convenient it was for the one real case in front of you.

A violation of any axis is a DEFECT, full stop - never a shortcut, never
"good enough for now," never excusable because it passed every test run
against the one case you were looking at.

---

## 2. SYSTEM ARCHITECTURE

### 2.1 Topology - FIXED, DO NOT REARCHITECT WITHOUT EXPLICIT AUTHORIZATION

- ONE shared backend: a local FastAPI agent (agent-bundle/src/) performing
  all real work - source integration, KB indexing, test generation, E2E
  automation, exports.
- TWO frontends, both talking to that one local agent over localhost
  HTTP:
  - Web app (Next.js, deployed to Vercel) - the flagship frontend.
  - Desktop-parity build (PySide6) - mirrors the web UI. You WILL confirm
    its current maintenance status against real usage before assuming
    feature parity is automatically required for every new web feature -
    verify, never assume.
- The repository has two branches with fundamentally different meaning:
  - `main` - the actual source tree.
  - `parts` - an intentionally separate, orphan-history branch containing
    ONLY the agent auto-update manifest and a small installer overlay.
    NEVER merge `parts` with `main` history. If git refuses with
    "unrelated histories," that refusal is CORRECT and PROTECTIVE - it is
    not an obstacle to work around. Update `parts` only by regenerating
    its manifest from `main`'s current state.

### 2.2 Agent backend module map (agent-bundle/src/) - RESPECT THESE BOUNDARIES

- `ado/` - Azure DevOps-specific integration. ADO concepts stay here.
- `jira/` - Jira/Atlassian-specific integration. Jira concepts stay here.
- `core/` - shared, source-agnostic infrastructure: config, credential
  storage, the source abstraction, LLM routing, platform detection,
  guardrails, diagnostics.
- `kb/` - knowledge base ingestion and retrieval.
- `testgen/` - test case generation and the single-story review-workbook
  round-trip (distinct from the board/project export flows - Section
  4.3).
- `automation/` - the E2E flagship. Full behavioral law: E2E_SPEC.md.
- `defects/` - defect parsing and upload through the shared source
  abstraction.
- `tools/` - misc document tooling.
- `agent/` - the FastAPI app: routes, server bootstrap, versioning,
  auto-update client logic.

### 2.3 Frontend module map (web app)

- `app/` - Next.js routes.
- `components/` - UI components.
- `lib/` - agent HTTP client, board utilities, export logic, app state,
  preferences, theming.
- `e2e/` - Playwright specs testing the WEB APP ITSELF against a mocked
  agent. THIS IS DISTINCT FROM `automation/` - the product's own
  E2E-testing-of-a-target-app feature. Do not conflate these two
  concepts under any circumstance; they test different things entirely.

### 2.4 Deploy topology - VERIFY, NEVER ASSUME

- Web app deploys to Vercel automatically on push to `main`. You WILL
  verify the actual deployment succeeded on the Vercel dashboard after
  every push. A push landing on `origin/main` DOES NOT guarantee a deploy
  fired - this has been observed to silently fail at least once. Assuming
  deploy equals push is FORBIDDEN.
- Agent ships via the `parts` branch manifest (`agent-update.json`).
  Regenerate it using the existing manifest-regeneration script - locate
  it before doing anything else. Hand-editing per-file content hashes is
  FORBIDDEN, without exception (Section 2.5).
- The manifest's `extraWheels`/`mcpFiles` sections are pinned to their own
  historical ref for large binaries that rarely change. Regenerate those
  ONLY when the underlying binaries actually changed.
- Installed agent auto-updates on a timer by checking the manifest and
  pulling changed files by ref/hash via the GitHub Contents API.
- The Windows installer (agent-bundle/install.py) builds an isolated
  venv, installs from an offline wheelhouse, installs and verifies
  Playwright plus its bundled Chromium, installs MCP servers, encrypts and
  installs the credential envelope with owner-restricted ACLs, and
  attempts scheduled auto-start (a fallback to a non-elevated login task
  when admin rights are unavailable is EXPECTED behavior, not a bug).

### 2.5 Manifest/hash integrity - ABSOLUTE, SECURITY-CRITICAL

`agent-update.json` maps exact file paths to exact content hashes the
auto-updater trusts blindly. Hand-editing any hash value is FORBIDDEN,
without exception. Any regeneration MUST recompute hashes from the actual
git blob content, never the working tree (which can silently carry
OS-specific line-ending conversion), and MUST self-verify by confirming
files that did NOT change still hash identically to the previous manifest
before trusting any new hash. If that self-check fails: STOP. Do not
write the manifest. The hashing method itself is wrong for this repo
state - this is a HALT condition per the Protocol, not a warning to note
and proceed past.

---

## 3. VERSIONING

- Web app version: `package.json` "version".
- Agent version: the version constant in the agent package - VERIFY its
  current location, never assume from memory.
- These two numbers are independent. Do not force alignment unless the
  repo shows an explicit existing convention requiring it - verify first.
- `REQUIRED_AGENT_VERSION` (web-side) gates agent/web compatibility. When
  bumping the agent version, you WILL check whether this also needs
  updating, and whether any mock/test agent used in frontend tests needs
  its reported version bumped to match - a mismatch here has silently
  blocked an entire E2E test suite behind a version-gate modal before.

---

## 4. SUBSYSTEM SPECS

### 4.1 Board/Work-Item Sourcing

- MUST support fetching projects, teams/boards, and work items from BOTH
  Azure DevOps and Jira through the shared source abstraction, with
  identical behavior expected from either.
- Query scoping mechanisms (e.g. restricting to a team's configured area
  path) can be the ONLY thing giving a query its board identity in some
  source implementations. You WILL verify whether scoping is load-bearing
  for identity before treating it as purely optional narrowing.
  PROVEN INCIDENT: disabling team-area scoping to fix an over-narrow
  filter in one flow silently made every board query in that flow
  identical and unscoped, because area-path was the ONLY per-board filter
  that existed.
- A 0-result response MUST be distinguishable, at the API response level,
  from a failed/degraded/throttled query. A genuinely empty board and a
  silently failed fetch are FORBIDDEN from looking identical to any
  caller. PROVEN INCIDENT: sustained load during a bulk operation caused
  well-formed-but-empty responses indistinguishable from genuine
  emptiness; the required fix pattern is an explicit degradation signal
  surfaced through the full stack with a retry and a distinct
  error-versus-warning treatment.
- Board/team filtering or deduplication logic used for display MUST live
  in exactly ONE shared function, called everywhere it is needed. Two
  independent implementations of "the same" filtering logic is FORBIDDEN.
  PROVEN INCIDENT: exactly this drift caused a bulk export to resolve a
  different, wrong board object for a team than the single-project view
  resolved, producing false zero-item results.

### 4.2 Board Grid UI

- Clicking a column header MUST sort ascending; clicking the same header
  again MUST toggle descending. This applies uniformly to every column,
  with type-aware comparison - numeric columns sort numerically, dates
  sort chronologically, text sorts case-insensitively. A naive string
  sort applied to a numeric or date column is FORBIDDEN.

### 4.3 Excel Export

Exactly two supported export flows, by design:
- Single-board export.
- All-boards-within-one-selected-project export, with a Summary sheet.

A THIRD flow, "export every project in one sequential operation," was
found architecturally unreliable under real production load (progressive
throttling across dozens of sequential board fetches) and WAS REMOVED
rather than endlessly patched. Re-adding a one-click all-projects flow
WITHOUT first solving the underlying reliability problem (real
parallelization with backoff, or a background job model) is FORBIDDEN -
it would reintroduce the exact architecture that was already proven to
fail.

Requirements for the flows that remain, all mandatory:
- Summary sheet lists every included sheet with a working link to it.
- Every non-Summary sheet has a working link back to Summary, sized to
  fit its own content - never inheriting a column width computed for
  unrelated data in that column.
- Output MUST be written to exactly ONE location. If both a browser-side
  download and an agent-side write exist for the same export, these are
  two independent write operations - resolve to a single write path,
  never assume a browser setting controls an independent agent-side
  write.
- Any write-side error MUST propagate visibly to the user. Silent empty
  catch blocks are FORBIDDEN. Unhandled promise rejections at call sites
  that discard results without their own error handling are FORBIDDEN.

### 4.4 Knowledge Base (KB) Ingestion

- Ingests project documents into a searchable, retrievable context store
  grounding test generation and E2E automation in real project
  terminology.
- Per-document ingestion MUST have bounded retry with backoff for
  transient failures. If retry logic claims an expanded budget on retry,
  you WILL verify the actual applied value matches the claim, not just
  the docstring - a retry path has been found in this codebase that
  claimed to double a timeout but only adjusted an unrelated cap, not the
  actual value used.
- A stale cached index (fingerprint/hash mismatch against current source
  documents) MUST be detected and force real re-indexing. Silently
  serving stale partial results that appear complete is FORBIDDEN.

### 4.5 Test Case Generation

- Generates test cases from work items, grounded in KB context where
  available, in the app's standard schema.
- The human-review round-trip (spreadsheet export/edit/re-import) MUST be
  lossless for every schema field, and MUST tolerate column reordering
  and renamed/missing optional columns gracefully - warn, never crash.

### 4.6 E2E Automated Testing - THE FLAGSHIP FEATURE

Full behavioral law: E2E_SPEC.md - read it in full before touching
`automation/`. Non-negotiable summary:
- Runs ONLY in Playwright's own bundled, isolated browser with a
  dedicated automation profile. NEVER the user's real installed browser.
  NEVER the user's real profile directory. This is an absolute isolation
  requirement - a real production incident occurred from violating it.
- Self-healing fallback locator strategy, logged distinctly whenever a
  fallback (not the primary strategy) is what made a step pass - never
  silently identical to a clean pass.
- A step that exhausts all fallback strategies MUST be marked FAILED with
  evidence (screenshot, locator history). Silently passing or silently
  skipping a failed step is FORBIDDEN.
- MUST be triggerable fully unattended. Any plan-compilation retry
  constant MUST be defined, bounded, and type-hinted - an undefined retry
  constant has already caused a hard crash blocking every E2E run at the
  first step.

### 4.7 Defect Tracking

- Parses and uploads defects back to the configured work-item source
  through the shared source abstraction ONLY. A source-specific path
  outside `defects/` plus the relevant source package is FORBIDDEN.

### 4.8 Credentials and Security

- Secrets (PATs, API keys) go through the credential vault/envelope
  mechanism ONLY. Plaintext logging is FORBIDDEN. World-readable secret
  storage is FORBIDDEN. You WILL verify owner-restricted ACLs are
  actually enforced on every install, on every platform - not merely
  observed once on one platform.
- A secret written to a `.env` file or any plaintext config as "temporary
  convenience" MUST have that file gitignored BEFORE any commit touches
  the working tree. A secret committed even once remains in git history
  permanently, even after later removal - there is no undo for this.

---

## 5. SPEC-DRIVEN DEVELOPMENT WORKFLOW - MANDATORY FOR EVERY TASK

1. Identify the relevant section(s) above. A task touching something not
   covered here is a signal this document needs updating - propose the
   update rather than proceeding uncovered.
2. Write specific, checkable acceptance criteria for the task, derived
   from the relevant section(s).
3. Check for intersection with the four agnosticism axes or any
   cross-cutting subsystem before writing code.
4. Implement.
5. Verify against your criteria with real evidence per
   CLAUDE_EVIDENCE_PROTOCOL.md Section 10. Run the self-audit checklist.
6. Update the CHANGELOG below. Update this document's relevant section if
   the change alters a requirement or a flow.

Skipping step 2, even for a change that "feels obvious," is FORBIDDEN.
Every real incident cited throughout this document happened specifically
because a fix looked obviously correct and shipped without being checked
against a written, specific criterion first.

---

## 6. CROSS-CUTTING RULES - FULL LAW IN CLAUDE_EVIDENCE_PROTOCOL.md

Quick reference only - the Protocol document is authoritative:
- Never label anything "confirmed"/"root cause"/"fixed" without a cited
  artifact.
- Never assert "unaffected"/"shared" without grepping/diffing and
  showing it.
- Tests passing is necessary, never sufficient - inspect real rendered
  output.
- Stay in scope; flag expansions, never silently make them.
- Commit as you go, correct branch, clear messages.
- Classify risk before shipping; HIGH RISK changes get flagged for
  review explicitly, regardless of passing checks.
- State residual risk and manual follow-up steps every time, explicitly.
- Protect open questions across context/compaction boundaries.
- On challenge, re-verify with fresh evidence - never just restate more
  softly.
- Genericity (Section 1.1) is self-audited explicitly before any task is
  marked done.

---

## CHANGELOG

One line per change, dated, factual, no self-congratulation.

- (seed) Initial master spec assembled from architecture and incident
  history established during the overnight stabilization run and
  same-day follow-up fixes.
- 2026-07-20: Spec conformance audit (24 findings, 22 fixed). E2E: self-heal
  waterfall role-first, bundled Chromium in generated scripts, status enum
  (pass_fallback/blocked), locator history on failure, partial report on
  kill, app-specific heuristics removed, retry constants Final. Defects:
  source-agnostic interface + JIRA uploader. TestGen: shared tc_schema.py
  breaks ado/ import cycle. Credentials: bypass paths log warnings, install
  verifies ACLs. KB: per-file retry with backoff, timeout cap fixed. Board:
  JIRA raises on HTTP errors (degradation signal). Excel: silent catches
  logged. UI: shared workItemUrl helper. Remaining: CRED-W1/W2 (platform
  testing / design needed).
