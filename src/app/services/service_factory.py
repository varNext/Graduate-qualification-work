import logging
from typing import Optional
from src.app.fbo.fbo_service import FBOService
from src.app.fbs.fbs_service import FBSService
from src.app.models.enums import ServiceType

logger = logging.getLogger(__name__)


class OzonServiceFactory:
    """Фабрика для создания сервисов Ozon"""

    @staticmethod
    def create_service(
            client_id: str,
            api_key: str,
            service_type: ServiceType = ServiceType.FBO,
            request_id: Optional[str] = None
    ):
        """
        Создает сервис для запроса

        Args:
            client_id: Client-Id Ozon
            api_key: Api-Key Ozon
            service_type: Тип сервиса (FBO/FBS)
            request_id: ID запроса для логирования

        Returns:
            Экземпляр сервиса
        """
        logger.info(f"Создание {service_type.value} сервиса для клиента: {client_id[:10]}...")

        if service_type == ServiceType.FBO:
            return FBOService(client_id=client_id, api_key=api_key, request_id=request_id)

        elif service_type == ServiceType.FBS:
            return FBSService(client_id=client_id, api_key=api_key,  request_id=request_id)
        else:
            raise ValueError(f"Неизвестный тип сервиса: {service_type}")