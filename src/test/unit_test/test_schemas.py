import pytest
from datetime import datetime
from pydantic import ValidationError

from src.app.models.schemas import FBORequest, FBSRequest, FBSApproveRequest
from src.app.models.enums import FBOStatus, FBSStatus


class TestFBORequest:
    """Юнит-тесты для FBORequest с Given-When-Then"""

    def test_valid_request_without_filter(self):
        """GWT: Создание валидного запроса без фильтра"""
        period_from = "2024-01-01T00:00:00Z"
        period_to = "2024-01-02T00:00:00Z"
        request = FBORequest(
            period_from=period_from,
            period_to=period_to
        )

        assert request.period_from == period_from
        assert request.period_to == period_to
        assert request.status_filter is None

    def test_valid_request_with_status_filter(self):
        """GWT: Создание валидного запроса с фильтром статусов"""
        period_from = "2024-01-01T00:00:00Z"
        period_to = "2024-01-02T00:00:00Z"
        status_filter = [FBOStatus.AWAITING_DELIVER, FBOStatus.DELIVERING]

        request = FBORequest(
            period_from=period_from,
            period_to=period_to,
            status_filter=status_filter
        )

        assert len(request.status_filter) == 2
        assert request.status_filter[0] == FBOStatus.AWAITING_DELIVER
        assert request.status_filter[1] == FBOStatus.DELIVERING

    def test_invalid_date_format_raises_error(self):
        """GWT: Создание запроса с некорректным форматом даты вызывает ошибку"""
        period_from = "некорректная-дата"
        period_to = "2024-01-02T00:00:00Z"

        with pytest.raises(ValidationError) as exc_info:
            FBORequest(
                period_from=period_from,
                period_to=period_to
            )

        assert "Invalid date format" in str(exc_info.value)


class TestFBSRequest:
    """Юнит-тесты для FBSRequest с Given-When-Then"""

    def test_default_values(self):
        """GWT: Проверка значений по умолчанию"""
        period_from = "2024-01-01T00:00:00Z"
        period_to = "2024-01-02T00:00:00Z"

        request = FBSRequest(
            period_from=period_from,
            period_to=period_to
        )

        assert request.require_full_details is True
        assert request.status_filter is None

    def test_with_custom_values(self):
        """GWT: Создание запроса с кастомными значениями"""

        period_from = "2024-01-01T00:00:00Z"
        period_to = "2024-01-02T00:00:00Z"
        status_filter = [FBSStatus.AWAITING_PACKAGING]

        request = FBSRequest(
            period_from=period_from,
            period_to=period_to,
            status_filter=status_filter,
            require_full_details=False
        )

        assert request.require_full_details is False
        assert request.status_filter == status_filter


class TestFBSApproveRequest:
    """Юнит-тесты для FBSApproveRequest с Given-When-Then"""

    def test_valid_approve_request(self):
        """GWT: Создание валидного запроса на подтверждение"""
        posting_number = "FBS-123456"
        packages_data = [
            {
                "weight": 1.5,
                "width": 10,
                "height": 20,
                "depth": 15,
                "products": [
                    {"sku": 111, "quantity": 2}
                ]
            }
        ]

        request = FBSApproveRequest(
            posting_number=posting_number,
            packages_data=packages_data
        )

        assert request.posting_number == posting_number
        assert len(request.packages_data) == 1
        assert request.packages_data[0]["weight"] == 1.5

    def test_packages_data_default_empty_list(self):
        """GWT: Поле packages_data по умолчанию - пустой список"""

        posting_number = "FBS-123456"
        request = FBSApproveRequest(
            posting_number=posting_number
        )

        assert request.posting_number == posting_number
        assert request.packages_data == []