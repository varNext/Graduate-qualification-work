import pytest
import os
import sys
from datetime import datetime, timedelta


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def base_url():
    """Базовый URL для тестирования"""
    return "http://localhost:8001"


@pytest.fixture
def test_headers():
    """Тестовые заголовки"""
    return {
        "Client-Id": "test_client_123",
        "Api-Key": "test_api_key_456",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }


@pytest.fixture
def valid_payload():
    """Валидный тестовый payload"""
    end_date = datetime.now() - timedelta(days=7)
    start_date = end_date - timedelta(days=3)

    return {
        "period_from": start_date.isoformat() + "Z",
        "period_to": end_date.isoformat() + "Z",
        "status_filter": "awaiting_deliver"
    }


@pytest.fixture(scope="session", autouse=True)
def setup_coverage_config():
    """Настройка переменных окружения для swagger-coverage-tool"""
    os.environ['SWAGGER_COVERAGE_SERVICES'] = '''[
        {
            "key": "ozon-fbo-service",
            "name": "Ozon FBO Service",
            "tags": ["Ozon", "FBO", "API", "Test"],
            "repository": "https://github.com/your-project/ozon-api",
            "swagger_file": "./test_swagger.json"
        }
    ]'''
    os.environ['SWAGGER_COVERAGE_RESULTS_DIR'] = "./coverage-results"
    os.environ['SWAGGER_COVERAGE_HISTORY_FILE'] = "./coverage-history.json"
    os.environ['SWAGGER_COVERAGE_HISTORY_RETENTION_LIMIT'] = "10"
    os.environ['SWAGGER_COVERAGE_HTML_REPORT_FILE'] = "./coverage-report.html"
    os.environ['SWAGGER_COVERAGE_JSON_REPORT_FILE'] = "./coverage-report.json"