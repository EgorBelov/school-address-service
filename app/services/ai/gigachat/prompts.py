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

Правила извлечения:
- Если указано "все" или "все дома" — parity="all", диапазоны null.
- "четные дома" — parity="even".
- "нечетные дома" — parity="odd".
- Сложное описание ("от пересечения до пересечения", "кроме д.11") сохраняй
  в comment, при этом старайся также заполнить house_from/house_to/exceptions.
- Если правило содержит несколько диапазонов или несколько улиц,
  создавай несколько записей в rules.
- Не выдумывай данные. Если поля нет — оставь "" / null.
- В street НЕ включай тип ("ул.", "пр-кт", "переулок") — только название.

Примеры (вход → выход одного rule):

"ул. Заречная (четные и нечетные до дома 18)" →
{"street":"Заречная","house_rule_raw":"(четные и нечетные до дома 18)","parity":"all","house_from":null,"house_to":18,"house_number":null,"comment":""}

"проспект Ленина, 10, 10а, 12, 14" →
{"street":"Ленина","house_rule_raw":"10, 10а, 12, 14","parity":"all","house_from":null,"house_to":null,"house_number":"10,10а,12,14","comment":""}

"ул. Молодежная (кроме д.11)" →
{"street":"Молодежная","house_rule_raw":"(кроме д.11)","parity":"all","house_from":null,"house_to":null,"house_number":null,"comment":"кроме д.11"}

"ул. Новая (начиная с дома 36)" →
{"street":"Новая","house_rule_raw":"(начиная с дома 36)","parity":"all","house_from":36,"house_to":null,"house_number":null,"comment":""}

"ул. 40 лет Победы, 1-17" →
{"street":"40 лет Победы","house_rule_raw":"1-17","parity":"all","house_from":1,"house_to":17,"house_number":null,"comment":""}

"ул. Институтская (дома с нечетными номерами)" →
{"street":"Институтская","house_rule_raw":"(дома с нечетными номерами)","parity":"odd","house_from":null,"house_to":null,"house_number":null,"comment":""}

"Щелковское шоссе (четные – от дома 102, нечетные – от дома 141)" →
[{"street":"Щелковское шоссе","house_rule_raw":"(четные – от дома 102)","parity":"even","house_from":102,"house_to":null,"house_number":null,"comment":""},
 {"street":"Щелковское шоссе","house_rule_raw":"(нечетные – от дома 141)","parity":"odd","house_from":141,"house_to":null,"house_number":null,"comment":""}]

Текст постановления:

{text}
"""
