# Business Requirements Document (BRD)
## Project: ToDoPlusPlus Core Service
## Version: 1.2
## Date: 2026-03-08

## 1. Executive Summary
ToDoPlusPlus Core Service is a backend platform for secure task management with role-based controls, deletion approval governance, scoped list/clear operations, independent task attachments, and event-driven integration support (Jira, Email, Audit).

The platform supports:
- Secure user login with JWT.
- Strict role model for `admin` and `user`.
- ToDo lifecycle operations (create, list, view, update, delete).
- Scoped list filtering (`all`, `done`, `pending`).
- Scoped clear operations (`all`, `done`, `pending`) available to all authenticated users.
- Controlled delete workflow for non-admin users on single-item delete.
- Bulk ToDo creation through file upload (`.csv`, `.xlsx`, `.json`).
- Optional file upload and download independent of task completion state.
- Pluggable storage architecture with local storage active by default.

## 2. Business Objectives
- Provide a reliable central service for team task tracking.
- Enforce governance over deletion actions through admin review.
- Improve operational traceability via audit logs.
- Enable operational productivity through bulk task onboarding.
- Improve daily usability with fast task filtering and scoped clear actions.
- Support optional attachments that can be uploaded/downloaded anytime in the task lifecycle.
- Keep file storage replaceable (local now, cloud later) without API redesign.

## 3. Stakeholders
- Product Owner: Defines operational behavior and approval expectations.
- Admin Users: Manage and approve/reject delete requests; perform scoped clear operations.
- Standard Users: Create and maintain tasks; request single-item deletions; filter tasks and perform scoped clear actions; upload optional task evidence.
- Engineering Team: Maintains API, storage adapters, infrastructure, and integrations.
- Compliance/Operations: Reviews auditability and workflow controls.

## 4. Scope
### In Scope
- Authentication and token-based session control.
- Strict enum-based role handling (`admin`, `user`).
- Role-aware ToDo operations.
- Scoped ToDo list filters via query param.
- Scoped ToDo clear endpoint without approval workflow.
- Delete approval workflow.
- Multipart upload for task attachments (optional usage, independent of completion).
- Bulk import from `.csv`, `.xlsx`, `.json` files.
- Attachment metadata persistence and file download APIs.
- Local file storage with provider abstraction for future cloud storage.
- Background event flow: Jira -> Email -> Audit.
- Persistence in PostgreSQL.

### Out of Scope
- Frontend web/mobile application.
- Multi-tenancy and organization-level isolation.
- Fine-grained ACLs beyond role-level controls.
- SLA monitoring dashboards and analytics UI.
- End-user self-signup/account management.

## 5. User Personas and Needs
- Admin:
  - Needs full ToDo access including direct deletion.
  - Needs ability to review pending delete requests.
  - Needs quick cleanup actions (clear done/pending/all) without approval overhead.
  - Needs trustable audit trail for decisions.
- Standard User:
  - Needs simple create/update/list/view capabilities.
  - Needs to request deletion when task is no longer needed.
  - Needs to filter view by done/pending/all.
  - Needs to clear done/pending/all tasks quickly without waiting for admin approval.
  - Needs ability to mark tasks complete independently from attachment uploads.
  - Needs ability to upload structured files for bulk task creation.
- Operator/Support:
  - Needs visibility into integration and storage behavior.
  - Needs clear logs and audit entries to diagnose issues.

## 6. Business Use Cases
1. User Login
- Actor: Admin/User
- Trigger: User submits credentials.
- Outcome: Receives bearer token and profile metadata.

2. Create ToDo
- Actor: Admin/User
- Trigger: Authenticated create request.
- Outcome: Task stored with creator reference; integration events emitted.

3. Bulk Import ToDos
- Actor: Admin/User
- Trigger: Upload `.csv`, `.xlsx`, or `.json` file.
- Outcome: Multiple tasks created in one operation with creator reference.

4. Complete ToDo
- Actor: Admin/User
- Trigger: Complete-task request.
- Outcome: Task marked completed.

5. Upload/Download Task Attachments
- Actor: Admin/User
- Trigger: Attachment upload or download request.
- Outcome: File bytes and metadata are stored/retrieved without changing completion state.

6. Delete ToDo (Admin)
- Actor: Admin
- Trigger: Admin deletes task.
- Outcome: Task deleted immediately.

7. Delete ToDo (User)
- Actor: Standard user
- Trigger: User deletes task.
- Outcome: Pending delete request created for admin decision.

8. Approve Delete Request
- Actor: Admin
- Trigger: Admin approves pending request.
- Outcome: Task deleted; request marked approved with review metadata.

9. Reject Delete Request
- Actor: Admin
- Trigger: Admin rejects pending request.
- Outcome: Task retained; request marked rejected with review metadata.

10. Filter ToDo List by Scope
- Actor: Admin/User
- Trigger: User requests list with scope (`all`, `done`, `pending`).
- Outcome: UI receives only the requested subset of tasks.

11. Clear ToDos by Scope
- Actor: Admin/User
- Trigger: User calls clear endpoint with scope (`all`, `done`, `pending`).
- Outcome: Matching tasks are deleted immediately without delete-request approval.

## 7. Key Business Rules
- All ToDo and delete-request endpoints require valid bearer token.
- User account must be active to access protected APIs.
- Role values are strictly constrained to `admin` and `user`.
- ToDo names must be non-empty and max length 255 characters.
- `GET /todos` supports `scope` query values: `all` (default), `done`, `pending`.
- `DELETE /todos/clear` supports `scope` query values: `all` (default), `done`, `pending`.
- Scoped clear is allowed for any authenticated role and does not create delete requests.
- Completion endpoint is independent and does not require file upload.
- Attachment upload/download is optional and independent of completion state.
- Upload size is bounded by configured maximum.
- Bulk import supports only `.csv`, `.xlsx`, `.json`.
- A user cannot create duplicate pending delete requests for same ToDo.
- Only `PENDING` delete requests can be approved/rejected.
- Admin can see all delete requests; user can only see own requests.
- Delete approval workflow applies to `DELETE /todos/{id}` (single-item delete), not `DELETE /todos/clear`.

## 8. Non-Functional Expectations
- Security: signed JWT auth and protected endpoints.
- Maintainability: clear API/repository/storage separation.
- Configurability: environment-based storage backend selection.
- Extensibility: storage provider contract allows local-to-cloud transition.
- Observability: structured logs and audit records for workflow visibility.

## 9. Risks and Constraints
- Kafka/DB availability impacts workflow completeness.
- Scoped clear actions are high-impact and can remove many records quickly; UI confirmation is recommended.
- File growth in local storage requires retention/cleanup strategy.
- No retry/DLQ strategy currently for async integrations.
- `status` filter on delete-requests remains string query input.

## 10. Success Criteria
- Role-constrained APIs behave correctly for `admin` and `user`.
- `GET /todos` returns correct subsets for `scope=all|done|pending`.
- `DELETE /todos/clear` removes correct subsets for `scope=all|done|pending` and is accessible to both roles.
- Completion endpoint works independently from file upload.
- Bulk import creates tasks from supported file types.
- Uploaded files are downloadable through API endpoints.
- Storage implementation can be swapped without endpoint contract changes.

## 11. Enhancement Ideas
- Add attachment lifecycle controls (list, delete, retention policy).
- Add import dry-run mode with row-level validation report.
- Add virus scanning and file-type policy enforcement.
- Add cloud provider adapters (S3/GCS/Azure Blob).
- Add user self-service account creation and admin user management.
