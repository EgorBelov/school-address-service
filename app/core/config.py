from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./school_service.db"

    dadata_token: str | None = None
    dadata_secret: str | None = None

    gigachat_credentials: str | None = None
    gigachat_verify_ssl_certs: bool = False

    ocr_space_api_key: str = "helloworld"

    class Config:
        env_file = ".env"


settings = Settings()