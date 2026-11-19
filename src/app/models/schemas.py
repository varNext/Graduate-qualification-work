from datetime import datetime
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, validator


class FBORequest(BaseModel):
    """Запрос для FBO"""
    period_from: str = Field(..., description="Начало периода в формате ISO")
    period_to: str = Field(..., description="Конец периода в формате ISO")

    status_filter: Optional[str] = Field(
        default=None,
        description="Фильтр по статусам FBO. "
                    "Доступные статусы: awaiting_packaging, awaiting_deliver, "
                    "delivering, delivered, cancelled, arbitration"
    )

    @validator('period_from', 'period_to')
    def validate_date_format(cls, v):
        try:
            datetime.fromisoformat(v.replace('Z', '+00:00'))
            return v
        except ValueError:
            raise ValueError(f"Invalid date format: {v}")


class FBSRequest(BaseModel):
    """Запрос для FBS"""
    period_from: str = Field(..., description="Начало периода в формате ISO")
    period_to: str = Field(..., description="Конец периода в формате ISO")
    # status_filter: Optional[List[FBSStatus]] = Field(
    # status_filter: Optional[str] = Field(
    status_filter: Optional[Union[str, List[str]]] = Field(
        default=None,
        description="Фильтр по статусам FBS"
    )

    require_full_details: bool = Field(
        default=True,
        description="Запрашивать полные детали по каждому отправлению"
    )

    @validator('period_from', 'period_to')
    def validate_date_format(cls, v):
        try:
            datetime.fromisoformat(v.replace('Z', '+00:00'))
            return v
        except ValueError:
            raise ValueError(f"Invalid date format: {v}")


class FBSApproveRequest(BaseModel):
    """Запрос на подтверждение FBS отгрузки"""
    posting_number: str = Field(..., description="Номер отправления")
    packages_data: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Данные упаковок"
    )


class APIResponse(BaseModel):
    """Базовый ответ API"""
    success: bool
    message: str
    timestamp: str
    service_type: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    errors: Optional[List[Dict[str, Any]]] = None