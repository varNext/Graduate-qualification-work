import pytest
import aiohttp
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch, MagicMock, Mock

from src.app.core.base_service import BaseOzonService


class ConcreteTestService(BaseOzonService):
    """Конкретная реализация для тестирования абстрактного класса"""

    async def stream_postings(self, period_from, period_to, status_filter=None, **kwargs):
        yield []

    def get_api_version(self):
        return "v1-test"


class TestBaseOzonService:
    """Ключевые юнит-тесты для BaseOzonService"""

    @pytest.fixture
    def service(self):
        return ConcreteTestService(
            client_id="test-client",
            api_key="test-key",
            request_id="test-123"
        )

    # 1. БАЗОВАЯ ФУНКЦИОНАЛЬНОСТЬ
    def test_initialization(self):
        """GWT: Корректная инициализация"""
        service = ConcreteTestService("client", "key", "req-1")

        assert service.client_id == "client"
        assert service.api_key == "key"
        assert service.request_id == "req-1"
        assert service.base_url == "https://api-seller.ozon.ru"
        assert service.session is None

        # Статистика инициализирована
        assert service.stats["total_batches"] == 0
        assert service.stats["start_time"] is None

    # 2. УПРАВЛЕНИЕ СЕССИЕЙ
    @pytest.mark.asyncio
    async def test_session_lifecycle(self):
        """GWT: Полный жизненный цикл сессии"""
        service = ConcreteTestService("client", "key")

        with patch('aiohttp.ClientSession') as MockSession:
            mock_session = AsyncMock()
            mock_session.closed = False
            MockSession.return_value = mock_session

            # Создание сессии
            await service.start()
            assert service.session is mock_session

            # Повторный вызов start не создает новую сессию
            await service.start()
            MockSession.assert_called_once()

            # Закрытие сессии
            await service.close()
            mock_session.close.assert_awaited_once()
            assert service.session is None


    def test_headers_generation(self):
        """GWT: Генерация заголовков"""
        service = ConcreteTestService("my-client", "my-key")
        headers = service._get_headers()

        assert headers == {
            "Client-Id": "my-client",
            "Api-Key": "my-key",
            "Content-Type": "application/json"
        }

    def test_date_formatting(self):
        """GWT: Форматирование даты"""
        service = ConcreteTestService("client", "key")

        # Дата с часовым поясом
        date_msk = datetime(2024, 1, 15, 17, 30, 45, tzinfo=timezone(timedelta(hours=3)))
        formatted = service._format_date_for_ozon(date_msk)

        assert formatted == "2024-01-15T14:30:45.000Z"  # Конвертация в UTC

    # 4. ОСНОВНОЙ API ЗАПРОС
    @pytest.mark.asyncio
    async def test_api_request_success(self):
        """GWT: Успешный API запрос с rate limiting"""
        service = ConcreteTestService("client", "key")

        # Используем MagicMock для сложных объектов
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"data": "test"})
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.post = Mock(return_value=mock_response)  # Обычный Mock
        service.session = mock_session

        with patch('asyncio.sleep', AsyncMock()) as mock_sleep:
            result = await service._make_api_request("/endpoint", {"param": "value"})

            mock_sleep.assert_awaited_once_with(0.3)
            mock_session.post.assert_called_once()
            assert result == {"data": "test"}



    # 7. КОНТЕКСТНЫЙ МЕНЕДЖЕР
    @pytest.mark.asyncio
    async def test_context_manager(self):
        """GWT: Работа контекстного менеджера"""
        service = ConcreteTestService("client", "key")

        with patch.object(service, 'start', AsyncMock()) as mock_start, \
                patch.object(service, 'close', AsyncMock()) as mock_close:
            async with service:
                mock_start.assert_awaited_once()

            mock_close.assert_awaited_once()

    # 8. КРАЙНИЕ СЛУЧАИ
    @pytest.mark.asyncio
    async def test_edge_cases(self):
        """GWT: Обработка крайних случаев"""
        service = ConcreteTestService("client", "key")

        # Закрытие без сессии
        await service.close()  # Не должно вызывать ошибку

        # Сессия уже закрыта
        mock_session = AsyncMock()
        mock_session.closed = True
        service.session = mock_session
        await service.start()  # Должна создать новую сессию

        # Пустой request_id
        service2 = ConcreteTestService("client", "key")
        assert service2.request_id == ""