import pytest
from unittest.mock import Mock, patch

from src.app.services.service_factory import OzonServiceFactory
from src.app.models.enums import ServiceType
from src.app.fbo.fbo_service import FBOService
from src.app.fbs.fbs_service import FBSService


class TestOzonServiceFactory:
    """Юнит-тесты для фабрики сервисов """

    def test_create_fbo_service(self):
        """GWT: Создание FBO сервиса через фабрику"""
        client_id = "test-client-id"
        api_key = "test-api-key"

        service = OzonServiceFactory.create_service(
            client_id=client_id,
            api_key=api_key,
            service_type=ServiceType.FBO
        )

        assert isinstance(service, FBOService)
        assert service.client_id == client_id
        assert service.api_key == api_key

    def test_create_fbs_service(self):
        """GWT: Создание FBS сервиса через фабрику"""
        client_id = "test-client-id"
        api_key = "test-api-key"

        service = OzonServiceFactory.create_service(
            client_id=client_id,
            api_key=api_key,
            service_type=ServiceType.FBS
        )

        assert isinstance(service, FBSService)
        assert service.client_id == client_id
        assert service.api_key == api_key

    def test_create_service_with_request_id(self):
        """GWT: Создание сервиса с request_id"""

        client_id = "test-client"
        api_key = "test-key"
        request_id = "test-request-123"

        service = OzonServiceFactory.create_service(
            client_id=client_id,
            api_key=api_key,
            service_type=ServiceType.FBO,
            request_id=request_id
        )

        assert service.request_id == request_id

    def test_create_service_with_invalid_type_raises_error(self):
        """GWT: Создание сервиса с неизвестным типом вызывает ошибку"""
        client_id = "test-client"
        api_key = "test-key"

        with pytest.raises(ValueError) as exc_info:
            class InvalidServiceType:
                value = "invalid"

            OzonServiceFactory.create_service(
                client_id=client_id,
                api_key=api_key,
                service_type=InvalidServiceType()  # type: ignore
            )

        assert "Неизвестный тип сервиса" in str(exc_info.value)