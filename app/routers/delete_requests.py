from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_admin
from app.db import get_db
from app.models import DeleteRequestStatus, User, UserRole
from app.repositories import (
    approve_delete_request,
    get_delete_request,
    list_delete_requests,
    reject_delete_request,
)
from app.schemas_delete_request import DeleteRequestDecisionResponse, ToDoDeleteRequestOut

router = APIRouter(prefix="/delete-requests", tags=["delete-requests"])


@router.get("", response_model=list[ToDoDeleteRequestOut])
def get_delete_requests(
    status_filter: str | None = Query(default=None, alias="status"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ToDoDeleteRequestOut]:
    if current_user.role == UserRole.ADMIN:
        return list_delete_requests(db, status_filter=status_filter)
    return list_delete_requests(db, requested_by_user_id=current_user.id, status_filter=status_filter)


@router.post("/{request_id}/approve", response_model=DeleteRequestDecisionResponse)
def approve_request(
    request_id: int,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> DeleteRequestDecisionResponse:
    delete_request = get_delete_request(db, request_id)
    if delete_request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delete request not found")
    if delete_request.status != DeleteRequestStatus.PENDING:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Delete request is already processed")

    todo_id = delete_request.todo_id
    try:
        approve_delete_request(db, delete_request, admin_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return DeleteRequestDecisionResponse(id=request_id, status=DeleteRequestStatus.APPROVED, todo_id=todo_id)


@router.post("/{request_id}/reject", response_model=DeleteRequestDecisionResponse)
def reject_request(
    request_id: int,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> DeleteRequestDecisionResponse:
    delete_request = get_delete_request(db, request_id)
    if delete_request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delete request not found")
    if delete_request.status != DeleteRequestStatus.PENDING:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Delete request is already processed")

    reject_delete_request(db, delete_request, admin_user.id)
    return DeleteRequestDecisionResponse(id=request_id, status=DeleteRequestStatus.REJECTED, todo_id=delete_request.todo_id)
