# Testify — Test Credentials

Local dev + testing agent credentials. Never use these in production.

## Admin
- Email: `admin@testify.day`
- Password: `AdminTest123!`
- Sourced from `ADMIN_EMAIL` / `ADMIN_PASSWORD` env vars — auto-seeded at backend startup.

## Regular test users
Registered on the fly by the pytest suite as `test_*@example.com` with password `TestPass123!`. All are cleaned up by the session-scoped fixture after each run.

## Environment for testing
- `MONGO_URL=mongodb://localhost:27017`
- `DB_NAME=testify_smoke`
- `JWT_SECRET=<any long random>`
- `CORS_ORIGINS=http://localhost:3000`
- `RECAPTCHA_SECRET_KEY=` (blank — captcha bypass in dev)
- `STRIPE_SECRET_KEY=` (blank — payment tests skipped)

## Production
Production admin credentials are set by the user in Railway environment variables and are not stored here.
