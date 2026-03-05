import json
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.core.config import settings
from app.db import get_db
from app.kafka_client import publisher
from app.logging_utils import Events, log_event
from app.models import DeleteRequestStatus, User, UserRole
from app.repositories import (
    create_delete_request,
    create_todo,
    delete_todo,
    get_pending_delete_request,
    get_todo,
    get_todo_item,
    list_todos,
    update_todo,
)
from app.schemas import ToDoCreate, ToDoOut, ToDoUpdate
from app.schemas_delete_request import DeleteTodoActionResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/todos", tags=["todos"])


@router.get("", response_model=list[ToDoOut])
def get_todos(_: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[ToDoOut]:
    return list_todos(db)


@router.get("/{todo_id}", response_model=ToDoOut)
def get_todo_by_id(todo_id: int, _: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ToDoOut:
    todo = get_todo(db, todo_id)
    if not todo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"ToDo item {todo_id} not found")
    return todo


@router.post("", response_model=ToDoOut, status_code=status.HTTP_201_CREATED)
def create_todo_item(payload: ToDoCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ToDoOut:
    log_event(
        logger,
        logging.INFO,
        Events.TODO_CREATE_REQUEST,
        name=payload.name,
        completed=payload.completed,
    )

    todo = create_todo(db, payload, current_user.id)
    todo_payload = {"id": todo.id, "name": todo.name, "completed": todo.completed}

    log_event(logger, logging.INFO, Events.TODO_CREATED_DB, todo_id=todo.id, name=todo.name, completed=todo.completed)

    publisher.publish(settings.topic_jira, str(todo.id), todo_payload)
    publisher.publish(settings.topic_audit, str(todo.id), {"type": "TODO", "value": json.dumps(todo_payload)})
    return get_todo(db, todo.id)


@router.put("/{todo_id}", response_model=ToDoOut)
def update_todo_item(
    todo_id: int,
    payload: ToDoUpdate,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ToDoOut:
    todo = get_todo_item(db, todo_id)
    if not todo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"ToDo item {todo_id} not found")
    updated_todo = update_todo(db, todo, payload)
    return get_todo(db, updated_todo.id)


@router.delete("/{todo_id}", response_model=DeleteTodoActionResponse)
def delete_todo_item(
    todo_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DeleteTodoActionResponse:
    todo = get_todo_item(db, todo_id)
    if not todo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"ToDo item {todo_id} not found")

    if current_user.role == UserRole.ADMIN:
        delete_todo(db, todo)
        return DeleteTodoActionResponse(action="deleted", message=f"ToDo item {todo_id} deleted")

    existing_request = get_pending_delete_request(db, todo_id, current_user.id)
    if existing_request:
        return DeleteTodoActionResponse(
            action="pending_approval",
            message="Delete request already pending admin approval",
            delete_request_id=existing_request.id,
        )

    delete_request = create_delete_request(db, todo_id=todo_id, requested_by_user_id=current_user.id)
    return DeleteTodoActionResponse(
        action=DeleteRequestStatus.PENDING,
        message="Delete request submitted for admin approval",
        delete_request_id=delete_request.id,
    )
