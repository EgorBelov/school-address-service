from app.services.parser.multi_column_extractor import (
    extract_multi_column_rows_from_table,
    rows_to_decree_dict,
    split_street_aliases,
)


class TestSplitStreetAliases:
    def test_no_alias(self):
        assert split_street_aliases("Ленина") == ["Ленина"]

    def test_with_alias(self):
        result = split_street_aliases("Монастырская (Орджоникидзе)")
        assert "Монастырская" in result
        assert "Орджоникидзе" in result

    def test_alias_same_as_main(self):
        """Если в скобках то же имя — не дублируем."""
        result = split_street_aliases("Ленина (Ленина)")
        assert result.count("Ленина") == 1

    def test_empty(self):
        assert split_street_aliases("") == []


class TestExtractMultiColumnRowsFromTable:
    def test_simple_table(self):
        table = [
            ["№", "Наименование", "улица", "номер дома"],
            ["1", "МАОУ «СОШ № 1»", "Ленина", "1, 3, 5"],
            ["1", "МАОУ «СОШ № 1»", "Пушкина", "2, 4"],
        ]
        rows, _ = extract_multi_column_rows_from_table(table, page_index=1)
        assert len(rows) == 2
        assert rows[0]["street"] == "Ленина"
        assert rows[1]["street"] == "Пушкина"

    def test_continuation_with_none_school(self):
        """Если в col[1] None, школа должна остаться предыдущей."""
        table = [
            ["1", "МАОУ «СОШ № 1»", "Ленина", "1, 3"],
            [None, None, "Пушкина", "5, 7"],
        ]
        rows, _ = extract_multi_column_rows_from_table(table, page_index=1)
        assert len(rows) == 2
        assert all(r["school_name"] == "МАОУ «СОШ № 1»" for r in rows)

    def test_current_school_propagates_between_tables(self):
        """current_school передаётся между таблицами (для многостраничных)."""
        # Первая таблица: устанавливает школу
        t1 = [["1", "МАОУ «СОШ № 32»", "Ленина", "1"]]
        rows1, current = extract_multi_column_rows_from_table(t1, 1)
        assert current == "МАОУ «СОШ № 32»"

        # Вторая таблица (другая страница): continuation без школы в col[1]
        t2 = [[None, None, "Пушкина", "5"]]
        rows2, _ = extract_multi_column_rows_from_table(t2, 2, current_school=current)
        assert len(rows2) == 1
        assert rows2[0]["school_name"] == "МАОУ «СОШ № 32»"

    def test_skips_header(self):
        table = [["Наименование", "учреждения", "улица", "номер дома"]]
        rows, _ = extract_multi_column_rows_from_table(table, 1)
        assert rows == []


class TestRowsToDecreeDict:
    def test_groups_by_school(self):
        rows = [
            {"page": 1, "school_name": "Школа 1", "street": "Ленина", "houses": "1, 3"},
            {"page": 1, "school_name": "Школа 1", "street": "Пушкина", "houses": "5"},
            {"page": 2, "school_name": "Школа 2", "street": "Мира", "houses": "1-10"},
        ]
        result = rows_to_decree_dict(rows, {"number": "01", "date": "01.01.2025", "municipality": "X"})
        assert len(result["schools"]) == 2
        school1 = next(s for s in result["schools"] if s["name"] == "Школа 1")
        assert len(school1["rules"]) == 2

    def test_range_houses(self):
        rows = [{"page": 1, "school_name": "X", "street": "Y", "houses": "1-10"}]
        result = rows_to_decree_dict(rows, {})
        rule = result["schools"][0]["rules"][0]
        assert rule["rule_type"] == "range"
        assert rule["house_from"] == 1
        assert rule["house_to"] == 10
