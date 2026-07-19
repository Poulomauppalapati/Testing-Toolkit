import { test, expect } from "@playwright/test";
import { guardAdoWrites, enterApp, mockAgent } from "./helpers";

test.describe("Shell dialogs", () => {
  test.beforeEach(async ({ page }) => {
    // Configured agent -> straight into the shell (no wizard/tour).
    await mockAgent(page, { configured: true });
    guardAdoWrites(page);
    await enterApp(page);
  });

  test("Settings exposes source credentials but never AI secrets or model controls", async ({
    page,
  }) => {
    await page.getByTitle("Settings").click();

    await expect(page.getByText("Testing Toolkit - Settings")).toBeVisible();
    await expect(page.getByText("Azure DevOps (optional)")).toBeVisible();
    await expect(page.getByText("JIRA (optional)")).toBeVisible();
    await expect(page.getByLabel("API Key:")).toHaveCount(0);
    await expect(page.getByText("Fast model", { exact: true })).toHaveCount(0);
    await expect(page.getByText("Fallback model", { exact: true })).toHaveCount(0);
    // Footer actions
    await expect(page.getByRole("button", { name: "Test ADO" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Test Jira" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Save" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Cancel" })).toBeVisible();

    await page.getByRole("button", { name: "Cancel" }).click();
    await expect(page.getByText("Testing Toolkit - Settings")).toHaveCount(0);
  });

  test("Help menu exposes the log/about actions and About dialog", async ({ page }) => {
    await page.getByTitle("Help").click();

    await expect(page.getByText("Open log folder")).toBeVisible();
    await expect(page.getByText("View recent log...")).toBeVisible();
    await expect(page.getByText("About")).toBeVisible();

    await page.getByText("About").click();
    await expect(page.getByText(/^Version \d+\.\d+\.\d+$/)).toBeVisible();
    await page.getByRole("button", { name: "OK", exact: true }).click();
    await expect(page.getByText(/^Version \d+\.\d+\.\d+$/)).toHaveCount(0);
  });

  test("log panel toggles open and closed", async ({ page }) => {
    const show = page.getByRole("button", { name: "Show log", exact: true });
    const hide = page.getByRole("button", { name: "Hide log", exact: true });
    await show.click();
    await expect(hide).toBeVisible();
    await hide.click();
    await expect(show).toBeVisible();
  });
});
