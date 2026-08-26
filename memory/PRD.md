# Testify — PRD & Migration Log

## Original problem statement
User has a web app in a GitHub repo (`lintnz/testifyown`). They want to deploy it with their **own credentials** — frontend on **Vercel** (`www.testify.day`) and backend on **Railway** (`www.backend.testify.day`) — with MongoDB Atlas. All Emergent APIs, code, and branding must be removed. The user deploys themselves; agent only prepares code, config, env vars, domains, and fixes issues.

## Architecture
- Backend: FastAPI + Motor (MongoDB Atlas) on Railway
- Frontend: React (CRA + craco) on Vercel
- Storage: AWS S3 via boto3 for testimonial images/videos
- Auth: JWT + Google Identity Services
- Payments: Stripe subscriptions (auto-apply coupon + allow customer promo codes)
- Email: Resend, Captcha: reCAPTCHA v2

## Iteration 1 — Emergent removal (Jan 2026)
- `storage.py` → boto3 + AWS S3
- `auth.py` → `id_token.verify_oauth2_token`
- `server.py` → removed `sk_test_emergent`, CORS env-driven, added `/health`
- `email_service.py` → prefer env vars
- `requirements.txt` → removed `emergentintegrations` and emergent litellm wheel
- `setup_stripe.py` → renamed emergent metadata keys
- `GoogleButton.jsx` → Google Identity Services
- `AuthContext.js` + `App.js` → credential-based Google auth
- `craco.config.js` + `package.json` → removed `@emergentbase/visual-edits`
- `index.html` → removed Emergent script + PostHog, rebranded
- Added: `Procfile`, `railway.toml`, `runtime.txt`, `vercel.json`, `.env.example`, `.gitignore`, deploy `README.md`

## Iteration 2 — Plans, coupons, image testimonials (Jan 2026)
- **Backend**
  - `settings_store.py` — DEFAULT_PLANS + `get_plans()` merges admin overrides; extended settings with `checkout_coupon_id`, `promo_banner`, `plans_override`
  - `models.py` — `TestimonialSubmit`/`TestimonialUpdate` get `image_url`; `SettingsInput` extended
  - `server.py`:
    - `/api/plans` reads from `get_plans()`
    - `/api/public/config` returns `promo_banner`
    - Submit accepts `image_url`; rejects video on Free plan; Free plan cap tightened to **5** testimonials
    - Stripe Checkout: auto-apply admin coupon; `allow_promotion_codes=true` when no coupon set
    - `_public_testimonial` returns `image_url` (fix)
    - `_public_collection` gates `allow_video` by workspace plan (fix)
    - `/api/health` route added (fix)
    - `require_admin` / `public_user` fail-closed on missing `ADMIN_EMAIL` (fix)
- **Frontend**
  - `Billing.jsx` — removed "Test mode 4242…" line
  - `PublicCollection.jsx` — image upload mode + 5 MB cap
  - `Landing.jsx` — pulls plans from `/api/plans` + promo banner
  - `AdminIntegrations.jsx` — plan/pricing/features editor + Sale banner + coupon ID
  - `Testimonials.jsx` / `TestimonialDetail.jsx` / `TestimonialWidget.jsx` — render image_url

## Test coverage
- Iteration 1: N/A (pre-runtime prep)
- Iteration 2: 35/35 backend tests green (`/app/backend/tests/`). Frontend not tested (no `.env`).

## Backlog
- P2: typed `PlanOverride` validation (currently plans_override is `Dict[str, Any]`)
- P2: move public-submit rate limiter to Mongo/Redis for multi-worker
- P2: split `server.py` (~1361 lines) into routers
- P2: Stripe/Google end-to-end tests once keys are configured in Railway

## Test credentials
See `/app/memory/test_credentials.md`.
