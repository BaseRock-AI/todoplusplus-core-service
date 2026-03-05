from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


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
    created_by_role: Literal["admin", "user"]
    created_by_username: Optional[str] = None


class JiraToDoItem(BaseModel):
    id: int
    name: str
    completed: bool
    jira_id: Optional[str] = None
    key: Optional[str] = None
    url: Optional[str] = None
