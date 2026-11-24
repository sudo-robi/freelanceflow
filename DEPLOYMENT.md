# Deployment

## Local development

Backend:

```bash
cd backend
.venv/bin/python -m pip install -e '.[test]'
.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Docker:

```bash
docker compose up --build
```

Set a strong PostgreSQL password and set `DATABASE_URL` to the production database. Do not expose the PostgreSQL port in production.

Docker Compose requires `POSTGRES_USER` and `POSTGRES_PASSWORD` in the environment or `.env` file. Use a unique, high-entropy password and restrict API CORS origins with `CORS_ALLOWED_ORIGINS`.

## Quality gates

CI runs backend pytest, frontend Vitest/build, and Cargo tests. Browser and funded-wallet checks require separate deployment credentials and are not part of credential-free CI.
