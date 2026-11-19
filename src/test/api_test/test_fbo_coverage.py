import asyncio
import json
from datetime import datetime, timedelta
import httpx
import pytest
from swagger_coverage_tool import SwaggerCoverageTracker

tracker = SwaggerCoverageTracker(service="ozon-fbo-service")


BASE_URL = "http://localhost:8001"

# Тестовые данные
TEST_CLIENT_ID = "test-client-12345"
TEST_API_KEY = "test-api-key-abcdапвпвпвef"
TEST_PERIOD_FROM = (datetime.now() - timedelta(days=3)).isoformat() + "Z"
TEST_PERIOD_TO = datetime.now().isoformat() + "Z"


@tracker.track_coverage_httpx("/fbo/postings")
async def test_get_fbo_postings_basic():
    """Тест базового запроса FBO данных"""

    headers = {
        "Client-Id": TEST_CLIENT_ID,
        "Api-Key": TEST_API_KEY,
        "Content-Type": "application/json"
    }

    payload = {
        "period_from": TEST_PERIOD_FROM,
        "period_to": TEST_PERIOD_TO,
        "status_filter": None
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{BASE_URL}/fbo/postings",
            headers=headers,
            json=payload
        )

    return response


@tracker.track_coverage_httpx("/fbo/postings")
async def test_get_fbo_postings_with_status_filter():
    """Тест запроса с фильтром по статусу"""

    headers = {
        "Client-Id": TEST_CLIENT_ID,
        "Api-Key": TEST_API_KEY,
        "Content-Type": "application/json"
    }

    payload = {
        "period_from": TEST_PERIOD_FROM,
        "period_to": TEST_PERIOD_TO,
        "status_filter": "awaiting_deliver"  # Один конкретный статус
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{BASE_URL}/fbo/postings",
            headers=headers,
            json=payload
        )

    return response


@tracker.track_coverage_httpx("/fbo/postings")
async def test_get_fbo_postings_long_period():
    """Тест запроса с длинным периодом (должен вернуть ошибку)"""

    headers = {
        "Client-Id": TEST_CLIENT_ID,
        "Api-Key": TEST_API_KEY,
        "Content-Type": "application/json"
    }

    # Период больше 30 дней (должен вернуть 400 ошибку)
    long_period_from = (datetime.now() - timedelta(days=40)).isoformat() + "Z"

    payload = {
        "period_from": long_period_from,
        "period_to": TEST_PERIOD_TO,
        "status_filter": None
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{BASE_URL}/fbo/postings",
            headers=headers,
            json=payload
        )

    return response


@tracker.track_coverage_httpx("/fbo/postings")
async def test_get_fbo_postings_invalid_dates():
    """Тест запроса с некорректными датами"""

    headers = {
        "Client-Id": TEST_CLIENT_ID,
        "Api-Key": TEST_API_KEY,
        "Content-Type": "application/json"
    }

    payload = {
        "period_from": TEST_PERIOD_TO,  # Начало позже окончания
        "period_to": TEST_PERIOD_FROM,
        "status_filter": None
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{BASE_URL}/fbo/postings",
            headers=headers,
            json=payload
        )

    return response


@tracker.track_coverage_httpx("/fbo/postings")
async def test_get_fbo_postings_missing_headers():
    """Тест запроса без заголовков авторизации"""

    headers = {
        "Content-Type": "application/json"
        # Нет Client-Id и Api-Key
    }

    payload = {
        "period_from": TEST_PERIOD_FROM,
        "period_to": TEST_PERIOD_TO,
        "status_filter": None
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{BASE_URL}/fbo/postings",
            headers=headers,
            json=payload
        )

    return response


@tracker.track_coverage_httpx("/fbo/postings")
async def test_get_fbo_postings_multiple_statuses():
    """Тест запроса с несколькими статусами"""

    headers = {
        "Client-Id": TEST_CLIENT_ID,
        "Api-Key": TEST_API_KEY,
        "Content-Type": "application/json"
    }

    payload = {
        "period_from": TEST_PERIOD_FROM,
        "period_to": TEST_PERIOD_TO,
        "status_filter": ["awaiting_deliver", "delivering", "delivered"]
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{BASE_URL}/fbo/postings",
            headers=headers,
            json=payload
        )

    return response


@tracker.track_coverage_httpx("/fbo/postings")
async def test_get_fbo_postings_small_period():
    """Тест запроса с очень коротким периодом (1 день)"""

    headers = {
        "Client-Id": TEST_CLIENT_ID,
        "Api-Key": TEST_API_KEY,
        "Content-Type": "application/json"
    }

    small_period_to = (datetime.now() - timedelta(days=2)).isoformat() + "Z"

    payload = {
        "period_from": TEST_PERIOD_FROM,
        "period_to": small_period_to,
        "status_filter": None
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{BASE_URL}/fbo/postings",
            headers=headers,
            json=payload
        )

    return response



async def run_all_tests():
    """Запуск всех тестов"""

    print("Запуск тестов FBO API...")

    tests = [
        test_get_fbo_postings_basic,
        test_get_fbo_postings_with_status_filter,
        test_get_fbo_postings_long_period,
        test_get_fbo_postings_invalid_dates,
        test_get_fbo_postings_missing_headers,
        test_get_fbo_postings_multiple_statuses,
        test_get_fbo_postings_small_period,
    ]

    for test_func in tests:
        try:
            print(f"\nЗапуск теста: {test_func.__name__}")
            response = await test_func()

            print(f"Статус: {response.status_code}")
            print(f"Content-Type: {response.headers.get('content-type')}")

            if response.status_code == 200:
                try:
                    data = response.json()
                    print(f"Успешно! Получено записей: {len(data.get('data', {}).get('отправления', []))}")
                except:
                    print(f"Успешно! (не JSON ответ)")
            elif response.status_code == 400:
                print(f"Ожидаемая ошибка валидации: {response.text[:100]}")
            elif response.status_code == 401:
                print(f"Ожидаемая ошибка авторизации: {response.text[:100]}")
            else:
                print(f"Неожиданный статус: {response.text[:200]}")

        except Exception as e:
            print(f"Ошибка при выполнении теста {test_func.__name__}: {str(e)}")

    print("\nВсе тесты завершены!")


import requests


def test_with_requests():
    """Пример с использованием requests (синхронно)"""

    headers = {
        "Client-Id": TEST_CLIENT_ID,
        "Api-Key": TEST_API_KEY,
        "Content-Type": "application/json"
    }

    payload = {
        "period_from": TEST_PERIOD_FROM,
        "period_to": TEST_PERIOD_TO,
        "status_filter": None
    }

    @tracker.track_coverage_requests("/fbo/postings")
    def make_request():
        return requests.post(
            f"{BASE_URL}/fbo/postings",
            headers=headers,
            json=payload,
            timeout=30
        )

    return make_request()



@pytest.mark.asyncio
async def test_fbo_basic_response_format():
    """Тест формата ответа"""
    response = await test_get_fbo_postings_basic()

    if response.status_code == 200:
        data = response.json()

        # Проверяем структуру ответа
        assert "success" in data
        assert "message" in data
        assert "timestamp" in data
        assert "data" in data

        if data.get("data") and data["data"].get("отправления"):
            posting = data["data"]["отправления"][0]
            assert "posting_number" in posting
            assert "status" in posting


@pytest.mark.asyncio
async def test_fbo_error_handling():
    """Тест обработки ошибок"""
    response = await test_get_fbo_postings_missing_headers()

    # Должен вернуть 401 без заголовков
    assert response.status_code == 401

    error_data = response.json()
    assert "detail" in error_data


# Основной запуск
if __name__ == "__main__":
    # Запуск всех асинхронных тестов
    asyncio.run(run_all_tests())


    print("\nДля генерации отчета покрытия выполните команду:")
    print("swagger-coverage-tool save-report")