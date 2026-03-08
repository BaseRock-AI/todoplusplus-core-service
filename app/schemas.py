from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models import UserRole


class ToDoCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    completed: bool = False


class ToDoUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    completed: Optional[bool] = None


class ToDoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    completed: bool
    created_by_role: UserRole
    created_by_username: Optional[str] = None


class ToDoCompleteResponse(BaseModel):
    id: int
    completed: bool


class ToDoBulkCreateResult(BaseModel):
    created_count: int
    ids: list[int]


class ToDoClearResponse(BaseModel):
    scope: Literal["all", "done", "pending"]
    deleted_count: int


class ToDoAttachmentOut(BaseModel):
    id: int
    todo_id: int
    filename: str
    content_type: str | None = None
    size_bytes: int


class ToDoAttachmentUploadOut(BaseModel):
    attachment_id: int
    todo_id: int
    filename: str
    content_type: str | None = None
    size_bytes: int


class JiraToDoItem(BaseModel):
    id: int
    name: str
    completed: bool
    jira_id: Optional[str] = None
    key: Optional[str] = None
    url: Optional[str] = None
