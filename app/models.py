from enum import Enum

from sqlalchemy import Boolean, Column, DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class UserRole(str, Enum):
    ADMIN = "admin"
    USER = "user"


class DeleteRequestStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class AttachmentCategory(str, Enum):
    COMPLETION_PROOF = "COMPLETION_PROOF"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(
        SAEnum(
            UserRole,
            name="user_role",
            native_enum=False,
            validate_strings=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=UserRole.USER,
    )
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ToDoItem(Base):
    __tablename__ = "todo_items"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    completed = Column(Boolean, nullable=False, default=False)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ToDoAttachment(Base):
    __tablename__ = "todo_attachments"

    id = Column(Integer, primary_key=True, index=True)
    todo_id = Column(Integer, ForeignKey("todo_items.id", ondelete="CASCADE"), nullable=False, index=True)
    category = Column(
        SAEnum(AttachmentCategory, name="attachment_category", native_enum=False, validate_strings=True),
        nullable=False,
        default=AttachmentCategory.COMPLETION_PROOF,
    )
    storage_key = Column(String(255), nullable=False, unique=True, index=True)
    original_filename = Column(String(255), nullable=False)
    content_type = Column(String(150), nullable=True)
    size_bytes = Column(Integer, nullable=False)
    uploaded_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ToDoDeleteRequest(Base):
    __tablename__ = "todo_delete_requests"

    id = Column(Integer, primary_key=True, index=True)
    todo_id = Column(Integer, ForeignKey("todo_items.id", ondelete="CASCADE"), nullable=False, index=True)
    requested_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(
        SAEnum(DeleteRequestStatus, name="delete_request_status", native_enum=False, validate_strings=True),
        nullable=False,
        default=DeleteRequestStatus.PENDING,
        index=True,
    )
    reviewed_by_admin_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Audit(Base):
    __tablename__ = "audits"

    id = Column(Integer, primary_key=True, index=True)
    type = Column(String(100), nullable=False)
    value = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
