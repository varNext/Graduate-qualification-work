# tests/test_fbo_service.py
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime, timedelta
from src.app.fbo.fbo_service import FBOService


class TestFBOService:
    """Тесты FBOService"""

    @pytest_asyncio.fixture
    async def fbo_service(self):
        service = FBOService(
            client_id="test_client",
            api_key="test_key",
            request_id="test_request"
        )
        await service.start()
        yield service
        await service.close()

    def test_get_api_version(self, fbo_service):
        """Тест версии API"""
        assert fbo_service.get_api_version() == "v2"

    def test_format_date_for_ozon(self, fbo_service):
        """Тест форматирования даты для Ozon"""
        test_date = datetime(2024, 1, 1, 10, 30, 0)
        formatted = fbo_service._format_date_for_ozon(test_date)


        assert formatted.endswith("Z")  # Проверяем формат UTC
        assert "2024-01-01" in formatted  # Проверяем дату


        from datetime import timezone
        utc_date = datetime(2024, 1, 1, 10, 30, 0, tzinfo=timezone.utc)
        formatted_utc = fbo_service._format_date_for_ozon(utc_date)
        assert formatted_utc == "2024-01-01T10:30:00.000Z"

    @pytest.mark.asyncio
    async def test_get_basic_postings_batch(self):
        """Тест получения батча данных"""

        service = FBOService(
            client_id="test_client",
            api_key="test_key",
            request_id="test_request"
        )

        with patch.object(service, '_make_api_request') as mock_make_request:
            # Мок ответа API
            mock_response = {
                "result": [
                    {
                        "posting_number": "FBO-001",
                        "order_id": "ORDER-001",
                        "status": "delivered",
                        "created_at": "2024-01-01T10:00:00Z"
                    }
                ]
            }
            mock_make_request.return_value = mock_response

            period_from = datetime.now() - timedelta(days=10)
            period_to = datetime.now()

            result = await service._get_basic_postings_batch(
                period_from=period_from,
                period_to=period_to,
                offset=0,
                status_filter=["delivered"],
                limit=100
            )

            assert len(result) == 1
            assert result[0]["posting_number"] == "FBO-001"
            mock_make_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_stream_postings_with_full_mock(self):
        """Полный тест с замоканными всеми зависимостями"""
        service = FBOService(
            client_id="test_client",
            api_key="test_key",
            request_id="test_request"
        )


        mock_get_batch = AsyncMock()
        mock_get_batch.side_effect = [
            [{"posting_number": "FBO-001"}, {"posting_number": "FBO-002"}],
            [{"posting_number": "FBO-003"}],
            []
        ]
        service._get_basic_postings_batch = mock_get_batch


        mock_transformer = AsyncMock()

        async def transform_mock(posting):
            return {
                "posting_number": posting.get("posting_number"),
                "order_number": "ORDER-" + posting.get("posting_number", "").split("-")[-1],
                "status": "delivered",
                "status_ru": "Доставлено"
            }

        mock_transformer.transform_single_posting = transform_mock
        service.transformer = mock_transformer

        with patch('asyncio.sleep', return_value=None):
            period_from = datetime.now() - timedelta(days=10)
            period_to = datetime.now()

            results = []
            async for batch in service.stream_postings(
                    period_from=period_from,
                    period_to=period_to,
                    status_filter=["delivered"],
                    batch_size=2  # Явно указываем размер батча
            ):
                results.extend(batch)


            assert len(results) == 3
            assert results[0]["posting_number"] == "FBO-001"
            assert results[1]["posting_number"] == "FBO-002"
            assert results[2]["posting_number"] == "FBO-003"

    @pytest.mark.asyncio
    async def test_service_context_manager(self):
        """Тест контекстного менеджера"""
        async with FBOService(
                client_id="test_client",
                api_key="test_key",
                request_id="test_request"
        ) as service:
            assert service.session is not None
            assert not service.session.closed

        assert service.session is None