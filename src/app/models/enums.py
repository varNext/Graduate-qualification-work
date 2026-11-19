from enum import Enum


class ServiceType(str, Enum):
    """Типы сервисов Ozon"""
    FBO = "fbo"
    FBS = "fbs"


class FBSStatus(str, Enum):
    """Статусы FBS отправлений"""
    AWAITING_REGISTRATION = "awaiting_registration"
    ACCEPTANCE_IN_PROGRESS = "acceptance_in_progress"
    AWAITING_APPROVE = "awaiting_approve"
    AWAITING_PACKAGING = "awaiting_packaging"
    AWAITING_DELIVER = "awaiting_deliver"
    DELIVERING = "delivering"
    DRIVER_PICKUP = "driver_pickup"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    ARBITRATION = "arbitration"
    NOT_ACCEPTED = "not_accepted"
    SENT_BY_SELLER = "sent_by_seller"


class FBOStatus(str, Enum):
    """Статусы FBO отправлений"""
    AWAITING_PACKAGING = "awaiting_packaging"
    AWAITING_DELIVER = "awaiting_deliver"
    DELIVERING = "delivering"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
