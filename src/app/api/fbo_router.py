import uuid
import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Header, Response

from src.app.models.schemas import FBORequest
from src.app.services.service_factory import OzonServiceFactory
from src.app.models.enums import ServiceType

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/fbo", tags=["FBO"])


@router.post("/postings", summary="Получение FBO отправлений для 1С")
async def get_fbo_postings(
        request: FBORequest,
        client_id: Optional[str] = Header(None, alias="Client-Id"),
        api_key: Optional[str] = Header(None, alias="Api-Key")
):
    """Основной FBO эндпоинт"""
    module_start_time = datetime.now()

    request_id = str(uuid.uuid4())[:8]
    logger.info(f"[{request_id}] FBO request: {request.period_from} - {request.period_to}")

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

    status_filter_str = request.status_filter
    if status_filter_str:
        logger.debug(f"[{request_id}] Status filter: {status_filter_str}")

    # Создание сервиса
    service = OzonServiceFactory.create_service(
        client_id=client_id.strip(),
        api_key=api_key.strip(),
        service_type=ServiceType.FBO,
        request_id=request_id
    )

    all_postings = []
    metadata = {}
    errors = []

    try:
        async with service:

            all_postings, metadata = await service.get_postings_with_limits(
                period_from=period_from,
                period_to=period_to,
                status_filter=status_filter_str,
                max_records=20000
            )


        module_end_time = datetime.now()
        module_duration = (module_end_time - module_start_time).total_seconds()


        execution_stats = service.get_execution_stats()


        timing_details = metadata.get("timing", {})
        efficiency_details = timing_details.get("efficiency", {})


        response_dict = {
            "success": metadata.get("success", True),
            "message": "FBO данные успешно получены",
            "timestamp": datetime.now().isoformat(),
            "service_type": "FBO",
            "performance": {
                "module_execution_time_seconds": round(module_duration, 3),
                "method_execution_time_seconds": timing_details.get("method_execution_time", 0),
                "api_execution_time_seconds": timing_details.get("api_execution_time", 0),
                "transformation_time_seconds": timing_details.get("transformation_time", 0),
                "rate_limiting_delay_seconds": timing_details.get("rate_limiting_delay", 0),
                "other_processing_time_seconds": timing_details.get("other_processing_time", 0),
                "total_batches": execution_stats.get("total_batches", 0),
                "total_api_calls": execution_stats.get("api_calls_count", 0),
                "avg_api_response_time_seconds": execution_stats.get("avg_api_response_time", 0),
                "start_time": module_start_time.isoformat(),
                "end_time": module_end_time.isoformat(),
                "efficiency": efficiency_details
            },
            "data": {
                "отправления": all_postings,
                "статистика": {
                    "всего_получено": metadata.get("total_retrieved", 0),
                    "дней_обработано": len(metadata.get("days_processed", [])),
                    "частичные_данные": metadata.get("partial_data", False),
                    "достигнут_лимит": metadata.get("max_limit_reached", False)
                }
            },
            "metadata": {
                "request_id": request_id,
                "период_запроса": {
                    "from": request.period_from,
                    "to": request.period_to
                },
                "обработанные_дни": metadata.get("days_processed", []),
                "статистика_по_дням": metadata.get("date_statistics", {}),
                "статус_фильтр": status_filter_str,
                "предупреждения": metadata.get("warnings", []),
                "api_statistics": metadata.get("api_statistics", {}),
                "timing_details": metadata.get("timing", {}),
                "рекомендации": []
            },
            "errors": errors
        }


        if metadata.get("max_limit_reached", False):
            recommendations = [
                f"Уменьшите период запроса с {period_days} дней до 3-7 дней",
                "Используйте фильтр по конкретным статусам отправлений",
                "Разбейте запрос на несколько меньших по периоду запросов"
            ]
            response_dict["metadata"]["рекомендации"] = recommendations


        logger.info(f"[{request_id}] FBO processing complete. "
                    f"Module time: {module_duration:.3f}s, "
                    f"Method time: {timing_details.get('method_execution_time', 0):.3f}s, "
                    f"API time: {timing_details.get('api_execution_time', 0):.3f}s, "
                    f"Transformation: {timing_details.get('transformation_time', 0):.3f}s, "
                    f"Rate limiting: {timing_details.get('rate_limiting_delay', 0):.3f}s, "
                    f"API calls: {execution_stats.get('api_calls_count', 0)}, "
                    f"Total records: {len(all_postings)}")


        if metadata.get("max_limit_reached", False):
            logger.warning(
                f"[{request_id}] FBO: Достигнут лимит 20000 записей. "
                f"Обработано {metadata.get('total_retrieved', 0)} записей за "
                f"{len(metadata.get('days_processed', []))} дней. "
                f"Рекомендуется уменьшить период запроса."
            )


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

        logger.error(f"[{request_id}] FBO critical error: {e}", exc_info=True)

        error_dict = {
            "success": False,
            "message": "FBO processing error",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
            "service_type": "FBO",
            "performance": {
                "module_execution_time_seconds": round(module_duration, 3),
                "start_time": module_start_time.isoformat(),
                "end_time": module_end_time.isoformat()
            },
            "data": None,
            "metadata": {
                "request_id": request_id,
                "status_filter": status_filter_str,
                "рекомендации": [
                    "Проверьте корректность периода запроса",
                    "Убедитесь в правильности фильтров",
                    f"Попробуйте уменьшить период запроса (сейчас {period_days} дней)"
                ] if 'period_days' in locals() else []
            },
            "errors": [{"message": str(e), "type": "critical"}]
        }

        error_json = json.dumps(error_dict, ensure_ascii=False, default=str)

        return Response(
            content=error_json,
            media_type="application/json; charset=utf-8",
            status_code=500
        )



