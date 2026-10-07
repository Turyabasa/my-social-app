---
name: Social App Feature
description: Implement a requested feature or fix using this project's existing architecture and conventions.
argument-hint: Describe the feature or bug to work on.
agent: agent
---

Implement the requested change in this repository: ${input:task:Describe the feature or bug}

## Project Context

- This is an X/Twitter-style social app. Read [README.md](../../README.md) for routes, local setup, and production deployment details.
- Backend: Python 3.12, FastAPI, async SQLAlchemy 2, PostgreSQL, Alembic, and pytest under `backend/`.
- Frontend: Next.js App Router, TypeScript, Tailwind, and TanStack Query under `frontend/`.
- Authentication uses JWTs in httpOnly cookies. The browser sends API requests to same-origin `/api/*`; Next.js rewrites them to FastAPI. WebSockets connect directly to FastAPI using a short-lived token.
- Production runs on Vercel + Render + Neon. Environment variable names and public endpoints are documented in the README; never read secrets into chat, commit them, or include them in generated output.
- Production deploys are controlled by `.github/workflows/ci.yml`: pull requests run checks only, and pushes to `main` deploy only after backend and frontend checks pass. Keep Render auto-deploy disabled and use GitHub Actions secrets for deploy credentials.
- Production Neon already contains 100 `demo_seed_####` accounts and 100 `#DemoData` posts. Do not duplicate, modify, or delete production data unless the task explicitly requests it.

## Working Rules

1. Inspect the owning code path and its neighboring tests before editing. State a local hypothesis and a focused check for behavioral changes.
2. Follow existing abstractions and naming. Keep changes scoped; add or update migrations when schema changes require them.
3. Preserve API contracts, cookie behavior, authorization checks, and post validation (1-280 characters). Add tests for changed behavior using existing test fixtures.
4. Never point tests, seed scripts, or exploratory writes at the production database. Do not seed production or deploy unless the user explicitly asks.
5. After the first edit, run the narrowest relevant check before making further changes. Then run required project checks when appropriate: `cd backend && pytest -q`; `cd frontend && npx eslint src && npm run build`.
6. Report changed files, verification results, and any risks or checks that could not be run. Do not claim deployment or test success without fresh output.