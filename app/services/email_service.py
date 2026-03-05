import logging
import smtplib
from email.message import EmailMessage

from app.core.config import settings
from app.logging_utils import Events, integration_mode, log_event

logger = logging.getLogger(__name__)


class EmailService:
    def send_todo_notification(self, subject: str, body: str) -> None:
        mode = integration_mode(settings.email_enabled)
        if not settings.email_enabled:
            log_event(logger, logging.INFO, Events.EMAIL_SEND_SKIPPED, mode=mode, reason="email_disabled", subject=subject)
            return

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = settings.email_from or settings.email_smtp_username
        msg["To"] = settings.email_recipient
        msg.set_content(body)

        log_event(
            logger,
            logging.INFO,
            Events.EMAIL_SEND_ATTEMPT,
            mode=mode,
            smtp_host=settings.email_smtp_host,
            smtp_port=settings.email_smtp_port,
            recipient=settings.email_recipient,
            subject=subject,
        )

        try:
            with smtplib.SMTP(settings.email_smtp_host, settings.email_smtp_port, timeout=20) as smtp:
                smtp.starttls()
                smtp.login(settings.email_smtp_username, settings.email_smtp_password)
                smtp.send_message(msg)
            log_event(logger, logging.INFO, Events.EMAIL_SEND_SUCCESS, mode=mode, recipient=settings.email_recipient, subject=subject)
        except Exception:
            log_event(logger, logging.ERROR, Events.EMAIL_SEND_FAILED, mode=mode, recipient=settings.email_recipient, subject=subject)
            logger.exception("[%s] stacktrace", Events.EMAIL_SEND_FAILED)
            raise
