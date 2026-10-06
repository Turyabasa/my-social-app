# Social — an X/Twitter-style app

Register, post (280 chars), follow people, get a timeline of the people you follow, like and reply to posts, browse profiles, and get live notifications when someone likes, replies to or follows you.

| Feed (light) | Profile (dark) |
| --- | --- |
| ![Feed](docs/feed-light.png) | ![Profile](docs/profile-dark.png) |

## Tech stack

| Layer | Tech |
| --- | --- |
| Backend | Python 3.12, FastAPI, SQLAlchemy 2 (async) + asyncpg, Alembic, Pydantic v2 |
| Auth | JWT (python-jose) in an httpOnly cookie, bcrypt password hashing (passlib) |
| Real-time | WebSocket (Starlette) for like / reply / follow notifications |
| Database | PostgreSQL 16 (Neon in production) |
| Frontend | Next.js 15 (App Router), TypeScript, Tailwind CSS v4, TanStack Query v5 |
| Infra | Docker Compose locally; Render (API) + Vercel (web) + Neon (DB) in production |

## Run it locally (Docker)

```bash
cp .env.example .env        # then replace POSTGRES_PASSWORD and SECRET_KEY
docker compose up --build
```

- App: http://localhost:3000
- API docs (Swagger): http://localhost:8000/docs

Migrations run automatically when the backend container starts. If ports 3000/8000 are taken, set `FRONTEND_PORT` / `BACKEND_PORT` in `.env`.

## Run it locally (without Docker)

Requires Python 3.12, Node 22+, and a running PostgreSQL.

```bash
# Backend
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env        # point DATABASE_URL at your database, set SECRET_KEY
createdb social
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# Frontend (second terminal)
cd frontend
npm install
npm run dev                 # http://localhost:3000, proxies /api to http://localhost:8000
```

Set `BACKEND_URL` / `NEXT_PUBLIC_WS_URL` in `frontend/.env.local` if the backend is not on `localhost:8000`.

## Tests

```bash
cd backend
createdb social_test
TEST_DATABASE_URL=postgresql+asyncpg://USER@localhost:5432/social_test pytest
```

CI (`.github/workflows/ci.yml`) runs on every push to `main` and on pull requests. The backend job runs migrations up, `alembic check` and down, then pytest against Postgres 16. The frontend job runs ESLint and `next build`, which includes type-checking.

## How it fits together

```
Browser ──/api/*──▶ Next.js (rewrite proxy) ──▶ FastAPI ──▶ PostgreSQL
   └─────── WebSocket (short-lived token) ──────▶ FastAPI /ws/notifications
```

- **Same-origin API.** The browser only calls `/api/*` on the frontend's own domain, and Next.js rewrites those requests to the backend. The auth cookie is therefore first-party, which matters because browsers block third-party cookies between `*.vercel.app` and `*.onrender.com`. The cookie is `httpOnly` and `SameSite=Lax`, plus `Secure` in production.
- **WebSocket auth.** Vercel can't proxy WebSockets, so the browser connects straight to the backend. It first fetches a 2-minute, WebSocket-only token from `GET /api/auth/ws-token`; that token can't be used as a login cookie.
- **Feed query.** `user_id = me OR user_id IN (SELECT following_id FROM follows WHERE follower_id = me)`, newest first, using offset/limit. Like counts, reply counts and `liked_by_me` are computed in the same query, so there's no N+1. The index on `(user_id, created_at)` serves it.

## API

Interactive docs are at `/docs` on the backend. Errors are always JSON: `{"detail": "..."}`. Validation errors (422) also include `errors`.

| Method | Path | Auth | Notes |
| --- | --- | --- | --- |
| POST | `/api/auth/register` | – | `{email, username, password, display_name?}` → 201 + cookie |
| POST | `/api/auth/login` | – | `{email, password}` → 200 + cookie |
| POST | `/api/auth/logout` | – | clears cookie |
| GET | `/api/auth/me` | ✓ | current user |
| GET | `/api/auth/ws-token` | ✓ | short-lived WebSocket token |
| POST | `/api/posts` | ✓ | `{content}` (1–280 chars) → 201 |
| GET | `/api/feed?page&limit` | ✓ | self + followed users |
| GET | `/api/explore?page&limit` | – | everyone's posts |
| GET | `/api/posts/:id` | – | post + replies |
| DELETE | `/api/posts/:id` | owner | 204, or 403 for non-owners |
| POST | `/api/posts/:id/like` | ✓ | toggle: 201 liked / 200 unliked |
| POST | `/api/posts/:id/replies` | ✓ | `{content}` → 201 |
| GET | `/api/users/:username` | – | profile, counts, last 10 posts |
| GET | `/api/users/:username/followers` | – | paginated |
| GET | `/api/users/:username/following` | – | paginated |
| GET | `/api/suggestions` | ✓ | who to follow |
| POST | `/api/follows/:username` | ✓ | 201 (idempotent); 400 on self-follow |
| DELETE | `/api/follows/:username` | ✓ | 204 (idempotent) |
| WS | `/ws/notifications?token=` | token | `{type, actor_username, actor_display_name, post_id}` |

## Deploy (free tiers)

1. **Neon (database).** Create a project and copy the connection string (`postgresql://…?sslmode=require`). The backend converts it for asyncpg automatically. Prefer the direct, non-pooled host.
2. **Render (backend).** Choose New → Blueprint, pick this repo, and `render.yaml` is used. When prompted:
   - `DATABASE_URL`: the Neon string
   - `CORS_ORIGINS`: your Vercel URL

   `SECRET_KEY` is generated for you. Migrations run on every start.
3. **Vercel (frontend).** Import the repo and set **Root Directory** to `frontend`. Add these environment variables:
   - `BACKEND_URL=https://<your-service>.onrender.com`
   - `NEXT_PUBLIC_WS_URL=wss://<your-service>.onrender.com`

   Both are read at build time, so redeploy after changing them.
4. Put the final Vercel URL into Render's `CORS_ORIGINS`.

Free-tier caveats:
- Render's free instances sleep after about 15 minutes idle, so the first request takes around a minute and open WebSockets drop; the client reconnects on its own.
- Notifications are held in the backend's memory, which only works while it runs as a single instance. Running more instances needs Redis or Postgres `LISTEN/NOTIFY`.

## Project layout

```
backend/   FastAPI app (app/), Alembic migrations, tests
frontend/  Next.js app (src/app pages, src/components, src/hooks, src/lib)
docker-compose.yml, render.yaml, .github/workflows/ci.yml
```
