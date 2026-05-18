"""
Общая retry-логика для вызовов GigaChat. Сетевые/SSL-ошибки и 429
у Сбера случаются регулярно, поэтому каждый вызов обёрнут в backoff.
"""
import time

# Сколько секунд ждать между последовательными запросами (анти-throttle).
# Сбер чувствителен к burst-нагрузке.
INTER_REQUEST_DELAY = 2.5

# Сколько попыток на каждый чанк / per-school запрос.
MAX_RETRIES = 4

# База для экспоненциального backoff: 4, 8, 16, 32 сек.
RETRY_BASE_DELAY = 4.0


def is_transient_error(exc: Exception) -> bool:
    """
    True для сетевых / SSL / rate-limit / 5xx ошибок — их имеет смысл
    повторить. False для логических ошибок (битый JSON, схема и т.п.).
    """
    text = str(exc).lower()
    return any(marker in text for marker in (
        # сеть/таймауты
        "timeout", "timed out",
        # rate limit и 5xx
        "429", "too many requests",
        "500", "502", "503", "504",
        # обрыв соединения
        "connection", "reset by peer", "disconnect",
        # SSL/TLS
        "ssl", "unexpected_eof", "handshake",
        "eof occurred", "protocol",
    ))


def call_with_retry(fn, *args, label: str = "gigachat", **kwargs):
    """
    Выполняет `fn(*args, **kwargs)` с retry на transient-ошибки.
    Логические ошибки (битый JSON и т.п.) пробрасываются сразу.
    """
    last_error: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            last_error = e

            if not is_transient_error(e) or attempt == MAX_RETRIES:
                raise

            wait = RETRY_BASE_DELAY * (2 ** (attempt - 1))
            print(
                f"[{label}] transient error on attempt {attempt}: {e}"
                f" → retry in {wait:.0f}s"
            )
            time.sleep(wait)

    # Недостижимо — для тайпчекера
    raise last_error if last_error else RuntimeError("unreachable")
