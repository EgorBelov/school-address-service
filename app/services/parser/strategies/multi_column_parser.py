from app.services.ai.gigachat.decree_parser import parse_decree_with_gigachat
from app.services.parser.strategies.base import BaseParserStrategy


class MultiColumnParserStrategy(BaseParserStrategy):
    def parse(self, text: str) -> dict:
        return parse_decree_with_gigachat(text)