import { useEffect } from "react";

function upsert(selector, attr, key, value, content) {
  if (!content) return;
  let el = document.head.querySelector(selector);
  if (!el) {
    el = document.createElement(attr === "name" ? "meta" : "meta");
    el.setAttribute(key, value);
    document.head.appendChild(el);
  }
  el.setAttribute("content", content);
}

function setLink(rel, href) {
  if (!href) return;
  let el = document.head.querySelector(`link[rel="${rel}"]`);
  if (!el) { el = document.createElement("link"); el.setAttribute("rel", rel); document.head.appendChild(el); }
  el.setAttribute("href", href);
}

/**
 * Sets SEO + Open Graph + Twitter meta tags for public pages (SPA-rendered).
 */
export default function useMeta({ title, description, image, url, robots }) {
  useEffect(() => {
    if (title) document.title = title;
    upsert('meta[name="description"]', "name", "name", "description", description);
    upsert('meta[property="og:title"]', "property", "property", "og:title", title);
    upsert('meta[property="og:description"]', "property", "property", "og:description", description);
    upsert('meta[property="og:type"]', "property", "property", "og:type", "website");
    upsert('meta[property="og:url"]', "property", "property", "og:url", url);
    upsert('meta[property="og:image"]', "property", "property", "og:image", image);
    upsert('meta[name="twitter:card"]', "name", "name", "twitter:card", image ? "summary_large_image" : "summary");
    upsert('meta[name="twitter:title"]', "name", "name", "twitter:title", title);
    upsert('meta[name="twitter:description"]', "name", "name", "twitter:description", description);
    upsert('meta[name="twitter:image"]', "name", "name", "twitter:image", image);
    upsert('meta[name="robots"]', "name", "name", "robots", robots);
    setLink("canonical", url);
  }, [title, description, image, url, robots]);
}
