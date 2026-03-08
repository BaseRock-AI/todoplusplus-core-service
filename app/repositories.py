import logging
from datetime import datetime, timezone
from typing import Literal

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.logging_utils import Events, log_event
from app.models import (
    AttachmentCategory,
    Audit,
    DeleteRequestStatus,
    ToDoAttachment,
    ToDoDeleteRequest,
    ToDoItem,
    User,
    UserRole,
)
from app.schemas import ToDoCreate, ToDoUpdate

logger = logging.getLogger(__name__)


def _map_todo_row(todo_row: tuple[int, str, bool, str | None, str | None]) -> dict:
    todo_id, name, completed, created_by_role, created_by_username = todo_row
    role = created_by_role if created_by_role in {UserRole.ADMIN, UserRole.USER} else UserRole.ADMIN
    return {
        "id": todo_id,
        "name": name,
        "completed": completed,
        "created_by_role": role,
        "created_by_username": created_by_username,
    }


def list_todos(db: Session, completed_filter: bool | None = None) -> list[dict]:
    stmt = (
        select(
            ToDoItem.id,
            ToDoItem.name,
            ToDoItem.completed,
            User.role.label("created_by_role"),
            User.username.label("created_by_username"),
        )
        .outerjoin(User, ToDoItem.created_by_user_id == User.id)
        .order_by(ToDoItem.id.asc())
    )
    if completed_filter is not None:
        stmt = stmt.where(ToDoItem.completed.is_(completed_filter))
    rows = db.execute(stmt).all()
    return [_map_todo_row(row) for row in rows]


def get_todo_item(db: Session, todo_id: int) -> ToDoItem | None:
    return db.get(ToDoItem, todo_id)


def get_todo(db: Session, todo_id: int) -> dict | None:
    stmt = (
        select(
            ToDoItem.id,
            ToDoItem.name,
            ToDoItem.completed,
            User.role.label("created_by_role"),
            User.username.label("created_by_username"),
        )
        .outerjoin(User, ToDoItem.created_by_user_id == User.id)
        .where(ToDoItem.id == todo_id)
    )
    row = db.execute(stmt).one_or_none()
    if row is None:
        return None
    return _map_todo_row(row)


def create_todo(db: Session, payload: ToDoCreate, created_by_user_id: int) -> ToDoItem:
    todo = ToDoItem(name=payload.name, completed=payload.completed, created_by_user_id=created_by_user_id)
    db.add(todo)

    try:
        db.commit()
        db.refresh(todo)
    except Exception:
        db.rollback()
        log_event(logger, logging.ERROR, Events.TODO_CREATE_FAILED, name=payload.name, completed=payload.completed)
        logger.exception("[%s] stacktrace", Events.TODO_CREATE_FAILED)
        raise

    return todo


def create_todos_bulk(db: Session, payloads: list[ToDoCreate], created_by_user_id: int) -> list[ToDoItem]:
    todos = [ToDoItem(name=payload.name, completed=payload.completed, created_by_user_id=created_by_user_id) for payload in payloads]
    db.add_all(todos)
    db.commit()
    for todo in todos:
        db.refresh(todo)
    return todos


def update_todo(db: Session, todo: ToDoItem, payload: ToDoUpdate) -> ToDoItem:
    if payload.name is not None:
        todo.name = payload.name
    if payload.completed is not None:
        todo.completed = payload.completed
    db.commit()
    db.refresh(todo)
    return todo


def delete_todo(db: Session, todo: ToDoItem) -> None:
    db.delete(todo)
    db.commit()


def clear_todos(db: Session, scope: Literal["all", "done", "pending"] = "all") -> int:
    stmt = select(ToDoItem)
    if scope == "done":
        stmt = stmt.where(ToDoItem.completed.is_(True))
    elif scope == "pending":
        stmt = stmt.where(ToDoItem.completed.is_(False))

    todos = list(db.scalars(stmt).all())
    if not todos:
        return 0

    for todo in todos:
        db.delete(todo)
    db.commit()
    return len(todos)


def create_todo_attachment(
    db: Session,
    todo_id: int,
    category: AttachmentCategory,
    storage_key: str,
    original_filename: str,
    content_type: str | None,
    size_bytes: int,
    uploaded_by_user_id: int,
) -> ToDoAttachment:
    attachment = ToDoAttachment(
        todo_id=todo_id,
        category=category,
        storage_key=storage_key,
        original_filename=original_filename,
        content_type=content_type,
        size_bytes=size_bytes,
        uploaded_by_user_id=uploaded_by_user_id,
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)
    return attachment


def get_todo_attachment(db: Session, attachment_id: int) -> ToDoAttachment | None:
    return db.get(ToDoAttachment, attachment_id)


def create_delete_request(db: Session, todo_id: int, requested_by_user_id: int) -> ToDoDeleteRequest:
    delete_request = ToDoDeleteRequest(
        todo_id=todo_id,
        requested_by_user_id=requested_by_user_id,
        status=DeleteRequestStatus.PENDING,
    )
    db.add(delete_request)
    db.commit()
    db.refresh(delete_request)
    return delete_request


def get_pending_delete_request(db: Session, todo_id: int, requested_by_user_id: int) -> ToDoDeleteRequest | None:
    stmt = (
        select(ToDoDeleteRequest)
        .where(ToDoDeleteRequest.todo_id == todo_id)
        .where(ToDoDeleteRequest.requested_by_user_id == requested_by_user_id)
        .where(ToDoDeleteRequest.status == DeleteRequestStatus.PENDING)
    )
    return db.scalar(stmt)


def get_delete_request(db: Session, request_id: int) -> ToDoDeleteRequest | None:
    return db.get(ToDoDeleteRequest, request_id)


def list_delete_requests(
    db: Session,
    requested_by_user_id: int | None = None,
    status_filter: str | None = None,
) -> list[ToDoDeleteRequest]:
    stmt: Select[tuple[ToDoDeleteRequest]] = select(ToDoDeleteRequest).order_by(ToDoDeleteRequest.id.desc())

    if requested_by_user_id is not None:
        stmt = stmt.where(ToDoDeleteRequest.requested_by_user_id == requested_by_user_id)
    if status_filter:
        stmt = stmt.where(ToDoDeleteRequest.status == status_filter)

    return list(db.scalars(stmt).all())


def approve_delete_request(db: Session, delete_request: ToDoDeleteRequest, admin_user_id: int) -> None:
    todo = get_todo_item(db, delete_request.todo_id)
    if todo is None:
        raise ValueError("ToDo item not found")

    delete_request.status = DeleteRequestStatus.APPROVED
    delete_request.reviewed_by_admin_id = admin_user_id
    delete_request.reviewed_at = datetime.now(timezone.utc)
    db.delete(todo)
    db.commit()


def reject_delete_request(db: Session, delete_request: ToDoDeleteRequest, admin_user_id: int) -> None:
    delete_request.status = DeleteRequestStatus.REJECTED
    delete_request.reviewed_by_admin_id = admin_user_id
    delete_request.reviewed_at = datetime.now(timezone.utc)
    db.commit()


def create_audit(db: Session, audit_type: str, value: str) -> Audit:
    audit = Audit(type=audit_type, value=value)
    db.add(audit)

    try:
        db.commit()
        db.refresh(audit)
        log_event(logger, logging.INFO, Events.DB_AUDIT_WRITE, audit_id=audit.id, audit_type=audit_type)
    except Exception:
        db.rollback()
        log_event(logger, logging.ERROR, Events.DB_AUDIT_WRITE_FAILED, audit_type=audit_type)
        logger.exception("[%s] stacktrace", Events.DB_AUDIT_WRITE_FAILED)
        raise

    return audit


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def get_user_by_username(db: Session, username: str) -> User | None:
    stmt = select(User).where(User.username == username)
    return db.scalar(stmt)


def create_user(db: Session, username: str, password: str, role: UserRole) -> User:
    user = User(
        username=username,
        password_hash=get_password_hash(password),
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def ensure_default_users(
    db: Session,
    admin_username: str,
    admin_password: str,
    default_user_username: str,
    default_user_password: str,
) -> None:
    admin = get_user_by_username(db, admin_username)
    if admin is None:
        create_user(db, username=admin_username, password=admin_password, role=UserRole.ADMIN)

    normal_user = get_user_by_username(db, default_user_username)
    if normal_user is None:
        create_user(db, username=default_user_username, password=default_user_password, role=UserRole.USER)
