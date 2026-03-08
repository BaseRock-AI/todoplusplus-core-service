import json

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.dependencies import get_current_user
from app.db import get_db
from app.models import Base, User, UserRole
from app.routers import todos as todos_router_module
from app.routers.todos import router as todos_router
from app.services.storage import LocalStorageProvider


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


def test_upload_download_independent_of_complete_status(monkeypatch, tmp_path):
    monkeypatch.setattr(todos_router_module.publisher, "publish", lambda *args, **kwargs: None)
    monkeypatch.setattr(todos_router_module, "storage_provider", LocalStorageProvider(str(tmp_path)))

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

        create_response = client.post("/todos", json={"name": "task with proof", "completed": False})
        assert create_response.status_code == 201
        todo_id = create_response.json()["id"]

        upload_response = client.post(
            f"/todos/{todo_id}/attachments/upload",
            files={"file": ("proof.txt", b"done", "text/plain")},
        )
        assert upload_response.status_code == 201
        uploaded = upload_response.json()
        assert uploaded["todo_id"] == todo_id
        assert uploaded["filename"] == "proof.txt"

        # Uploading a file must not change completion status.
        todo_after_upload = client.get(f"/todos/{todo_id}")
        assert todo_after_upload.status_code == 200
        assert todo_after_upload.json()["completed"] is False

        complete_response = client.post(f"/todos/{todo_id}/complete")
        assert complete_response.status_code == 200
        assert complete_response.json() == {"id": todo_id, "completed": True}

        download_response = client.get(f"/todos/{todo_id}/attachments/{uploaded['attachment_id']}/download")
        assert download_response.status_code == 200
        assert download_response.content == b"done"
        assert "attachment; filename=\"proof.txt\"" in download_response.headers["content-disposition"]



def test_bulk_import_json(monkeypatch):
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
        client = _build_client(db_session, current_user_id=normal_user.id)

        payload = [
            {"name": "bulk one", "completed": False},
            {"name": "bulk two", "completed": True},
        ]
        response = client.post(
            "/todos/bulk-import",
            files={"file": ("todos.json", json.dumps(payload).encode("utf-8"), "application/json")},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["created_count"] == 2
        assert len(data["ids"]) == 2

        list_response = client.get("/todos")
        assert list_response.status_code == 200
        todos = list_response.json()
        assert len(todos) == 2
        assert {todo["name"] for todo in todos} == {"bulk one", "bulk two"}


def test_bulk_import_json_request_body(monkeypatch):
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
        client = _build_client(db_session, current_user_id=normal_user.id)

        response = client.post(
            "/todos/bulk-import",
            json=[
                {"name": "json body one", "completed": False},
                {"name": "json body two", "completed": True},
            ],
        )

        assert response.status_code == 201
        data = response.json()
        assert data["created_count"] == 2
        assert len(data["ids"]) == 2


def test_bulk_import_csv_requires_name_header(monkeypatch):
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
        client = _build_client(db_session, current_user_id=normal_user.id)

        csv_without_header = b"eat coffee\ndrink cake\nwalk on swimming pool\n"
        response = client.post(
            "/todos/bulk-import",
            files={"file": ("todos.csv", csv_without_header, "text/csv")},
        )

        assert response.status_code == 422
        assert response.json()["detail"] == "CSV import requires a 'name' header column"


def test_bulk_import_example_downloads_are_usable(monkeypatch):
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
        client = _build_client(db_session, current_user_id=normal_user.id)

        csv_example = client.get("/todos/bulk-import/examples/tabular?format=csv")
        assert csv_example.status_code == 200
        assert "attachment; filename=\"bulk-import-example.csv\"" in csv_example.headers["content-disposition"]
        assert "name,completed" in csv_example.text

        json_example = client.get("/todos/bulk-import/examples/json")
        assert json_example.status_code == 200
        assert "attachment; filename=\"bulk-import-example.json\"" in json_example.headers["content-disposition"]
        parsed_json = json.loads(json_example.text)
        assert isinstance(parsed_json, list)
        assert parsed_json[0]["name"] == "Write sprint summary"

        xlsx_example = client.get("/todos/bulk-import/examples/tabular?format=xlsx")
        assert xlsx_example.status_code == 200
        assert "attachment; filename=\"bulk-import-example.xlsx\"" in xlsx_example.headers["content-disposition"]
        assert xlsx_example.content.startswith(b"PK")

        csv_import = client.post(
            "/todos/bulk-import",
            files={"file": ("bulk-import-example.csv", csv_example.content, "text/csv")},
        )
        assert csv_import.status_code == 201
        assert csv_import.json()["created_count"] == 3

        json_import = client.post(
            "/todos/bulk-import",
            files={"file": ("bulk-import-example.json", json_example.content, "application/json")},
        )
        assert json_import.status_code == 201
        assert json_import.json()["created_count"] == 3

        xlsx_import = client.post(
            "/todos/bulk-import",
            files={
                "file": (
                    "bulk-import-example.xlsx",
                    xlsx_example.content,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )
        assert xlsx_import.status_code == 201
        assert xlsx_import.json()["created_count"] == 3
