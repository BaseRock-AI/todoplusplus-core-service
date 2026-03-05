import json
import logging
from typing import Any


class Events:
    APP_STARTUP = "APP_STARTUP"
    APP_SHUTDOWN = "APP_SHUTDOWN"
    APP_MODE = "APP_MODE"

    TODO_CREATE_REQUEST = "TODO_CREATE_REQUEST"
    TODO_CREATED_DB = "TODO_CREATED_DB"
    TODO_CREATE_FAILED = "TODO_CREATE_FAILED"

    DB_AUDIT_WRITE = "DB_AUDIT_WRITE"
    DB_AUDIT_WRITE_FAILED = "DB_AUDIT_WRITE_FAILED"

    KAFKA_PUBLISH_REQUEST = "KAFKA_PUBLISH_REQUEST"
    KAFKA_PUBLISH_ACK = "KAFKA_PUBLISH_ACK"
    KAFKA_PUBLISH_FAILED = "KAFKA_PUBLISH_FAILED"

    KAFKA_CONSUMER_INIT = "KAFKA_CONSUMER_INIT"
    KAFKA_CONSUMER_START = "KAFKA_CONSUMER_START"
    KAFKA_CONSUMER_MESSAGE = "KAFKA_CONSUMER_MESSAGE"
    KAFKA_CONSUMER_HANDLER_FAILED = "KAFKA_CONSUMER_HANDLER_FAILED"
    KAFKA_CONSUMER_STOP = "KAFKA_CONSUMER_STOP"

    JIRA_CREATE_ATTEMPT = "JIRA_CREATE_ATTEMPT"
    JIRA_CREATE_SUCCESS = "JIRA_CREATE_SUCCESS"
    JIRA_CREATE_FAILED = "JIRA_CREATE_FAILED"
    JIRA_CREATE_SKIPPED = "JIRA_CREATE_SKIPPED"

    EMAIL_SEND_ATTEMPT = "EMAIL_SEND_ATTEMPT"
    EMAIL_SEND_SUCCESS = "EMAIL_SEND_SUCCESS"
    EMAIL_SEND_FAILED = "EMAIL_SEND_FAILED"
    EMAIL_SEND_SKIPPED = "EMAIL_SEND_SKIPPED"


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s.%(msecs)03d | %(levelname)-5s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def integration_mode(enabled: bool) -> str:
    return "REAL" if enabled else "LOCAL"


def log_event(logger: logging.Logger, level: int, event: str, **fields: Any) -> None:
    payload = json.dumps(fields, sort_keys=True, default=str)
    logger.log(level, "=== [%s] %s", event, payload)

# -----------------------------------------------------------------------------
# HOW TO USE THIS LOGGER IN A NEW PYTHON FILE (STEP-BY-STEP)
#
# 1) Add a new event constant in Events above.
#    Example:
#      USER_SYNC_STARTED = "USER_SYNC_STARTED"
#      USER_SYNC_SUCCESS = "USER_SYNC_SUCCESS"
#      USER_SYNC_FAILED = "USER_SYNC_FAILED"
#
# 2) In the new file, import logging + helpers from this module.
#    Example (in app/services/user_sync_service.py):
#      import logging
#      from app.logging_utils import Events, log_event
#
#      logger = logging.getLogger(__name__)
#
# 3) Log major flow points: start, success, failure.
#    Example:
#      def sync_user(user_id: int) -> None:
#          log_event(logger, logging.INFO, Events.USER_SYNC_STARTED, user_id=user_id)
#          try:
#              # ... do work ...
#              log_event(logger, logging.INFO, Events.USER_SYNC_SUCCESS, user_id=user_id)
#          except Exception as exc:
#              log_event(
#                  logger,
#                  logging.ERROR,
#                  Events.USER_SYNC_FAILED,
#                  user_id=user_id,
#                  error=str(exc),
#              )
#              logger.exception("[%s] stacktrace", Events.USER_SYNC_FAILED)
#              raise
#
# 4) If your new file talks to an external integration, include mode/component.
#    Example fields:
#      mode="LOCAL" or "REAL"
#      component="kafka_producer" / "kafka_consumer" / "jira" / "email"
#
# 5) No extra setup needed in the new file if app startup already calls
#    configure_logging() (currently done in app/main.py).
#
# Expected log style:
# 2026-03-04 16:00:00.123 | INFO  | app.services.user_sync_service |
# === [USER_SYNC_STARTED] {"user_id":123}
# -----------------------------------------------------------------------------
