import { type NextRequest } from "next/server";

/**
 * Secure LLM proxy.
 *
 * The Testing Toolkit agent runs on each end user's machine, so it can never be
 * trusted to hold the real GenAI gateway credentials — anything shipped to a
 * user machine is ultimately extractable. Instead, the agent points its
 * `BASE_URL` at THIS route (e.g. https://testing-toolkit.vercel.app/api/llm)
 * and sends no real key. This route:
 *
 *   1. (optionally) authenticates the caller against LLM_PROXY_TOKEN,
 *   2. injects the real Authorization/x-api-key from server-only env,
 *   3. forwards the request to the real upstream gateway, and
 *   4. streams the response straight back (SSE-safe).
 *
 * The real key + base URL live ONLY in Vercel Environment Variables
 * (LLM_UPSTREAM_API_KEY / LLM_UPSTREAM_BASE_URL) which only the project owner
 * can set or rotate. They are never in the repo (.env* is gitignored) and never
 * shipped in the agent bundle. Serverless functions never expose their env to
 * the client, so end users cannot read them.
 *
 * Supported upstream paths (catch-all): v1/messages, messages,
 * chat/completions, completions, embeddings, rerank, audio/transcriptions,
 * audio/speech, images/generations, v1/responses, models, etc.
 */

// Node runtime: we forward to an internal gateway and stream large responses.
export const runtime = "nodejs";
// LLM generations can be long-running; allow up to the platform max.
export const maxDuration = 300;
// Never cache proxied LLM traffic.
export const dynamic = "force-dynamic";

// Request/response headers we must NOT copy verbatim.
const STRIP_REQUEST_HEADERS = new Set([
  "host",
  "connection",
  "content-length",
  "authorization",
  "x-api-key",
  "x-proxy-token",
  "cookie",
  "accept-encoding",
]);

const STRIP_RESPONSE_HEADERS = new Set([
  "content-encoding",
  "content-length",
  "transfer-encoding",
  "connection",
]);

function upstreamBase(): string | null {
  const raw = process.env.LLM_UPSTREAM_BASE_URL?.trim();
  if (!raw) return null;
  return raw.replace(/\/+$/, "");
}

/**
 * Enforce the optional shared proxy token. When LLM_PROXY_TOKEN is set on the
 * server, callers must present it (via `x-proxy-token`, or as the Bearer token
 * / x-api-key the agent already sends). This keeps the endpoint from being an
 * open relay to your gateway.
 *
 * AUDIT-014: In production, if no token is configured the endpoint rejects
 * requests unless LLM_PROXY_ALLOW_UNAUTHENTICATED=true is explicitly set.
 */
function callerAuthorized(req: NextRequest): boolean {
  const expected = process.env.LLM_PROXY_TOKEN?.trim();
  if (!expected) {
    // In production, require explicit opt-in to run without auth
    if (
      process.env.NODE_ENV === "production" &&
      process.env.LLM_PROXY_ALLOW_UNAUTHENTICATED !== "true"
    ) {
      return false;
    }
    return true; // dev convenience
  }

  const presented =
    req.headers.get("x-proxy-token")?.trim() ||
    req.headers.get("authorization")?.replace(/^Bearer\s+/i, "").trim() ||
    req.headers.get("x-api-key")?.trim() ||
    "";

  // Constant-time-ish compare (lengths first, then char accumulation).
  if (presented.length !== expected.length) return false;
  let diff = 0;
  for (let i = 0; i < expected.length; i++) {
    diff |= presented.charCodeAt(i) ^ expected.charCodeAt(i);
  }
  return diff === 0;
}

async function handle(
  req: NextRequest,
  ctx: { params: Promise<{ path: string[] }> }
): Promise<Response> {
  const base = upstreamBase();
  const key = process.env.LLM_UPSTREAM_API_KEY?.trim();

  if (!base || !key) {
    return Response.json(
      {
        error:
          "LLM proxy not configured. Set LLM_UPSTREAM_BASE_URL and LLM_UPSTREAM_API_KEY in the project environment.",
      },
      { status: 503 }
    );
  }

  if (!callerAuthorized(req)) {
    const tokenConfigured = !!process.env.LLM_PROXY_TOKEN?.trim();
    if (!tokenConfigured) {
      return Response.json(
        {
          error:
            "LLM_PROXY_TOKEN must be set in production. Set LLM_PROXY_ALLOW_UNAUTHENTICATED=true to bypass (not recommended).",
        },
        { status: 503 }
      );
    }
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { path } = await ctx.params;

  // AUDIT-015: Reject path traversal / SSRF attempts.
  const segments = path ?? [];
  for (const seg of segments) {
    if (!seg || seg === ".." || seg.includes("\\") || seg.includes("\0")) {
      return Response.json({ error: "Invalid path segment" }, { status: 400 });
    }
  }

  const suffix = segments.join("/");
  const search = req.nextUrl.search ?? "";
  const target = `${base}/${suffix}${search}`;

  // Build forwarded headers: copy safe ones, then inject the real credentials.
  const headers = new Headers();
  req.headers.forEach((value, name) => {
    if (!STRIP_REQUEST_HEADERS.has(name.toLowerCase())) headers.set(name, value);
  });
  headers.set("Authorization", `Bearer ${key}`);
  headers.set("x-api-key", key);

  // Forward the raw body for non-GET/HEAD (streamed, no buffering).
  const method = req.method.toUpperCase();
  const hasBody = method !== "GET" && method !== "HEAD";

  let upstream: Response;
  try {
    upstream = await fetch(target, {
      method,
      headers,
      body: hasBody ? await req.arrayBuffer() : undefined,
      redirect: "manual",
      // @ts-expect-error - Node fetch duplex hint for streaming bodies.
      duplex: "half",
    });
  } catch (e) {
    return Response.json(
      { error: `Upstream request failed: ${(e as Error).message}` },
      { status: 502 }
    );
  }

  // Stream the upstream response straight back, preserving status + type.
  const respHeaders = new Headers();
  upstream.headers.forEach((value, name) => {
    if (!STRIP_RESPONSE_HEADERS.has(name.toLowerCase()))
      respHeaders.set(name, value);
  });

  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: respHeaders,
  });
}

export const GET = handle;
export const POST = handle;
export const PUT = handle;
export const DELETE = handle;
export const PATCH = handle;
