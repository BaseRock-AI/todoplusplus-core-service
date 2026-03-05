from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DeleteTodoActionResponse(BaseModel):
    action: str
    message: str
    delete_request_id: int | None = None


class DeleteRequestDecisionResponse(BaseModel):
    id: int
    status: str
    todo_id: int


class ToDoDeleteRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    todo_id: int
    requested_by_user_id: int
    status: str
    reviewed_by_admin_id: int | None
    reviewed_at: datetime | None
    created_at: datetime
