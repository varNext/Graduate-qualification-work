import uuid
import json
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from fastapi import APIRouter, HTTPException, Header, Response, Body
from src.app.services.service_factory import OzonServiceFactory
from src.app.models.enums import ServiceType

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/fbs", tags=["FBS"])


class FBSRequest(BaseModel):
    """Запрос для FBS"""
    period_from: str = Field(..., description="Начало периода в формате ISO")
    period_to: str = Field(..., description="Конец периода в формате ISO")
    status_filter: Optional[str] = Field(
        default=None,
        description="Фильтр по статусам FBS"
    )
    auto_confirm: bool = Field(
        default=False,
        description="Автоматически подтверждать отгрузки"
    )
    require_full_details: bool = Field(
        default=True,
        description="Запрашивать полные детали по каждому отправлению"
    )


class FBSApproveRequest(BaseModel):
    """Запрос на подтверждение FBS отгрузки"""
    posting_number: str = Field(..., description="Номер отправления")
    packages_data: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Данные упаковок"
    )

@router.post("/postings", summary="Получение FBS отправлений для 1С")
async def get_fbs_postings(
        request: FBSRequest,
        client_id: Optional[str] = Header(None, alias="Client-Id"),
        api_key: Optional[str] = Header(None, alias="Api-Key")
):
    """Основной FBS эндпоинт"""
    request_id = str(uuid.uuid4())[:8]
    module_start_time = datetime.now()

    logger.info(f"[{request_id}] FBS request: {request.period_from} - {request.period_to}")

    # Валидация заголовков
    if not client_id or not api_key:
        raise HTTPException(
            status_code=401,
            detail="Укажите Client-Id и Api-Key в заголовках"
        )

    # Валидация периода
    try:
        period_from = datetime.fromisoformat(request.period_from.replace('Z', '+00:00'))
        period_to = datetime.fromisoformat(request.period_to.replace('Z', '+00:00'))

        if period_from > period_to:
            raise HTTPException(
                status_code=400,
                detail="Начало периода позже окончания"
            )

        period_days = (period_to - period_from).days
        if period_days > 30:
            raise HTTPException(
                status_code=400,
                detail="Период не может превышать 30 дней"
            )

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Неверный формат даты: {e}"
        )

    # Создание сервиса
    service = OzonServiceFactory.create_service(
        client_id=client_id.strip(),
        api_key=api_key.strip(),
        service_type=ServiceType.FBS,
        request_id=request_id
    )

    all_postings = []
    total_postings = 0
    errors = []

    try:

        async with service:
            logger.info(f"[{request_id}] Starting to stream postings...")
            batch_count = 0

            async for posting_batch in service.stream_postings(
                    period_from=period_from,
                    period_to=period_to,
                    status_filter=request.status_filter,
                    auto_confirm=request.auto_confirm,
                    require_details=request.require_full_details
            ):
                batch_count += 1
                logger.info(f"[{request_id}] Received batch #{batch_count} with {len(posting_batch)} postings")

                for posting in posting_batch:
                    if isinstance(posting, dict) and "posting_number" in posting:
                        all_postings.append(posting)
                    else:
                        errors.append({
                            "error": "Invalid posting format",
                            "data": str(posting)[:200]
                        })

                total_postings += len(posting_batch)

        module_end_time = datetime.now()
        module_duration = (module_end_time - module_start_time).total_seconds()


        metrics = service.get_metrics()


        confirmed_count = len([p for p in all_postings if p.get("подтверждение_отгрузки")])


        response_dict = {
            "success": True,
            "message": f"FBS данные успешно получены. Найдено {len(all_postings)} отправлений",
            "timestamp": datetime.now().isoformat(),
            "service_type": "FBS",
            "performance": {
                "module_execution_time_seconds": round(module_duration, 3),
                "method_execution_time_seconds": round(metrics["method_duration"], 3),
                "api_execution_time_seconds": round(metrics["api_active_time"], 3),
                "transformation_time_seconds": round(metrics["transformation_time"], 3),
                "rate_limiting_delay_seconds": round(metrics["rate_limiting_time"], 3),
                "total_api_calls": metrics["api_calls_count"],
                "memory_increase_mb": round(metrics["memory_increase_mb"], 1),
                "cpu_peak_percent": round(metrics["peak_cpu_percent"], 1),
                "awaiting_packaging": metrics["awaiting_packaging"],
                "awaiting_deliver": metrics["awaiting_deliver"],
                "processing_speed_records_per_second": round(
                    metrics["total_postings"] / module_duration if module_duration > 0 else 0, 1
                )
            },
            "data": {
                "отправления": all_postings,
                "статистика": {
                    "всего_получено": total_postings,
                    "успешно_обработано": len(all_postings),
                    "подтверждено_отгрузок": confirmed_count,
                    "ошибок_трансформации": len(errors)
                }
            },
            "metadata": {
                "request_id": request_id,
                "period": {
                    "from": request.period_from,
                    "to": request.period_to
                },
                "auto_confirm": request.auto_confirm,
                "status_filter": request.status_filter,
                "api_version": service.get_api_version()
            },
            "errors": errors if errors else []
        }


        json_str = json.dumps(
            response_dict,
            ensure_ascii=False,
            default=str,
            indent=None,
            separators=(',', ':'),
            allow_nan=False
        )

        return Response(
            content=json_str,
            media_type="application/json; charset=utf-8",
            status_code=200
        )

    except Exception as e:
        module_end_time = datetime.now()
        module_duration = (module_end_time - module_start_time).total_seconds()

        logger.error(f"[{request_id}] FBS critical error: {e}", exc_info=True)

        error_dict = {
            "success": False,
            "message": "FBS processing error",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
            "service_type": "FBS",
            "performance": {
                "module_execution_time_seconds": round(module_duration, 3)
            },
            "data": None,
            "metadata": {"request_id": request_id},
            "errors": [{"message": str(e), "type": "critical"}]
        }

        error_json = json.dumps(error_dict, ensure_ascii=False, default=str)

        return Response(
            content=error_json,
            media_type="application/json; charset=utf-8",
            status_code=500
        )


@router.post("/approve", summary="Подтверждение FBS отгрузки")
async def approve_fbs_shipment(
        request: FBSApproveRequest = Body(...),
        client_id: Optional[str] = Header(None, alias="Client-Id"),
        api_key: Optional[str] = Header(None, alias="Api-Key")
):
    """Ручное подтверждение FBS отгрузки"""
    if not client_id or not api_key:
        raise HTTPException(status_code=401, detail="Укажите заголовки авторизации")

    request_id = str(uuid.uuid4())[:8]

    service = OzonServiceFactory.create_service(
        client_id=client_id,
        api_key=api_key,
        service_type=ServiceType.FBS,
        request_id=request_id
    )

    try:
        async with service:
            result = await service.approve_posting(
                request.posting_number,
                request.packages_data
            )

        return {
            "success": result.get("success", False),
            "message": "Отгрузка подтверждена" if result.get("success") else "Ошибка подтверждения",
            "posting_number": request.posting_number,
            "result": result,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"[{request_id}] FBS approve error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))