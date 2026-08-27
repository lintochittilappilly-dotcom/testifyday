# Testify Brand Pack

Everything you need to use Testify consistently across Stripe, socials, decks, and press.

## Colors

| Token | Hex | Use |
| --- | --- | --- |
| Ember Orange | `#ff5722` | Primary — logos, CTAs, highlights |
| Deep Black | `#0a0a0a` | App background, dark surfaces |
| Warm Charcoal | `#151515` | Cards, elevated surfaces |
| White | `#ffffff` | Body text on dark |
| Neutral 400 | `#a3a3a3` | Muted text |

## Typography
- Body & UI: **Inter** (400 / 500 / 600 / 700)
- The wordmark in this pack is custom — use the `testify-wordmark.png` as an image when you need it standalone.

## Files in this folder

| File | Dimensions | Use |
| --- | --- | --- |
| `testify-logo-mark.png` | 512×512 (transparent) | Favicon, app icon, avatars, footer marks |
| `testify-wordmark.png` | 1200×400 (transparent) | Marketing headers, footers, decks |
| `testify-plan-pro-stripe.jpg` | 768×768 (~62 KB) | **Upload to Stripe → Products → Testify Pro → Image** |
| `testify-plan-pro-stripe.png` | 768×768 | Higher-quality version if you prefer PNG on Stripe |
| `testify-plan-business-stripe.jpg` | 768×768 (~84 KB) | **Upload to Stripe → Products → Testify Business → Image** |
| `testify-plan-business-stripe.png` | 768×768 | PNG version |
| `testify-og-image.png` | 1200×630 | Facebook / LinkedIn / Slack link previews (already wired into `index.html`) |
| `testify-instagram-square.png` | 1080×1080 | Instagram feed, LinkedIn feed post, Twitter square |
| `testify-twitter-header.png` | 1500×500 | Twitter / X profile header |
| `testify-linkedin-banner.png` | 1584×396 | LinkedIn company / personal page cover |

## Publishing checklist

- [ ] Push this repo → files auto-serve at `https://www.testify.day/brand/*` after the next Vercel deploy
- [ ] Stripe Dashboard → Products → **Testify Pro** → Edit → upload `testify-plan-pro-stripe.jpg`
- [ ] Stripe Dashboard → Products → **Testify Business** → Edit → upload `testify-plan-business-stripe.jpg`
- [ ] Twitter/X → Settings → Profile → upload `testify-twitter-header.png`
- [ ] LinkedIn → Company page → Edit page → upload `testify-linkedin-banner.png`
- [ ] Instagram → post `testify-instagram-square.png` with a short caption
- [ ] Share `https://www.testify.day` on any chat → the OG image will now show up automatically

## Regenerating the pack

Prompts and script live in `/scripts/generate_brand_pack.py`. Edit any prompt in `ASSETS`, then:

```
cd /app
python scripts/generate_brand_pack.py
```

Uses Gemini Nano Banana via `EMERGENT_LLM_KEY` (already in `backend/.env`).
