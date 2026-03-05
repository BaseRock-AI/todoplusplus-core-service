import json
import logging
import threading
from collections.abc import Callable

from confluent_kafka import Consumer

from app.core.config import settings
from app.db import SessionLocal
from app.kafka_client import publisher
from app.logging_utils import Events, integration_mode, log_event
from app.repositories import create_audit
from app.schemas import JiraToDoItem
from app.services.email_service import EmailService
from app.services.jira_service import JiraService

logger = logging.getLogger(__name__)


class ConsumerWorker(threading.Thread):
    def __init__(self, topic: str, group_id: str, handler: Callable[[dict], None]):
        super().__init__(daemon=True)
        self.topic = topic
        self.group_id = group_id
        self.handler = handler
        self._stop_event = threading.Event()
        self._consumer = Consumer(
            {
                "bootstrap.servers": settings.kafka_bootstrap_servers,
                "group.id": group_id,
                "auto.offset.reset": "earliest",
            }
        )
        self._consumer.subscribe([topic])
        log_event(
            logger,
            logging.INFO,
            Events.KAFKA_CONSUMER_INIT,
            component="kafka_consumer",
            topic=topic,
            group_id=group_id,
        )

    def run(self) -> None:
        log_event(
            logger,
            logging.INFO,
            Events.KAFKA_CONSUMER_START,
            component="kafka_consumer",
            topic=self.topic,
            group_id=self.group_id,
        )

        while not self._stop_event.is_set():
            msg = self._consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                log_event(
                    logger,
                    logging.ERROR,
                    Events.KAFKA_CONSUMER_HANDLER_FAILED,
                    component="kafka_consumer",
                    topic=self.topic,
                    group_id=self.group_id,
                    error=str(msg.error()),
                )
                continue
            try:
                payload = json.loads(msg.value().decode("utf-8"))
                log_event(
                    logger,
                    logging.INFO,
                    Events.KAFKA_CONSUMER_MESSAGE,
                    component="kafka_consumer",
                    topic=msg.topic(),
                    partition=msg.partition(),
                    offset=msg.offset(),
                    key=msg.key().decode("utf-8") if msg.key() else None,
                )
                self.handler(payload)
            except Exception:
                log_event(
                    logger,
                    logging.ERROR,
                    Events.KAFKA_CONSUMER_HANDLER_FAILED,
                    component="kafka_consumer",
                    topic=self.topic,
                    group_id=self.group_id,
                )
                logger.exception("[%s] stacktrace", Events.KAFKA_CONSUMER_HANDLER_FAILED)

        self._consumer.close()
        log_event(
            logger,
            logging.INFO,
            Events.KAFKA_CONSUMER_STOP,
            component="kafka_consumer",
            topic=self.topic,
            group_id=self.group_id,
        )

    def stop(self) -> None:
        self._stop_event.set()


jira_service = JiraService()
email_service = EmailService()
workers: list[ConsumerWorker] = []


def handle_jira(payload: dict) -> None:
    jira_response = {}
    jira_mode = integration_mode(settings.jira_enabled)

    if not settings.jira_enabled:
        log_event(
            logger,
            logging.INFO,
            Events.JIRA_CREATE_SKIPPED,
            mode=jira_mode,
            reason="local_mode_integration_disabled",
            todo_id=payload.get("id"),
            todo_name=payload.get("name"),
        )
    else:
        try:
            jira_response = jira_service.create_issue(payload["name"])
        except Exception as exc:
            logger.error("[%s] error=%r", Events.JIRA_CREATE_FAILED, exc)

    jira_item = JiraToDoItem(
        id=payload["id"],
        name=payload["name"],
        completed=payload["completed"],
        jira_id=str(jira_response.get("id")) if jira_response.get("id") else None,
        key=jira_response.get("key"),
        url=jira_response.get("self"),
    )

    publisher.publish(settings.topic_email, str(jira_item.id), jira_item.model_dump())


def handle_email(payload: dict) -> None:
    jira_item = JiraToDoItem.model_validate(payload)
    subject = f"New ToDo Item Created-> {jira_item.name}"
    body = f"A new task has been assigned: {jira_item.model_dump_json()}"
    email_mode = integration_mode(settings.email_enabled)

    if not settings.email_enabled:
        email_service.send_todo_notification(subject, body)
        audit_type = "EMAIL_SKIPPED"
        audit_value = (
            f"mode={email_mode}; reason=local_mode_integration_disabled; "
            f"subject={subject}; payload={jira_item.model_dump_json()}"
        )
    else:
        try:
            email_service.send_todo_notification(subject, body)
            audit_type = "EMAIL"
            audit_value = f"mode={email_mode}; sent_to={settings.email_recipient}; subject={subject}; body={body}"
        except Exception as exc:
            logger.error("[%s] error=%r", Events.EMAIL_SEND_FAILED, exc)
            audit_type = "ERROR"
            audit_value = f"mode={email_mode}; email_failed={exc}; payload={jira_item.model_dump_json()}"

    publisher.publish(settings.topic_audit, str(jira_item.id), {"type": audit_type, "value": audit_value})


def handle_audit(payload: dict) -> None:
    db = SessionLocal()
    try:
        create_audit(db, audit_type=payload["type"], value=payload["value"])
    finally:
        db.close()


def start_consumers() -> None:
    global workers
    workers = [
        ConsumerWorker(settings.topic_jira, "todo-jira-consumer-group", handle_jira),
        ConsumerWorker(settings.topic_email, "todo-email-consumer-group", handle_email),
        ConsumerWorker(settings.topic_audit, "todo-audit-consumer-group", handle_audit),
    ]
    for worker in workers:
        worker.start()


def stop_consumers() -> None:
    for worker in workers:
        worker.stop()
    for worker in workers:
        worker.join(timeout=5)
