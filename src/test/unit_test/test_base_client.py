import pytest
import aiohttp
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, Mock
from src.app.core.base_client import BaseOzonClient, RequestParams


class TestBaseOzonClient:
    """Юнит-тесты для BaseOzonClient"""

    @pytest.fixture
    def mock_config(self):
        """Фикстура конфигурации"""
        config = MagicMock()
        config.client_id = "test-client-123"
        config.api_key = "test-api-key-456"
        config.base_url = "https://api.ozon.ru"
        config.rate_limit_delay = 0.1
        return config

    @pytest.fixture
    def client(self, mock_config):
        """Фикстура клиента"""
        with patch('aiohttp.ClientSession'):
            client = BaseOzonClient(mock_config)
            client.session = None  # Убеждаемся, что сессия None
            return client

    @pytest.fixture
    def request_params(self):
        """Фикстура параметров запроса"""
        return RequestParams(
            method="POST",
            path="/v1/posting/fbs/list",
            json_data={"filter": {"since": "2024-01-01"}},
            headers={"X-Custom-Header": "value"}
        )

    def create_mock_context_manager(self, return_value=None):
        """Создает мок асинхронного контекстного менеджера"""
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=return_value or mock_cm)
        mock_cm.__aexit__ = AsyncMock(return_value=None)
        return mock_cm

    # Тесты RequestParams dataclass
    def test_request_params_default_values(self):
        """GWT: Значения по умолчанию в RequestParams"""
        params = RequestParams(method="GET", path="/test")
        assert params.method == "GET"
        assert params.path == "/test"
        assert params.json_data is None
        assert params.headers is None

    def test_request_params_with_all_values(self):
        """GWT: RequestParams со всеми значениями"""
        json_data = {"key": "value"}
        headers = {"Custom": "Header"}

        params = RequestParams(
            method="POST",
            path="/api/test",
            json_data=json_data,
            headers=headers
        )

        assert params.method == "POST"
        assert params.path == "/api/test"
        assert params.json_data == json_data
        assert params.headers == headers

    @pytest.mark.parametrize("method", ["GET", "POST", "PUT", "DELETE"])
    def test_request_params_various_methods(self, method):
        """GWT: Различные HTTP методы"""
        params = RequestParams(method=method, path="/test")
        assert params.method == method

    # Тесты BaseOzonClient
    @pytest.mark.asyncio
    async def test_make_request_success(self, client, request_params):
        """GWT: Успешный запрос к API"""
        # Given
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.ok = True
        mock_response.json = AsyncMock(return_value={"result": [{"posting_number": "123"}]})

        mock_request_cm = self.create_mock_context_manager(mock_response)

        mock_session = MagicMock()
        mock_session.request = Mock(return_value=mock_request_cm)

        # Патчим _ensure_session чтобы он устанавливал нашу мок-сессию
        async def mock_ensure_session():
            client.session = mock_session

        # When
        with patch.object(client, '_ensure_session', side_effect=mock_ensure_session):
            with patch('asyncio.sleep', AsyncMock()):
                result = await client.make_request(request_params)

        # Then
        assert result == {"result": [{"posting_number": "123"}]}
        mock_session.request.assert_called_once()
        call_kwargs = mock_session.request.call_args[1]
        assert call_kwargs['url'] == "https://api.ozon.ru/v1/posting/fbs/list"
        assert call_kwargs['headers']['Client-Id'] == "test-client-123"
        assert call_kwargs['headers']['X-Custom-Header'] == "value"

    @pytest.mark.asyncio
    async def test_make_request_api_error(self, client, request_params):
        """GWT: Ошибка API (не 200 статус)"""
        # Given
        mock_response = MagicMock()
        mock_response.status = 400
        mock_response.ok = False
        mock_response.text = AsyncMock(return_value='{"error": "Bad request"}')

        mock_request_cm = self.create_mock_context_manager(mock_response)

        mock_session = MagicMock()
        mock_session.request = Mock(return_value=mock_request_cm)

        async def mock_ensure_session():
            client.session = mock_session

        # When/Then
        with patch.object(client, '_ensure_session', side_effect=mock_ensure_session):
            with patch('asyncio.sleep', AsyncMock()):
                with pytest.raises(Exception) as exc_info:
                    await client.make_request(request_params)

        assert "API returned 400" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_make_request_rate_limit_delay(self, client, request_params):
        """GWT: Проверка задержки rate limit"""
        # Given
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.ok = True
        mock_response.json = AsyncMock(return_value={})

        mock_request_cm = self.create_mock_context_manager(mock_response)

        mock_session = MagicMock()
        mock_session.request = Mock(return_value=mock_request_cm)

        async def mock_ensure_session():
            client.session = mock_session

        # When
        with patch.object(client, '_ensure_session', side_effect=mock_ensure_session):
            with patch('asyncio.sleep', AsyncMock()) as mock_sleep:
                await client.make_request(request_params)

        # Then
        mock_sleep.assert_called_once_with(0.1)

    @pytest.mark.asyncio
    async def test_make_request_without_custom_headers(self, client):
        """GWT: Запрос без дополнительных заголовков"""
        # Given
        params = RequestParams(
            method="GET",
            path="/v1/product/info",
            json_data={"product_id": 123}
        )

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.ok = True
        mock_response.json = AsyncMock(return_value={"product": {}})

        mock_request_cm = self.create_mock_context_manager(mock_response)

        mock_session = MagicMock()
        mock_session.request = Mock(return_value=mock_request_cm)

        async def mock_ensure_session():
            client.session = mock_session

        # When
        with patch.object(client, '_ensure_session', side_effect=mock_ensure_session):
            with patch('asyncio.sleep', AsyncMock()):
                await client.make_request(params)

        # Then
        call_kwargs = mock_session.request.call_args[1]
        headers = call_kwargs['headers']

        # Только базовые заголовки
        assert headers == {
            "Client-Id": "test-client-123",
            "Api-Key": "test-api-key-456",
            "Content-Type": "application/json"
        }

    @pytest.mark.asyncio
    async def test_headers_merge_correctly(self, client):
        """GWT: Заголовки правильно объединяются"""
        # Given
        params = RequestParams(
            method="POST",
            path="/test",
            json_data={},
            headers={"X-Custom": "Value", "Content-Type": "application/xml"}
        )

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.ok = True
        mock_response.json = AsyncMock(return_value={})

        mock_request_cm = self.create_mock_context_manager(mock_response)

        mock_session = MagicMock()
        mock_session.request = Mock(return_value=mock_request_cm)

        async def mock_ensure_session():
            client.session = mock_session

        # When
        with patch.object(client, '_ensure_session', side_effect=mock_ensure_session):
            with patch('asyncio.sleep', AsyncMock()):
                await client.make_request(params)

        # Then
        call_kwargs = mock_session.request.call_args[1]
        headers = call_kwargs['headers']

        # Проверяем, что базовые заголовки есть
        assert headers["Client-Id"] == "test-client-123"
        assert headers["Api-Key"] == "test-api-key-456"

        # Кастомные заголовки переопределяют базовые
        assert headers["X-Custom"] == "Value"
        assert headers["Content-Type"] == "application/xml"  # Переопределен

    @pytest.mark.asyncio
    async def test_make_request_json_parsing_error(self, client, request_params):
        """GWT: Ошибка при парсинге JSON ответа"""
        # Given
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.ok = True
        mock_response.json = AsyncMock(side_effect=ValueError("Invalid JSON"))

        mock_request_cm = self.create_mock_context_manager(mock_response)

        mock_session = MagicMock()
        mock_session.request = Mock(return_value=mock_request_cm)

        async def mock_ensure_session():
            client.session = mock_session

        # When/Then
        with patch.object(client, '_ensure_session', side_effect=mock_ensure_session):
            with patch('asyncio.sleep', AsyncMock()):
                with pytest.raises(ValueError):
                    await client.make_request(request_params)

    @pytest.mark.asyncio
    async def test_ensure_session_creates_session(self, client):
        """GWT: Сессия создается при необходимости"""
        # Given
        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch('aiohttp.ClientSession', return_value=mock_session):
            # When
            await client._ensure_session()

            # Then
            assert client.session is mock_session

    @pytest.mark.asyncio
    async def test_close_closes_session(self, client):
        """GWT: Закрытие сессии"""
        # Given
        mock_session = MagicMock()
        mock_session.closed = False  # Важно: сессия должна быть не закрыта
        mock_session.close = AsyncMock()  # close - асинхронный метод
        client.session = mock_session

        # When
        await client.close()

        # Then
        # Проверяем, что close был вызван (await)
        mock_session.close.assert_awaited_once()


    @pytest.mark.asyncio
    async def test_make_request_builds_correct_url(self, client):
        """GWT: URL строится правильно"""
        # Given
        params = RequestParams(method="GET", path="/test/path")

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.ok = True
        mock_response.json = AsyncMock(return_value={})

        mock_request_cm = self.create_mock_context_manager(mock_response)

        mock_session = MagicMock()
        mock_session.request = Mock(return_value=mock_request_cm)

        async def mock_ensure_session():
            client.session = mock_session

        # When
        with patch.object(client, '_ensure_session', side_effect=mock_ensure_session):
            with patch('asyncio.sleep', AsyncMock()):
                await client.make_request(params)

        # Then
        call_kwargs = mock_session.request.call_args[1]
        assert call_kwargs['url'] == "https://api.ozon.ru/test/path"

    def test_init_sets_config(self, mock_config):
        """GWT: Конфигурация устанавливается при инициализации"""
        # When
        with patch('aiohttp.ClientSession'):
            client = BaseOzonClient(mock_config)

        # Then
        assert client.config is mock_config
        assert client.session is None

    @pytest.mark.asyncio
    async def test_make_request_network_error_retry(self, client, request_params):
        """GWT: Сетевая ошибка вызывает повторные попытки"""
        # Given
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.ok = True
        mock_response.json = AsyncMock(return_value={"success": True})

        mock_request_cm = self.create_mock_context_manager(mock_response)

        mock_session = MagicMock()
        # Первый вызов вызывает ошибку, второй - успех
        mock_session.request = Mock(side_effect=[
            aiohttp.ClientError("Network error"),
            mock_request_cm
        ])

        async def mock_ensure_session():
            client.session = mock_session

        # When
        with patch.object(client, '_ensure_session', side_effect=mock_ensure_session):
            with patch('asyncio.sleep', AsyncMock()):
                result = await client.make_request(request_params)

        # Then
        assert result == {"success": True}
        assert mock_session.request.call_count == 2