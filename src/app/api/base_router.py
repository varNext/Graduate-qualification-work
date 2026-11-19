from fastapi import APIRouter
from datetime import datetime
import logging

from config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/status", summary="Статус сервиса")
async def get_service_status():
    """Простой статус"""
    return {
        "status": "active",
        "timestamp": datetime.now().isoformat(),
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "modules": ["FBO", "FBS"],
        "endpoints": {
            "fbo_postings": "/fbo/postings",
            "fbs_postings": "/fbs/postings",
            "fbs_approve": "/fbs/approve"
        }
    }


@router.get("/test", summary="Тест подключения")
async def test_connection():
    """тест подключения"""
    return {
        "success": True,
        "message": "API доступен",
        "timestamp": datetime.now().isoformat(),
        "service": settings.APP_NAME
    }