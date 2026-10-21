import { applyWallMeta } from "./lib/wallMeta.mjs";

/**
 * Vercel Edge Middleware: give /wall/:slug real, per-wall social metadata.
 *
 * Everything else is untouched (returns undefined → normal static handling).
 * The wall data is public, so this leaks nothing; if the API is unreachable we
 * fall through to the generic shell rather than failing the page.
 */
export const config = {
  matcher: "/wall/:slug",
};

const BACKEND_URL = (process.env.BACKEND_URL || "https://www.backend.testify.day").replace(/\/$/, "");
const HTML_HEADERS = {
  "content-type": "text/html; charset=utf-8",
  // Short edge cache: a new approved testimonial updates the card within minutes.
  "cache-control": "public, max-age=0, s-maxage=300, stale-while-revalidate=86400",
};

export default async function middleware(request) {
  const url = new URL(request.url);
  const slug = url.pathname.split("/")[2];
  if (!slug) return undefined;

  const shell = await fetch(new URL("/index.html", url.origin));
  if (!shell.ok) return undefined;
  const html = await shell.text();

  let wall = null;
  try {
    const res = await fetch(`${BACKEND_URL}/api/public/wall/${encodeURIComponent(slug)}`, {
      headers: { accept: "application/json" },
    });
    if (res.ok) wall = await res.json();
  } catch {
    return new Response(html, { headers: HTML_HEADERS });
  }

  if (!wall) return new Response(html, { headers: HTML_HEADERS });

  return new Response(applyWallMeta(html, wall, { origin: url.origin, slug }), {
    headers: HTML_HEADERS,
  });
}
