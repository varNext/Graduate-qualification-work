import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch


class TestFBOTransformer:
    """Юнит-тесты для FBO трансформера с Given-When-Then"""

    def test_safe_float_with_valid_string(self, fbo_transformer):
        """GWT: Преобразование корректной строки в float"""
        input_value = "1 000,75"
        result = fbo_transformer._safe_float(input_value)
        assert result == 1000.75
        assert isinstance(result, float)

    def test_safe_float_with_invalid_string(self, fbo_transformer):
        """GWT: Преобразование некорректной строки в float"""
        input_value = "не число"
        result = fbo_transformer._safe_float(input_value)
        assert result == 0.0

    def test_safe_float_with_none_value(self, fbo_transformer):
        """GWT: Преобразование None в float"""
        input_value = None
        result = fbo_transformer._safe_float(input_value)
        assert result == 0.0

    def test_to_iso_string_with_datetime_object(self, fbo_transformer):
        """GWT: Конвертация datetime объекта в ISO строку"""

        date_obj = datetime(2024, 1, 15, 10, 30, 45)
        result = fbo_transformer._to_iso_string(date_obj)
        assert result.startswith("2024-01-15T10:30:45")

    def test_to_iso_string_with_zulu_time_string(self, fbo_transformer):
        """GWT: Конвертация строки с Z-форматом в ISO строку"""
        date_str = "2024-01-15T10:30:45Z"
        result = fbo_transformer._to_iso_string(date_str)
        assert result == "2024-01-15T10:30:45+00:00"

    def test_to_iso_string_with_invalid_format(self, fbo_transformer):
        """GWT: Конвертация некорректной строки даты"""
        date_str = "некорректная дата"
        result = fbo_transformer._to_iso_string(date_str)
        assert isinstance(result, str)
        assert result == "некорректная дата+00:00"


    def test_extract_posting_number_found(self, fbo_transformer):
        """GWT: Извлечение номера отправления при его наличии"""
        posting_data = {"posting_number": "123456"}
        result = fbo_transformer._extract_posting_number(posting_data)
        assert result == "123456"

    def test_extract_posting_number_with_postingNumber_key(self, fbo_transformer):
        """GWT: Извлечение номера отправления из ключа postingNumber"""
        posting_data = {"postingNumber": "789012"}
        result = fbo_transformer._extract_posting_number(posting_data)
        assert result == "789012"

    def test_extract_posting_number_not_found(self, fbo_transformer):
        """GWT: Извлечение номера отправления при его отсутствии"""
        posting_data = {"other_field": "value"}
        result = fbo_transformer._extract_posting_number(posting_data)
        assert result is None

    def test_extract_posting_number_empty_value(self, fbo_transformer):
        """GWT: Извлечение номера отправления с пустым значением"""
        posting_data = {"posting_number": None}
        result = fbo_transformer._extract_posting_number(posting_data)
        assert result is None

    def test_translate_status_known_status(self, fbo_transformer):
        """GWT: Перевод известного статуса на русский"""
        status = "delivering"
        result = fbo_transformer._translate_status(status)
        assert result == "Доставляется"

    def test_translate_status_unknown_status(self, fbo_transformer):
        """GWT: Перевод неизвестного статуса (возврат оригинала)"""
        status = "unknown_status"
        result = fbo_transformer._translate_status(status)
        assert result == "unknown_status"

    def test_extract_product_items_dict_empty_products(self, fbo_transformer):
        """GWT: Извлечение товаров из пустого списка"""
        posting_data = {"posting_number": "123"}
        result = fbo_transformer._extract_product_items_dict(posting_data, "123")
        assert result == []

    def test_extract_product_items_dict_with_zero_quantity(self, fbo_transformer):
        """GWT: Извлечение товара с нулевым количеством (должен быть проигнорирован)"""
        posting_data = {
            "products": [
                {"sku": 111, "quantity": 0, "price": "100"}
            ]
        }
        result = fbo_transformer._extract_product_items_dict(posting_data, "123")
        assert result == []

    def test_extract_product_items_dict_valid_product(self, fbo_transformer):
        """GWT: Извлечение корректного товара"""
        posting_data = {
            "products": [
                {
                    "sku": 111,
                    "name": "Товар 1",
                    "quantity": 2,
                    "price": "100.50",
                    "offer_id": "OFFER-111",
                    "currency_code": "RUB"
                }
            ]
        }
        result = fbo_transformer._extract_product_items_dict(posting_data, "123")
        assert len(result) == 1
        assert result[0]["sku"] == 111
        assert result[0]["quantity"] == 2
        assert result[0]["price"] == 100.5
        assert result[0]["total"] == 201.0  # 100.5 * 2
        assert result[0]["vat_rate"] == 20.0


    @pytest.mark.asyncio
    async def test_transform_single_posting_valid_data(self, fbo_transformer, sample_posting_data):
        """GWT: Трансформация валидных данных отправления"""
        data = sample_posting_data
        result = await fbo_transformer.transform_single_posting(data)

        assert result is not None
        assert result["posting_number"] == "123456"
        assert result["order_number"] == "789"
        assert result["status"] == "delivering"
        assert result["status_ru"] == "Доставляется"
        assert len(result["товары"]) == 1
        assert result["товары"][0]["sku"] == 111
        assert result["товары"][0]["total"] == 201.0

    @pytest.mark.asyncio
    async def test_transform_single_posting_empty_data(self, fbo_transformer):
        """GWT: Трансформация пустых данных"""
        data = {}
        result = await fbo_transformer.transform_single_posting(data)
        assert result is None

    @pytest.mark.asyncio
    async def test_transform_single_posting_without_posting_number(self, fbo_transformer):
        """GWT: Трансформация данных без номера отправления"""
        data = {"status": "delivering", "products": []}
        result = await fbo_transformer.transform_single_posting(data)
        assert result is None

    @pytest.mark.asyncio
    async def test_transform_single_posting_with_wrapped_result(self, fbo_transformer):
        """GWT: Трансформация данных обернутых в result"""
        data = {
            "result": {
                "posting_number": "789012",
                "status": "delivered",
                "products": []
            }
        }
        result = await fbo_transformer.transform_single_posting(data)

        assert result is not None
        assert result["posting_number"] == "789012"
        assert result["status"] == "delivered"