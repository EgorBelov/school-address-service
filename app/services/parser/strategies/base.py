from abc import ABC, abstractmethod


class BaseParserStrategy(ABC):
    """
    Базовый класс стратегии парсинга постановления.
    Все конкретные стратегии (`TwoColumnParserStrategy`,
    `MultiColumnParserStrategy`) принимают извлечённый текст и
    опционально путь к исходному файлу (нужен для табличных
    экстракторов, которые работают с PDF/DOCX напрямую).
    """

    @abstractmethod
    def parse(self, text: str, file_path: str | None = None) -> dict:
        """
        Возвращает структуру:
            {
              "decree": {"number": "", "date": "", "municipality": ""},
              "schools": [{"name": "", "address": "", "rules": [...]}],
              "errors": [...]
            }
        """
