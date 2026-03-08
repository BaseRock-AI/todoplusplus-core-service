from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.dependencies import get_current_user
from app.db import get_db
from app.models import Base, ToDoDeleteRequest, ToDoItem, User, UserRole
from app.routers import todos as todos_router_module
from app.routers.todos import router as todos_router


def _build_client(db_session: Session, current_user_id: int) -> TestClient:
    state = {"user_id": current_user_id}
    app = FastAPI()
    app.include_router(todos_router)

    def override_get_db():
        yield db_session

    def override_get_current_user() -> User:
        return db_session.get(User, state["user_id"])

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    client = TestClient(app)
    client.state.test_user_state = state
    return client


def _seed_users(db_session: Session) -> tuple[User, User]:
    admin = User(username="admin", password_hash="x", role=UserRole.ADMIN, is_active=True)
    normal_user = User(username="user", password_hash="x", role=UserRole.USER, is_active=True)
    db_session.add_all([admin, normal_user])
    db_session.commit()
    db_session.refresh(admin)
    db_session.refresh(normal_user)
    return admin, normal_user


def test_list_todos_includes_created_by_role_and_username(monkeypatch):
    monkeypatch.setattr(todos_router_module.publisher, "publish", lambda *args, **kwargs: None)

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)

    with TestingSessionLocal() as db_session:
        admin, normal_user = _seed_users(db_session)
        db_session.add_all(
            [
                ToDoItem(name="task a", completed=False, created_by_user_id=admin.id),
                ToDoItem(name="task b", completed=True, created_by_user_id=normal_user.id),
            ]
        )
        db_session.commit()

        client = _build_client(db_session, current_user_id=admin.id)
        response = client.get("/todos")
        assert response.status_code == 200
        data = response.json()

        assert data == [
            {
                "id": 1,
                "name": "task a",
                "completed": False,
                "created_by_role": "admin",
                "created_by_username": "admin",
            },
            {
                "id": 2,
                "name": "task b",
                "completed": True,
                "created_by_role": "user",
                "created_by_username": "user",
            },
        ]


def test_list_todos_supports_scope_filter(monkeypatch):
    monkeypatch.setattr(todos_router_module.publisher, "publish", lambda *args, **kwargs: None)

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)

    with TestingSessionLocal() as db_session:
        admin, normal_user = _seed_users(db_session)
        db_session.add_all(
            [
                ToDoItem(name="pending a", completed=False, created_by_user_id=admin.id),
                ToDoItem(name="done a", completed=True, created_by_user_id=normal_user.id),
                ToDoItem(name="pending b", completed=False, created_by_user_id=normal_user.id),
            ]
        )
        db_session.commit()

        client = _build_client(db_session, current_user_id=normal_user.id)

        done_response = client.get("/todos?scope=done")
        assert done_response.status_code == 200
        assert [todo["name"] for todo in done_response.json()] == ["done a"]

        pending_response = client.get("/todos?scope=pending")
        assert pending_response.status_code == 200
        assert [todo["name"] for todo in pending_response.json()] == ["pending a", "pending b"]

        default_response = client.get("/todos")
        assert default_response.status_code == 200
        assert len(default_response.json()) == 3


def test_clear_todos_by_scope_is_allowed_for_non_admin(monkeypatch):
    monkeypatch.setattr(todos_router_module.publisher, "publish", lambda *args, **kwargs: None)

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)

    with TestingSessionLocal() as db_session:
        _admin, normal_user = _seed_users(db_session)
        db_session.add_all(
            [
                ToDoItem(name="pending a", completed=False, created_by_user_id=normal_user.id),
                ToDoItem(name="done a", completed=True, created_by_user_id=normal_user.id),
                ToDoItem(name="pending b", completed=False, created_by_user_id=normal_user.id),
            ]
        )
        db_session.commit()

        client = _build_client(db_session, current_user_id=normal_user.id)

        clear_pending = client.delete("/todos/clear?scope=pending")
        assert clear_pending.status_code == 200
        assert clear_pending.json() == {"scope": "pending", "deleted_count": 2}

        todos_after_pending_clear = client.get("/todos")
        assert todos_after_pending_clear.status_code == 200
        assert todos_after_pending_clear.json()[0]["name"] == "done a"

        clear_all_default = client.delete("/todos/clear")
        assert clear_all_default.status_code == 200
        assert clear_all_default.json() == {"scope": "all", "deleted_count": 1}

        todos_after_clear_all = client.get("/todos")
        assert todos_after_clear_all.status_code == 200
        assert todos_after_clear_all.json() == []
        assert db_session.query(ToDoDeleteRequest).count() == 0


def test_get_todo_by_id_includes_created_by_fields(monkeypatch):
    monkeypatch.setattr(todos_router_module.publisher, "publish", lambda *args, **kwargs: None)

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)

    with TestingSessionLocal() as db_session:
        admin, normal_user = _seed_users(db_session)
        todo = ToDoItem(name="task c", completed=False, created_by_user_id=normal_user.id)
        db_session.add(todo)
        db_session.commit()
        db_session.refresh(todo)

        client = _build_client(db_session, current_user_id=admin.id)
        response = client.get(f"/todos/{todo.id}")
        assert response.status_code == 200
        assert response.json() == {
            "id": todo.id,
            "name": "task c",
            "completed": False,
            "created_by_role": "user",
            "created_by_username": "user",
        }


def test_create_and_update_todo_return_creator_fields(monkeypatch):
    monkeypatch.setattr(todos_router_module.publisher, "publish", lambda *args, **kwargs: None)

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)

    with TestingSessionLocal() as db_session:
        admin, normal_user = _seed_users(db_session)
        client = _build_client(db_session, current_user_id=normal_user.id)

        create_response = client.post("/todos", json={"name": "task new", "completed": False})
        assert create_response.status_code == 201
        created = create_response.json()
        assert created["created_by_role"] == "user"
        assert created["created_by_username"] == "user"

        update_response = client.put(f"/todos/{created['id']}", json={"completed": True})
        assert update_response.status_code == 200
        updated = update_response.json()
        assert updated["created_by_role"] == "user"
        assert updated["created_by_username"] == "user"
        assert updated["completed"] is True
