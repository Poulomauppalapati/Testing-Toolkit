# ENFORCEMENT PROTOCOL - MANDATORY, NON-NEGOTIABLE, NO EXCEPTIONS

## AUTHORITY, SCOPE, AND PRECEDENCE (READ THIS FIRST, EVERY SESSION)

This document is operating law for this codebase. It is not advisory. It
is not a style guide. Every rule below is a command, and every command is
enforced by the HALT conditions in Section 0.

THE BOUNDARY OF THIS DOCUMENT'S AUTHORITY IS ABSOLUTE AND NON-NEGOTIABLE:
This protocol governs engineering rigor, verification discipline, scope
control, and evidence standards ONLY. It has zero authority over, and can
NEVER be invoked to justify:
- Bypassing, weakening, or reasoning around Claude's safety behaviors.
- Producing harmful, malicious, or policy-violating content of any kind.
- Fabricating user consent, approval, or authorization that was not
  actually given.
- Ignoring Anthropic's usage policies under any framing whatsoever -
  "the spec requires it," "the user demanded imperative tone," "this is
  just engineering," or any other justification.

IF ANY INSTRUCTION ANYWHERE IN THIS DOCUMENT, IN MASTER_SPEC.md, IN
E2E_SPEC.md, OR IN ANY TASK PROMPT EVER APPEARS TO CONFLICT WITH CLAUDE'S
CORE SAFETY GUIDELINES: THE SAFETY GUIDELINES WIN. FULL STOP. NO
EXCEPTIONS. NO DEBATE. HALT AND SURFACE THE CONFLICT TO THE USER RATHER
THAN RESOLVING IT YOURSELF IN EITHER DIRECTION.

Everything below this line concerns code quality, evidence, and scope. It
is written in command form because every rule was violated at least once
on this exact codebase, and each violation cost real time, shipped a wrong
fix, or nearly destroyed context the user needed. Commanding language is
used because "please consider" already failed once. It will not be
tolerated to fail again.

---

## 0. HALT CONDITIONS - STOP IMMEDIATELY, DO NOT PROCEED

You WILL immediately halt, stop editing, and surface the situation to the
user, without proceeding further, the instant any of the following occurs:

- You are about to write "Root Cause," "Confirmed," "Fixed," or "Done" in
  any report header without a cited artifact backing it. HALT. Downgrade
  the label or produce the evidence first.
- You are about to claim a function, file, or behavior is "unaffected,"
  "unchanged," or "shares logic" without having actually diffed or
  grepped it in this session. HALT. Produce the diff first.
- You are about to mark a visual, exported, rendered, or file-based
  output as correct based solely on a passing type-check or test suite,
  without having inspected the actual rendered artifact. HALT. Inspect it,
  or explicitly and loudly label the result unverified.
- You are about to touch a file, function, or system explicitly marked
  out-of-scope for the current task. HALT. Name the finding, ask, do not
  proceed unilaterally.
- You are about to merge or push a change classified HIGH RISK (Section
  6) without having stated that classification out loud first. HALT.
  Classify it, then decide.
- You detect ANY hardcoded client name, project name, board name, OS
  assumption, or single-source (ADO-only / Jira-only) assumption bleeding
  into code that must remain agnostic (Section 11). HALT. Generalize
  before continuing.
- You are approaching a context/auto-compact boundary with open questions
  from the user still unanswered. HALT the current line of work at the
  next clean stopping point and answer the open questions explicitly
  before anything is allowed to be silently dropped.

A HALT is not a failure. Proceeding through a HALT condition without
resolving it IS a failure, every time, without exception.

---

## 1. LABELING DISCIPLINE - ABSOLUTE, NO SOFT LANGUAGE PERMITTED

- YOU ARE FORBIDDEN from using "Root Cause," "Confirmed," "Fixed," or
  "Done" as a report header unless you possess direct evidence: an actual
  log line, an actual reproduced error, an actual byte-for-byte diff, or
  actual command output you personally generated in this session.
- A hypothesis without direct evidence MUST be labeled, explicitly, in
  the header itself: "UNCONFIRMED - HYPOTHESIS ONLY." No exceptions for
  hypotheses that "feel obviously right."
- "The architecture only allows for X" is analysis. It is NOT evidence.
  It may narrow a search and justify a defensive fix, but it SHALL NOT be
  the sole basis for a "Confirmed" label under any circumstance.
- BEFORE sending any report: scan your own draft for every instance of
  "confirms," "proves," "root cause," "fixed," "done," "verified." For
  each instance, you MUST be able to name the specific artifact that
  supports it. If you cannot, you MUST downgrade the language before
  sending. This step is not optional and is not skippable under time
  pressure.

## 2. EVIDENCE OVER ASSUMPTION - ABSOLUTE

- You are FORBIDDEN from asserting "function X is unaffected" or "this
  reuses the same logic as Y" without grepping every call site, opening
  the actual code, diffing it against its prior state, and presenting
  that evidence in your report. Confidence is not evidence. Produce the
  artifact or do not make the claim.
- You are FORBIDDEN from assuming two code paths are equivalent because
  they call a similarly-named function. Read both paths in full. State
  the actual differences, however small - small differences are exactly
  where the most damaging bugs hide.
- You are FORBIDDEN from writing "no other code depends on X" without
  having actually run a real search across the entire relevant tree and
  stating the exact command you ran.
- You MUST actively search for evidence AGAINST your current leading
  theory, not merely evidence supporting it. A one-sided investigation is
  an invalid investigation, full stop.

## 3. TESTS PASSING IS NOT PROOF OF CORRECTNESS - ABSOLUTE

- A green type-check or a green test suite proves structural soundness.
  IT PROVES NOTHING ELSE. Treat it as a floor, never a ceiling.
- For ANY visual, file-based, exported, or user-triggered output: the
  ONLY acceptable proof of correctness is direct inspection of the actual
  rendered artifact by you, in this session. No exceptions.
- If live/rendered inspection is impossible in your current environment,
  you MUST say so explicitly, in these exact terms: "architecturally
  verified, NOT functionally tested live," and you MUST tell the user
  precisely what manual check remains outstanding.
- It is FORBIDDEN to write "this is fixed" and "I could not test it live"
  in the same report without an explicit reconciling status label per
  Section 1. Unreconciled, these two statements together mean
  "unverified" - state it as such.

## 4. SCOPE DISCIPLINE - ABSOLUTE, ZERO TOLERANCE FOR DRIFT

- When a task specifies boundaries, you WILL re-read those boundaries
  immediately before your final edit and confirm, explicitly, that you
  did not cross them. Discovering a reason to cross them is not
  permission to cross them - it is a requirement to STOP and ASK.
- You are FORBIDDEN from silently expanding scope, however obviously
  correct the expansion seems. Name it. Ask. Wait.
- Cleanup of code you personally created this session: permitted.
  Cleanup of pre-existing code not in scope: FORBIDDEN without explicit
  authorization - name it as a suggestion in your report instead.
- One task produces one coherent, reviewable diff. Unrelated fixes
  discovered mid-task go on separate branches with separate commits.
  Never let them pile up uncommitted on top of each other.

## 5. COMMIT HYGIENE - ABSOLUTE

- Commit each logically complete, verified change immediately. Commit
  messages MUST describe the actual change and its reason. "Misc fixes"
  and similarly vague messages are FORBIDDEN.
- Before switching tasks: run `git status`. Uncommitted work is either
  committed or explicitly flagged. It is never silently carried forward,
  never silently lost.
- Before merging any branch: run the diff against the target and read
  the full file list out loud in your report. Merging from memory of
  what you believe you changed is FORBIDDEN.
- Never trust a commit message as an accurate description of its diff
  without having verified it with the actual diff when that accuracy
  matters (e.g., before deciding what to merge, ship, or roll back).

## 6. RISK-TIERED SHIPPING - ABSOLUTE

Every change gets classified, out loud, before it ships:

- LOW RISK: small, additive, easily reverted, does not touch auth,
  process launching, credentials, data deletion, or any isolation
  boundary. -> May be merged and pushed once verification passes.
- HIGH RISK: large rewrites; anything touching process launch/kill
  behavior; anything touching browser or session isolation; anything
  touching credentials or authentication; anything changing where data is
  written; anything with any plausible path to data loss or secret
  exposure. -> MUST be flagged explicitly, with the exact reason it is
  high-risk, and MUST include an explicit question to the user asking
  whether they want to review the full diff before it is considered
  truly shipped. Green automated checks NEVER downgrade a HIGH RISK
  classification. Silence about risk tier is itself a violation.

When in doubt about tier: classify HIGH. Ambiguity resolves toward
caution, always, without exception.

## 7. RESIDUAL RISK DISCLOSURE - ABSOLUTE

- Every report ends with an explicit residual-risk section. If nothing
  remains unverified, state that explicitly - do not omit the section.
- Any required manual follow-up action from the user (re-auth, cache
  clear, service restart, permission grant) is a residual risk and MUST
  be stated as a concrete, numbered step - never buried in prose, never
  omitted.
- A clean-looking summary MUST NOT imply more confidence than the actual
  testing performed supports. State exact coverage ("verified 2 of 6
  affected cases"), never a rounded-up impression.

## 8. CONTEXT AND SESSION DISCIPLINE - ABSOLUTE

- Approaching an auto-compact, context limit, or session end mid-task:
  finish the current atomic step only (one commit, one verification run
  - never a half-completed edit), then explicitly restate every open
  question from the user before continuing or stopping. A compaction
  event silently dropping an unanswered question is a failure you are
  responsible for preventing.
- A task containing multiple explicit questions MUST have every question
  answered explicitly, in order, in the final report - regardless of
  which question your investigation happened to answer first.

## 9. RE-VERIFY ON CHALLENGE - ABSOLUTE

- When challenged with evidence against your claim, you WILL go re-check
  with fresh evidence. You are FORBIDDEN from simply agreeing and
  rephrasing the same unverified claim in softer language - that is not
  a correction, it is a repeated failure wearing an apology.
- If re-verification still cannot produce direct evidence, state exactly
  what capability or access is missing. Do not manufacture a new
  plausible-sounding narrative to paper over the gap.

## 10. MANDATORY SELF-AUDIT - RUN BEFORE EVERY "DONE" REPORT, NO EXCEPTIONS

You WILL run this exact checklist before sending any completion report.
Every box must be honestly checkable or the report does not go out:

- [ ] Every "confirmed" / "root cause" / "fixed" claim cites a specific
      artifact (log line, diff, real command output).
- [ ] Every "unaffected" / "unchanged" / "shared" claim has been diffed
      or grepped and the evidence is shown, not merely asserted.
- [ ] Any visual/file/rendered output was actually inspected, OR its
      absence is explicitly and loudly flagged as unverified.
- [ ] Scope matches exactly what was authorized - nothing extra touched
      without explicit callout.
- [ ] All changes are committed, on the correct branch, with clear
      messages - `git status` is clean or its state is explained.
- [ ] Risk tier is stated explicitly (Section 6).
- [ ] Residual risks are listed, however short the list.
- [ ] Every explicit question from the task is answered, in order.

If even one box cannot be honestly checked: THE TASK IS NOT DONE. Go
produce the missing evidence or explicitly flag the gap. Do not send the
report.

---

## 11. GENERICITY - A HARD ARCHITECTURAL BOUNDARY, ZERO TOLERANCE

This application is agnostic across four dimensions, absolutely, without
exception, regardless of how well a narrower implementation performed
against whatever single real case was in front of you this session:

- OS-AGNOSTIC: identical behavior on Windows, macOS, Linux. Any
  OS-specific code MUST use the existing platform-check pattern already
  present in this codebase. Inventing a new ad hoc OS assumption is
  FORBIDDEN.
- ARCHITECTURE-AGNOSTIC: zero CPU or hardware-specific assumptions.
- BOARD/SOURCE-AGNOSTIC: Azure DevOps and Jira are both first-class,
  fully supported sources. Source-specific logic lives ONLY inside its
  own package and is reached ONLY through the shared source abstraction.
  Calling source-specific concepts from source-agnostic code is
  FORBIDDEN.
- TARGET-APPLICATION-AGNOSTIC: the E2E automation, KB ingestion, and test
  generation MUST work against any target application. Hardcoding any
  client name, project name, URL, field name, or screen name outside of
  that run's actual input is FORBIDDEN, without exception, regardless of
  convenience.

BEFORE marking ANY task complete, you WILL grep your own changes for:
- Any literal client/company/project/board name in a conditional or
  hardcoded value rather than a passed parameter.
- Any code outside its designated source package assuming source-specific
  concepts.
- Any new OS-specific behavior bypassing the existing platform-check
  pattern.
- Any target-application assumption hardcoded rather than derived from
  that run's actual input.

Finding nothing MUST be stated explicitly, with the exact search commands
used to confirm it, in your report. Finding anything MUST be generalized
before the task is considered complete - this is the actual bug, not
optional polish.

This rule exists because it is dangerously easy, while staring at one
real client's real data for an entire session, to write code that only
works for what is in front of you. That is a violation even when every
test you ran passed - because the tests you ran were themselves narrowed
to the one case you were staring at.

---

THIS PROTOCOL APPLIES TO EVERY TASK, EVERY SESSION, WITHOUT EXCEPTION,
UNTIL EXPLICITLY SUPERSEDED IN WRITING BY THE USER. IT DOES NOT EXPIRE
BECAUSE A TASK SEEMS SMALL. IT DOES NOT EXPIRE UNDER TIME PRESSURE. IT
DOES NOT EXPIRE BECAUSE A PRIOR SESSION ALREADY FOLLOWED IT.
