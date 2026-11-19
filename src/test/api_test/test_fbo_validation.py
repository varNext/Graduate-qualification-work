# tests/test_fbo_validation.py
import pytest
from datetime import datetime
from src.app.models.schemas import FBORequest
from src.app.models.enums import FBOStatus


class TestFBOValidation:
    """Тесты валидации Pydantic моделей FBO"""

    def test_valid_fbo_request(self):
        """Валидный запрос"""
        request = FBORequest(
            period_from="2024-01-01T00:00:00+03:00",
            period_to="2024-01-10T00:00:00+03:00",
            status_filter=[FBOStatus.DELIVERED, FBOStatus.CANCELLED]
        )

        assert request.period_from == "2024-01-01T00:00:00+03:00"
        assert request.period_to == "2024-01-10T00:00:00+03:00"
        assert request.status_filter == [FBOStatus.DELIVERED, FBOStatus.CANCELLED]

    def test_fbo_request_no_status(self):
        """Запрос без статуса"""
        request = FBORequest(
            period_from="2024-01-01T00:00:00+03:00",
            period_to="2024-01-10T00:00:00+03:00"
        )

        assert request.status_filter is None

    def test_fbo_request_invalid_date(self):
        """Невалидная дата"""
        with pytest.raises(ValueError) as exc_info:
            FBORequest(
                period_from="неправильная дата",
                period_to="2024-01-10T00:00:00+03:00"
            )

        assert "Invalid date format" in str(exc_info.value)

    def test_fbo_request_empty_status_list(self):
        """Пустой список статусов"""
        request = FBORequest(
            period_from="2024-01-01T00:00:00+03:00",
            period_to="2024-01-10T00:00:00+03:00",
            status_filter=[]
        )

        assert request.status_filter == []

    @pytest.mark.parametrize("status_enum", [
        FBOStatus.AWAITING_PACKAGING,
        FBOStatus.AWAITING_DELIVER,
        FBOStatus.DELIVERING,
        FBOStatus.DELIVERED,
        FBOStatus.CANCELLED
    ])
    def test_fbo_all_status_enums(self, status_enum):
        """Все возможные статусы Enum"""
        request = FBORequest(
            period_from="2024-01-01T00:00:00+03:00",
            period_to="2024-01-10T00:00:00+03:00",
            status_filter=[status_enum]
        )

        assert request.status_filter == [status_enum]
        assert request.status_filter[0].value == status_enum.value