# URL Shortner

---

## Description 📝

A URL Shortner API that solves the inconvinience of memorizing long URLs by providing a short code for users to access their desired websites and webpages.

---

## Technology Stack 🛠️

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Pydantic](https://img.shields.io/badge/Pydantic-2C3E50?style=for-the-badge&logo=pydantic&logoColor=white)
![Postgres](https://img.shields.io/badge/Postgres-336791?style=for-the-badge&logo=postgresql&logoColor=white)
![Celery](https://img.shields.io/badge/Celery-37814A?style=for-the-badge&logo=celery&logoColor=white)
![RabbitMQ](https://img.shields.io/badge/RabbitMQ-FF6600?style=for-the-badge&logo=rabbitmq&logoColor=white)
![Sentry](https://img.shields.io/badge/Sentry-362D59?style=for-the-badge&logo=sentry&logoColor=white)

---

## Features ✨

- Sign in using Google account
- Sign up with email and password with OTP-based email verification
- Shorten a url with optional custom slug
- Create and manage custom slugs
- View URL analytics

## Technical Highlights ⚙️

- Redis Counter to track URL clicks. It provides atomicity and fast increment, avoiding the overheads of using a traditional database.
- Background Workers to handle email processing and clicks flush for seamless user experience
- Celery Flower to monitor failed tasks and retries
- Redis-cached user lookups on authenticated requests, avoiding a Postgres round trip per request. Cache entries invalidate immediately on logout, deactivation, or account deletion so revoked access takes effect right away.
- Atomic upsert (`INSERT ... ON CONFLICT`) for URL creation instead of a check-then-insert, removing a race condition and an extra round trip under concurrent writes.
- Load tested with k6 using constant-arrival-rate scenarios to find real throughput ceilings instead of assuming capacity.

---

[Live API Here](https://url-shortner-1-9opz.onrender.com/docs)

---

## Steps to Run Application 🚀

### Prerequisites 📋

- Install Python 3.14. [Installation link](https://www.python.org/downloads/)
- Install uv (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Install Redis [Installation link](https://redis.io/downloads/#stack)
- Install and set up RabbitMQ on your machine. [Installation link](https://www.rabbitmq.com/docs/download)
- Install and set up PgAdmin. [Installation link](https://www.pgadmin.org/download/)

---

#### Clone the repository:
```bash
git clone `https://github.com/Samson23-ux/url-shortner`
```

#### Navigate to the project directory:
```bash
cd "url-shortner"
```

#### Create and activate virtual environment:

**Install dependencies:**
```bash
uv sync
```

- **Copy and configure variables:**
```bash
cp .env.example .env
```

#### Create API database using PgAdmin.

#### Start Redis Server

#### Start Celery worker:
```bash
uv run celery -A app.task.celery_app worker -l info -P gevent
```

#### Start Celery beat:
```bash
uv run celery -A app.task.celery_app beat -l info
```

#### Start Flower (Optional) for Task monitoring:
```bash
uv run celery -A app.task.celery_app flower --port=5555
```

#### Run the application:
```bash
uv run uvicorn app.main:app --reload
```

#### Test API endpoints via docs:
Open your browser and navigate to [http://localhost:8000/docs](http://localhost:8000/docs).

---

## Testing 🧪

### Run tests:
```bash
uv run pytest
```

### Run a particular test module:
```bash
uv run pytest tests/<preferred_test_module.py>
```

### CI/CD

GitHub Actions runs on every PR to `main`:
- Linting (`ruff`)
- Runs tests (`pytest`)

---

## Performance & Known Limitations 📊

Load tested with [k6](https://k6.io/) using `constant-arrival-rate` — a controlled req/s rather than an emergent one driven by VU count (see `load-tests/*.js` for full methodology notes). Measured in two environments: local (WSL2 + Docker containers for Postgres/Redis/RabbitMQ) and deployed (Render free tier: 0.1 CPU / 512MB, single instance, no autoscaling; Postgres via Supabase and Redis via Upstash, both in eu-central-1/Frankfurt).

### Local

| Path | Throughput | p95 | p99 | Errors |
|---|---|---|---|---|
| Write only | 80 req/s | 139ms | — | 0% |
| Write only | 100 req/s | 210ms | — | 0.21% |
| Redirect only | 80 req/s | 25ms | 287ms | 0% |
| Redirect spike | ≥300 req/s | — | — | fails |
| Combined (write 40/s + read 50/s, 200/s spike) | 90 req/s sustained | create 128ms / redirect 83ms | redirect 185ms | 0.24% / 0% |

Write throughput holds cleanly to ~80 req/s; latency and error rate both turn over between 80 and 100 req/s. Redirects stay under 30ms until several hundred req/s.

### Deployed (Render free tier)

| Path | Throughput | p95 | p99 | Errors |
|---|---|---|---|---|
| Write only | 5 req/s | 264ms-1.17s | — | 0% |
| Write only | 10 req/s | 2.15s-5.87s | — | 0% |
| Redirect only | 10 req/s sustained / 15 req/s spike | 194-211ms | 267-494ms | 0% |
| Combined (write 5/s + read 5/s, 10/s spike) | ~10 req/s | 328ms-798ms | 577ms-1.77s | 0% |
| Combined (write 5/s + read 10/s, 15/s spike) | ~20 req/s peak | 10s | 10s | 95.65%-96.43% |

Redirect latency here is flat across rates — ~200ms regardless of load — because it's dominated by network round-trip to Frankfurt rather than app processing time (confirmed via Upstash's Service Time Latency dashboard, which shows ~0ms of that as actual Redis processing).

Combined read+write load at a fixed ~10 req/s produced p95s ranging from 328ms to 798ms across separate runs at the identical rate, all with 0% request failures. Same input, different output — a fixed throughput number doesn't predict latency here the way it does locally, most likely due to CPU scheduling on a shared 0.1-vCPU instance (Render doesn't expose CPU metrics on free-tier instances to confirm directly). Past roughly 15-20 req/s aggregate, the instance stops draining its request queue and the majority of requests time out.

---

## Troubleshooting 🔧

### Database Connection Issues

**Problem**: `could not connect to server`

**Solution**:
- Verify PostgreSQL is running: `pg_isready`
- Check database URL in `.env`
- Ensure database and user exist: `psql -l -U postgres`

### Migration Issues

**Problem**: Migration fails to apply

**Solution**:
```bash
# Check alembic version
alembic current

# Downgrade to previous version
alembic downgrade -1

# Review migration files in alembic/versions/
```

### Virtual Environment Issues

**Problem**: `ModuleNotFoundError` after installing dependencies

**Solution**:
- Ensure virtual environment is activated
- Reinstall dependencies: `pip install -r requirements.txt --force-reinstall`

### Redis Issues

**Problem**: Request fail when interacting with redis

**Solution**:
- Start Server from wsl terminal
