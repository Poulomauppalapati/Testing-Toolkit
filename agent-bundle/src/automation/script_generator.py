"""
automation/script_generator.py
Generates rerunnable Playwright Python scripts from E2E test steps.

SECURITY: Password is NEVER embedded in generated scripts.
          Uses os.environ["E2E_PASSWORD"] placeholder instead.

The generated script structure:
    async def main() -> None:
        async with async_playwright() as pw:
            browser = ...           # 8-space block
            context = ...
            page = ...
            # Step 1: ...           # steps at 8-space indent
            await page.goto(...)
            ...
            await context.close()   # 8-space cleanup
"""

from __future__ import annotations

import ast
from typing import Any


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _esc(value: str) -> str:
    """Escape a string for safe embedding in Python source."""
    return repr(value)


_SENSITIVE_KEYS = frozenset({"password", "passwd", "pwd", "secret", "token"})


def _is_password_target(target: str) -> bool:
    return any(s in target.lower() for s in _SENSITIVE_KEYS)


def _locator_expr(target: str, strategy: str, pf: str = "page") -> str:
    """Return the Playwright locator expression string (no await)."""
    if strategy == "role":
        if ":" in target:
            role, name = target.split(":", 1)
            return f"{pf}.get_by_role({_esc(role.strip())}, name={_esc(name.strip())})"
        return f"{pf}.get_by_role({_esc(target)})"
    elif strategy == "label":
        return f"{pf}.get_by_label({_esc(target)})"
    elif strategy == "placeholder":
        return f"{pf}.get_by_placeholder({_esc(target)})"
    elif strategy == "text":
        return f"{pf}.get_by_text({_esc(target)}, exact=False)"
    elif strategy == "test_id":
        return f"{pf}.get_by_test_id({_esc(target)})"
    elif strategy == "css":
        return f"{pf}.locator({_esc(target)})"
    else:
        if ":" in target:
            role, name = target.split(":", 1)
            return f"{pf}.get_by_role({_esc(role.strip())}, name={_esc(name.strip())})"
        return f"{pf}.get_by_text({_esc(target)}, exact=False)"


# ---------------------------------------------------------------------------
# Per-step code generation (4-space indent = caller doubles to 8 in body)
# ---------------------------------------------------------------------------

def _step_to_code(step: dict[str, Any], username: str) -> list[str]:
    """Convert one step dict to lines of Python at 4-space base indent.

    The caller prepends 4 more spaces so the lines land at 8-space inside the
    async with async_playwright() block where `page` is defined.
    """
    action = step.get("action", "").lower().strip()
    target = step.get("target", "")
    value = step.get("value", "")
    expected = step.get("expected", "")
    strategy = step.get("locator", "role")
    loc = _locator_expr(target, strategy)
    lines: list[str] = []

    if action == "navigate":
        url = value or target
        lines.append(f"    await page.goto({_esc(url)}, wait_until='domcontentloaded')")

    elif action == "fill":
        if _is_password_target(target) or value.lower() == "{{password}}":
            fill_val = "os.environ['E2E_PASSWORD']"
        elif value.lower() == "{{username}}":
            fill_val = _esc(username)
        else:
            fill_val = _esc(value)
        lines.append(f"    await {loc}.clear()")
        lines.append(f"    await {loc}.fill({fill_val})")

    elif action == "type":
        if _is_password_target(target) or value.lower() == "{{password}}":
            type_val = "os.environ['E2E_PASSWORD']"
        elif value.lower() == "{{username}}":
            type_val = _esc(username)
        else:
            type_val = _esc(value)
        lines.append(f"    await {loc}.press_sequentially({type_val}, delay=40)")

    elif action == "click":
        lines.append(f"    await {loc}.click()")

    elif action == "double_click":
        lines.append(f"    await {loc}.dblclick()")

    elif action == "hover":
        lines.append(f"    await {loc}.hover()")

    elif action == "select":
        lines.append(f"    await {loc}.select_option({_esc(value)})")

    elif action == "check":
        lines.append(f"    await {loc}.check()")

    elif action == "uncheck":
        lines.append(f"    await {loc}.uncheck()")

    elif action == "clear":
        lines.append(f"    await {loc}.clear()")

    elif action == "press_key":
        key = value or target
        lines.append(f"    await page.keyboard.press({_esc(key)})")

    elif action == "scroll":
        direction = value.lower() if value else "down"
        delta = 400 if direction == "down" else -400
        lines.append(f"    await page.mouse.wheel(0, {delta})")

    elif action == "wait":
        ms = value if str(value).isdigit() else "2000"
        lines.append(f"    await page.wait_for_timeout({ms})")

    elif action == "wait_for_text":
        text = value or expected
        lines.append(
            f"    await expect(page.get_by_text({_esc(text)}, exact=False).first)"
            f".to_be_visible()"
        )

    elif action == "wait_for_url":
        fragment = value or expected
        lines.append(f"    await page.wait_for_url('**{fragment}**')")

    elif action == "assert_text":
        text = value or expected
        lines.append(
            f"    await expect(page.get_by_text({_esc(text)}, exact=False).first)"
            f".to_be_visible()"
        )

    elif action == "assert_url":
        # Use the correct Playwright async expect API for URL assertions.
        fragment = value or expected
        lines.append(
            f"    await expect(page).to_have_url(re.compile({_esc(fragment)}))"
        )

    elif action == "assert_element":
        lines.append(f"    await expect({loc}).to_be_visible()")

    elif action == "assert_not_present":
        lines.append(f"    await expect({loc}).to_be_hidden()")

    elif action == "screenshot":
        lines.append(f"    await page.screenshot(path='screenshot_{action}.png')")

    else:
        lines.append(f"    # Unknown action: {action}")

    return lines


# ---------------------------------------------------------------------------
# Full script assembly
# ---------------------------------------------------------------------------

def generate_playwright_script(
    tc_id: str,
    title: str,
    steps: list[dict[str, Any]],
    login_url: str,
    username: str,
) -> str:
    """Generate a complete, rerunnable Playwright Python script.

    SECURITY: Password is replaced with os.environ["E2E_PASSWORD"].

    The script uses CDP attach to the user's real browser for SSO so that
    MFA/SSO state is preserved across runs.

    Args:
        tc_id:      Test case identifier.
        title:      Test case title.
        steps:      List of step dicts.
        login_url:  Starting URL.
        username:   Login username.

    Returns:
        Complete Python script string, validated with ast.parse.
    """
    header = [
        '"""',
        f"Auto-generated Playwright script for: {tc_id} - {title}",
        "",
        "SECURITY: Set E2E_PASSWORD environment variable before running.",
        "  $env:E2E_PASSWORD = 'your_password'   # PowerShell",
        "  export E2E_PASSWORD='your_password'    # Bash/zsh",
        "",
        "Requires the real browser running with --remote-debugging-port=9222:",
        "  chrome.exe --remote-debugging-port=9222 --user-data-dir=...",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "import asyncio",
        "import os",
        "import re",
        "import sys",
        "",
        "from playwright.async_api import async_playwright, expect",
        "",
        "",
        f"TARGET_URL = {_esc(login_url)}",
        f"USERNAME = {_esc(username)}",
        "CDP_PORT = int(os.environ.get('CDP_PORT', '9222'))",
        "",
        "",
        "async def main() -> None:",
        '    """Execute test case steps via CDP attach."""',
        "    password = os.environ.get('E2E_PASSWORD')",
        "    if not password:",
        "        print('[ERROR] E2E_PASSWORD environment variable not set.')",
        "        sys.exit(1)",
        "",
        "    async with async_playwright() as pw:",
        "        browser = await pw.chromium.connect_over_cdp(",
        "            f'http://127.0.0.1:{CDP_PORT}'",
        "        )",
        "        context = await browser.new_context(",
        "            viewport={'width': 1920, 'height': 1080},",
        "        )",
        "        page = await context.new_page()",
        "",
    ]

    # Build step lines at 8-space indent (inside the async with block)
    body: list[str] = []
    for idx, step in enumerate(steps, start=1):
        action = step.get("action", "")
        target = step.get("target", "")
        # Comment at 8-space
        body.append(f"        # Step {idx}: {action} {target}".rstrip())
        # _step_to_code returns 4-space lines; we add 4 more to reach 8-space
        raw_lines = _step_to_code(step, username)
        for line in raw_lines:
            if line.strip():
                body.append("    " + line)   # 4 existing + 4 extra = 8 total
            else:
                body.append("")
        body.append("")

    footer = [
        "        # Cleanup",
        "        await context.close()",
        "        await browser.close()",
        "        print('[SUCCESS] Test completed.')",
        "",
        "",
        "if __name__ == '__main__':",
        "    asyncio.run(main())",
        "",
    ]

    script = "\n".join(header + body + footer)

    # Validate: if the script is unparseable, emit a safe stub instead
    try:
        ast.parse(script)
    except SyntaxError as exc:
        script = (
            f"# ERROR: Script generation failed for {tc_id}: {exc}\n"
            f"# Steps: {len(steps)}\n"
            f"# Fix the step definitions and regenerate.\n"
        )

    return script
