/**
 * Head-tag helpers shared by the build-time prerender script and the edge
 * middleware. Plain ESM, no JSX, no DOM — safe in Node and in workerd.
 */

export const escapeHtml = (value) =>
  String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");

export function setMeta(html, attr, key, content) {
  if (!content) return html;
  const escaped = escapeHtml(content);
  const re = new RegExp(`<meta ${attr}="${key.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}" content="[^"]*"\\s*/?>`);
  if (re.test(html)) return html.replace(re, `<meta ${attr}="${key}" content="${escaped}" />`);
  return html.replace("</head>", `    <meta ${attr}="${key}" content="${escaped}" />\n  </head>`);
}

export function setTitle(html, title) {
  const tag = `<title>${escapeHtml(title)}</title>`;
  if (/<title>[\s\S]*?<\/title>/.test(html)) return html.replace(/<title>[\s\S]*?<\/title>/, tag);
  return html.replace("</head>", `    ${tag}\n  </head>`);
}

export function setCanonical(html, url) {
  if (!url) return html;
  const tag = `<link rel="canonical" href="${escapeHtml(url)}" />`;
  const re = /<link rel="canonical" href="[^"]*"\s*\/?>/;
  if (re.test(html)) return html.replace(re, tag);
  return html.replace("</head>", `    ${tag}\n  </head>`);
}

export function setJsonLd(html, data) {
  const tag = `    <script type="application/ld+json">${JSON.stringify(data)}</script>\n  </head>`;
  return html.replace("</head>", tag);
}

/**
 * Apply a full document head: title, description, canonical, Open Graph,
 * Twitter card, optional robots directive, optional JSON-LD.
 */
export function withHead(html, { title, description, url, image, type = "website", robots, jsonLd }) {
  let out = html;
  if (title) out = setTitle(out, title);
  out = setMeta(out, "name", "description", description);
  out = setMeta(out, "property", "og:site_name", "Testify");
  out = setMeta(out, "property", "og:type", type);
  out = setMeta(out, "property", "og:title", title);
  out = setMeta(out, "property", "og:description", description);
  out = setMeta(out, "property", "og:url", url);
  if (image) {
    out = setMeta(out, "property", "og:image", image);
    out = setMeta(out, "property", "og:image:width", "1200");
    out = setMeta(out, "property", "og:image:height", "630");
  }
  out = setMeta(out, "name", "twitter:card", image ? "summary_large_image" : "summary");
  out = setMeta(out, "name", "twitter:title", title);
  out = setMeta(out, "name", "twitter:description", description);
  if (image) out = setMeta(out, "name", "twitter:image", image);
  if (robots) out = setMeta(out, "name", "robots", robots);
  out = setCanonical(out, url);
  if (jsonLd) out = setJsonLd(out, jsonLd);
  return out;
}
