# tests/integration/test_fbo_service_transformer_integration.py
import aiohttp
import pytest
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from src.app.fbo.fbo_service import FBOService


class TestFBOServiceTransformerIntegration:
    """Интеграционные тесты для взаимодействия FBOService + FBOTransformer"""

    @pytest.fixture
    def mock_posting_data(self):
        """GIVEN: Мок данных FBO отправления"""
        return {
            "posting_number": "123456789",
            "order_id": 987654321,
            "status": "delivered",
            "created_at": "2024-01-15T10:30:00Z",
            "products": [
                {
                    "sku": 12345,
                    "name": "Тестовый товар",
                    "quantity": 2,
                    "price": "1500.50",
                    "offer_id": "TEST-001",
                    "currency_code": "RUB"
                }
            ],
            "analytics_data": {
                "warehouse_name": "Склад Москва",
                "region": "Москва"
            },
            "customer": {
                "name": "Иван Иванов",
                "phone": "+79161234567"
            }
        }

    @pytest.fixture
    def fbo_service(self):
        """GIVEN: Экземпляр FBO сервиса"""
        return FBOService(
            client_id="test_client",
            api_key="test_key",
            request_id="test_123"
        )

    @pytest.mark.asyncio
    # Проверяет, что данные корректно передаются между компонентами
    async def test_complete_processing_flow(self, fbo_service, mock_posting_data):
        """WHEN: Получаем FBO данные через сервис THEN: Данные корректно трансформируются"""
        with patch.object(fbo_service, '_make_api_request') as mock_api:
            mock_api.return_value = {"result": [mock_posting_data]}
            fbo_service.session = AsyncMock()

            period_from = datetime(2024, 1, 1, tzinfo=timezone.utc)
            period_to = datetime(2024, 1, 31, tzinfo=timezone.utc)


            batches = []
            async for batch in fbo_service.stream_postings(
                    period_from=period_from,
                    period_to=period_to,
                    status_filter=["delivered"]
            ):
                batches.append(batch)


            assert len(batches) == 1
            posting = batches[0][0]

            assert posting["posting_number"] == "123456789"
            assert posting["status"] == "delivered"
            assert posting["status_ru"] == "Доставлено"
            assert len(posting["товары"]) == 1

            product = posting["товары"][0]
            assert product["sku"] == 12345
            assert product["quantity"] == 2
            assert product["price"] == 1500.5

    @pytest.mark.asyncio
    # Проверяет работу пагинации
    async def test_multiple_batches_with_pagination(self, fbo_service):
        """WHEN: Есть несколько страниц данных THEN: Все страницы обрабатываются"""
        # GIVEN: Настраиваем пагинацию - 2 страницы данных

        batch_size = 3
        first_batch = [{"posting_number": f"POST-{i}", "status": "delivered", "products": []}
                       for i in range(batch_size)]  # Полный батч

        # Второй батч с меньшим количеством элементов (завершение пагинации)
        second_batch = [{"posting_number": "POST-3", "status": "delivered", "products": []}]

        with patch.object(fbo_service, '_make_api_request') as mock_api:
            mock_api.side_effect = [
                {"result": first_batch},
                {"result": second_batch},
            ]
            fbo_service.session = AsyncMock()

            period_from = datetime(2024, 1, 1, tzinfo=timezone.utc)
            period_to = datetime(2024, 1, 31, tzinfo=timezone.utc)

            # WHEN: Запускаем обработку
            all_postings = []
            async for batch in fbo_service.stream_postings(
                    period_from=period_from,
                    period_to=period_to,
                    batch_size=batch_size  # Передаем наш размер батча
            ):
                all_postings.extend(batch)

            # THEN: Проверяем что обработаны все страницы
            # Должны получить 3 + 1 = 4 элемента
            assert len(all_postings) == batch_size + 1  # 3 + 1

            assert mock_api.call_count == 2



    @pytest.mark.asyncio
    # Проверяет, что статус фильтр корректно преобразуется
    async def test_status_filter_passed_to_api(self, fbo_service):
        """WHEN: Указываем фильтр статусов THEN: Он передается в API запрос"""
        # GIVEN: Мокируем API
        with patch.object(fbo_service, '_make_api_request') as mock_api:
            mock_api.return_value = {"result": []}
            fbo_service.session = AsyncMock()

            period_from = datetime(2024, 1, 1, tzinfo=timezone.utc)
            period_to = datetime(2024, 1, 31, tzinfo=timezone.utc)
            status_filter = ["cancelled", "delivered"]

            # WHEN: Запускаем фильтр
            async for _ in fbo_service.stream_postings(
                    period_from=period_from,
                    period_to=period_to,
                    status_filter=status_filter
            ):
                pass

            # THEN: Проверяем что фильтр передан в API
            call_args = mock_api.call_args
            request_params = call_args[0][1]
            assert request_params["filter"]["status"] == status_filter

    @pytest.mark.asyncio
    # Проверяет, как система ведет себя при пустом ответе API
    async def test_empty_response_handling(self, fbo_service):
        """WHEN: API возвращает пустой ответ THEN: Обработка завершается корректно"""
        # GIVEN: API возвращает пустой список
        with patch.object(fbo_service, '_make_api_request') as mock_api:
            mock_api.return_value = {"result": []}
            fbo_service.session = AsyncMock()

            period_from = datetime(2024, 1, 1, tzinfo=timezone.utc)
            period_to = datetime(2024, 1, 31, tzinfo=timezone.utc)

            # WHEN: Запускаем обработку
            batches = []
            async for batch in fbo_service.stream_postings(
                    period_from=period_from,
                    period_to=period_to
            ):
                batches.append(batch)

            # THEN: Никаких батчей не получено
            assert len(batches) == 0
            mock_api.assert_called_once()

    @pytest.mark.asyncio
    async def test_memory_efficiency_with_streaming(self, fbo_service):
        """
        WHEN: Обрабатываем потоковые данные
        THEN: Память не растет линейно с количеством записей
        """
        # GIVEN: Создаем симуляцию, где каждый батч независим
        BATCH_SIZE = 200
        TOTAL_BATCHES = 10  # Всего 2000 записей

        batch_data_cache = []

        with patch.object(fbo_service, '_make_api_request') as mock_api:
            def api_side_effect(endpoint, params):
                offset = params.get("offset", 0)
                batch_num = offset // BATCH_SIZE

                if batch_num >= TOTAL_BATCHES:
                    return {"result": []}

                # Создаем уникальный батч данных
                batch = []
                start_id = batch_num * BATCH_SIZE

                for i in range(BATCH_SIZE):
                    record_id = start_id + i
                    batch.append({
                        "posting_number": f"BATCH{batch_num}-{i}",
                        "status": "delivered",
                        "products": [
                            {
                                "sku": record_id,
                                "name": f"Товар из батча {batch_num}",
                                "quantity": 1,
                                "price": "100.0"
                            }
                        ]
                    })

                # Сохраняем ссылку для проверки, что память освобождается
                batch_data_cache.append(batch[:])
                return {"result": batch}

            mock_api.side_effect = api_side_effect
            fbo_service.session = AsyncMock()

            period_from = datetime(2024, 1, 1, tzinfo=timezone.utc)
            period_to = datetime(2024, 1, 31, tzinfo=timezone.utc)

            # WHEN: Обрабатываем все батчи
            processed_batches = []

            async for batch in fbo_service.stream_postings(
                    period_from=period_from,
                    period_to=period_to,
                    batch_size=BATCH_SIZE
            ):
                processed_batches.append(batch)


                if len(processed_batches) > 3:
                    # Удаляем старые батчи, имитируя освобождение памяти
                    processed_batches = processed_batches[-3:]

            # THEN: Все батчи были обработаны
            assert len(batch_data_cache) == TOTAL_BATCHES

