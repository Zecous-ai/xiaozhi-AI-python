from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "xiaozhi-server-python"
    environment: str = "dev"
    server_host: str = "0.0.0.0"
    server_port: int = 8091
    server_domain: str = ""

    # MySQL
    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_user: str = "xiaozhi"
    mysql_password: str = "123456"
    mysql_db: str = "xiaozhi"

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str | None = None

    # Token
    token_name: str = "Authorization"
    token_prefix: str = "Bearer"
    token_timeout_seconds: int = 2592000

    # Upload
    upload_path: str = "uploads"

    # WebSocket
    websocket_path: str = "/ws/xiaozhi/v1/"
    websocket_allowed_origins: str = "*"

    # Session
    check_inactive_session: bool = True
    inactive_timeout_seconds: int = 20

    # COS
    tencent_cos_secret_id: str | None = None
    tencent_cos_secret_key: str | None = None
    tencent_cos_region: str | None = None
    tencent_cos_bucket_name: str | None = None
    tencent_cos_path_prefix: str = "uploads/"

    # SMS (Aliyun)
    sms_aliyun_access_key_id: str | None = None
    sms_aliyun_access_key_secret: str | None = None
    sms_aliyun_sign_name: str | None = None
    sms_aliyun_template_code: str | None = None

    # Email
    email_host: str | None = None
    email_port: int = 465
    email_user: str | None = None
    email_password: str | None = None
    email_from: str | None = None

    # TTS
    tts_timeout_ms: int = 10000
    tts_max_retry_count: int = 1
    tts_retry_delay_ms: int = 1000
    tts_max_concurrent_per_session: int = 3


settings = Settings()
