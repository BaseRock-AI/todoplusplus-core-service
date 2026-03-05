import base64
import logging
from typing import Any

import httpx

from app.core.config import settings
from app.logging_utils import Events, integration_mode, log_event

logger = logging.getLogger(__name__)


class JiraService:
    def create_issue(self, name: str) -> dict[str, Any]:
        mode = integration_mode(settings.jira_enabled)
        if not settings.jira_enabled:
            log_event(logger, logging.INFO, Events.JIRA_CREATE_SKIPPED, mode=mode, reason="jira_disabled", todo_name=name)
            return {}

        token = base64.b64encode(
            f"{settings.jira_api_email}:{settings.jira_api_token}".encode("utf-8")
        ).decode("utf-8")

        payload = {
            "fields": {
                "summary": f"ToDo: {name}",
                "issuetype": {"name": settings.jira_issue_type},
                "project": {"key": settings.jira_project_key},
            }
        }

        headers = {
            "Authorization": f"Basic {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        endpoint = f"{settings.jira_api_url}/rest/api/3/issue"
        log_event(
            logger,
            logging.INFO,
            Events.JIRA_CREATE_ATTEMPT,
            mode=mode,
            endpoint=endpoint,
            project_key=settings.jira_project_key,
            issue_type=settings.jira_issue_type,
            todo_name=name,
        )

        try:
            with httpx.Client(timeout=20.0) as client:
                response = client.post(endpoint, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
                log_event(
                    logger,
                    logging.INFO,
                    Events.JIRA_CREATE_SUCCESS,
                    mode=mode,
                    jira_id=data.get("id"),
                    jira_key=data.get("key"),
                    status_code=response.status_code,
                )
                return data
        except httpx.HTTPStatusError as exc:
            error_text = exc.response.text.strip().replace("\n", " ")
            log_event(
                logger,
                logging.ERROR,
                Events.JIRA_CREATE_FAILED,
                mode=mode,
                status_code=exc.response.status_code,
                endpoint=endpoint,
                error_body=error_text,
            )
            raise
        except Exception:
            log_event(logger, logging.ERROR, Events.JIRA_CREATE_FAILED, mode=mode, endpoint=endpoint)
            logger.exception("[%s] stacktrace", Events.JIRA_CREATE_FAILED)
            raise
