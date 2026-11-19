# tests/test_fbo_error_handling.py
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch
from datetime import datetime
from src.app.fbo.fbo_service import FBOService


class TestFBOErrorHandling:
    """Тесты обработки ошибок Ozon API"""

    @pytest.mark.asyncio
    async def test_handle_ozon_api_400_error(self):
        """Обработка ошибки 400 от Ozon API"""
        service = FBOService(
            client_id="test",
            api_key="test",
            request_id="test"
        )

        with patch.object(service, '_make_api_request') as mock_api:
            mock_api.side_effect = Exception("API error 400: Invalid request")

            period_from = datetime(2024, 1, 1)
            period_to = datetime(2024, 1, 10)

            # Должен выбросить исключение
            with pytest.raises(Exception) as exc_info:
                async for _ in service.stream_postings(
                        period_from=period_from,
                        period_to=period_to
                ):
                    pass

            assert "API error 400" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_handle_ozon_api_429_rate_limit(self):
        """Обработка ошибки 429 (Rate Limit)"""
        service = FBOService(
            client_id="test",
            api_key="test",
            request_id="test"
        )

        with patch.object(service, '_make_api_request') as mock_api:
            mock_api.side_effect = Exception("API error 429: Rate limit exceeded")

            period_from = datetime(2024, 1, 1)
            period_to = datetime(2024, 1, 10)

            with pytest.raises(Exception) as exc_info:
                async for _ in service.stream_postings(
                        period_from=period_from,
                        period_to=period_to
                ):
                    pass

            assert "Rate limit" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_handle_network_error(self):
        """Обработка сетевой ошибки"""
        service = FBOService(
            client_id="test",
            api_key="test",
            request_id="test"
        )

        with patch.object(service, '_make_api_request') as mock_api:
            mock_api.side_effect = Exception("Network error: Connection refused")

            period_from = datetime(2024, 1, 1)
            period_to = datetime(2024, 1, 10)

            with pytest.raises(Exception) as exc_info:
                async for _ in service.stream_postings(
                        period_from=period_from,
                        period_to=period_to
                ):
                    pass

            assert "Network error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_handle_timeout_error(self):
        """Обработка таймаута"""
        service = FBOService(
            client_id="test",
            api_key="test",
            request_id="test"
        )

        with patch.object(service, '_make_api_request') as mock_api:
            mock_api.side_effect = Exception("Request timeout")

            period_from = datetime(2024, 1, 1)
            period_to = datetime(2024, 1, 10)

            with pytest.raises(Exception) as exc_info:
                async for _ in service.stream_postings(
                        period_from=period_from,
                        period_to=period_to
                ):
                    pass

            assert "timeout" in str(exc_info.value).lower()