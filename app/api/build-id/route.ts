import { NextResponse } from "next/server";

// Always evaluated at request time so it reflects the CURRENTLY deployed build,
// never a cached value. The client compares this against the build id baked into
// its bundle (NEXT_PUBLIC_BUILD_ID); a mismatch means a newer web app has been
// deployed and the open tab should reload to pick it up.
export const dynamic = "force-dynamic";
export const revalidate = 0;

export function GET() {
  const buildId =
    process.env.VERCEL_GIT_COMMIT_SHA ||
    process.env.VERCEL_DEPLOYMENT_ID ||
    process.env.NEXT_PUBLIC_BUILD_ID ||
    "dev";

  return NextResponse.json(
    { buildId },
    {
      headers: {
        "Cache-Control": "no-cache, no-store, must-revalidate",
      },
    }
  );
}
