from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_encoding="utf-8",
        extra="allow",
        case_sensitive=False
    )

    # environment
    ENVIRONMENT: str = "development"

    # api details
    API_PREFIX: str = "/api/v1"
    API_TITLE: str = "URL Shortner"
    API_VERSION: str = "v1.0"

    # async db
    ASYNC_DB_URL: str

    # sync db
    SYNC_DB_URL: str

    # test db
    ASYNC_TEST_DB_URL: str

    # Argon2
    ARGON2_PASSWORD_PEPPER: str

    # JWT
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_TIME: int = 3
    REFRESH_TOKEN_EXPIRE_TIME: int = 1
    ACCESS_TOKEN_SECRET_KEY: str
    REFRESH_TOKEN_SECRET_KEY: str

    # redis
    REDIS_URL: str

    # sentry
    SENTRY_SDK_DSN: str

    # google oauth
    CLIENT_ID: str
    CLIENT_SECRET: str

    # session middleware
    SESSION_SECRET_KEY: str

    # get shortened url
    URL_EXPIRE_TIME: int
    SHORTEN_URL: str = "http://localhost:8000/api/v1/shorten"

    # rabbitmq
    API_BROKER: str

    # resend email
    API_EMAIL: str
    RESEND_API_KEY: str

    # otp
    OTP_EXPIRE_TIME: int

@lru_cache(maxsize=1)
def get_settings():
    return Settings()
