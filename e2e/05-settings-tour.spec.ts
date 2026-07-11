import { test, expect } from "@playwright/test";
import { guardAdoWrites, enterApp, mockAgent } from "./helpers";

/**
 * Settings flow, first-run tour, and navigator collapse/expand.
 * All tests run against the mocked agent (no real agent, no ADO data).
 */

test.describe("Settings save flow", () => {
  test.beforeEach(async ({ page }) => {
    await mockAgent(page, { configured: true });
    guardAdoWrites(page);
    await enterApp(page);
  });

  test("Settings dialog saves and closes without error", async ({ page }) => {
    await page.getByTitle("Settings").click();
    await expect(page.getByText("Testing Toolkit - Settings")).toBeVisible();

    // The mock POST /settings returns the same settings object (no validation
    // required from the UI side to close). Click Save directly.
    await page.getByRole("button", { name: "Save" }).click();

    // Either dialog closes (success) or an error message appears.
    // With the mock returning valid settings, it must close.
    await expect(page.getByText("Testing Toolkit - Settings")).toHaveCount(0, {
      timeout: 10_000,
    });
  });

  test("Settings source connection buttons are accessible", async ({ page }) => {
    await page.getByTitle("Settings").click();
    const testAdo = page.getByRole("button", { name: "Test ADO" });
    const testJira = page.getByRole("button", { name: "Test Jira" });
    await expect(testAdo).toBeVisible();
    await expect(testAdo).toBeEnabled();
    await expect(testJira).toBeVisible();
    await expect(testJira).toBeEnabled();

    // Test ADO verifies both the saved source settings and central AI service.
    await testAdo.click();
    // Should NOT navigate away or throw — status text updates.
    await expect(page.getByText("Testing Toolkit - Settings")).toBeVisible();

    // Cancel to close.
    await page.getByRole("button", { name: "Cancel" }).click();
    await expect(page.getByText("Testing Toolkit - Settings")).toHaveCount(0);
  });

  test("Settings dialog is keyboard-focusable (accessibility)", async ({ page }) => {
    await page.getByTitle("Settings").click();
    await expect(page.getByText("Testing Toolkit - Settings")).toBeVisible();

    // Tab through the dialog; Cancel button must be reachable and activatable.
    const cancel = page.getByRole("button", { name: "Cancel" });
    await expect(cancel).toBeVisible();
    await cancel.focus();
    await cancel.press("Enter");
    await expect(page.getByText("Testing Toolkit - Settings")).toHaveCount(0);
  });
});

test.describe("Guided tour (first-run)", () => {
  test.beforeEach(async ({ page }) => {
    // tourCompleted=false triggers the tour overlay after entering the app.
    await mockAgent(page, { configured: true, tourCompleted: false });
    guardAdoWrites(page);
    await enterApp(page);
  });

  test("tour shows step 1 of 6 and advances to step 2 via Next", async ({ page }) => {
    // Tour renders on top of the shell.
    await expect(page.getByText("Quick tour · 1 of 6")).toBeVisible();
    await expect(page.getByText("Welcome to Testing Toolkit")).toBeVisible();

    await page.getByRole("button", { name: "Next" }).click();
    await expect(page.getByText("Quick tour · 2 of 6")).toBeVisible();
    await expect(page.getByText("Projects")).toBeVisible();
  });

  test("tour Back button navigates backwards", async ({ page }) => {
    await expect(page.getByText("Quick tour · 1 of 6")).toBeVisible();
    // Back is disabled on step 1.
    const back = page.getByRole("button", { name: "Back" });
    await expect(back).toBeDisabled();

    await page.getByRole("button", { name: "Next" }).click();
    await expect(page.getByText("Quick tour · 2 of 6")).toBeVisible();

    await back.click();
    await expect(page.getByText("Quick tour · 1 of 6")).toBeVisible();
  });

  test("Skip tour dismisses the overlay immediately", async ({ page }) => {
    await expect(page.getByText("Quick tour · 1 of 6")).toBeVisible();
    await page.getByRole("button", { name: "Skip tour" }).click();
    await expect(page.getByText("Quick tour · 1 of 6")).toHaveCount(0, {
      timeout: 5_000,
    });
    // App shell is fully usable.
    await expect(page.getByText("Projects", { exact: true })).toBeVisible();
  });

  test("Get started on last step dismisses the tour", async ({ page }) => {
    // Advance through all 6 steps.
    for (let i = 1; i < 6; i++) {
      await expect(page.getByText(`Quick tour · ${i} of 6`)).toBeVisible();
      await page.getByRole("button", { name: "Next" }).click();
    }
    await expect(page.getByText("Quick tour · 6 of 6")).toBeVisible();
    await page.getByRole("button", { name: "Get started" }).click();
    await expect(page.getByText("Quick tour · 6 of 6")).toHaveCount(0, {
      timeout: 5_000,
    });
  });
});

test.describe("Navigator collapse / expand", () => {
  test.beforeEach(async ({ page }) => {
    await mockAgent(page, { configured: true });
    guardAdoWrites(page);
    await enterApp(page);
  });

  test("Collapse navigator reveals activity bar; Show navigator restores it", async ({ page }) => {
    const collapseNav = page.getByRole("button", { name: "Collapse navigator" });
    await expect(collapseNav).toBeVisible();
    await collapseNav.click();

    // NavPanel gone; activity bar appears (has "Show navigator" / ChevronRight).
    const showNav = page.getByRole("button", { name: "Show navigator" });
    await expect(showNav).toBeVisible();

    // Restore.
    await showNav.click();
    await expect(collapseNav).toBeVisible();
    await expect(page.getByText("Projects", { exact: true })).toBeVisible();
  });

  test("Projects and Boards labels always visible in the navigator", async ({ page }) => {
    await expect(page.getByText("Projects", { exact: true })).toBeVisible();
    await expect(page.getByText("Boards", { exact: true })).toBeVisible();
  });
});
