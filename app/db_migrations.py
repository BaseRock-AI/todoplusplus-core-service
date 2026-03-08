from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from app.core.config import settings
from app.models import UserRole


def migrate_todo_creator_fields(engine: Engine) -> None:
    inspector = inspect(engine)
    if "todo_items" not in inspector.get_table_names():
        return

    todo_columns = {column["name"] for column in inspector.get_columns("todo_items")}

    with engine.begin() as conn:
        if "created_by_user_id" not in todo_columns:
            conn.execute(text("ALTER TABLE todo_items ADD COLUMN created_by_user_id INTEGER"))

        if engine.dialect.name == "postgresql":
            fk_exists = conn.execute(
                text(
                    """
                    SELECT 1
                    FROM pg_constraint
                    WHERE conname = 'fk_todo_items_created_by_user_id_users'
                    """
                )
            ).scalar_one_or_none()
            if fk_exists is None:
                conn.execute(
                    text(
                        """
                        ALTER TABLE todo_items
                        ADD CONSTRAINT fk_todo_items_created_by_user_id_users
                        FOREIGN KEY (created_by_user_id) REFERENCES users(id)
                        ON DELETE SET NULL
                        """
                    )
                )

            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_todo_items_created_by_user_id ON todo_items (created_by_user_id)"))

        creator_id = conn.execute(
            text("SELECT id FROM users WHERE username = :username LIMIT 1"),
            {"username": settings.app_auth_user},
        ).scalar_one_or_none()
        if creator_id is None:
            creator_id = conn.execute(
                text("SELECT id FROM users WHERE role = :role ORDER BY id ASC LIMIT 1"),
                {"role": UserRole.ADMIN},
            ).scalar_one_or_none()
        if creator_id is None:
            creator_id = conn.execute(text("SELECT id FROM users ORDER BY id ASC LIMIT 1")).scalar_one_or_none()

        if creator_id is not None:
            conn.execute(
                text("UPDATE todo_items SET created_by_user_id = :creator_id WHERE created_by_user_id IS NULL"),
                {"creator_id": creator_id},
            )


def migrate_user_role_values(engine: Engine) -> None:
    inspector = inspect(engine)
    if "users" not in inspector.get_table_names():
        return

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE users
                SET role = CASE
                    WHEN lower(role) = :admin THEN :admin
                    WHEN lower(role) = :user THEN :user
                    ELSE :user
                END
                """
            ),
            {"admin": UserRole.ADMIN.value, "user": UserRole.USER.value},
        )
