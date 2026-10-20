# ShelterED

Offline-first education hub for air-raid shelters. Lessons, quizzes and class roll call work without internet and sync to the cloud when the network is back.

Student team project, demo on 12 December 2026. Full spec: [`docs/tz.md`](docs/tz.md) (Ukrainian).

## Repository structure

```
frontend/   PWA: React, TypeScript, Vite, Tailwind CSS
backend/    Cloud API: FastAPI, PostgreSQL, Celery + Redis
docs/       Spec and DB schema
```

`Another Folders` are planned.

## Getting started

**Frontend** (Node.js, run in `frontend/`):

```
npm install
npm run dev
npm run build
npm run lint
```

**Backend** (Python 3.13+, Docker, run in `backend/`; details in [`backend/README.md`](backend/README.md)):

```
alembic upgrade head
docker compose -f docker-compose.dev.yml up -d --wait test-db
pytest
ruff check . && ruff format --check .
```

Secrets live in `.env` (never committed). See `backend/.env.example`.

## Offline-first principles

1. UI reads from local storage and never waits for the network.
2. Clients generate UUIDs.
3. Write requests are idempotent.
4. Every student action is an event stored in an IndexedDB outbox until the server confirms it.
5. Sync in batches: shelter local server first, then the cloud.
6. Never lose data (answers, roll call) on network loss or restart.
7. Fallback without any network: progress via QR code.

## Workflow

- Pull with `git pull --rebase` before pushing to `main`.
- Run the linter and tests of your folder before a PR; do not merge on a red pipeline.
