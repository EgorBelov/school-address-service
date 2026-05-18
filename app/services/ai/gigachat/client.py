from gigachat import GigaChat

from app.core.config import settings


def get_gigachat_client() -> GigaChat:
    return GigaChat(
        credentials=settings.gigachat_credentials,
        verify_ssl_certs=settings.gigachat_verify_ssl_certs,

        # Длинные постановления: дефолт ~30s — мало.
        timeout=120.0,

        # Встроенный в gigachat-клиент retry на сетевые/HTTP ошибки.
        # SSL UNEXPECTED_EOF, разрывы соединения, 5xx — лечатся повтором.
        max_retries=4,
        retry_backoff_factor=2.0,
        retry_on_status_codes=(408, 425, 429, 500, 502, 503, 504),

        # Один коннект — без пула. Часто SSL EOF возникает на reused
        # keep-alive соединениях, у Сбера это бывает регулярно.
        max_connections=1,
    )
