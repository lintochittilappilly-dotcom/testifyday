import { applyWallMeta, wallMetadata } from "../../../lib/wallMeta.mjs";
import { withHead } from "../../../lib/headTags.mjs";

const SHELL = `<!doctype html><html><head>
  <meta property="og:title" content="Testify — Testimonials, minus the awkward ask" />
  <meta property="og:image" content="https://www.testify.day/brand/testify-og-image.png" />
  <meta name="twitter:card" content="summary_large_image" />
  <title>Testify — Customer Testimonials Made Simple</title>
</head><body><div id="root"></div></body></html>`;

const WALL = {
  business_name: "Northwind Studio",
  slug: "northwind",
  count: 12,
  og_image: "/api/og/wall/northwind.png",
};

describe("wallMetadata", () => {
  it("names the business, the count, and the canonical wall URL", () => {
    const meta = wallMetadata(WALL, { origin: "https://www.testify.day", slug: "northwind" });
    expect(meta.title).toBe("Northwind Studio — Wall of Love");
    expect(meta.description).toContain("12 customers");
    expect(meta.description).toContain("Northwind Studio");
    expect(meta.url).toBe("https://www.testify.day/wall/northwind");
    expect(meta.image).toBe("https://www.testify.day/api/og/wall/northwind.png");
  });

  it("uses singular copy for a single testimonial", () => {
    const meta = wallMetadata({ ...WALL, count: 1 }, { origin: "https://www.testify.day" });
    expect(meta.description).toContain("1 customer says");
  });

  it("falls back to a consistent image path when the API omits og_image", () => {
    const meta = wallMetadata({ business_name: "Acme", count: 3 }, { origin: "https://www.testify.day/", slug: "acme" });
    expect(meta.image).toBe("https://www.testify.day/api/og/wall/acme.png");
  });
});

describe("applyWallMeta", () => {
  const html = applyWallMeta(SHELL, WALL, { origin: "https://www.testify.day", slug: "northwind" });

  it("rewrites the shell instead of appending duplicates", () => {
    expect(html.match(/property="og:title"/g)).toHaveLength(1);
    expect(html.match(/property="og:image"/g)).toHaveLength(1);
    expect(html.match(/<title>/g)).toHaveLength(1);
    expect(html).toContain('content="Northwind Studio — Wall of Love"');
    expect(html).not.toContain("minus the awkward ask");
  });

  it("adds canonical, twitter and a 1200x630 image declaration", () => {
    expect(html).toContain('<link rel="canonical" href="https://www.testify.day/wall/northwind" />');
    expect(html).toContain('name="twitter:title" content="Northwind Studio — Wall of Love"');
    expect(html).toContain('property="og:image:width" content="1200"');
    expect(html).toContain('property="og:image:height" content="630"');
  });

  it("leaves the shell untouched when the wall is missing", () => {
    expect(applyWallMeta(SHELL, null, {})).toBe(SHELL);
  });

  it("escapes quotes so a business name cannot break out of the tag", () => {
    const html = withHead(SHELL, { title: 'Bad "quoted" <name>', description: "x" });
    expect(html).toContain("&quot;quoted&quot;");
    expect(html).not.toContain('content="Bad "quoted"');
  });
});
