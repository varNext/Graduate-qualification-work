# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from datetime import datetime

from config import settings
from src.app.api.fbo_router import router as fbo_router
from src.app.api.fbs_router import router as fbs_router


logging.basicConfig(
    level=settings.LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Создаем приложение
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="API для интеграции 1С с Ozon Marketplace",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключаем роутеры
app.include_router(fbo_router)
app.include_router(fbs_router)


@app.get("/")
async def root():
    """Корневой эндпоинт"""
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "description": "API для интеграции 1С с Ozon Marketplace",
        "modules": ["FBO", "FBS"],
        "endpoints": {
            "health": "/health",
            "status": "/status",
            "fbo_postings": "/fbo/postings",
            "fbs_postings": "/fbs/postings",
            "fbs_approve": "/fbs/approve",
            "docs": "/docs",
            "redoc": "/redoc"
        }
    }


@app.get("/health")
async def health():
    """Проверка здоровья сервиса"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.get("/status")
async def status():
    """Статус сервиса"""
    return {
        "status": "active",
        "timestamp": datetime.now().isoformat(),
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "api_url": settings.OZON_API_URL
    }


if __name__ == "__main__":
    import uvicorn

    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"Server will run on http://{settings.HOST}:{settings.PORT}")
    logger.info(f"API documentation: http://localhost:{settings.PORT}/docs")

    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )