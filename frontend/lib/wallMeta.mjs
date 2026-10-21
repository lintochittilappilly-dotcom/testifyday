/**
 * Per-wall social metadata.
 *
 * /wall/:slug is a client-rendered SPA page, so crawlers that do not execute
 * JavaScript (Slack, LinkedIn, iMessage, most of X) would otherwise unfurl the
 * generic homepage card. The edge middleware fetches the wall from the API and
 * rewrites the shell's <head> with these values.
 */
import { withHead } from "./headTags.mjs";

const SITE_URL = "https://www.testify.day";

export function wallMetadata(wall, { origin = SITE_URL, slug } = {}) {
  const business = (wall?.business_name || "").trim() || "This business";
  const count = Number(wall?.count || 0);
  const wallUrl = `${origin.replace(/\/$/, "")}/wall/${encodeURIComponent(slug || wall?.slug || "")}`;
  const ogPath = wall?.og_image || (slug ? `/api/og/wall/${encodeURIComponent(slug)}.png` : null);
  const image = ogPath ? `${origin.replace(/\/$/, "")}${ogPath}` : null;

  return {
    title: `${business} — Wall of Love`,
    description:
      count > 0
        ? `See what ${count} ${count === 1 ? "customer says" : "customers say"} about ${business}. Real, approved testimonials collected with Testify.`
        : `Real, approved customer testimonials for ${business}, collected with Testify.`,
    url: wallUrl,
    image,
    type: "website",
  };
}

export function applyWallMeta(html, wall, opts = {}) {
  if (!wall) return html;
  return withHead(html, wallMetadata(wall, opts));
}
