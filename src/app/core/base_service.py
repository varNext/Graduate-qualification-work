from abc import ABC, abstractmethod
from typing import AsyncGenerator, Dict, List, Any, Optional
from datetime import datetime, timezone
import aiohttp
import logging
import asyncio

logger = logging.getLogger(__name__)


class BaseOzonService(ABC):
    """Абстрактный базовый класс для всех Ozon сервисов"""

    def __init__(self, client_id: str, api_key: str, request_id: Optional[str] = None):
        self.client_id = client_id
        self.api_key = api_key
        self.request_id = request_id or ""
        self.session: Optional[aiohttp.ClientSession] = None
        self.base_url = "https://api-seller.ozon.ru"

        # Статистика выполнения
        self.stats = {
            "total_batches": 0,
            "total_postings": 0,
            "errors": 0,
            "warnings": 0,
            "start_time": None,
            "end_time": None,
            "status_filter": None
        }

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def start(self):
        """Инициализация сессии"""
        if not self.session or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                connector=aiohttp.TCPConnector(limit=20)
            )
            logger.debug(f"[{self.request_id}] Session created")

    async def close(self):
        """Закрытие сессии"""
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None
            logger.debug(f"[{self.request_id}] Session closed")

    def _get_headers(self) -> Dict[str, str]:
        """Базовые заголовки для всех запросов"""
        return {
            "Client-Id": self.client_id,
            "Api-Key": self.api_key,
            "Content-Type": "application/json"
        }

    def _format_date_for_ozon(self, date_obj: datetime) -> str:
        """Форматирует дату для Ozon API"""
        return date_obj.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    async def _make_api_request(self, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Общий метод для HTTP запросов с ретраями"""
        await asyncio.sleep(0.3)  # Rate limiting

        if not self.session or self.session.closed:
            await self.start()

        headers = self._get_headers()
        url = f"{self.base_url}{endpoint}"

        try:
            async with self.session.post(url, json=payload, headers=headers) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    logger.error(f"[{self.request_id}] API error {resp.status}: {error_text[:200]}")
                    raise Exception(f"API error {resp.status}: {error_text[:200]}")

                return await resp.json()

        except aiohttp.ClientError as e:
            logger.error(f"[{self.request_id}] Network error: {e}")
            raise
        except asyncio.TimeoutError:
            logger.error(f"[{self.request_id}] Request timeout")
            raise

    @abstractmethod
    async def stream_postings(
            self,
            period_from: datetime,
            period_to: datetime,
            status_filter: Optional[List[str]] = None,
            **kwargs
    ) -> AsyncGenerator[list, None]:
        """Основной метод для потокового получения данных"""
        pass

    @abstractmethod
    def get_api_version(self) -> str:
        """Получить версию API (v2 для FBO, v3 для FBS)"""
        pass

    def get_execution_stats(self) -> Dict[str, Any]:
        """Получение статистики выполнения"""
        stats = self.stats.copy()

        if stats["start_time"] and stats["end_time"]:
            duration = (stats["end_time"] - stats["start_time"]).total_seconds()
            if duration > 0:
                stats["postings_per_second"] = stats["total_postings"] / duration
            else:
                stats["postings_per_second"] = 0


        if stats.get("method_duration", 0) > 0:
            method_duration = stats["method_duration"]

            stats["api_efficiency_percent"] = round(stats["api_total_time"] / method_duration * 100, 1)
            stats["transformation_efficiency_percent"] = round(
                stats["transformation_time"] / method_duration * 100, 1)
            stats["waiting_efficiency_percent"] = round(stats["rate_limiting_delay"] / method_duration * 100, 1)

            # Для FBS учитываем время запросов деталей
            details_time = stats.get("details_request_time", 0)
            if details_time > 0:
                stats["details_efficiency_percent"] = round(details_time / method_duration * 100, 1)
            else:
                stats["details_efficiency_percent"] = 0


            other_time = method_duration
            other_time -= stats.get("api_total_time", 0)
            other_time -= stats.get("transformation_time", 0)
            other_time -= stats.get("rate_limiting_delay", 0)
            other_time -= details_time
            stats["other_processing_time"] = max(0, other_time)
            stats["other_efficiency_percent"] = round(stats.get("other_processing_time", 0) / method_duration * 100, 1)
        else:
            stats["api_efficiency_percent"] = 0
            stats["transformation_efficiency_percent"] = 0
            stats["waiting_efficiency_percent"] = 0
            stats["details_efficiency_percent"] = 0
            stats["other_processing_time"] = 0
            stats["other_efficiency_percent"] = 0

        # Округляем значения для читаемости
        stats["transformation_time"] = round(stats.get("transformation_time", 0), 3)
        stats["rate_limiting_delay"] = round(stats.get("rate_limiting_delay", 0), 3)
        stats["api_total_time"] = round(stats.get("api_total_time", 0), 3)
        stats["details_request_time"] = round(stats.get("details_request_time", 0), 3)
        stats["avg_api_response_time"] = round(stats.get("avg_api_response_time", 0), 3) if stats.get("api_calls_count",
                                                                                                      0) > 0 else 0
        stats["method_duration"] = round(stats.get("method_duration", 0), 3) if stats.get("method_duration") else 0
        stats["other_processing_time"] = round(stats.get("other_processing_time", 0), 3)

        logger.debug(f"[{self.request_id}] Execution stats prepared: "
                     f"transformation={stats.get('transformation_time', 0)}s, "
                     f"rate_limiting={stats.get('rate_limiting_delay', 0)}s, "
                     f"api_total={stats.get('api_total_time', 0)}s, "
                     f"details={stats.get('details_request_time', 0)}s")

        return stats