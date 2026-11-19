import pytest
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from src.app.fbs.fbs_service import FBSService
from src.app.fbs.fbs_transformer import FBSTransformer


@pytest.mark.integration
class TestFBSComponentIntegration:
    """ интеграционные тесты: взаимодействие сервиса и трансформера"""

    @pytest.fixture
    def fbs_service(self):
        return FBSService(
            client_id="test_client",
            api_key="test_key",
            request_id="integration_test"
        )

    @pytest.mark.asyncio
    async def test_fbs_complete_data_flow_integration(self, fbs_service):
        """
        WHEN: Сервис получает данные из API
        THEN: Данные корректно проходят через всю цепочку обработки
        """
        # GIVEN: Реальные данные в формате Ozon API
        real_ozon_data = {
            "posting_number": "FBS-INTEGRATION-001",
            "order_id": 100500,
            "status": "awaiting_packaging",
            "created_at": "2024-01-15T10:30:00Z",
            "products": [
                {
                    "sku": 123456,
                    "name": "Тестовый товар",
                    "quantity": 2,
                    "price": "1000.00"
                }
            ]
        }


        with patch.object(fbs_service, '_make_api_request') as mock_api:
            mock_api.side_effect = [
                # Список отправлений
                {
                    "result": {
                        "postings": [{"posting_number": "FBS-INTEGRATION-001"}],
                        "has_next": False
                    }
                },
                # Детали отправления
                {"result": [real_ozon_data]}
            ]

            period_from = datetime(2024, 1, 1, tzinfo=timezone.utc)
            period_to = datetime(2024, 1, 31, tzinfo=timezone.utc)

            # WHEN: Запускаем полный поток обработки
            all_results = []
            async for batch in fbs_service.stream_postings(
                    period_from=period_from,
                    period_to=period_to,
                    require_details=True
            ):
                all_results.extend(batch)

            # THEN: Проверяем интеграцию всех компонентов
            assert len(all_results) == 1
            result = all_results[0]


            assert result["posting_number"] == "FBS-INTEGRATION-001"


            assert result["status_ru"] == "Ожидает упаковки"


            assert len(result["товары"]) == 1
            assert result["товары"][0]["total"] == 2000.00  # 1000 * 2

    @pytest.mark.asyncio
    async def test_fbs_empty_response_integration(self, fbs_service):
        """
        WHEN: API возвращает пустые данные
        THEN: Сервис корректно завершается без ошибок
        """
        with patch.object(fbs_service, '_make_api_request') as mock_api:
            mock_api.return_value = {
                "result": {
                    "postings": [],
                    "has_next": False
                }
            }

            period_from = datetime(2024, 1, 1, tzinfo=timezone.utc)
            period_to = datetime(2024, 1, 31, tzinfo=timezone.utc)

            # WHEN: Запрашиваем пустые данные
            batches = []
            async for batch in fbs_service.stream_postings(
                    period_from=period_from,
                    period_to=period_to
            ):
                batches.append(batch)

            # THEN: Нет данных,  и нет ошибок
            assert len(batches) == 0

    @pytest.mark.asyncio
    async def test_fbs_pagination_integration(self, fbs_service):
        """
        WHEN: Есть несколько страниц данных
        THEN: Пагинация работает через API
        """
        with patch.object(fbs_service, '_make_api_request') as mock_api:
            mock_api.side_effect = [
                # Первая страница
                {
                    "result": {
                        "postings": [{"posting_number": "PAGE-1"} for _ in range(5)],
                        "has_next": True
                    }
                },
                # Вторая страница (последняя)
                {
                    "result": {
                        "postings": [{"posting_number": "PAGE-2"} for _ in range(3)],
                        "has_next": False
                    }
                }
            ]

            period_from = datetime(2024, 1, 1, tzinfo=timezone.utc)
            period_to = datetime(2024, 1, 31, tzinfo=timezone.utc)

            # WHEN: Обрабатываем все страницы
            all_results = []
            async for batch in fbs_service.stream_postings(
                    period_from=period_from,
                    period_to=period_to,
                    require_details=False  # Упрощаем
            ):
                all_results.extend(batch)

            # THEN: Все страницы обработаны
            assert len(all_results) == 8  # 5 + 3
            assert mock_api.call_count == 2


@pytest.mark.integration
class TestFBSTransformerIntegration:
    """Интеграция трансформера с реальными данными формата Ozon"""

    @pytest.fixture
    def transformer(self):
        return FBSTransformer()

    @pytest.mark.asyncio
    async def test_fbs_real_data_format_integration(self, transformer):
        """
        WHEN: Трансформер получает реальные данные Ozon API
        THEN: Корректно преобразует их в формат 1С
        """
        # GIVEN: Реальные данные из Ozon API (пример из документации)
        real_fbs_data = {
            "posting_number": "1234567890",
            "order_id": 987654321,
            "status": "delivered",
            "created_at": "2024-01-15T10:30:00Z",
            "shipment_date": "2024-01-16T12:00:00Z",
            "delivery_date": "2024-01-17T15:30:00Z",
            "products": [
                {
                    "sku": 55555,
                    "offer_id": "TEST-OFFER-001",
                    "name": "Тестовый товар",
                    "quantity": 3,
                    "price": "2500.00",
                    "currency_code": "RUB"
                }
            ],
            "analytics_data": {
                "warehouse_name": "Склад Ozon",
                "region": "Москва"
            },
            "customer": {
                "name": "Тестовый клиент",
                "phone": "+79161234567"
            }
        }

        # WHEN: Трансформируем реальные данные
        result = await transformer.transform_single_posting(real_fbs_data)

        # THEN: Проверяем интеграцию по формату данных
        assert result is not None
        assert result["posting_number"] == "1234567890"
        assert result["status"] == "delivered"
        assert result["status_ru"] == "Доставлено"

        # Проверяем расчеты
        assert len(result["товары"]) == 1
        product = result["товары"][0]
        assert product["total"] == 7500.0  # 2500 * 3


@pytest.mark.integration
@pytest.mark.error_handling
class TestFBSIntegrationErrorHandling:
    """Интеграционные тесты обработки ошибок"""

    @pytest.fixture
    def fbs_service(self):
        return FBSService(
            client_id="test_client",
            api_key="test_key",
            request_id="error_test"
        )

    @pytest.mark.asyncio
    async def test_fbs_api_error_propagates_integration(self, fbs_service):
        """
        WHEN: API возвращает ошибку
        THEN: Ошибка корректно передается вызывающему коду
        """
        with patch.object(fbs_service, '_make_api_request') as mock_api:
            mock_api.side_effect = Exception("API временно недоступен")

            period_from = datetime(2024, 1, 1, tzinfo=timezone.utc)
            period_to = datetime(2024, 1, 31, tzinfo=timezone.utc)

            # WHEN/THEN: Ошибка должна проброситься
            with pytest.raises(Exception, match="API временно недоступен"):
                async for _ in fbs_service.stream_postings(
                        period_from=period_from,
                        period_to=period_to
                ):
                    pass

    @pytest.mark.asyncio
    async def test_fbs_transformer_error_integration(self, fbs_service):
        """
        WHEN: Трансформер падает с исключением
        THEN: Ошибка обрабатывается, статистика обновляется, работа продолжается
        """
        # GIVEN: Корректные данные, но трансформер падает
        valid_data = {
            "posting_number": "TEST-001",
            "status": "delivered",
            "products": []
        }

        with patch.object(fbs_service, '_make_api_request') as mock_api, \
                patch.object(fbs_service.transformer, 'transform_single_posting') as mock_transform:
            mock_api.side_effect = [
                {
                    "result": {
                        "postings": [{"posting_number": "TEST-001"}],
                        "has_next": False
                    }
                },
                {"result": [valid_data]}
            ]

            # Трансформер падает с исключением
            mock_transform.side_effect = ValueError("Ошибка в трансформере")

            period_from = datetime(2024, 1, 1, tzinfo=timezone.utc)
            period_to = datetime(2024, 1, 31, tzinfo=timezone.utc)

            # WHEN: Обрабатываем данные с ошибкой в трансформере
            batches = []
            async for batch in fbs_service.stream_postings(
                    period_from=period_from,
                    period_to=period_to
            ):
                batches.append(batch)

            # THEN: Есть батч с ошибкой трансформации
            assert len(batches) == 1
            assert len(batches[0]) == 1

            error_item = batches[0][0]
            # Проверяем что ошибка записана в результат
            assert "transformation_error" in error_item
            assert "Ошибка в трансформере" in error_item["transformation_error"]

            # Статистика об ошибках должна обновиться
            assert fbs_service.stats["errors"] == 1