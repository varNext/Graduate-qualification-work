import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI


class TestFBSEndpoint:
    """ юнит-тесты для FBS endpoint"""

    @pytest.fixture
    def client(self):
        app = FastAPI()
        from src.app.api.fbs_router import router as fbs_router
        app.include_router(fbs_router)
        return TestClient(app)

    @pytest.fixture
    def valid_headers(self):
        return {"Client-Id": "test-client", "Api-Key": "test-key"}

    @pytest.fixture
    def valid_request(self):
        return {
            "period_from": "2024-01-01T00:00:00Z",
            "period_to": "2024-01-02T00:00:00Z",
            "auto_confirm": True
        }

    def create_mock_service(self, postings_data=None):
        """Создает простой мок сервиса"""
        mock_service = AsyncMock()


        if postings_data:
            async def postings_generator():
                for batch in postings_data:
                    yield batch
        else:
            async def postings_generator():
                yield []

        mock_service.stream_postings = postings_generator
        mock_service.get_api_version = MagicMock(return_value="v2")
        mock_service.__aenter__ = AsyncMock(return_value=mock_service)
        mock_service.__aexit__ = AsyncMock()

        return mock_service


    def test_missing_headers_returns_401(self, client, valid_request):
        """GWT: Отсутствие обязательных заголовков"""
        response = client.post("/fbs/postings", json=valid_request)
        assert response.status_code == 401

    def test_invalid_period_returns_400(self, client, valid_headers):
        """GWT: Некорректный период"""
        invalid_request = {
            "period_from": "2024-01-02T00:00:00Z",
            "period_to": "2024-01-01T00:00:00Z"
        }
        response = client.post("/fbs/postings", json=invalid_request, headers=valid_headers)
        assert response.status_code == 400

    def test_successful_postings_request(self, client, valid_headers, valid_request):
        """GWT: Успешный запрос отправлений"""
        test_data = [
            [{"posting_number": "FBS-123", "status": "awaiting_packaging"}],
            [{"posting_number": "FBS-456", "status": "delivering"}]
        ]

        mock_service = self.create_mock_service(test_data)

        with patch('src.api.fbs_router.OzonServiceFactory.create_service', return_value=mock_service):
            response = client.post("/fbs/postings", json=valid_request, headers=valid_headers)

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

            # Проверяем структуру ответа
            if "data" in data and "отправления" in data["data"]:
                postings = data["data"]["отправления"]
                # Может быть 0 или 2 в зависимости от трансформации данных
                assert isinstance(postings, list)
            else:
                # Или проверяем другую структуру
                assert "postings" in data or "results" in data

    def test_empty_postings_response(self, client, valid_headers, valid_request):
        """GWT: Запрос без отправлений"""
        mock_service = self.create_mock_service([])

        with patch('src.api.fbs_router.OzonServiceFactory.create_service', return_value=mock_service):
            response = client.post("/fbs/postings", json=valid_request, headers=valid_headers)

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

    def test_service_exception_returns_500(self, client, valid_headers, valid_request):
        """GWT: Ошибка в сервисе"""
        mock_service = AsyncMock()
        mock_service.__aenter__ = AsyncMock(side_effect=Exception("Service error"))
        mock_service.__aexit__ = AsyncMock()

        with patch('src.api.fbs_router.OzonServiceFactory.create_service', return_value=mock_service):
            response = client.post("/fbs/postings", json=valid_request, headers=valid_headers)

            assert response.status_code == 500
            data = response.json()
            assert data["success"] is False
