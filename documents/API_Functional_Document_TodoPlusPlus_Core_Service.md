# API Functional Document
## Project: ToDoPlusPlus Core Service
## Version: 1.0
## Date: 2026-03-05

## 1. Purpose
This document provides complete API-level functional and technical details for the ToDoPlusPlus Core Service, including endpoint contracts, schemas, validations, auth rules, business/technical rules, variables, and request/response examples.

## 2. Base Technical Context
- Framework: FastAPI
- Language: Python
- Persistence: PostgreSQL (SQLAlchemy ORM)
- Messaging: Kafka (confluent-kafka producer/consumer)
- Auth: JWT bearer token (HS256 by default)
- Default API base URL: `http://localhost:8081`

## 3. Authentication and Authorization
### 3.1 Token Issuance
- Endpoint: `POST /auth/login`
- Input: username/password
- Token payload claims:
  - `sub`: user id (string form)
  - `role`: `admin` or `user`
  - `exp`: expiration timestamp

### 3.2 Protected APIs
Bearer token required for all endpoints except `GET /health` and `POST /auth/login`.

### 3.3 Role Rules
- `admin`:
  - Can delete ToDo immediately.
  - Can approve/reject delete requests.
  - Can list all delete requests.
- `user`:
  - Cannot perform direct deletion.
  - Creates pending delete requests.
  - Can only list own delete requests.

### 3.4 Auth Failure Responses
- Missing token: `401` + `{"detail":"Missing bearer token"}`
- Invalid token: `401` + `{"detail":"Invalid token"}`
- Inactive/missing user: `401` + `{"detail":"User not found or inactive"}`
- Non-admin on admin endpoint: `403` + `{"detail":"Admin access required"}`

## 4. API Endpoints

## 4.1 Health
### GET `/health`
- Auth required: No
- Purpose: Service heartbeat

Success Response (200):
```json
{"status": "ok"}
```

## 4.2 Auth
### POST `/auth/login`
- Auth required: No
- Purpose: Authenticate user and issue JWT

Request Schema:
```json
{
  "username": "string",
  "password": "string"
}
```

Example Request:
```bash
curl -X POST http://localhost:8081/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"password123"}'
```

Success Response (200):
```json
{
  "access_token": "<jwt>",
  "token_type": "bearer",
  "expires_in_seconds": 3600,
  "user": {
    "id": 1,
    "username": "admin",
    "role": "admin"
  }
}
```

Error Responses:
- `401`: invalid credentials
- `403`: user inactive

### GET `/auth/me`
- Auth required: Yes
- Purpose: Return current authenticated user profile

Success Response (200):
```json
{
  "id": 1,
  "username": "admin",
  "role": "admin"
}
```

## 4.3 ToDo APIs
### GET `/todos`
- Auth required: Yes
- Purpose: List all ToDo items (ascending by `id`)

Success Response (200):
```json
[
  {
    "id": 1,
    "name": "task a",
    "completed": false,
    "created_by_role": "admin",
    "created_by_username": "admin"
  }
]
```

### GET `/todos/{todo_id}`
- Auth required: Yes
- Path variable: `todo_id` (integer)
- Purpose: Fetch specific ToDo

Success Response (200):
```json
{
  "id": 1,
  "name": "task a",
  "completed": false,
  "created_by_role": "admin",
  "created_by_username": "admin"
}
```

Not Found (404):
```json
{"detail": "ToDo item 999 not found"}
```

### POST `/todos`
- Auth required: Yes
- Purpose: Create ToDo and trigger async pipeline

Request Schema:
```json
{
  "name": "string (1..255)",
  "completed": "boolean (optional, default false)"
}
```

Example Request:
```bash
curl -X POST http://localhost:8081/todos \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"name":"Prepare sprint notes","completed":false}'
```

Success Response (201):
```json
{
  "id": 10,
  "name": "Prepare sprint notes",
  "completed": false,
  "created_by_role": "user",
  "created_by_username": "user"
}
```

Side Effects:
- Inserts row into `todo_items`
- Publishes to Kafka topic `TOPIC_JIRA` with payload:
```json
{"id":10,"name":"Prepare sprint notes","completed":false}
```
- Publishes audit event to `TOPIC_AUDIT`:
```json
{
  "type": "TODO",
  "value": "{\"id\": 10, \"name\": \"Prepare sprint notes\", \"completed\": false}"
}
```

### PUT `/todos/{todo_id}`
- Auth required: Yes
- Purpose: Partial update of ToDo

Request Schema:
```json
{
  "name": "string (optional, 1..255)",
  "completed": "boolean (optional)"
}
```

Example Request:
```bash
curl -X PUT http://localhost:8081/todos/10 \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"completed":true}'
```

Success Response (200):
```json
{
  "id": 10,
  "name": "Prepare sprint notes",
  "completed": true,
  "created_by_role": "user",
  "created_by_username": "user"
}
```

Not Found (404):
```json
{"detail": "ToDo item 10 not found"}
```

### DELETE `/todos/{todo_id}`
- Auth required: Yes
- Purpose: Delete or request delete depending on role

Behavior:
- If caller role is `admin`: immediate deletion
- If caller role is `user`: create/find pending delete request

Admin Success Response (200):
```json
{
  "action": "deleted",
  "message": "ToDo item 10 deleted",
  "delete_request_id": null
}
```

User (new pending request) Response (200):
```json
{
  "action": "PENDING",
  "message": "Delete request submitted for admin approval",
  "delete_request_id": 5
}
```

User (already pending) Response (200):
```json
{
  "action": "pending_approval",
  "message": "Delete request already pending admin approval",
  "delete_request_id": 5
}
```

Not Found (404):
```json
{"detail": "ToDo item 10 not found"}
```

## 4.4 Delete Request APIs
### GET `/delete-requests`
- Auth required: Yes
- Query variable: `status` (optional string)
- Purpose: List delete requests

Role behavior:
- Admin: returns all requests (optionally filtered by status)
- User: returns only own requests (optionally filtered)

Example Request:
```bash
curl -X GET "http://localhost:8081/delete-requests?status=PENDING" \
  -H "Authorization: Bearer <token>"
```

Success Response (200):
```json
[
  {
    "id": 5,
    "todo_id": 10,
    "requested_by_user_id": 2,
    "status": "PENDING",
    "reviewed_by_admin_id": null,
    "reviewed_at": null,
    "created_at": "2026-03-05T06:00:00.000000+00:00"
  }
]
```

### POST `/delete-requests/{request_id}/approve`
- Auth required: Yes (admin only)
- Path variable: `request_id` (integer)
- Purpose: Approve pending request and delete target ToDo

Success Response (200):
```json
{
  "id": 5,
  "status": "APPROVED",
  "todo_id": 10
}
```

Errors:
- `404` if request missing
- `404` if linked ToDo missing at approval time
- `409` if request already processed
- `403` if non-admin

### POST `/delete-requests/{request_id}/reject`
- Auth required: Yes (admin only)
- Path variable: `request_id` (integer)
- Purpose: Reject pending request

Success Response (200):
```json
{
  "id": 5,
  "status": "REJECTED",
  "todo_id": 10
}
```

Errors:
- `404` if request missing
- `409` if request already processed
- `403` if non-admin

## 5. Request/Response Schema Definitions

## 5.1 `LoginRequest`
```json
{
  "username": "string",
  "password": "string"
}
```

## 5.2 `AuthUser`
```json
{
  "id": "integer",
  "username": "string",
  "role": "string"
}
```

## 5.3 `TokenResponse`
```json
{
  "access_token": "string",
  "token_type": "bearer",
  "expires_in_seconds": "integer",
  "user": "AuthUser"
}
```

## 5.4 `ToDoCreate`
```json
{
  "name": "string, required, min 1, max 255",
  "completed": "boolean, optional, default false"
}
```

## 5.5 `ToDoUpdate`
```json
{
  "name": "string, optional, min 1, max 255",
  "completed": "boolean, optional"
}
```

## 5.6 `ToDoOut`
```json
{
  "id": "integer",
  "name": "string",
  "completed": "boolean",
  "created_by_role": "literal(admin|user)",
  "created_by_username": "string|null"
}
```

## 5.7 `DeleteTodoActionResponse`
```json
{
  "action": "string",
  "message": "string",
  "delete_request_id": "integer|null"
}
```

## 5.8 `DeleteRequestDecisionResponse`
```json
{
  "id": "integer",
  "status": "string",
  "todo_id": "integer"
}
```

## 5.9 `ToDoDeleteRequestOut`
```json
{
  "id": "integer",
  "todo_id": "integer",
  "requested_by_user_id": "integer",
  "status": "string",
  "reviewed_by_admin_id": "integer|null",
  "reviewed_at": "datetime|null",
  "created_at": "datetime"
}
```

## 6. Validation and Error Model
- Pydantic validation errors produce `422 Unprocessable Entity`.
- Typical validation body:
```json
{
  "detail": [
    {
      "type": "string_too_short",
      "loc": ["body", "name"],
      "msg": "String should have at least 1 character",
      "input": "",
      "ctx": {"min_length": 1}
    }
  ]
}
```

Application-level errors:
- 401 authentication/authorization token issues.
- 403 forbidden role action.
- 404 not found resources.
- 409 conflicting state transition for processed delete request.

## 7. Business and Technical Rules
- ToDo list is globally visible to authenticated users.
- Creator metadata is always returned (`created_by_role`, `created_by_username`).
- `created_by_role` defaults to `admin` in mapper if role cannot be resolved.
- Duplicate pending delete request by same user for same todo is not created.
- Only `PENDING` requests can transition to `APPROVED` or `REJECTED`.
- Approving a request deletes the todo and sets review metadata atomically in one transaction.

## 8. Data Model (Database)
### 8.1 `users`
- `id` (PK)
- `username` (unique, indexed, not null)
- `password_hash` (not null)
- `role` (`admin`/`user` expected)
- `is_active` (bool)
- `created_at`

### 8.2 `todo_items`
- `id` (PK)
- `name` (varchar 255, not null)
- `completed` (bool, default false)
- `created_by_user_id` (FK users.id, nullable, on delete set null)
- `created_at`

### 8.3 `todo_delete_requests`
- `id` (PK)
- `todo_id` (FK todo_items.id, on delete cascade)
- `requested_by_user_id` (FK users.id, on delete cascade)
- `status` (`PENDING`, `APPROVED`, `REJECTED`)
- `reviewed_by_admin_id` (FK users.id, nullable)
- `reviewed_at` (nullable)
- `created_at`

### 8.4 `audits`
- `id` (PK)
- `type` (varchar 100)
- `value` (text)
- `created_at`

## 9. Event-Driven Functional Details

## 9.1 Kafka Topics (Configurable)
- `TOPIC_JIRA` default: `todo-items-jira`
- `TOPIC_EMAIL` default: `todo-items-email`
- `TOPIC_AUDIT` default: `todo-items-audit`

## 9.2 Producer Rules
- Key: ToDo ID as string
- Value: JSON serialized payload
- Flush: producer flushes on each publish call

## 9.3 Consumer Groups
- Jira consumer group: `todo-jira-consumer-group`
- Email consumer group: `todo-email-consumer-group`
- Audit consumer group: `todo-audit-consumer-group`

## 9.4 Jira Handler Contract
Input payload:
```json
{"id":10,"name":"Prepare sprint notes","completed":false}
```

Output to email topic (`JiraToDoItem`):
```json
{
  "id": 10,
  "name": "Prepare sprint notes",
  "completed": false,
  "jira_id": "10000",
  "key": "TODO-123",
  "url": "https://your-domain.atlassian.net/rest/api/3/issue/10000"
}
```

If Jira disabled, output still sent with Jira fields as null.

## 9.5 Email Handler Contract
Input: `JiraToDoItem`
- Subject format: `New ToDo Item Created-> <todo_name>`
- Body includes serialized jira item JSON

Audit outputs to audit topic:
- Email disabled: `type=EMAIL_SKIPPED`
- Email success: `type=EMAIL`
- Email failure: `type=ERROR`

## 9.6 Audit Handler Contract
Input payload:
```json
{"type":"EMAIL","value":"..."}
```

Behavior: persists into `audits` table.

## 10. Variables and Configuration
All values are environment-driven (`.env`).

Application:
- `APP_NAME`
- `APP_HOST`
- `APP_PORT`
- `CORS_ALLOWED_ORIGINS` (comma-separated)

Identity and bootstrap users:
- `APP_AUTH_USER` (admin username)
- `APP_AUTH_PASSWORD` (admin password)
- `DEFAULT_USER_USERNAME`
- `DEFAULT_USER_PASSWORD`

JWT:
- `JWT_SECRET_KEY`
- `JWT_ALGORITHM` (default `HS256`)
- `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`

Database:
- `DATABASE_URL`

Kafka:
- `KAFKA_BOOTSTRAP_SERVERS`
- `TOPIC_JIRA`
- `TOPIC_EMAIL`
- `TOPIC_AUDIT`

Jira integration:
- `JIRA_ENABLED`
- `JIRA_API_URL`
- `JIRA_API_EMAIL`
- `JIRA_API_TOKEN`
- `JIRA_PROJECT_KEY`
- `JIRA_ISSUE_TYPE`

Email integration:
- `EMAIL_ENABLED`
- `EMAIL_SMTP_HOST`
- `EMAIL_SMTP_PORT`
- `EMAIL_SMTP_USERNAME`
- `EMAIL_SMTP_PASSWORD`
- `EMAIL_FROM`
- `EMAIL_RECIPIENT`

## 11. Seeded Users and Runtime Initialization
At startup:
- Tables are created if missing.
- Migration ensures `todo_items.created_by_user_id` and index/FK.
- Default users are created if absent:
  - Admin from `APP_AUTH_USER` / `APP_AUTH_PASSWORD`
  - Normal user from `DEFAULT_USER_USERNAME` / `DEFAULT_USER_PASSWORD`
- Kafka consumers are started.

## 12. Observability and Logs
Structured event logs exist for:
- App startup/shutdown and mode
- ToDo create request/success/failure
- Kafka publish and delivery
- Consumer init/start/message/failure/stop
- Jira create attempt/success/failure/skipped
- Email send attempt/success/failure/skipped
- Audit write success/failure

## 13. Known Edge Cases and Implementation Notes
- `GET /delete-requests?status=<value>` accepts raw string; invalid values do not raise validation error but may return empty set.
- `DELETE /todos/{id}` returns 200 with action payload (not 204).
- If a token has valid signature but user is inactive/deleted, API returns 401.
- Approve operation fails with 404 if todo already missing.

## 14. End-to-End Example Flow
1. Login as user -> receive token.
2. Create ToDo -> returns created row and triggers async events.
3. User tries delete -> request becomes `PENDING`.
4. Admin lists pending requests.
5. Admin approves -> request status `APPROVED`, todo removed.
6. Audit table includes TODO + email workflow records.
