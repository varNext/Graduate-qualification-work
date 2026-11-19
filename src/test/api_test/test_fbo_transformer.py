# tests/test_fbo_transformer_fixed.py
import pytest
import pytest_asyncio
from datetime import datetime
from src.app.fbo.fbo_transformer import FBOTransformer


class TestFBOTransformerFixed:
    """тесты FBOTransformer"""

    @pytest.fixture
    def transformer(self):
        return FBOTransformer()

    @pytest.fixture
    def sample_posting_data(self):
        """Пример данных отправления от Ozon API"""
        return {
            "posting_number": "FBO-123456",
            "order_id": "ORDER-789",
            "status": "delivered",
            "created_at": "2024-01-01T10:00:00Z",
            "in_process_at": "2024-01-01T11:00:00Z",
            "products": [
                {
                    "sku": 123456,
                    "name": "Тестовый товар",
                    "quantity": 2,
                    "price": "1000.50",
                    "offer_id": "OFFER-001",
                    "currency_code": "RUB"
                }
            ],
            "analytics_data": {
                "warehouse_name": "Москва",
                "region": "Московская область",
                "city": "Москва"
            },
            "delivery_method": {
                "name": "СДЭК",
                "tpl_provider": "CDEK"
            },
            "tracking_number": "TRACK-123",
            "warehouse": {
                "name": "Склад Ozon"
            },
            "customer": {
                "name": "Иван Иванов",
                "phone": "+79991234567",
                "email": "ivan@test.ru"
            },
            "addressee": {
                "name": "Иван Иванов",
                "address": "ул. Примерная, д. 1"
            }
        }

    @pytest.mark.asyncio
    async def test_transform_single_posting(self, transformer, sample_posting_data):
        """Тест трансформации одного отправления"""
        result = await transformer.transform_single_posting(sample_posting_data)

        assert result is not None
        assert result["posting_number"] == "FBO-123456"
        assert result["order_number"] == "ORDER-789"
        assert result["status"] == "delivered"
        assert result["status_ru"] == "Доставлено"

        # Проверка товаров
        assert len(result["товары"]) == 1
        product = result["товары"][0]
        assert product["sku"] == 123456
        assert product["quantity"] == 2
        assert product["price"] == 1000.5
        assert product["total"] == 2001.0

        # Проверка аналитики
        assert result["аналитика"]["warehouse_name"] == "Москва"

        # Проверка доставки
        assert result["доставка"]["method"] == "СДЭК"
        assert result["доставка"]["tracking_number"] == "TRACK-123"

        # Проверка клиента
        assert result["клиент"]["name"] == "Иван Иванов"
        assert result["клиент"]["phone"] == "+79991234567"

    @pytest.mark.asyncio
    async def test_transform_empty_posting(self, transformer):
        """Тест с пустыми данными"""
        result = await transformer.transform_single_posting({})
        assert result is None

    @pytest.mark.asyncio
    async def test_transform_posting_with_result_wrapper(self, transformer):
        """Тест с оберткой result"""
        data = {
            "result": {
                "posting_number": "FBO-001",
                "order_id": "ORDER-001",
                "status": "delivered"
            }
        }

        result = await transformer.transform_single_posting(data)
        assert result is not None
        assert result["posting_number"] == "FBO-001"

    def test_extract_posting_number_various_keys(self, transformer):
        """Тест извлечения номера отправления из разных ключей"""
        test_cases = [
            ({"posting_number": "FBO-001"}, "FBO-001"),
            ({"postingNumber": "FBO-002"}, "FBO-002"),
            ({"posting": "FBO-003"}, "FBO-003"),
            ({}, None),
            ({"posting_number": None}, None),
        ]

        for data, expected in test_cases:
            result = transformer._extract_posting_number(data)
            assert result == expected

    def test_extract_product_items_dict(self, transformer):
        """Тест извлечения товаров"""
        posting_data = {
            "posting_number": "FBO-001",
            "products": [
                {
                    "sku": 123,
                    "name": "Товар 1",
                    "quantity": 1,
                    "price": "100.50"
                },
                {
                    "sku": 456,
                    "name": "Товар 2",
                    "quantity": 0,  # Должен быть пропущен
                    "price": "200.00"
                }
            ]
        }

        result = transformer._extract_product_items_dict(posting_data, "FBO-001")

        assert len(result) == 1
        assert result[0]["sku"] == 123
        assert result[0]["name"] == "Товар 1"
        assert result[0]["quantity"] == 1
        assert result[0]["price"] == 100.5
        assert result[0]["total"] == 100.5

    def test_translate_status(self, transformer):
        """Тест перевода статусов"""
        status_map = {
            "awaiting_deliver": "Ожидает отгрузки",
            "delivering": "Доставляется",
            "delivered": "Доставлено",
            "cancelled": "Отменено",
            "unknown_status": "unknown_status"
        }

        for status, expected in status_map.items():
            result = transformer._translate_status(status)
            assert result == expected

    def test_to_iso_string(self, transformer):
        """Тест преобразования даты в ISO строку"""
        test_date = datetime(2024, 1, 1, 10, 30, 0)

        test_cases = [
            (test_date, test_date.isoformat()),
            ("2024-01-01T10:30:00Z", "2024-01-01T10:30:00+00:00"),
            ("2024-01-01T10:30:00", "2024-01-01T10:30:00+00:00"),
            (None, None),

        ]

        for input_date, expected in test_cases:
            result = transformer._to_iso_string(input_date)
            assert result == expected

    def test_safe_float(self, transformer):
        """Тест безопасного преобразования в float"""
        test_cases = [
            (100.50, 100.5),
            ("100.50", 100.5),
            ("100,50", 100.5),

            ("1000.50", 1000.5),
            ("invalid", 0.0),
            (None, 0.0),
            ("", 0.0),
        ]

        for input_val, expected in test_cases:
            result = transformer._safe_float(input_val)
            assert result == expected

