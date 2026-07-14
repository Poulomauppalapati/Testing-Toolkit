/**
 * build-agent-update-manifest.mjs
 *
 * Generates `agent-update.json`, the manifest the installed agent polls to
 * auto-update itself after a deployment.
 *
 * It walks agent-bundle/src, hashes every file, and emits a manifest whose
 * `version` is read from src/agent/version.py. Each entry points at the file in
 * the repo via the GitHub contents API at a chosen ref (branch), so the running
 * agent (which has a read-only token) can fetch changed files directly.
 *
 * Usage:
 *   node scripts/build-agent-update-manifest.mjs            # ref = main
 *   UPDATE_SRC_REF=<branch> node scripts/build-agent-update-manifest.mjs
 *
 * Deploy flow (each time you ship an agent change):
 *   1. Bump AGENT_VERSION in agent-bundle/src/agent/version.py
 *   2. Commit/push the src changes to the src branch (UPDATE_SRC_REF)
 *   3. Run this script and commit the resulting agent-update.json to the
 *      `parts` branch (that is where install.py points the agent to look).
 * Installed agents poll every 60s, see the new version, pull the changed
 * files, and restart.
 */

import { createHash } from "node:crypto";
import {
  readFileSync,
  writeFileSync,
  readdirSync,
  statSync,
  existsSync,
} from "node:fs";
import { execSync } from "node:child_process";
import { join, relative } from "node:path";

const REPO = "nrcharanvignesh/Testing-Toolkit";
const SRC_REF = process.env.UPDATE_SRC_REF || "main";

const ROOT = process.cwd();
const SRC_DIR = join(ROOT, "agent-bundle", "src");
const VERSION_FILE = join(SRC_DIR, "agent", "version.py");
const INSTALLER_FILE = join(ROOT, "agent-bundle", "install.py");
const REQUIREMENTS_FILE = join(ROOT, "agent-bundle", "requirements.txt");
const EXTRA_WHEELS_DIR = join(ROOT, "agent-bundle", "extra-wheels");
const MCP_DIR = join(ROOT, "agent-bundle", "mcp_servers");
const OUT_FILE = join(ROOT, "agent-update.json");

function contentsUrl(repoPath) {
  return `https://api.github.com/repos/${REPO}/contents/${repoPath}?ref=${SRC_REF}`;
}

function readVersion() {
  const text = readFileSync(VERSION_FILE, "utf8");
  const m = text.match(/AGENT_VERSION\s*=\s*["']([^"']+)["']/);
  if (!m) throw new Error("Could not find AGENT_VERSION in version.py");
  return m[1];
}

function gitContent(repoRelPath) {
  // Hash what git stores (LF-normalized), not the working-tree copy (CRLF on
  // Windows). The overlay fetches raw content from GitHub which matches git's
  // internal representation, so the manifest must hash the same bytes.
  return execSync(`git show HEAD:${repoRelPath}`, { encoding: "buffer", maxBuffer: 10 * 1024 * 1024 });
}

function sha256File(path) {
  return createHash("sha256").update(readFileSync(path)).digest("hex");
}

function walk(dir, files = []) {
  for (const name of readdirSync(dir)) {
    if (name === "__pycache__" || name.endsWith(".pyc")) continue;
    const full = join(dir, name);
    const st = statSync(full);
    if (st.isDirectory()) walk(full, files);
    else files.push(full);
  }
  return files;
}

function main() {
  const version = readVersion();
  const files = walk(SRC_DIR).sort();

  const entries = files.map((full) => {
    // installed-relative path (relative to src/), forward slashes
    const installedRel = relative(SRC_DIR, full).split("\\").join("/");
    // repo path for the GitHub contents API
    const repoPath = `agent-bundle/src/${installedRel}`;
    const content = gitContent(repoPath);
    const hash = createHash("sha256").update(content).digest("hex");
    return { path: installedRel, url: contentsUrl(repoPath), hash };
  });

  const installer = existsSync(INSTALLER_FILE)
    ? {
        url: contentsUrl("agent-bundle/install.py"),
        hash: createHash("sha256").update(gitContent("agent-bundle/install.py")).digest("hex"),
      }
    : null;
  if (!installer) throw new Error("agent-bundle/install.py is missing");

  // The bundle-root requirements.txt, overlaid so newly-added deps are picked
  // up by the offline installer without re-packing the 470 MB bundle.
  const requirements = existsSync(REQUIREMENTS_FILE)
    ? {
        url: contentsUrl("agent-bundle/requirements.txt"),
        hash: createHash("sha256").update(gitContent("agent-bundle/requirements.txt")).digest("hex"),
      }
    : null;
  if (!requirements) throw new Error("agent-bundle/requirements.txt is missing");

  // Wheels added after the bundle was built. Every binary is hashed so staging
  // fails closed before a corrupted or wrong-architecture wheel can be promoted.
  // Wheels are binary (.whl = zip); git never applies line-ending conversion to
  // them so readFileSync is safe here.
  const extraWheels = existsSync(EXTRA_WHEELS_DIR)
    ? readdirSync(EXTRA_WHEELS_DIR)
        .filter((n) => n.endsWith(".whl"))
        .sort()
        .map((name) => ({
          name,
          url: contentsUrl(`agent-bundle/extra-wheels/${name}`),
          hash: sha256File(join(EXTRA_WHEELS_DIR, name)),
        }))
    : [];

  const nodeBinsFile = join(MCP_DIR, "node-bins.json");
  if (!existsSync(nodeBinsFile)) {
    throw new Error("agent-bundle/mcp_servers/node-bins.json is missing");
  }
  const nodeBins = JSON.parse(readFileSync(nodeBinsFile, "utf8"));
  const platformParts = new Map();
  for (const [platform, details] of Object.entries(nodeBins.platforms ?? {})) {
    for (const part of details.parts ?? []) {
      const platforms = platformParts.get(part) ?? [];
      platforms.push(platform);
      platformParts.set(part, platforms);
    }
  }

  const mcpFiles = existsSync(MCP_DIR)
    ? walk(MCP_DIR, [])
        .sort()
        .map((full) => {
          const name = relative(MCP_DIR, full).split("\\").join("/");
          const repoPath = `agent-bundle/mcp_servers/${name}`;
          const content = gitContent(repoPath);
          return {
            name,
            url: contentsUrl(repoPath),
            hash: createHash("sha256").update(content).digest("hex"),
            ...(platformParts.has(name)
              ? { platforms: platformParts.get(name) }
              : {}),
          };
        })
    : [];
  if (mcpFiles.length === 0) {
    throw new Error("agent-bundle/mcp_servers payload is missing");
  }

  const manifest = {
    version,
    ref: SRC_REF,
    generatedAt: new Date().toISOString(),
    files: entries,
    installer,
    requirements,
    extraWheels,
    mcpFiles,
  };

  writeFileSync(OUT_FILE, JSON.stringify(manifest, null, 2) + "\n");
  console.log(
    `Wrote ${OUT_FILE}\n  version=${version} ref=${SRC_REF} files=${entries.length} extraWheels=${extraWheels.length} mcpFiles=${mcpFiles.length}`,
  );
  console.log(
    "Next: commit agent-update.json to the `parts` branch so installed agents can see it.",
  );
}

main();
