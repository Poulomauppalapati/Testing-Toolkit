import type { NextConfig } from "next";

// A stable identifier for THIS build/deployment. On Vercel the git commit SHA is
// available at build time and uniquely identifies a deployment; locally we fall
// back to a timestamp. It is baked into the client bundle as NEXT_PUBLIC_BUILD_ID
// and also returned at runtime by /api/build-id, so the running app can detect
// when a newer web build has been deployed and reload itself.
const BUILD_ID =
  process.env.VERCEL_GIT_COMMIT_SHA ||
  process.env.VERCEL_DEPLOYMENT_ID ||
  `dev-${Date.now()}`;

const nextConfig: NextConfig = {
  env: {
    NEXT_PUBLIC_BUILD_ID: BUILD_ID,
  },
  generateBuildId: async () => BUILD_ID,
  async headers() {
    // Never let the HTML shell be served stale from a CDN/browser cache, so a
    // refresh always lands on the latest deployment's entrypoint. Hashed JS/CSS
    // assets remain immutable/cacheable (Next handles those separately).
    return [
      {
        source: "/",
        headers: [
          {
            key: "Cache-Control",
            value: "no-cache, no-store, must-revalidate",
          },
        ],
      },
    ];
  },
};

export default nextConfig;
