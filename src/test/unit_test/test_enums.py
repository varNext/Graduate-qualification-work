import pytest
from src.app.models.enums import ServiceType, FBOStatus, FBSStatus


class TestServiceType:
    """Тесты для ServiceType enum"""

    def test_enum_iteration(self):
        """Проверка что enum содержит ожидаемые типы сервисов"""
        expected_values = {"fbo", "fbs"}
        actual_values = {item.value for item in ServiceType}
        assert actual_values == expected_values

    @pytest.mark.parametrize("enum_item,expected_value", [
        (ServiceType.FBO, "fbo"),
        (ServiceType.FBS, "fbs"),
    ])
    def test_enum_values(self, enum_item, expected_value):
        """Проверка значений типов сервисов"""
        assert enum_item.value == expected_value


class TestFBOStatus:
    """Тесты для статусов FBO"""

    @pytest.mark.parametrize("status_enum,expected_value", [
        (FBOStatus.AWAITING_PACKAGING, "awaiting_packaging"),
        (FBOStatus.AWAITING_DELIVER, "awaiting_deliver"),
        (FBOStatus.DELIVERING, "delivering"),
        (FBOStatus.DELIVERED, "delivered"),
        (FBOStatus.CANCELLED, "cancelled"),
    ])
    def test_status_values(self, status_enum, expected_value):
        """Проверка значений статусов FBO"""
        assert status_enum.value == expected_value


class TestFBSStatus:
    """Тесты для статусов FBS"""

    @pytest.mark.parametrize("status_enum,expected_value", [
        (FBSStatus.AWAITING_PACKAGING, "awaiting_packaging"),
        (FBSStatus.DELIVERING, "delivering"),
        (FBSStatus.DELIVERED, "delivered"),
        (FBSStatus.ARBITRATION, "arbitration"),
    ])
    def test_status_values(self, status_enum, expected_value):
        """Проверка критических статусов FBS"""
        assert status_enum.value == expected_value