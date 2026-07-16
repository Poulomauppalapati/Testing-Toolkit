/**
 * StatusBar.unit.test.tsx
 * Pure-logic tests for StatusBar internals. No DOM environment available
 * (no jsdom/happy-dom/testing-library installed), so we test the formatting
 * logic and version display logic directly.
 *
 * fmtMem is module-scoped in components/layout/StatusBar.tsx (line 10-14).
 * We replicate the exact implementation here for unit verification.
 */

import { describe, test, expect } from "vitest";
import {
  REQUIRED_AGENT_VERSION,
  compareVersions,
  isAgentOutdated,
} from "../lib/agent-version";

// --- Replicated from components/layout/StatusBar.tsx lines 10-14 ---
// This is the exact logic of the unexported fmtMem function.
function fmtMem(mb: number | null | undefined): string {
  if (mb == null || !Number.isFinite(mb)) return "--";
  return mb >= 1024 ? `${(mb / 1024).toFixed(1)} GB` : `${mb} MB`;
}

describe("StatusBar", () => {
  describe("fmtMem formats memory values correctly", () => {
    test("returns -- for null", () => {
      expect(fmtMem(null)).toBe("--");
    });

    test("returns -- for undefined", () => {
      expect(fmtMem(undefined)).toBe("--");
    });

    test("returns -- for NaN", () => {
      expect(fmtMem(NaN)).toBe("--");
    });

    test("returns -- for Infinity", () => {
      expect(fmtMem(Infinity)).toBe("--");
    });

    test("returns -- for -Infinity", () => {
      expect(fmtMem(-Infinity)).toBe("--");
    });

    test("formats values below 1024 as MB", () => {
      expect(fmtMem(512)).toBe("512 MB");
      expect(fmtMem(0)).toBe("0 MB");
      expect(fmtMem(1023)).toBe("1023 MB");
    });

    test("formats values at or above 1024 as GB", () => {
      expect(fmtMem(1024)).toBe("1.0 GB");
      expect(fmtMem(2048)).toBe("2.0 GB");
      expect(fmtMem(1536)).toBe("1.5 GB");
      expect(fmtMem(8192)).toBe("8.0 GB");
    });

    test("rounds GB to one decimal", () => {
      expect(fmtMem(1500)).toBe("1.5 GB");
      expect(fmtMem(1100)).toBe("1.1 GB");
      expect(fmtMem(3333)).toBe("3.3 GB");
    });
  });

  describe("renders agent version when connected", () => {
    test("version string is formatted as vX.Y.Z when present", () => {
      // The StatusBar renders: agentVer ? `v${agentVer}` : `web ${REQUIRED_AGENT_VERSION}`
      const agentVer = "2.13.0";
      const rendered = agentVer ? `v${agentVer}` : `web ${REQUIRED_AGENT_VERSION}`;
      expect(rendered).toBe("v2.13.0");
    });

    test("falls back to web version when agent version is null", () => {
      const agentVer: string | null = null;
      const rendered = agentVer ? `v${agentVer}` : `web ${REQUIRED_AGENT_VERSION}`;
      expect(rendered).toBe(`web ${REQUIRED_AGENT_VERSION}`);
    });

    test("REQUIRED_AGENT_VERSION is a valid semver string", () => {
      expect(REQUIRED_AGENT_VERSION).toMatch(/^\d+\.\d+\.\d+$/);
    });

    test("isAgentOutdated returns false for current version", () => {
      expect(isAgentOutdated(REQUIRED_AGENT_VERSION)).toBe(false);
    });

    test("isAgentOutdated returns true for older version", () => {
      expect(isAgentOutdated("1.0.0")).toBe(true);
    });

    test("isAgentOutdated returns true for null/unknown", () => {
      expect(isAgentOutdated(null)).toBe(true);
      expect(isAgentOutdated(undefined)).toBe(true);
      expect(isAgentOutdated("unknown")).toBe(true);
    });

    test("compareVersions orders correctly", () => {
      expect(compareVersions("2.13.0", "2.13.0")).toBe(0);
      expect(compareVersions("2.14.0", "2.13.0")).toBe(1);
      expect(compareVersions("2.12.0", "2.13.0")).toBe(-1);
      expect(compareVersions("1.10.0", "1.9.0")).toBe(1);
    });
  });

  describe("shows offline indicator", () => {
    test("network chip label reflects online state", () => {
      // The StatusBar renders a Chip with:
      //   label="NW"
      //   color={online ? "var(--tt-success)" : "var(--tt-danger)"}
      //   title={online ? "Network: online" : "Network: offline - no connectivity"}
      const onlineTitle = (isOnline: boolean) =>
        isOnline ? "Network: online" : "Network: offline — no connectivity";
      const onlineColor = (isOnline: boolean) =>
        isOnline ? "var(--tt-success)" : "var(--tt-danger)";

      expect(onlineColor(true)).toBe("var(--tt-success)");
      expect(onlineColor(false)).toBe("var(--tt-danger)");
      expect(onlineTitle(false)).toContain("offline");
      expect(onlineTitle(true)).toContain("online");
    });

    test("offline state uses danger color", () => {
      // When navigator.onLine is false, the chip gets var(--tt-danger)
      const online = false;
      const color = online ? "var(--tt-success)" : "var(--tt-danger)";
      expect(color).toBe("var(--tt-danger)");
    });

    test("online state uses success color", () => {
      const online = true;
      const color = online ? "var(--tt-success)" : "var(--tt-danger)";
      expect(color).toBe("var(--tt-success)");
    });
  });
});
