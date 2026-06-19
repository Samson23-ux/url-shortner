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

- Redis filter to check for url and slug existence. A redis filter is a space efficient probablistic data structure that guarantees inexistence of an item in a set but comes with some false positive as data size increases. Its usage is a trade-off between fast, space efficient checks and precision.
- Redis Counter to track URL clicks. It provides atomicity and fast increment, avoiding the overheads of using a traditional database.
- Background Workers to handle email processing and clicks flush for seamless user experience
- Celery Flower to monitor failed tasks and retries

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
