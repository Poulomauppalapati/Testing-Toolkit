import { test, expect } from "@playwright/test";
import { guardAdoWrites, mockAgent } from "./helpers";

test.describe("Onboarding / first-run gate", () => {
  test.beforeEach(async ({ page }) => {
    // Agent online but UNCONFIGURED -> the first-run SetupWizard renders
    // (no real agent needed; fully deterministic in-sandbox).
    await mockAgent(page, { configured: false, tourCompleted: false });
    guardAdoWrites(page);
  });

  test("first-run form never exposes centrally managed AI configuration", async ({
    page,
  }) => {
    await page.goto("/");

    await expect(page.getByText("Set up your connection")).toBeVisible();
    await expect(page.getByText("Azure DevOps (optional)")).toBeVisible();
    await expect(page.getByLabel("API Key:")).toHaveCount(0);
    await expect(
      page.getByPlaceholder("https://your-llm-api-endpoint.com"),
    ).toHaveCount(0);
    await expect(page.getByText("Fast model", { exact: true })).toHaveCount(0);
    await expect(page.getByText("Fallback model", { exact: true })).toHaveCount(0);
  });

  test("Skip (manual mode) enters the app shell with an empty board", async ({ page }) => {
    await page.goto("/");

    const skip = page.getByRole("button", { name: "Skip (manual mode)" });
    await expect(skip).toBeVisible();
    await skip.click();
    await page.getByRole("button", { name: "Skip tour" }).click();

    // The main window is always shown; Skip lands us in the shell, not back on
    // the setup form.
    await expect(page.getByText("Projects", { exact: true })).toBeVisible();
    await expect(page.getByText("Boards", { exact: true })).toBeVisible();
    await expect(
      page.getByText("No projects. Configure ADO in Settings."),
    ).toBeVisible();
    // We are no longer on the setup form.
    await expect(
      page.getByRole("button", { name: "Skip (manual mode)" }),
    ).toHaveCount(0);
  });
});
