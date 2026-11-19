import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from src.app.fbo.fbo_transformer import FBOTransformer
from src.app.fbs.fbs_transformer import FBSTransformer


@pytest.fixture
def fbo_transformer():
    """Фикстура для FBO трансформера"""
    return FBOTransformer()


@pytest.fixture
def fbs_transformer():
    """Фикстура для FBS трансформера"""
    return FBSTransformer()


@pytest.fixture
def sample_posting_data():
    """Образец данных отправления для тестов"""
    return {
        "posting_number": "123456",
        "order_id": 789,
        "status": "delivering",
        "created_at": "2024-01-15T10:30:45Z",
        "in_process_at": "2024-01-15T11:00:00Z",
        "products": [
            {
                "sku": 111,
                "name": "Тестовый товар",
                "quantity": 2,
                "price": "100.50",
                "offer_id": "OFFER-111",
                "currency_code": "RUB"
            }
        ]
    }


@pytest.fixture
def sample_fbs_posting_data():
    """Образец FBS данных отправления"""
    return {
        "posting_number": "FBS-789",
        "order_id": "ORDER-456",
        "status": "awaiting_packaging",
        "products": [
            {
                "sku": 222,
                "name": "FBS Товар",
                "quantity": 1,
                "price": "500.00",
                "mandatory_mark": "010460406000600021N4N57RTB"
            }
        ],
        "packages": [
            {
                "package_id": "PKG-001",
                "weight": 1.5,
                "width": 10,
                "height": 20,
                "depth": 15
            }
        ]
    }


@pytest.fixture
def event_loop():
    """Фикстура для event loop в async тестах"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


