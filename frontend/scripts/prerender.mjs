#!/usr/bin/env node
/**
 * Post-build prerender for the marketing pages.
 *
 * CRA ships one index.html for every route, so crawlers see a generic title and
 * no content. This script, run right after `craco build`:
 *
 *   1. renders the static marketing pages (/, /terms, /privacy) to HTML with
 *      react-dom/server and bakes that markup into per-route index.html files
 *      with route-specific <title>/description/canonical/OG tags,
 *   2. writes build/404.html so Vercel can answer unknown URLs with a real 404,
 *   3. writes build/robots.txt and build/sitemap.xml.
 *
 * If a page fails to render we keep going with an empty shell for that route so
 * a marketing-page regression can never take the whole deploy down.
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import * as esbuild from "esbuild";

import { withHead } from "../lib/headTags.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, "..");
const BUILD = path.join(ROOT, "build");
const SITE = (process.env.SITE_URL || "https://www.testify.day").replace(/\/$/, "");
const BRAND_OG = `${SITE}/brand/testify-og-image.png`;

const ROUTES = [
  {
    path: "/",
    page: "Landing",
    title: "Testify — Customer Testimonials Made Simple",
    description:
      "Collect video and written customer testimonials in the browser, approve them, and embed them anywhere with one line of code. Free plan, no card required.",
    priority: "1.0",
    changefreq: "weekly",
    jsonLd: true,
  },
  {
    path: "/terms",
    page: "Terms",
    title: "Terms of Service — Testify",
    description: "The terms that govern your use of Testify's testimonial collection and display services.",
    priority: "0.3",
    changefreq: "yearly",
  },
  {
    path: "/privacy",
    page: "Privacy",
    title: "Privacy Policy — Testify",
    description: "How Testify collects, uses, and protects the information you and your customers share with us.",
    priority: "0.3",
    changefreq: "yearly",
  },
];

const NOT_FOUND = {
  title: "Page not found — Testify",
  description: "This page doesn't exist.",
};

function withMarkup(html, markup) {
  return html.replace('<div id="root"></div>', `<div id="root">${markup}</div>`);
}

async function renderPages(routeList) {
  // Keep the generated entry inside the project so Node can resolve react etc.
  // from frontend/node_modules (a /tmp entry cannot).
  const tmpDir = path.join(ROOT, "node_modules", ".cache", "testify-prerender");
  fs.mkdirSync(tmpDir, { recursive: true });
  const entryPath = path.join(tmpDir, `entry-${process.pid}.jsx`);
  const outPath = path.join(tmpDir, `bundle-${process.pid}.cjs`);
  const imports = routeList
    .map((r) => `import ${r.page} from ${JSON.stringify(path.join(ROOT, "src/pages", `${r.page}.jsx`))};`)
    .join("\n");
  const table = routeList.map((r) => `  ${JSON.stringify(r.path)}: ${r.page},`).join("\n");
  fs.writeFileSync(
    entryPath,
    `import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
${imports}

const PAGES = {
${table}
};

export function render(route) {
  const Page = PAGES[route];
  if (!Page) throw new Error("no page for " + route);
  return renderToStaticMarkup(
    React.createElement(MemoryRouter, { initialEntries: [route] }, React.createElement(Page)),
  );
}
`,
  );

  await esbuild.build({
    entryPoints: [entryPath],
    outfile: outPath,
    bundle: true,
    platform: "node",
    // CJS: several React-adjacent packages still call require("util") internally,
    // which esbuild cannot shim in an ESM bundle.
    format: "cjs",
    target: "node18",
    jsx: "automatic",
    alias: { "@": path.join(ROOT, "src") },
    loader: { ".css": "empty", ".svg": "text", ".png": "dataurl" },
    define: { "process.env.NODE_ENV": '"production"' },
    logLevel: "silent",
  });
  return import(pathToFileURL(outPath).href);
}

async function main() {
  const indexPath = path.join(BUILD, "index.html");
  if (!fs.existsSync(indexPath)) {
    console.error("[prerender] build/index.html missing — run `craco build` first.");
    process.exit(1);
  }
  const template = fs.readFileSync(indexPath, "utf8");

  let renderer = null;
  try {
    renderer = await renderPages(ROUTES);
  } catch (err) {
    console.warn(`[prerender] could not bundle pages, writing head-only shells: ${err.message}`);
  }

  for (const route of ROUTES) {
    let markup = "";
    if (renderer) {
      try {
        markup = renderer.render(route.path);
      } catch (err) {
        console.warn(`[prerender] ${route.path} failed to render: ${err.message}`);
      }
    }
    const html = withMarkup(
      withHead(template, {
        title: route.title,
        description: route.description,
        url: `${SITE}${route.path === "/" ? "/" : route.path}`,
        jsonLd: route.jsonLd,
      }),
      markup,
    );
    const outDir = route.path === "/" ? BUILD : path.join(BUILD, route.path.slice(1));
    fs.mkdirSync(outDir, { recursive: true });
    fs.writeFileSync(path.join(outDir, "index.html"), html);
    console.log(`[prerender] ${route.path.padEnd(9)} ${(markup.length / 1024).toFixed(1)} KB of markup`);
  }

  // Real 404 for unknown paths (Vercel serves build/404.html with a 404 status).
  const notFoundHtml = withMarkup(
    withHead(template, {
      title: NOT_FOUND.title,
      description: NOT_FOUND.description,
      url: `${SITE}/404`,
      robots: "noindex",
    }),
    `<main style="min-height:70vh;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;font-family:system-ui,sans-serif;background:#0a0a0a;color:#fafafa;padding:40px">
      <p style="letter-spacing:.2em;text-transform:uppercase;font-size:12px;color:#ff5722;margin:0 0 12px">404</p>
      <h1 style="font-size:32px;margin:0 0 12px">This page doesn't exist</h1>
      <p style="color:#a3a3a3;margin:0 0 24px">The link may be broken, or the page may have moved.</p>
      <a href="/" style="background:#ff5722;color:#fff;text-decoration:none;padding:12px 22px;border-radius:10px;font-weight:600">Back to Testify</a>
    </main>`,
  );
  fs.writeFileSync(path.join(BUILD, "404.html"), notFoundHtml);

  const robots = `# Testify
User-agent: *
Allow: /
Disallow: /dashboard
Disallow: /onboarding
Disallow: /embed/
Disallow: /payment/
Disallow: /reset-password
Disallow: /forgot-password

Sitemap: ${SITE}/sitemap.xml
`;
  fs.writeFileSync(path.join(BUILD, "robots.txt"), robots);

  const today = new Date().toISOString().slice(0, 10);
  const urls = ROUTES.map(
    (r) => `  <url>
    <loc>${SITE}${r.path}</loc>
    <lastmod>${today}</lastmod>
    <changefreq>${r.changefreq}</changefreq>
    <priority>${r.priority}</priority>
  </url>`,
  ).join("\n");
  fs.writeFileSync(
    path.join(BUILD, "sitemap.xml"),
    `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${urls}
</urlset>
`,
  );

  console.log("[prerender] wrote 404.html, robots.txt, sitemap.xml");
}

main().catch((err) => {
  console.error("[prerender] failed:", err);
  process.exit(1);
});
