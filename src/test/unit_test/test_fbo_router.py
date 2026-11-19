import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient


class TestFBOEndpoint:
    """ тесты для FBO endpoint"""

    @pytest.fixture
    def client(self):
        from src.app.api.fbo_router import router as fbo_router
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(fbo_router)
        return TestClient(app)

    @pytest.fixture
    def headers(self):
        return {"Client-Id": "test", "Api-Key": "test"}

    @pytest.fixture
    def mock_service(self):
        mock = AsyncMock()
        mock.__aenter__ = AsyncMock(return_value=mock)
        mock.__aexit__ = AsyncMock()
        mock.get_api_version = MagicMock(return_value="v2")
        return mock

    def create_generator(self, data):
        async def generator(period_from, period_to, status_filter=None):
            for batch in data:
                yield batch

        return generator

    # Тесты валидации
    def test_missing_client_id(self, client):
        response = client.post("/fbo/postings", json={
            "period_from": "2024-01-01T00:00:00Z",
            "period_to": "2024-01-02T00:00:00Z"
        }, headers={"Api-Key": "test"})
        assert response.status_code == 401

    def test_missing_api_key(self, client):
        response = client.post("/fbo/postings", json={
            "period_from": "2024-01-01T00:00:00Z",
            "period_to": "2024-01-02T00:00:00Z"
        }, headers={"Client-Id": "test"})
        assert response.status_code == 401

    def test_invalid_period(self, client, headers):
        response = client.post("/fbo/postings", json={
            "period_from": "2024-01-02T00:00:00Z",
            "period_to": "2024-01-01T00:00:00Z"
        }, headers=headers)
        assert response.status_code == 400
        assert "позже окончания" in response.json()["detail"]

    # Основные тесты
    def test_success_empty_response(self, client, headers, mock_service):
        """Успешный запрос с пустым ответом"""
        mock_service.stream_postings = self.create_generator([])

        with patch('src.api.fbo_router.OzonServiceFactory.create_service', return_value=mock_service):
            response = client.post("/fbo/postings", json={
                "period_from": "2024-01-01T00:00:00Z",
                "period_to": "2024-01-02T00:00:00Z"
            }, headers=headers)

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["data"]["отправления"] == []
            assert data["metadata"]["api_version"] == "v2"

    def test_success_with_data(self, client, headers, mock_service):
        """Успешный запрос с данными"""
        mock_service.stream_postings = self.create_generator([
            [{"posting_number": "FBO-123"}],
            [{"posting_number": "FBO-456"}]
        ])

        with patch('src.api.fbo_router.OzonServiceFactory.create_service', return_value=mock_service):
            response = client.post("/fbo/postings", json={
                "period_from": "2024-01-01T00:00:00Z",
                "period_to": "2024-01-02T00:00:00Z",
                "status_filter": ["awaiting_deliver"]
            }, headers=headers)

            assert response.status_code == 200
            data = response.json()
            assert len(data["data"]["отправления"]) == 2
            assert data["data"]["статистика"]["всего_получено"] == 2

    def test_service_error(self, client, headers, mock_service):
        """Исключение при вызове stream_postings"""

        # Создаем исключение при вызове метода
        async def raise_exception(*args, **kwargs):
            raise Exception("Service error")

        # Используем side_effect для вызова функции
        mock_service.stream_postings = raise_exception

        with patch('src.api.fbo_router.OzonServiceFactory.create_service', return_value=mock_service):
            response = client.post("/fbo/postings", json={
                "period_from": "2024-01-01T00:00:00Z",
                "period_to": "2024-01-02T00:00:00Z"
            }, headers=headers)

            print(f"\n=== DEBUG ===")
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text[:500]}")

            data = response.json()

            # Проверяем структуру ответа
            if response.status_code == 500:
                # Классическая ошибка 500
                assert data["success"] is False
                assert "error" in data
            else:
                # Если 200, но с ошибкой в данных
                assert data["success"] is False or "errors" in data



    def test_invalid_data_format(self, client, headers, mock_service):
        """Некорректный формат данных"""

        async def mixed_generator(period_from, period_to, status_filter=None):
            yield [{"posting_number": "FBO-123"}]
            yield [{"invalid": "data"}]  # Нет posting_number
            yield [{"posting_number": "FBO-456"}]

        mock_service.stream_postings = mixed_generator

        with patch('src.api.fbo_router.OzonServiceFactory.create_service', return_value=mock_service):
            response = client.post("/fbo/postings", json={
                "period_from": "2024-01-01T00:00:00Z",
                "period_to": "2024-01-02T00:00:00Z"
            }, headers=headers)

            assert response.status_code == 200
            data = response.json()
            assert len(data["data"]["отправления"]) == 2  # 2 валидных из 3
            assert data["data"]["статистика"]["ошибок_трансформации"] == 1
            assert data["errors"]  # Должны быть ошибки