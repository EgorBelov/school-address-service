from abc import ABC, abstractmethod


class BaseParserStrategy(ABC):
    @abstractmethod
    def parse(self, text: str) -> dict:
        pass