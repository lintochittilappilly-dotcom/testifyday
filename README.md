# Testify — Deployment Guide

Testimonial collection SaaS.
Stack: **FastAPI + MongoDB Atlas** (backend on **Railway**) · **React + CRA/craco** (frontend on **Vercel**).

Domains:
- Frontend → `https://www.testify.day`
- Backend → `https://www.backend.testify.day`

---

## 1. Prerequisites (accounts / keys)

| Service | What you need |
| --- | --- |
| MongoDB Atlas | Connection string (SRV URI) + database name |
| Google Cloud → OAuth Client ID (Web) | Client ID + Client Secret. Add `https://www.testify.day` to **Authorized JavaScript origins** and **Authorized redirect URIs** |
| Resend | API key + verified sender (e.g. `no-reply@testify.day`) |
| Stripe | Secret key, webhook secret, and prices set up (run `python setup_stripe.py` once locally) |
| Google reCAPTCHA v2 | Site key + secret key |
| AWS S3 | Bucket, access key ID, secret access key, region |

Optional: Google Places API key (only if you want to import Google reviews — add it later from Admin → Settings).

---

## 2. Backend — deploy to Railway

1. Push this repo to GitHub (private is fine).
2. Go to https://railway.app → **New Project → Deploy from GitHub**.
3. Pick this repo. In **Settings → Root Directory**, set: `backend`.
4. In **Settings → Networking**, add a public domain and later set the custom domain `www.backend.testify.day`.
   - Railway will show CNAME records — add them at your DNS provider (Cloudflare / registrar). Once verified, SSL is automatic.
5. In **Settings → Variables**, paste every variable from `backend/.env.example`, filling real values:

```
MONGO_URL=mongodb+srv://...
DB_NAME=testifyday
JWT_SECRET=<generate a 64+ char random string>
ADMIN_EMAIL=you@testify.day
ADMIN_PASSWORD=<strong password>

GOOGLE_CLIENT_ID=xxxxx.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=xxx

CORS_ORIGINS=https://www.testify.day,https://testify.day

RESEND_API_KEY=re_xxx
SENDER_EMAIL=no-reply@testify.day

STRIPE_SECRET_KEY=sk_live_xxx
STRIPE_WEBHOOK_SECRET=whsec_xxx

RECAPTCHA_SITE_KEY=xxx
RECAPTCHA_SECRET_KEY=xxx

AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=xxx
AWS_REGION=us-east-1
S3_BUCKET_NAME=testify-uploads
# Optional: leave blank for API-proxied /api/media/... URLs.
S3_PUBLIC_URL=
```

6. Railway will build automatically (uses `railway.toml` + `Procfile`). First deploy takes ~2 min.
7. Test: `curl https://www.backend.testify.day/health` → `{"status":"ok"}`.

### One-time Stripe catalog setup

From your laptop with the same env vars in a local `backend/.env`:

```bash
cd backend
pip install -r requirements.txt
python setup_stripe.py
```

Then in Stripe Dashboard → Developers → Webhooks, add endpoint:
`https://www.backend.testify.day/api/stripe/webhook`
Events: `checkout.session.completed`, `customer.subscription.deleted`.
Copy the signing secret → paste into Railway `STRIPE_WEBHOOK_SECRET`.

---

## 3. Frontend — deploy to Vercel

1. Same GitHub repo → https://vercel.com → **Add New → Project**.
2. **Root Directory**: `frontend`.
3. **Framework preset**: Create React App (auto-detected).
4. **Build Command**: `yarn build` · **Output Directory**: `build`.
5. **Environment Variables**:

```
REACT_APP_BACKEND_URL=https://www.backend.testify.day
REACT_APP_GOOGLE_CLIENT_ID=xxxxx.apps.googleusercontent.com
```

6. Deploy. Then in **Settings → Domains** add `www.testify.day` and `testify.day` (redirect apex to www).

---

## 4. AWS S3 bucket — quick setup

1. Create bucket `testify-uploads` (region matching `AWS_REGION`).
2. Turn off **Block all public access** (only if you want direct public URLs). Then attach a bucket policy allowing `s3:GetObject` on `arn:aws:s3:::testify-uploads/*` for principal `"*"`.
3. Enable CORS on the bucket:

```json
[
  {
    "AllowedOrigins": ["https://www.testify.day"],
    "AllowedMethods": ["GET", "PUT", "POST"],
    "AllowedHeaders": ["*"],
    "ExposeHeaders": ["ETag"]
  }
]
```

4. If bucket is public, set `S3_PUBLIC_URL=https://testify-uploads.s3.<region>.amazonaws.com` in Railway (or a CloudFront domain). If left blank, files are served through the backend proxy at `/api/media/<path>` (works, but uses Railway egress).

---

## 5. Google OAuth setup

At https://console.cloud.google.com/apis/credentials:

- Create OAuth Client → Web application
- **Authorized JavaScript origins**: `https://www.testify.day`
- **Authorized redirect URIs**: `https://www.testify.day`
- Copy Client ID → paste into both Railway (`GOOGLE_CLIENT_ID`) and Vercel (`REACT_APP_GOOGLE_CLIENT_ID`).

---

## 6. Custom domain DNS (at your registrar / Cloudflare)

| Record | Host | Value |
| --- | --- | --- |
| CNAME | `www` | `cname.vercel-dns.com.` |
| A / ALIAS | `@` (apex `testify.day`) | Vercel-provided IP or use Vercel apex config |
| CNAME | `www.backend` | (whatever Railway shows in Settings → Networking) |

Wait 5–15 min for propagation, both platforms auto-issue SSL.

---

## 7. First login

Once the backend boots on Railway, the admin user is auto-seeded from `ADMIN_EMAIL` / `ADMIN_PASSWORD`. Log in at `https://www.testify.day/login`.

---

## Local development

```bash
# backend
cd backend
cp .env.example .env  # fill values
pip install -r requirements.txt
uvicorn server:app --reload --port 8001

# frontend
cd frontend
cp .env.example .env  # set REACT_APP_BACKEND_URL=http://localhost:8001
yarn install
yarn start
```
