import pytest
from datetime import datetime
from src.app.core.base_transformer import BaseTransformer


class ConcreteTestTransformer(BaseTransformer):
    pass


class TestBaseTransformer:
    """Минимальные тесты для BaseTransformer"""

    @pytest.fixture
    def transformer(self):
        return ConcreteTestTransformer()

    # 1. safe_float - 2 основных теста
    def test_safe_float_conversions(self, transformer):
        """Основные преобразования"""
        assert transformer._safe_float(100) == 100.0
        assert transformer._safe_float("1,000.75") == 1000.75
        assert transformer._safe_float(None) == 0.0

    # 2. to_iso_string - 2 основных теста
    def test_to_iso_string_formats(self, transformer):
        """Основные форматы дат"""
        # ISO с Z
        assert transformer._to_iso_string("2024-01-01T12:00:00Z") == "2024-01-01T12:00:00+00:00"

        # datetime объект
        dt = datetime(2024, 1, 1, 12, 0, 0)
        assert transformer._to_iso_string(dt) == "2024-01-01T12:00:00"

        # Пустое значение
        assert transformer._to_iso_string("") is None

    # 3. extract_customer_data_dict - 4 основных теста
    def test_customer_has_priority(self, transformer):
        """Приоритет customer"""
        data = {
            "customer": {"name": "Иван", "phone": "111"},
            "addressee": {"name": "Петр", "phone": "222"}
        }
        result = transformer._extract_customer_data_dict(data)
        assert result["name"] == "Иван"
        assert result["phone"] == "111"

    def test_only_addressee(self, transformer):
        """Только addressee"""
        data = {"addressee": {"name": "Петр", "phone": "222", "address": "ул. Ленина"}}
        result = transformer._extract_customer_data_dict(data)
        assert result["name"] == "Петр"
        assert result["delivery_address"] == "ул. Ленина"

    def test_only_customer(self, transformer):
        """Только customer"""
        data = {"customer": {"name": "Иван", "phone": "111", "email": "test@test.com"}}
        result = transformer._extract_customer_data_dict(data)
        assert result["name"] == "Иван"
        assert result["email"] == "test@test.com"

    def test_empty_data(self, transformer):
        """Пустые данные"""
        result = transformer._extract_customer_data_dict({})
        assert result["name"] is None
        assert result["delivery_address"] == ""