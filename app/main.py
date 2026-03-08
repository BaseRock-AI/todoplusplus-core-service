import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.consumers import start_consumers, stop_consumers
from app.core.config import settings
from app.db import SessionLocal, engine
from app.db_migrations import migrate_todo_creator_fields, migrate_user_role_values
from app.kafka_client import publisher
from app.logging_utils import Events, configure_logging, integration_mode, log_event
from app.models import Base
from app.repositories import ensure_default_users
from app.routers.auth import router as auth_router
from app.routers.delete_requests import router as delete_requests_router
from app.routers.todos import router as todos_router

configure_logging()
logger = logging.getLogger(__name__)


def _parse_origins(raw_origins: str) -> list[str]:
    return [origin.strip() for origin in raw_origins.split(",") if origin.strip()]


@asynccontextmanager
async def lifespan(_: FastAPI):
    mode_jira = integration_mode(settings.jira_enabled)
    mode_email = integration_mode(settings.email_enabled)
    runtime_mode = "LOCAL" if (mode_jira == "LOCAL" and mode_email == "LOCAL") else "REAL_INTEGRATIONS"

    log_event(
        logger,
        logging.INFO,
        Events.APP_STARTUP,
        app_name=settings.app_name,
        runtime_mode=runtime_mode,
        jira_mode=mode_jira,
        email_mode=mode_email,
        kafka_bootstrap=settings.kafka_bootstrap_servers,
        topic_jira=settings.topic_jira,
        topic_email=settings.topic_email,
        topic_audit=settings.topic_audit,
    )

    Base.metadata.create_all(bind=engine)
    migrate_todo_creator_fields(engine)
    migrate_user_role_values(engine)

    db = SessionLocal()
    try:
        ensure_default_users(
            db,
            admin_username=settings.app_auth_user,
            admin_password=settings.app_auth_password,
            default_user_username=settings.default_user_username,
            default_user_password=settings.default_user_password,
        )
    finally:
        db.close()

    start_consumers()
    log_event(logger, logging.INFO, Events.APP_MODE, detail="consumers_started")

    try:
        yield
    finally:
        stop_consumers()
        publisher.close()
        log_event(logger, logging.INFO, Events.APP_SHUTDOWN, detail="consumers_stopped_publisher_closed")


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_parse_origins(settings.cors_allowed_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router)
app.include_router(todos_router)
app.include_router(delete_requests_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
