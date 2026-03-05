# Business Requirements Document (BRD)
## Project: ToDoPlusPlus Core Service
## Version: 1.0
## Date: 2026-03-05

## 1. Executive Summary
ToDoPlusPlus Core Service is a backend platform for secure task management with role-based controls, deletion approval governance, and event-driven integration support (Jira, Email, Audit). The product serves teams that need a lightweight task lifecycle with accountability and auditable operations.

The platform supports:
- Secure user login with JWT.
- Role-based behavior for `admin` and `user`.
- ToDo lifecycle operations (create, list, view, update, delete).
- Controlled delete workflow for non-admin users.
- Kafka-driven integration flow for Jira enrichment, email notifications, and audit persistence.

## 2. Business Objectives
- Provide a reliable central service for team task tracking.
- Enforce governance over deletion actions through admin review.
- Improve operational traceability via audit logs.
- Enable optional downstream integration with enterprise tools (Jira and email).
- Keep integration modes configurable for local development and production environments.

## 3. Stakeholders
- Product Owner: Defines operational behavior and approval expectations.
- Admin Users: Manage and approve/reject delete requests.
- Standard Users: Create and maintain tasks; request deletions.
- Engineering Team: Maintains API, infrastructure, and integrations.
- Compliance/Operations: Reviews auditability and workflow controls.

## 4. Scope
### In Scope
- Authentication and token-based session control.
- Role-aware ToDo operations.
- Delete approval workflow.
- Background event flow: Jira -> Email -> Audit.
- Persistence in PostgreSQL.

### Out of Scope
- Frontend web/mobile application.
- Multi-tenancy and organization-level isolation.
- Fine-grained ACLs beyond role-level controls.
- SLA monitoring dashboards and analytics UI.

## 5. User Personas and Needs
- Admin:
  - Needs full ToDo access including direct deletion.
  - Needs ability to review pending delete requests.
  - Needs trustable audit trail for decisions.
- Standard User:
  - Needs simple create/update/list/view capabilities.
  - Needs to request deletion when task is no longer needed.
  - Needs predictable response when delete is pending.
- Operator/Support:
  - Needs visibility into integration behavior (local vs real mode).
  - Needs clear logs and audit entries to diagnose issues.

## 6. Business Use Cases
1. User Login:
- Actor: Admin/User
- Trigger: User submits credentials.
- Outcome: Receives bearer token and profile metadata.

2. Create ToDo:
- Actor: Admin/User
- Trigger: Authenticated create request.
- Outcome: Task stored with creator reference; integration events emitted.

3. Update ToDo:
- Actor: Admin/User
- Trigger: Authenticated update request.
- Outcome: Existing task updated.

4. Delete ToDo (Admin):
- Actor: Admin
- Trigger: Admin deletes task.
- Outcome: Task deleted immediately.

5. Delete ToDo (User):
- Actor: Standard user
- Trigger: User deletes task.
- Outcome: Pending delete request created for admin decision.

6. Approve Delete Request:
- Actor: Admin
- Trigger: Admin approves pending request.
- Outcome: Task deleted; request marked approved with review metadata.

7. Reject Delete Request:
- Actor: Admin
- Trigger: Admin rejects pending request.
- Outcome: Task retained; request marked rejected with review metadata.

## 7. Key User Flows
### Flow A: Authentication and Session Start
1. User submits username/password.
2. System validates credentials and active status.
3. JWT token issued with `sub`, `role`, `exp`.
4. User calls protected APIs with `Authorization: Bearer <token>`.

### Flow B: Task Creation and Event Pipeline
1. Authenticated user submits new ToDo.
2. System saves ToDo in DB including `created_by_user_id`.
3. System emits event to Jira topic.
4. Jira consumer enriches payload (or skips in local mode) and publishes to email topic.
5. Email consumer sends email (or skips in local mode) and emits audit event.
6. Audit consumer persists audit record in DB.

### Flow C: Controlled Deletion
1. User sends delete request for a ToDo.
2. If actor is admin: direct deletion.
3. If actor is standard user:
- Check existing pending request for same user+todo.
- If pending exists: return existing request reference.
- Else create new pending request.
4. Admin lists pending requests and decides approve/reject.
5. System updates request status and review metadata.

## 8. Business Rules
- All ToDo and delete-request endpoints require valid bearer token.
- User account must be active to access protected APIs.
- Role behavior:
  - `admin`: unrestricted ToDo delete, can approve/reject requests.
  - `user`: cannot directly delete; must request approval.
- A user cannot create duplicate pending delete requests for same ToDo.
- Only `PENDING` requests can be approved/rejected.
- If linked ToDo is missing at approval time, approve operation fails.
- ToDo names must be non-empty and max length 255 characters.

## 9. Functional Expectations from the Application
- Reliable API availability and deterministic status codes.
- Idempotent-like behavior for repeated user delete requests while pending.
- Consistent role visibility:
  - Admin can see all delete requests.
  - User can only see own requests.
- Audit records must be persisted for workflow observability.
- Integration toggles must support local development without external dependencies.

## 10. Non-Functional Expectations (Business Level)
- Security: credential-based login, signed token auth, protected endpoints.
- Performance: responsive CRUD for normal operational load.
- Maintainability: clear separation of API, repositories, services, and consumers.
- Observability: structured event logs and audit records.
- Configurability: environment variable-driven deployment behavior.

## 11. Risks and Constraints
- Kafka/DB availability directly impacts workflow completeness.
- Integration failures (Jira/email) can degrade downstream automation.
- No retry/DLQ strategy currently; failed integration handling is limited.
- `status` filter on delete-requests is free-form and not enum-validated at API boundary.

## 12. Success Criteria
- Users can authenticate and perform role-appropriate task operations.
- Delete requests are governed through admin decisions.
- Audit trail accurately reflects asynchronous workflow outcomes.
- Local mode runs without external Jira/email services.

## 13. Enhancements
1. Workflow and Governance
- Add approval comments and reason codes (business justification).
- Add bulk approval/rejection for operational efficiency.
- Add SLA timers/escalations for pending delete requests.

2. Product Features
- Add due dates, priority, tags, assignment, and status transitions.
- Add search/filter/sort APIs (name, creator, completion, date range).
- Add soft-delete with retention and restore capability.

3. Access and Security
- Add refresh tokens and token revocation.
- Add password policy, lockout, and audit for login failures.
- Add granular permissions (beyond admin/user roles).

4. Reliability and Integration
- Add retry/backoff and dead-letter queues for Kafka consumers.
- Add idempotency keys for create/update APIs.
- Add health endpoints for DB/Kafka readiness and liveness.

5. Reporting and Analytics
- Add metrics endpoint and dashboards (task throughput, approval cycle time).
- Add compliance reports for deletion decisions and actor history.

## 14. Acceptance Checklist
- Authentication flow works and returns role context.
- CRUD and delete approval behavior match role rules.
- Integration pipeline publishes and consumes expected events.
- Audit entries persist for operational traceability.
- Required configuration variables are documented and deployable.
