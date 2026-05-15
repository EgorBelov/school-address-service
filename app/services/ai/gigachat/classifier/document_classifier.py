import json
import re

from app.services.ai.gigachat.client import get_gigachat_client


CLASSIFIER_PROMPT = """
Ты классифицируешь формат муниципального постановления о закреплении школ за территориями.

Верни строго JSON без markdown.

Типы:
- two_column_school_territories: таблица, где слева школа, справа список улиц/территорий
- multi_column_street_house: таблица, где отдельно указаны школа, улица и номера домов
- plain_text_list: список в свободном текстовом формате
- unknown: формат неясен

Формат ответа:

{
  "document_type": "",
  "confidence": 0.0,
  "reason": ""
}

Текст документа:

{text}
"""


def extract_json(content: str) -> dict:
    content = content.replace("```json", "").replace("```", "").strip()
    match = re.search(r"\{.*\}", content, re.DOTALL)

    if not match:
        raise ValueError("Классификатор не вернул JSON")

    return json.loads(match.group(0))


def classify_document(text: str) -> dict:
    client = get_gigachat_client()

    prompt = CLASSIFIER_PROMPT.replace("{text}", text[:5000])
    response = client.chat(prompt)

    return extract_json(response.choices[0].message.content)