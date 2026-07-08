"""
automation/e2e_runner.py
RPA-grade E2E test execution engine using Playwright.

DESIGN PRINCIPLES
-----------------
1. Self-healing locator waterfall: six ordered strategies are tried in
   sequence (role -> label -> placeholder -> text -> test_id -> css/shadow).
   The first that resolves a visible element wins; the winning strategy is
   logged so engineers can harden the step definition.

2. Auto-retry with backoff: transient Playwright TimeoutError and stale-
   element exceptions trigger up to MAX_STEP_RETRIES automatic retries with
   exponential backoff before the step is marked as a failure.

3. Stop signal propagation: the caller can pass a stop_fn() predicate;
   it is checked between every test case (and at the start of each step)
   so a UI "Stop" button cancels the run promptly without killing mid-step.

4. Iframe traversal: when a locator is not found in the main frame, the
   runner automatically walks all attached iframes (1 level deep) and retries
   the locate-and-interact there. Needed for enterprise apps (ADO, SharePoint,
   ServiceNow) that embed significant UI in iframes.

5. Shadow DOM: if every frame lookup fails, a last-resort CSS query with
   Playwright's native ">>" shadow-piercing combinator is attempted.

6. Smart post-click wait: navigation clicks (submit, a[href], button[type=submit])
   wait for "commit"; pure in-page clicks (dropdown open, tab switch, checkbox)
   get a short stability wait only, preventing 30-second timeouts on SPAs.

7. Stability guard: before each interact, the target element is checked for
   positional stability across two frames (50 ms apart) so clicks land on
   moving/animating elements correctly.

8. Configurable continue-on-fail: assertion steps (assert_text, assert_url,
   assert_element) are "soft" by default -- they record FAIL without aborting
   the remaining flow. Hard actions (navigate, fill, click on submit) abort.

SECURITY: Password is ONLY passed to page.fill(). NEVER logged, NEVER written
to disk, NEVER included in any artifact or exception message.
"""

from __future__ import annotations

import asyncio
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

try:
    from playwright.async_api import (
        FrameLocator,
        Locator,
        Page,
        TimeoutError as PwTimeout,
    )
except ImportError:
    Page = object          # type: ignore[assignment,misc]
    Locator = object       # type: ignore[assignment,misc]
    FrameLocator = object  # type: ignore[assignment,misc]
    PwTimeout = Exception  # type: ignore[assignment,misc]

from .artifact_collector import ArtifactCollector
from .playwright_bridge import BrowserProfile, browser_session
from .screenshot_annotator import annotate_screenshot
from .script_generator import generate_playwright_script


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_STEP_RETRIES: int = 3          # attempts before marking step as failure
RETRY_BASE_MS: int = 600           # initial retry backoff (doubles each attempt)
STABILITY_CHECK_MS: int = 50       # gap between two position checks for stability
ELEMENT_TIMEOUT_MS: int = 12_000   # default per-element wait
NAVIGATE_TIMEOUT_MS: int = 30_000  # goto() timeout


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class StepResult:
    step_num: int
    action: str
    expected: str
    actual: str
    status: str            # "pass" | "fail" | "skip" | "error"
    locator_strategy: str = ""   # which strategy won (for self-heal reporting)
    screenshot_path: Path | None = None
    duration_ms: int = 0


@dataclass(slots=True)
class TestCaseResult:
    tc_id: str
    title: str
    steps: list[StepResult]
    video_path: Path | None = None
    script_path: Path | None = None
    overall_status: str = "pass"   # "pass" | "fail" | "error"
    duration_ms: int = 0


# ---------------------------------------------------------------------------
# Security helpers
# ---------------------------------------------------------------------------

_SENSITIVE_KEYS = frozenset({"password", "passwd", "pwd", "secret", "token"})


def _is_password_target(label: str) -> bool:
    return any(s in label.lower() for s in _SENSITIVE_KEYS)


def _scrub(msg: str, password: str) -> str:
    """Remove any accidental password leakage from an exception message."""
    if password and password in msg:
        return msg.replace(password, "***")
    return msg


# ---------------------------------------------------------------------------
# Self-healing locator resolution
# ---------------------------------------------------------------------------

_STRATEGY_ORDER = ("role", "label", "placeholder", "text", "test_id", "css")


def _build_locator(page_or_frame: Any, target: str, strategy: str) -> Any:
    """Build a Playwright locator for a given strategy without touching the DOM."""
    if strategy == "role":
        if ":" in target:
            role, name = target.split(":", 1)
            return page_or_frame.get_by_role(role.strip(), name=name.strip())
        return page_or_frame.get_by_role(target)
    elif strategy == "label":
        return page_or_frame.get_by_label(target)
    elif strategy == "placeholder":
        return page_or_frame.get_by_placeholder(target)
    elif strategy == "text":
        return page_or_frame.get_by_text(target, exact=False)
    elif strategy == "test_id":
        return page_or_frame.get_by_test_id(target)
    elif strategy == "css":
        # Try plain CSS first; if that contains no special chars, also try
        # the shadow-piercing variant with ">>".
        return page_or_frame.locator(target)
    return page_or_frame.get_by_text(target)


def _shadow_locator(page_or_frame: Any, target: str) -> Any:
    """Attempt shadow DOM pierce via CSS '>>' combinator."""
    # Playwright's >> pierces shadow roots; we construct a best-effort
    # CSS selector from the target string.
    css_target = target.replace(":", "[name='") + "']" if ":" in target else target
    return page_or_frame.locator(f">> {css_target}")


async def _find_element(
    page: Any,
    target: str,
    preferred_strategy: str,
    timeout_ms: int = ELEMENT_TIMEOUT_MS,
) -> tuple[Any, str]:
    """Find an element using self-healing locator waterfall.

    Order: preferred strategy -> remaining strategies in _STRATEGY_ORDER ->
           iframe traversal (1 level deep) -> shadow DOM pierce.

    Returns (locator, winning_strategy). Raises RuntimeError if all fail.
    """
    # Build ordered strategy list: preferred first
    ordered = [preferred_strategy] + [
        s for s in _STRATEGY_ORDER if s != preferred_strategy
    ]

    # 1) Try each strategy on the main frame
    for strategy in ordered:
        try:
            loc = _build_locator(page, target, strategy)
            await loc.wait_for(state="visible", timeout=timeout_ms // len(ordered))
            return loc, strategy
        except Exception:
            continue

    # 2) Walk iframes (1 level deep)
    for frame in page.frames:
        if frame == page.main_frame:
            continue
        for strategy in ordered:
            try:
                loc = _build_locator(frame, target, strategy)
                await loc.wait_for(state="visible", timeout=2_000)
                return loc, f"iframe:{strategy}"
            except Exception:
                continue

    # 3) Shadow DOM pierce (last resort)
    try:
        loc = _shadow_locator(page, target)
        await loc.wait_for(state="visible", timeout=2_000)
        return loc, "shadow"
    except Exception:
        pass

    raise RuntimeError(
        f"Element not found: [{target}] — tried {ordered} + iframe + shadow"
    )


# ---------------------------------------------------------------------------
# Element stability guard
# ---------------------------------------------------------------------------

async def _wait_for_stable(locator: Any, *, checks: int = 2) -> None:
    """Wait until the element's bounding box stops moving.

    Takes `checks` bounding-box samples STABILITY_CHECK_MS apart; if they
    match, the element is stable. Gives up silently after 3 rounds — a
    moving element is still preferable to a hard timeout.
    """
    last_box = None
    for _ in range(checks * 3):
        try:
            box = await locator.bounding_box()
            if box == last_box and box is not None:
                return
            last_box = box
            await asyncio.sleep(STABILITY_CHECK_MS / 1000)
        except Exception:
            return


# ---------------------------------------------------------------------------
# Single step executor
# ---------------------------------------------------------------------------

_NAVIGATION_ACTIONS = frozenset({"navigate", "submit"})
# Actions that are "soft" (assert failures do not abort the remaining flow)
_SOFT_ACTIONS = frozenset({"assert_text", "assert_url", "assert_element", "screenshot"})


async def _execute_step(
    page: Page,
    step: dict[str, Any],
    username: str,
    password: str,
    screenshot_dir: Path,
    step_num: int,
    *,
    stop_fn: Callable[[], bool] | None = None,
) -> StepResult:
    """Execute a single test step with auto-retry and self-healing locators.

    Returns a StepResult; never raises (all errors are captured in status).
    """
    t0 = time.perf_counter_ns()
    action = step.get("action", "").lower().strip()
    target = step.get("target", "")
    value = step.get("value", "")
    expected = step.get("expected", "")
    preferred_strategy = step.get("locator", "role")

    actual = ""
    status = "pass"
    winning_strategy = preferred_strategy
    screenshot_path: Path | None = None

    # Check stop signal before starting the step
    if stop_fn and stop_fn():
        return StepResult(
            step_num=step_num, action=action, expected=expected,
            actual="Stopped by user", status="skip",
            locator_strategy="", duration_ms=0,
        )

    for attempt in range(1, MAX_STEP_RETRIES + 1):
        try:
            if action == "navigate":
                url = value or target
                await page.goto(url, wait_until="domcontentloaded",
                                timeout=NAVIGATE_TIMEOUT_MS)
                actual = f"Navigated to {page.url}"
                if expected and expected not in page.url:
                    status = "fail"
                    actual = f"URL mismatch: got {page.url}, expected to contain [{expected}]"
                winning_strategy = "navigate"

            elif action == "fill":
                loc, winning_strategy = await _find_element(
                    page, target, preferred_strategy
                )
                await _wait_for_stable(loc)
                # Determine fill value
                if _is_password_target(target) or value.lower() == "{{password}}":
                    fill_value = password
                    log_value = "***"
                elif value.lower() == "{{username}}":
                    fill_value = username
                    log_value = username
                else:
                    fill_value = value
                    log_value = value
                await loc.clear()
                await loc.fill(fill_value, timeout=ELEMENT_TIMEOUT_MS)
                actual = f"Filled [{target}] with [{log_value}] via [{winning_strategy}]"

            elif action == "click":
                loc, winning_strategy = await _find_element(
                    page, target, preferred_strategy
                )
                await _wait_for_stable(loc)
                # Detect navigation intent from element attributes
                tag = await loc.evaluate("el => el.tagName.toLowerCase()")
                el_type = await loc.evaluate(
                    "el => (el.getAttribute('type') || '').toLowerCase()"
                )
                is_nav = tag == "a" or el_type in ("submit", "button")
                await loc.click(timeout=ELEMENT_TIMEOUT_MS)
                actual = f"Clicked [{target}] via [{winning_strategy}]"
                if is_nav:
                    try:
                        await page.wait_for_load_state("commit", timeout=10_000)
                    except Exception:
                        pass

            elif action == "type":
                # Slower keystroke-by-keystroke fill (for autocomplete/masked fields)
                loc, winning_strategy = await _find_element(
                    page, target, preferred_strategy
                )
                await _wait_for_stable(loc)
                fill_value = (
                    password if (_is_password_target(target) or value.lower() == "{{password}}")
                    else (username if value.lower() == "{{username}}" else value)
                )
                await loc.press_sequentially(fill_value, delay=40)
                actual = f"Typed into [{target}] via [{winning_strategy}]"

            elif action == "select":
                loc, winning_strategy = await _find_element(
                    page, target, preferred_strategy
                )
                await loc.select_option(value, timeout=ELEMENT_TIMEOUT_MS)
                actual = f"Selected [{value}] in [{target}] via [{winning_strategy}]"

            elif action == "check":
                loc, winning_strategy = await _find_element(
                    page, target, preferred_strategy
                )
                await loc.check(timeout=ELEMENT_TIMEOUT_MS)
                actual = f"Checked [{target}] via [{winning_strategy}]"

            elif action == "uncheck":
                loc, winning_strategy = await _find_element(
                    page, target, preferred_strategy
                )
                await loc.uncheck(timeout=ELEMENT_TIMEOUT_MS)
                actual = f"Unchecked [{target}] via [{winning_strategy}]"

            elif action == "hover":
                loc, winning_strategy = await _find_element(
                    page, target, preferred_strategy
                )
                await _wait_for_stable(loc)
                await loc.hover(timeout=ELEMENT_TIMEOUT_MS)
                actual = f"Hovered [{target}] via [{winning_strategy}]"

            elif action == "double_click":
                loc, winning_strategy = await _find_element(
                    page, target, preferred_strategy
                )
                await _wait_for_stable(loc)
                await loc.dblclick(timeout=ELEMENT_TIMEOUT_MS)
                actual = f"Double-clicked [{target}] via [{winning_strategy}]"

            elif action == "press_key":
                key = value or target
                await page.keyboard.press(key)
                actual = f"Pressed key [{key}]"

            elif action == "scroll":
                direction = value.lower() if value else "down"
                delta = 400 if direction == "down" else -400
                await page.mouse.wheel(0, delta)
                actual = f"Scrolled [{direction}]"

            elif action == "wait":
                ms = int(value) if str(value).isdigit() else 2000
                await page.wait_for_timeout(ms)
                actual = f"Waited {ms}ms"

            elif action == "wait_for_text":
                text = value or expected
                try:
                    await page.get_by_text(text).wait_for(
                        state="visible", timeout=ELEMENT_TIMEOUT_MS
                    )
                    actual = f"Text appeared: [{text}]"
                except PwTimeout:
                    status = "fail"
                    actual = f"Text did NOT appear within timeout: [{text}]"

            elif action == "wait_for_url":
                url_fragment = value or expected
                try:
                    await page.wait_for_url(f"**{url_fragment}**",
                                            timeout=ELEMENT_TIMEOUT_MS)
                    actual = f"URL matched: [{url_fragment}]"
                except PwTimeout:
                    status = "fail"
                    actual = f"URL never matched: [{url_fragment}] (current: {page.url})"

            elif action == "assert_text":
                text_to_find = value or expected
                loc = page.get_by_text(text_to_find, exact=False)
                try:
                    await loc.first.wait_for(state="visible", timeout=ELEMENT_TIMEOUT_MS)
                    actual = f"Text found: [{text_to_find}]"
                except PwTimeout:
                    status = "fail"
                    actual = f"Text NOT found: [{text_to_find}]"

            elif action == "assert_url":
                expected_fragment = value or expected
                current = page.url
                if expected_fragment in current:
                    actual = f"URL contains [{expected_fragment}]"
                else:
                    status = "fail"
                    actual = f"URL mismatch: [{current}] does not contain [{expected_fragment}]"

            elif action == "assert_element":
                try:
                    loc, winning_strategy = await _find_element(
                        page, target, preferred_strategy, timeout_ms=ELEMENT_TIMEOUT_MS
                    )
                    actual = f"Element visible: [{target}] via [{winning_strategy}]"
                except RuntimeError:
                    status = "fail"
                    actual = f"Element NOT visible: [{target}]"
                    winning_strategy = "not-found"

            elif action == "assert_not_present":
                # Passes when element is absent or hidden
                all_gone = True
                for strategy in _STRATEGY_ORDER:
                    try:
                        loc = _build_locator(page, target, strategy)
                        count = await loc.count()
                        if count > 0:
                            visible = await loc.first.is_visible()
                            if visible:
                                all_gone = False
                                break
                    except Exception:
                        continue
                actual = (
                    f"Element absent: [{target}]" if all_gone
                    else f"Element STILL PRESENT: [{target}]"
                )
                if not all_gone:
                    status = "fail"

            elif action == "screenshot":
                actual = "Screenshot captured"

            elif action == "clear":
                loc, winning_strategy = await _find_element(
                    page, target, preferred_strategy
                )
                await loc.clear()
                actual = f"Cleared [{target}] via [{winning_strategy}]"

            else:
                status = "skip"
                actual = f"Unknown action: [{action}] — step skipped"

            # Success: break out of retry loop
            break

        except PwTimeout as exc:
            if attempt < MAX_STEP_RETRIES:
                wait_ms = RETRY_BASE_MS * (2 ** (attempt - 1))
                await asyncio.sleep(wait_ms / 1000)
                continue
            status = "error"
            actual = f"Timeout after {MAX_STEP_RETRIES} attempts: {action} on [{target}]"

        except RuntimeError as exc:
            # Self-healing failures (element-not-found after all strategies)
            if attempt < MAX_STEP_RETRIES:
                wait_ms = RETRY_BASE_MS * (2 ** (attempt - 1))
                await asyncio.sleep(wait_ms / 1000)
                continue
            status = "error"
            actual = _scrub(str(exc)[:300], password)

        except Exception as exc:
            err_msg = _scrub(str(exc)[:300], password)
            if attempt < MAX_STEP_RETRIES:
                wait_ms = RETRY_BASE_MS * (2 ** (attempt - 1))
                await asyncio.sleep(wait_ms / 1000)
                continue
            status = "error"
            actual = f"Error: {err_msg}"

    # Take screenshot after every step (failure screenshots are most valuable)
    try:
        raw_path = screenshot_dir / f"step_{step_num:03d}.png"
        await page.screenshot(path=str(raw_path), full_page=False)
        screenshot_path = annotate_screenshot(
            screenshot_path=raw_path,
            step_num=step_num,
            status=status,
            label=f"{action}: {target}"[:60],
        )
    except Exception:
        pass

    elapsed_ms = int((time.perf_counter_ns() - t0) / 1_000_000)
    return StepResult(
        step_num=step_num,
        action=action,
        expected=expected,
        actual=actual,
        status=status,
        locator_strategy=winning_strategy,
        screenshot_path=screenshot_path,
        duration_ms=elapsed_ms,
    )


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

async def run_e2e_tests(
    test_cases: list[dict[str, Any]],
    login_url: str,
    username: str,
    password: str,
    output_dir: Path,
    *,
    profile: BrowserProfile | None = None,
    headless: bool = False,
    ai_instructions: str = "",
    stop_fn: Callable[[], bool] | None = None,
    on_progress: Callable[[int, int], None] | None = None,
    on_log: Callable[[str], None] | None = None,
    on_screenshot: Callable[[Path, int, str], None] | None = None,
    on_tc_done: Callable[[str, str], None] | None = None,
) -> list[TestCaseResult]:
    """Execute E2E tests using the user's real browser via CDP.

    Args:
        test_cases:      List of dicts with keys: id, title, steps.
        login_url:       Starting URL for the test session.
        username:        Login username.
        password:        Login password (from vault, NEVER logged).
        output_dir:      Base directory for all artifacts.
        profile:         BrowserProfile to use (auto-detect if None).
        headless:        Ignored (CDP attach uses visible browser for SSO).
        ai_instructions: Free-text instructions for AI-driven login steps.
        stop_fn:         Zero-arg predicate; if truthy, stops between TCs.
        on_progress:     Callback(current, total) for progress reporting.
        on_log:          Callback(message) for log output.
        on_screenshot:   Callback(path, step_num, status) after each screenshot.
        on_tc_done:      Callback(tc_id, overall_status) after each TC.

    Returns:
        List of TestCaseResult, one per test case.
    """
    results: list[TestCaseResult] = []
    total = len(test_cases)
    output_dir.mkdir(parents=True, exist_ok=True)

    def _log(msg: str) -> None:
        if on_log:
            on_log(msg)

    for idx, tc in enumerate(test_cases):
        # Check stop signal between test cases
        if stop_fn and stop_fn():
            _log("[WARN] Stop signal received. Aborting remaining test cases.")
            break

        tc_id = str(tc.get("id", f"TC_{idx + 1:03d}"))
        title = str(tc.get("title", "Untitled"))
        steps_data: list[dict[str, Any]] = tc.get("steps", [])

        _log(f"[INFO] ({idx + 1}/{total}) Starting: {tc_id} — {title}")
        if on_progress:
            on_progress(idx, total)

        collector = ArtifactCollector(output_dir, tc_id)
        tc_start = time.perf_counter_ns()
        step_results: list[StepResult] = []

        try:
            async with browser_session(
                profile=profile,
                output_dir=collector.video_dir,
            ) as (_browser, page):

                for step_idx, step_data in enumerate(steps_data, start=1):
                    # Per-step stop check
                    if stop_fn and stop_fn():
                        remaining = steps_data[step_idx - 1:]
                        for skip_idx, skip_step in enumerate(remaining, start=step_idx):
                            step_results.append(StepResult(
                                step_num=skip_idx,
                                action=skip_step.get("action", ""),
                                expected=skip_step.get("expected", ""),
                                actual="Stopped by user",
                                status="skip",
                            ))
                        break

                    step_r = await _execute_step(
                        page=page,
                        step=step_data,
                        username=username,
                        password=password,
                        screenshot_dir=collector.screenshot_dir,
                        step_num=step_idx,
                        stop_fn=stop_fn,
                    )
                    step_results.append(step_r)

                    # Notify UI immediately on screenshot save
                    if step_r.screenshot_path and on_screenshot:
                        try:
                            on_screenshot(step_r.screenshot_path, step_idx, step_r.status)
                        except Exception:
                            pass

                    # Report self-heal if a fallback strategy was used
                    if (step_r.locator_strategy
                            and step_r.locator_strategy != step_data.get("locator", "role")
                            and step_r.locator_strategy not in ("navigate", "not-found", "")):
                        _log(
                            f"  [HEAL] Step {step_idx}: fell back to [{step_r.locator_strategy}] "
                            f"for [{step_data.get('target', '')}]"
                        )

                    action_name = step_data.get("action", "")
                    tag = f"[{step_r.status.upper()}]"
                    _log(f"  {tag} Step {step_idx}: {action_name} -> {step_r.actual}")

                    # Abort remaining steps only on hard-action failures
                    if (step_r.status in ("error", "fail")
                            and action_name.lower() not in _SOFT_ACTIONS):
                        remaining_start = step_idx + 1
                        for skip_idx, skip_step in enumerate(
                            steps_data[step_idx:], start=remaining_start
                        ):
                            step_results.append(StepResult(
                                step_num=skip_idx,
                                action=skip_step.get("action", ""),
                                expected=skip_step.get("expected", ""),
                                actual="Skipped (prior hard step failed)",
                                status="skip",
                            ))
                        break

                    # In-progress video copy (best-effort)
                    try:
                        video_src = page.video
                        if video_src:
                            src_path = await video_src.path()
                            if src_path and Path(src_path).exists():
                                dest = collector.video_dir / "recording_live.webm"
                                shutil.copy2(src_path, dest)
                    except Exception:
                        pass

        except Exception as exc:
            err_msg = _scrub(str(exc)[:300], password)
            _log(f"[ERROR] {tc_id} crashed during setup: {err_msg}")
            if not step_results:
                step_results.append(StepResult(
                    step_num=0,
                    action="setup",
                    expected="Browser session started",
                    actual=f"Crash: {err_msg}",
                    status="error",
                ))

        # Determine overall status
        statuses = {s.status for s in step_results}
        if "error" in statuses:
            overall = "error"
        elif "fail" in statuses:
            overall = "fail"
        else:
            overall = "pass"

        tc_elapsed_ms = int((time.perf_counter_ns() - tc_start) / 1_000_000)
        video_path = collector.collect_video()

        script_content = generate_playwright_script(
            tc_id=tc_id,
            title=title,
            steps=steps_data,
            login_url=login_url,
            username=username,
        )
        script_path = collector.save_script(script_content, tc_id)

        tc_result = TestCaseResult(
            tc_id=tc_id,
            title=title,
            steps=step_results,
            video_path=video_path,
            script_path=script_path,
            overall_status=overall,
            duration_ms=tc_elapsed_ms,
        )
        results.append(tc_result)

        if on_tc_done:
            on_tc_done(tc_id, overall)

        _log(f"[{overall.upper()}] {tc_id} finished in {tc_elapsed_ms}ms")

    if on_progress:
        on_progress(total, total)
    _log(f"[INFO] Run complete. {len(results)}/{total} test cases executed.")
    return results
