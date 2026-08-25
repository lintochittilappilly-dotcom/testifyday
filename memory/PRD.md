# Testify — PRD & Migration Log

## Original problem statement
User has a web app in a GitHub repo (`lintnz/testifyown`). They want to deploy it with their **own credentials** — frontend on **Vercel** (`www.testify.day`) and backend on **Railway** (`www.backend.testify.day`) — with MongoDB Atlas. All Emergent APIs, code, and backgrounds must be removed. The user deploys themselves; agent only prepares code, config, env vars, domains, and fixes issues.

## Architecture
- Backend: FastAPI + Motor (MongoDB Atlas) on Railway
- Frontend: React (CRA + craco) on Vercel
- Storage: AWS S3 via boto3 for testimonial images/videos
- Auth: JWT + Google Identity Services (standard Google OAuth)
- Payments: Stripe subscriptions with webhook
- Email: Resend, Captcha: reCAPTCHA v2

## Emergent-code removed (Jan 2026)
- `backend/storage.py` → boto3 + AWS S3 (was `integrations.emergentagent.com/objstore`)
- `backend/auth.py` → `google.oauth2.id_token.verify_oauth2_token` (was `demobackend.emergentagent.com`)
- `backend/server.py` → removed `sk_test_emergent` fallback; `CORS_ORIGINS` env-driven; added `/health`
- `backend/email_service.py` → prefer env vars
- `backend/requirements.txt` → removed `emergentintegrations`, emergent litellm wheel
- `backend/setup_stripe.py` → renamed emergent metadata keys
- `frontend/src/components/GoogleButton.jsx` → Google Identity Services with `REACT_APP_GOOGLE_CLIENT_ID`
- `frontend/src/context/AuthContext.js` + `App.js` → credential-based Google auth, removed session_id callback
- `frontend/craco.config.js` + `package.json` → removed `@emergentbase/visual-edits`
- `frontend/public/index.html` → removed Emergent script + PostHog init, rebranded

## Added deployment files
- `backend/Procfile`, `backend/railway.toml`, `backend/runtime.txt`, `backend/.env.example`
- `frontend/vercel.json`, `frontend/.env.example`
- `README.md` — full Railway + Vercel deploy guide
- `.gitignore` — protects `.env` files

## What the user still needs before deploying
- Google OAuth: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `REACT_APP_GOOGLE_CLIENT_ID`
- Stripe: `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` (after creating webhook)
- reCAPTCHA: `RECAPTCHA_SITE_KEY`, `RECAPTCHA_SECRET_KEY`
- `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `JWT_SECRET` (64+ char random)
- `S3_BUCKET_NAME`, `AWS_REGION`, verified Resend sender email

## Backlog
- P1: E2E smoke test after live deploy (register, login, S3 upload, testimonial submit, Stripe checkout)
- P2: Cloudinary/R2 alternative if S3 egress becomes costly
