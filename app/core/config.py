from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


# Корень проекта — папка, в которой лежит /app/.
# Используется чтобы относительные пути в .env (DATABASE_URL и .env)
# резолвились относительно проекта, а не cwd процесса.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_PROJECT_ROOT / ".env", extra="ignore")

    database_url: str = f"sqlite:///{_PROJECT_ROOT / 'school_service.db'}"

    dadata_token: str | None = None
    dadata_secret: str | None = None

    gigachat_credentials: str | None = None
    gigachat_verify_ssl_certs: bool = False

    ocr_space_api_key: str = "helloworld"


settings = Settings()

# Если в .env задан DATABASE_URL с относительным sqlite-путём
# (`sqlite:///./school_service.db`) — перепишем его в абсолютный.
# Без этого SQLite иногда открывает «не тот» файл (cwd может быть
# другим) и падает с `attempt to write a readonly database`.
if settings.database_url.startswith("sqlite:///./"):
    rel = settings.database_url.removeprefix("sqlite:///./")
    settings.database_url = f"sqlite:///{_PROJECT_ROOT / rel}"
