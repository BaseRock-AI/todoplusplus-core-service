# ToDoPlusPlus Core Service

FastAPI + PostgreSQL + Kafka ToDo service with:
- JWT authentication
- Role-based access (`admin`, `user`)
- Delete approval workflow (`user` requests, `admin` approves/rejects)
- Kafka/Jira/Email/Audit flow for todo creation

## Python Version
- Recommended: Python `3.12` (best compatibility across dependencies).
- Also supported: Python `3.11+`.

## Quick Run
Use this when you have already set up the project before (venv, dependencies, `.env` already done).

1. Start infrastructure
```bash
docker compose up -d
```

2. Activate virtual environment
```bash
source .venv/bin/activate
```

3. Run API
```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8081
```

4. Stop when done
```bash
docker compose down
```

## Run First Time
Use this if you are running the project for the first time on your machine.

1. Clone and enter project folder
```bash
git clone <your-repo-url>
cd todoplusplus-core-service
```

2. Start infrastructure (Postgres + Kafka + Zookeeper)
```bash
docker compose up -d
```

3. Create environment config
```bash
cp .env.example .env
```

4. Recreate Python virtual environment (safe even if `.venv` already exists)
```bash
python3.12 -m venv .venv --clear
```
If `python3.12` is not installed, use `python3 -m venv .venv --clear`.

5. Activate virtual environment
```bash
source .venv/bin/activate
```

6. Install dependencies
```bash
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
```

7. Run API
```bash
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8081
```

8. Verify health
```bash
curl http://localhost:8081/health
```

Default seeded users (created on startup if missing):
- admin: `APP_AUTH_USER` / `APP_AUTH_PASSWORD`
- normal user: `DEFAULT_USER_USERNAME` / `DEFAULT_USER_PASSWORD`

## Auth Flow
1. Login
```bash
curl -X POST http://localhost:8081/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"password123"}'
```

2. Use `access_token` as bearer token
```bash
TOKEN="<paste-token>"
curl -H "Authorization: Bearer $TOKEN" http://localhost:8081/todos
```

## Delete Approval Flow
- If `admin` calls `DELETE /todos/{id}`: todo is deleted immediately.
- If `user` calls `DELETE /todos/{id}`: request is created with `PENDING` status.
- Admin reviews via:
```bash
GET  /delete-requests?status=PENDING
POST /delete-requests/{request_id}/approve
POST /delete-requests/{request_id}/reject
```

## ToDo Scope Filters and Clear
- `GET /todos?scope=all|done|pending` (default `scope=all`)
  - `all`: list all todos
  - `done`: list only completed todos
  - `pending`: list only incomplete todos
- `DELETE /todos/clear?scope=all|done|pending` (default `scope=all`)
  - Clears todos by scope.
  - Works for any authenticated role and does not create delete requests.
