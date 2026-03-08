# API Functional Document
## Project: ToDoPlusPlus Core Service
## Version: 1.1
## Date: 2026-03-07

## 1. Purpose
API-level functional and technical details for ToDoPlusPlus Core Service, including auth, role rules, CRUD flows, delete approval, multipart uploads, bulk imports, and attachment download.

## 2. Technical Context
- Framework: FastAPI
- Language: Python
- Persistence: PostgreSQL (SQLAlchemy ORM)
- Messaging: Kafka
- Auth: JWT bearer token
- Storage: provider abstraction (`local` backend active)
- Base URL: `http://localhost:8081`

## 3. Authentication and Authorization
### 3.1 Token Issuance
- Endpoint: `POST /auth/login`
- Claims:
  - `sub`: user id
  - `role`: `admin` or `user`
  - `exp`: expiration timestamp

### 3.2 Protected APIs
Bearer token required for all endpoints except:
- `GET /health`
- `POST /auth/login`

### 3.3 Role Rules
- `admin`:
  - Can delete ToDo immediately.
  - Can approve/reject delete requests.
  - Can view all delete requests.
- `user`:
  - Cannot directly delete ToDo.
  - Can create pending delete requests.
  - Can view only own delete requests.

## 4. Core Schemas
### 4.1 ToDoCreate
```json
{
  "name": "string (1..255)",
  "completed": "boolean (optional, default false)"
}
```

### 4.2 ToDoOut
```json
{
  "id": 10,
  "name": "Prepare sprint notes",
  "completed": false,
  "created_by_role": "user",
  "created_by_username": "user"
}
```

### 4.3 ToDoCompleteResponse
```json
{
  "id": 10,
  "completed": true
}
```

### 4.4 ToDoBulkCreateResult
```json
{
  "created_count": 2,
  "ids": [11, 12]
}
```

### 4.5 ToDoAttachmentOut
```json
{
  "id": 3,
  "todo_id": 10,
  "filename": "proof.pdf",
  "content_type": "application/pdf",
  "size_bytes": 24517
}
```

### 4.6 ToDoAttachmentUploadOut
```json
{
  "attachment_id": 3,
  "todo_id": 10,
  "filename": "proof.pdf",
  "content_type": "application/pdf",
  "size_bytes": 24517
}
```

## 5. Endpoints

## 5.1 Health
### GET `/health`
- Auth: No
- Response `200`:
```json
{"status": "ok"}
```

## 5.2 Auth
### POST `/auth/login`
- Auth: No
- Request:
```json
{
  "username": "admin",
  "password": "password123"
}
```
- Response `200`:
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

### GET `/auth/me`
- Auth: Yes
- Response `200`:
```json
{
  "id": 1,
  "username": "admin",
  "role": "admin"
}
```

## 5.3 ToDo CRUD
### GET `/todos`
- Auth: Yes
- Query param:
  - `scope` (optional): `all` (default) | `done` | `pending`
- Behavior:
  - `all`: returns all todos
  - `done`: returns only `completed=true`
  - `pending`: returns only `completed=false`
- Response `200`: `ToDoOut[]`

### GET `/todos/{todo_id}`
- Auth: Yes
- Path param: `todo_id` (int)
- Response `200`: `ToDoOut`
- Error `404`: todo not found

### POST `/todos`
- Auth: Yes
- Request: `ToDoCreate`
- Response `201`: `ToDoOut`
- Side effects:
  - Persists todo in DB
  - Publishes todo event to Jira topic
  - Publishes audit event to Audit topic

### PUT `/todos/{todo_id}`
- Auth: Yes
- Request: partial fields of `ToDoCreate`
- Response `200`: `ToDoOut`
- Error `404`: todo not found

### DELETE `/todos/{todo_id}`
- Auth: Yes
- Response `200`: delete action payload
- Behavior:
  - `admin`: immediate delete
  - `user`: pending delete request creation/reuse

### DELETE `/todos/clear`
- Auth: Yes
- Query param:
  - `scope` (optional): `all` (default) | `done` | `pending`
- Behavior:
  - `all`: deletes all todos
  - `done`: deletes todos with `completed=true`
  - `pending`: deletes todos with `completed=false`
  - Allowed for all authenticated roles; no delete-approval workflow is used.
- Response `200`:
```json
{
  "scope": "pending",
  "deleted_count": 4
}
```

## 5.4 Complete Task
### POST `/todos/{todo_id}/complete`
- Auth: Yes
- Behavior:
  - Marks todo `completed=true`
- Response `200`: `ToDoCompleteResponse`
- Errors:
  - `404` if todo not found

Example:
```bash
curl -X POST http://localhost:8081/todos/10/complete \
  -H "Authorization: Bearer <token>"
```

## 5.5 Bulk Import
### POST `/todos/bulk-import`
- Auth: Yes
- Content type: `multipart/form-data` or `application/json`
- Request options:
  - `multipart/form-data`: `file` (required) as `.json`, `.csv`, or `.xlsx`
  - `application/json`: body as a JSON array of todo objects, or `{"items":[...]}`
- Behavior:
  - Parses uploaded file
  - Creates multiple ToDos under current user
  - Publishes todo + audit messages for each created item
- Response `201`: `ToDoBulkCreateResult`
- Errors:
  - `422` invalid format/content
  - `413` file too large

Format rules (strict):
- CSV and XLSX must include a header row with a `name` column (case-insensitive).
- `completed` is optional; if present, accepted values are `true/false/1/0/yes/no` (also `y/n`).
- Rows with both `name` and `completed` empty are skipped.
- Any non-empty row with invalid data returns `422` with row/item context.

JSON file format options:
```json
[
  {"name":"task 1","completed":false},
  {"name":"task 2","completed":true}
]
```
or
```json
{
  "items": [
    {"name":"task 1","completed":false},
    {"name":"task 2","completed":true}
  ]
}
```

Strict JSON examples:
```json
[
  {"name":"Write report","completed":false},
  {"name":"Send email","completed":true}
]
```
or
```json
{
  "items": [
    {"name":"Write report","completed":false},
    {"name":"Send email","completed":true}
  ]
}
```

CSV expected headers:
- `name` (required)
- `completed` (optional; accepted values like `true/false/1/0/yes/no`)

CSV example:
```csv
name,completed
Write report,false
Send email,true
```

XLSX expected headers (first row):
- `name` (required)
- `completed` (optional)

Example:
```bash
curl -X POST http://localhost:8081/todos/bulk-import \
  -H "Authorization: Bearer <token>" \
  -F "file=@./todos.xlsx"
```

Example (direct JSON body):
```bash
curl -X POST http://localhost:8081/todos/bulk-import \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '[{"name":"task 1","completed":false},{"name":"task 2","completed":true}]'
```

Sample download endpoints (for UI "Download format" buttons):
- `GET /todos/bulk-import/examples/tabular?format=csv`
- `GET /todos/bulk-import/examples/tabular?format=xlsx`
- `GET /todos/bulk-import/examples/json`
- Auth: Yes
- Response: downloadable attachment with a valid import template for each format

Example:
```bash
curl -L "http://localhost:8081/todos/bulk-import/examples/tabular?format=csv" \
  -H "Authorization: Bearer <token>" \
  -o bulk-import-example.csv
```

## 5.6 Attachments (Independent of Complete Status)
### POST `/todos/{todo_id}/attachments/upload`
- Auth: Yes
- Content type: `multipart/form-data`
- Part:
  - `file` (required): any file type
- Behavior:
  - Stores attachment for the todo without changing `completed` status
- Response `201`: `ToDoAttachmentUploadOut`
- Note: use `attachment_id` from this response in download URL.
- Errors:
  - `404` if todo not found
  - `413` if file exceeds configured max upload size

Example:
```bash
curl -X POST http://localhost:8081/todos/10/attachments/upload \
  -H "Authorization: Bearer <token>" \
  -F "file=@./proof.pdf"
```

### GET `/todos/{todo_id}/attachments/{attachment_id}`
- Auth: Yes
- Response `200`: `ToDoAttachmentOut`
- Error `404`: attachment not found or does not belong to todo

### GET `/todos/{todo_id}/attachments/{attachment_id}/download`
- Auth: Yes
- Response `200`: binary stream with `Content-Disposition: attachment; filename="..."`
- Errors:
  - `404` if metadata missing
  - `404` if physical file missing from storage backend

Example:
```bash
curl -L "http://localhost:8081/todos/10/attachments/3/download" \
  -H "Authorization: Bearer <token>" \
  -o proof.pdf
```

## 5.7 Delete Requests
### GET `/delete-requests?status=PENDING`
- Auth: Yes
- Query param: `status` (optional)
- `admin`: all requests
- `user`: own requests only

### POST `/delete-requests/{request_id}/approve`
- Auth: Yes (admin)
- Response `200`: approved status payload
- Errors: `403`, `404`, `409`

### POST `/delete-requests/{request_id}/reject`
- Auth: Yes (admin)
- Response `200`: rejected status payload
- Errors: `403`, `404`, `409`

## 6. Storage Design (Local Now, Cloud-Ready)
- API/router layer uses a storage provider interface (`save/read/exists/delete`).
- Current backend: local filesystem.
- Storage backend selection is config-driven:
  - `STORAGE_BACKEND=local`
  - `STORAGE_LOCAL_ROOT=./data/uploads`
- Upload size control:
  - `UPLOAD_MAX_BYTES` (default 10 MB)
- Future cloud migration requires adding a new provider implementation, without changing endpoint contracts.

## 7. Notes
- `created_by_user_id` remains source of truth for actor identity.
- `created_by_role` in API responses is strictly enum-constrained (`admin`/`user`).
- Default users remain seeded from configuration on startup.
