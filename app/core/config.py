from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "ToDoPlusPlus Core Service"
    app_host: str = "0.0.0.0"
    app_port: int = 8081
    cors_allowed_origins: str = "http://localhost:5173,http://localhost:5174"

    app_auth_user: str = "admin"
    app_auth_password: str = "password123"
    default_user_username: str = "user"
    default_user_password: str = "password123"

    jwt_secret_key: str = "change-this-in-env"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60

    database_url: str = "postgresql+psycopg://todo:todo@localhost:5437/todo_app"

    kafka_bootstrap_servers: str = "localhost:9093"
    topic_jira: str = "todo-items-jira"
    topic_email: str = "todo-items-email"
    topic_audit: str = "todo-items-audit"

    jira_enabled: bool = False
    jira_api_url: str = ""
    jira_api_email: str = ""
    jira_api_token: str = ""
    jira_project_key: str = "TODO"
    jira_issue_type: str = "Task"

    email_enabled: bool = False
    email_smtp_host: str = "smtp.gmail.com"
    email_smtp_port: int = 587
    email_smtp_username: str = ""
    email_smtp_password: str = ""
    email_from: str = ""
    email_recipient: str = ""


settings = Settings()
