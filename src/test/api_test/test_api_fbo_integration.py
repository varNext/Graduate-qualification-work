# tests/test_fbo_integration.py
import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta
import json
from unittest.mock import AsyncMock, patch, MagicMock
from src.main import app


class TestFBOIntegration:
    """Интеграционные тесты FBO API с моками"""

    @pytest.fixture
    def client(self):
        with TestClient(app) as client:
            yield client

    @pytest.fixture
    def valid_headers(self):
        return {
            "Client-Id": "test_client_123",
            "Api-Key": "test_api_key_456"
        }

    @pytest.fixture
    def valid_request_data(self):
        now = datetime.now()
        return {
            "period_from": (now - timedelta(days=10)).isoformat(),
            "period_to": now.isoformat(),
            "status_filter": ["delivered", "cancelled"]
        }



    def test_fbo_postings_success_with_mocks(self, client, valid_request_data, valid_headers):
        """
        Тест успешного получения FBO отправлений с моками
        """

        mock_service = AsyncMock()


        async def mock_stream_postings(*args, **kwargs):

            yield [{
                "posting_number": "FBO-001",
                "order_number": "ORDER-001",
                "status": "delivered",
                "status_ru": "Доставлено",
                "created_at": "2024-01-01T10:00:00+03:00",
                "in_process_at": "2024-01-01T11:00:00+03:00",
                "товары": [
                    {
                        "line_number": 1,
                        "sku": 123456,
                        "name": "Тестовый товар",
                        "quantity": 1,
                        "price": 1000.0,
                        "total": 1000.0,
                        "unit": "шт",
                        "vat_rate": 20.0,
                        "posting_number": "FBO-001",
                        "offer_id": "OFFER-001",
                        "currency_code": "RUB"
                    }
                ],
                "аналитика": {
                    "warehouse_name": "Москва",
                    "region": "Московская область",
                    "city": "Москва",
                    "delivery_type": "pickup",
                    "warehouse_id": 123,
                    "tpl_provider": "CDEK"
                },
                "доставка": {
                    "method": "СДЭК",
                    "tracking_number": "TRACK-123",
                    "warehouse": "Склад Ozon",
                    "delivery_date": "2024-01-02T10:00:00+03:00",
                    "address": "ул. Примерная, д. 1",
                    "tpl_provider": "CDEK"
                },
                "клиент": {
                    "name": "Иван Иванов",
                    "phone": "+79991234567",
                    "email": "ivan@test.ru",
                    "address": "",
                    "delivery_address": "ул. Примерная, д. 1"
                }
            }]

        mock_service.stream_postings = mock_stream_postings
        mock_service.get_api_version = MagicMock(return_value="v2")
        mock_service.__aenter__ = AsyncMock(return_value=mock_service)
        mock_service.__aexit__ = AsyncMock(return_value=None)


        with patch('src.api.fbo_router.OzonServiceFactory.create_service', return_value=mock_service):
            response = client.post(
                "/fbo/postings",
                json=valid_request_data,
                headers=valid_headers
            )

            print(f"Response status: {response.status_code}")
            print(f"Response data: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")

            assert response.status_code == 200
            data = response.json()


            assert data["success"] is True
            assert data["service_type"] == "FBO"
            assert "отправления" in data["data"]
            assert "статистика" in data["data"]
            assert "metadata" in data


            metadata = data["metadata"]
            assert "request_id" in metadata
            assert "period" in metadata
            assert "status_filter" in metadata
            assert metadata["status_filter"] == ["delivered", "cancelled"]
            assert "api_version" in metadata
            assert metadata["api_version"] == "v2"

    def test_fbo_with_single_status_with_mocks(self, client, valid_headers):
        """Тест с одним статусом в фильтре с моками"""
        mock_service = AsyncMock()

        async def mock_stream_postings(*args, **kwargs):
            yield []

        mock_service.stream_postings = mock_stream_postings
        mock_service.get_api_version = MagicMock(return_value="v2")
        mock_service.__aenter__ = AsyncMock(return_value=mock_service)
        mock_service.__aexit__ = AsyncMock(return_value=None)

        with patch('src.api.fbo_router.OzonServiceFactory.create_service', return_value=mock_service):
            request_data = {
                "period_from": "2024-01-01T00:00:00+03:00",
                "period_to": "2024-01-10T00:00:00+03:00",
                "status_filter": ["awaiting_packaging"]
            }

            response = client.post(
                "/fbo/postings",
                json=request_data,
                headers=valid_headers
            )

            assert response.status_code == 200
            data = response.json()
            assert data["metadata"]["status_filter"] == ["awaiting_packaging"]

    def test_fbo_without_status_filter_with_mocks(self, client, valid_headers):
        """Тест без фильтра статуса с моками"""
        mock_service = AsyncMock()

        async def mock_stream_postings(*args, **kwargs):
            yield []

        mock_service.stream_postings = mock_stream_postings
        mock_service.get_api_version = MagicMock(return_value="v2")
        mock_service.__aenter__ = AsyncMock(return_value=mock_service)
        mock_service.__aexit__ = AsyncMock(return_value=None)

        with patch('src.api.fbo_router.OzonServiceFactory.create_service', return_value=mock_service):
            request_data = {
                "period_from": "2024-01-01T00:00:00+03:00",
                "period_to": "2024-01-10T00:00:00+03:00"
            }

            response = client.post(
                "/fbo/postings",
                json=request_data,
                headers=valid_headers
            )

            assert response.status_code == 200
            data = response.json()
            assert data["metadata"]["status_filter"] is None



    def test_fbo_invalid_period(self, client, valid_headers):
        """Тест с некорректным периодом (начало позже окончания)"""

        request_data = {
            "period_from": "2024-01-10T00:00:00+03:00",
            "period_to": "2024-01-01T00:00:00+03:00"
        }

        response = client.post(
            "/fbo/postings",
            json=request_data,
            headers=valid_headers
        )

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "Начало периода позже окончания" in data["detail"]

    def test_fbo_period_too_long(self, client, valid_headers):
        """Тест с периодом больше 30 дней"""
        request_data = {
            "period_from": "2024-01-01T00:00:00+03:00",
            "period_to": "2024-02-02T00:00:00+03:00"  # 32 дня
        }

        response = client.post(
            "/fbo/postings",
            json=request_data,
            headers=valid_headers
        )

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "Период не может превышать 30 дней" in data["detail"]

    def test_fbo_no_auth_headers(self, client, valid_request_data):
        """Тест без заголовков авторизации"""
        response = client.post(
            "/fbo/postings",
            json=valid_request_data
        )

        assert response.status_code == 401
        data = response.json()
        assert "detail" in data
        assert "Client-Id" in data["detail"]

    def test_fbo_invalid_date_format(self, client, valid_headers):
        """Тест с некорректным форматом даты"""
        request_data = {
            "period_from": "2024-01-01",  # Неполный ISO формат
            "period_to": "неправильная дата"
        }

        response = client.post(
            "/fbo/postings",
            json=request_data,
            headers=valid_headers
        )

        # Pydantic валидация вернет 422
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data



    def test_fbo_empty_response_with_mocks(self, client, valid_headers):
        """Тест с периодом без данных"""
        mock_service = AsyncMock()

        async def mock_stream_postings(*args, **kwargs):
            yield []  # Пустой результат

        mock_service.stream_postings = mock_stream_postings
        mock_service.get_api_version = MagicMock(return_value="v2")
        mock_service.__aenter__ = AsyncMock(return_value=mock_service)
        mock_service.__aexit__ = AsyncMock(return_value=None)

        with patch('src.api.fbo_router.OzonServiceFactory.create_service', return_value=mock_service):
            request_data = {
                "period_from": "2024-01-01T00:00:00+03:00",
                "period_to": "2024-01-02T00:00:00+03:00",
                "status_filter": ["delivered"]
            }

            response = client.post(
                "/fbo/postings",
                json=request_data,
                headers=valid_headers
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert isinstance(data["data"]["отправления"], list)
            assert len(data["data"]["отправления"]) == 0

    def test_fbo_malformed_json(self, client, valid_headers):
        """Тест с некорректным JSON"""
        response = client.post(
            "/fbo/postings",
            content="{invalid json",
            headers=valid_headers
        )

        assert response.status_code == 422

    def test_fbo_partial_headers(self, client, valid_request_data):
        """Тест с частичными заголовками"""
        # Только Client-Id
        response1 = client.post(
            "/fbo/postings",
            json=valid_request_data,
            headers={"Client-Id": "test_client"}
        )
        assert response1.status_code == 401

        # Только Api-Key
        response2 = client.post(
            "/fbo/postings",
            json=valid_request_data,
            headers={"Api-Key": "test_key"}
        )
        assert response2.status_code == 401

    def test_fbo_service_exception_with_mocks(self, client, valid_headers):
        """Тест с исключением в сервисе"""
        mock_service = AsyncMock()
        mock_service.__aenter__ = AsyncMock(side_effect=Exception("Test service error"))

        with patch('src.api.fbo_router.OzonServiceFactory.create_service', return_value=mock_service):
            request_data = {
                "period_from": "2024-01-01T00:00:00+03:00",
                "period_to": "2024-01-10T00:00:00+03:00"
            }

            response = client.post(
                "/fbo/postings",
                json=request_data,
                headers=valid_headers
            )

            assert response.status_code == 500
            data = response.json()
            assert data["success"] is False
            assert "error" in data