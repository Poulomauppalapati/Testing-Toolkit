import { test, expect } from "@playwright/test";
import { guardAdoWrites, mockAgent } from "./helpers";

test.describe("Onboarding / first-run gate", () => {
  test.beforeEach(async ({ page }) => {
    // Agent online but UNCONFIGURED -> the first-run SetupWizard renders
    // (no real agent needed; fully deterministic in-sandbox).
    await mockAgent(page, { configured: false, tourCompleted: false });
    guardAdoWrites(page);
  });

  test("first-run form shows an editable Base URL placeholder (not masked dots)", async ({
    page,
  }) => {
    await page.goto("/");

    // Base URL must render as an editable text field with its placeholder
    // (no value seeded, no mask). Waiting for it to be visible also serves as
    // the readiness wait (the app polls health, so networkidle never fires).
    const baseUrl = page.getByPlaceholder("https://your-llm-api-endpoint.com");
    await expect(baseUrl).toBeVisible();
    await expect(baseUrl).toBeEditable();
    await expect(baseUrl).toHaveValue("");
  });

  test("Skip (manual mode) enters the app shell with an empty board", async ({ page }) => {
    await page.goto("/");

    const skip = page.getByRole("button", { name: "Skip (manual mode)" });
    await expect(skip).toBeVisible();
    await skip.click();

    // The main window is always shown; Skip lands us in the shell, not back on
    // the setup form.
    await expect(page.getByText("Projects", { exact: true })).toBeVisible();
    await expect(page.getByText("Boards", { exact: true })).toBeVisible();
    await expect(
      page.getByText("No projects. Configure ADO in Settings, then Refresh."),
    ).toBeVisible();
    // We are no longer on the setup form.
    await expect(
      page.getByRole("button", { name: "Skip (manual mode)" }),
    ).toHaveCount(0);
  });
});
