DECREE_PARSE_PROMPT = """
Ты анализируешь текст муниципального постановления о закреплении школ за территориями.

Задача: извлечь структурированные данные.

Верни СТРОГО JSON без markdown и пояснений.

Формат:

{
  "decree": {
    "number": "",
    "date": "",
    "municipality": ""
  },
  "schools": [
    {
      "name": "",
      "address": "",
      "rules": [
        {
          "locality": "",
          "street": "",
          "house_rule_raw": "",
          "parity": "all|even|odd|mixed|unknown",
          "house_from": null,
          "house_to": null,
          "house_number": null,
          "comment": ""
        }
      ]
    }
  ]
}

Правила:
- Если указано "все" или "все дома", parity = "all".
- Если указаны "четные дома", parity = "even".
- Если указаны "нечетные дома", parity = "odd".
- Если есть сложное описание "от пересечения до пересечения", сохрани его в comment.
- Если правило содержит несколько диапазонов, создай несколько rules.
- Не выдумывай данные.

Текст постановления:

{text}
"""