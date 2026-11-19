import asyncio
import logging
import time
import psutil
import os
from typing import AsyncGenerator, Dict, Any, Optional, List, Tuple, Union
from datetime import datetime

from src.app.core.base_service import BaseOzonService
from src.app.fbo.fbo_transformer import FBOTransformer

logger = logging.getLogger(__name__)


class ResourceMonitor:


    @staticmethod
    def get_memory_usage() -> Dict[str, Any]:
        """ получение информации об использовании памяти"""
        try:
            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()

            return {
                "rss_mb": round(memory_info.rss / 1024 / 1024, 2),
                "percent": round(process.memory_percent(), 2),
                "threads": process.num_threads()
            }
        except Exception as e:
            logger.debug(f"Error getting memory usage: {e}")
            return {"rss_mb": 0, "percent": 0, "threads": 0}

    @staticmethod
    def get_cpu_usage() -> Dict[str, Any]:
        """ получение информации об использовании CPU"""
        try:
            process = psutil.Process(os.getpid())
            return {
                "percent": round(process.cpu_percent(interval=0.0), 2),
                "threads": process.num_threads()
            }
        except Exception as e:
            logger.debug(f"Error getting CPU usage: {e}")
            return {"percent": 0, "threads": 0}


class FBOService(BaseOzonService):
    """FBO сервис с  метриками"""

    def __init__(self, client_id: str, api_key: str, request_id: Optional[str] = None):
        super().__init__(client_id, api_key, request_id)
        self.transformer = FBOTransformer()
        self.request_id = request_id or ""
        self.resource_monitor = ResourceMonitor()

        # Rate limiter для контроля частоты (v2 FBO)
        self._min_interval = 0.5  # 500 мс между запросами
        self._last_request_time = 0
        self._rate_lock = asyncio.Lock()

        #  семафор - для v2 API
        self._semaphore = asyncio.Semaphore(3)  # 3 одновременных запроса для v2

        # Инициализация статистики
        self.stats = {}
        self._init_stats()

    def _init_stats(self):
        """Инициализация статистики"""
        self.stats = {
            "total_batches": 0,
            "total_postings": 0,
            "errors": 0,
            "warnings": 0,
            "start_time": None,
            "end_time": None,
            "transformation_time": 0,
            "rate_limiting_delay": 0,
            "api_total_time": 0,
            "api_calls_count": 0,
            "api_failed_calls": 0,
            "avg_api_response_time": 0,
            "method_duration": 0,
            "status_filter": None,
            "resource_usage": {}
        }

    def get_api_version(self) -> str:
        return "v2"

    def get_service_type(self) -> str:
        return "FBO"

    def get_execution_stats(self) -> Dict[str, Any]:
        """Получение статистики выполнения"""
        if self.stats["start_time"] and self.stats["end_time"]:
            self.stats["method_duration"] = (
                    self.stats["end_time"] - self.stats["start_time"]
            ).total_seconds()

        if self.stats["api_calls_count"] > 0:
            self.stats["avg_api_response_time"] = (
                    self.stats["api_total_time"] / self.stats["api_calls_count"]
            )

        # Рассчитываем эффективность
        if self.stats["method_duration"] > 0:
            self.stats["api_efficiency_percent"] = round(
                (self.stats["api_total_time"] / self.stats["method_duration"]) * 100, 2
            )
            self.stats["transformation_efficiency_percent"] = round(
                (self.stats["transformation_time"] / self.stats["method_duration"]) * 100, 2
            )
            self.stats["waiting_efficiency_percent"] = round(
                (self.stats["rate_limiting_delay"] / self.stats["method_duration"]) * 100, 2
            )
            other_time = max(0, self.stats["method_duration"] -
                             self.stats["api_total_time"] -
                             self.stats["transformation_time"] -
                             self.stats["rate_limiting_delay"])
            self.stats["other_processing_time"] = other_time
            self.stats["other_efficiency_percent"] = round(
                (other_time / self.stats["method_duration"]) * 100, 2
            )

        return self.stats.copy()

    async def _get_basic_postings_batch(
            self,
            period_from: datetime,
            period_to: datetime,
            offset: int,
            status_filter: Optional[List[str]] = None,
            limit: int = 1000
    ) -> list:
        """Получение батча данных с фиксацией метрик"""
        endpoint = "/v2/posting/fbo/list"

        params = {
            "dir": "ASC",
            "filter": {
                "since": self._format_date_for_ozon(period_from),
                "to": self._format_date_for_ozon(period_to)
            },
            "limit": limit,
            "offset": offset,
            "with": {
                "analytics_data": True,
                "financial_data": True,
                "barcodes": True
            }
        }

        if status_filter and len(status_filter) > 0:
            params["filter"]["status"] = status_filter

        # Замер времени API запроса
        api_start = time.time()

        # Шаг 1: Rate limiting (контроль частоты)
        async with self._rate_lock:
            now = time.time()
            elapsed = now - self._last_request_time

            if elapsed < self._min_interval:
                wait_time = self._min_interval - elapsed
                rate_start = time.time()
                await asyncio.sleep(wait_time)
                self.stats["rate_limiting_delay"] += time.time() - rate_start

            self._last_request_time = time.time()

        # Шаг 2: Контроль параллелизма через семафор
        async with self._semaphore:
            # Шаг 3: Выполнение API запроса
            api_start = time.time()
            try:
                response = await self._make_api_request(endpoint, params)
                api_duration = time.time() - api_start

                self.stats["api_total_time"] += api_duration
                self.stats["api_calls_count"] += 1

            except Exception as e:
                api_duration = time.time() - api_start
                self.stats["api_total_time"] += api_duration
                self.stats["api_calls_count"] += 1
                self.stats["api_failed_calls"] += 1
                raise

        result = response.get("result", [])
        return result if isinstance(result, list) else []


    async def _transform_batch(
            self,
            postings_batch: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Трансформация батча с фиксацией времени"""
        transformation_start = time.time()
        transformed_batch = []

        for posting in postings_batch:
            try:
                transformed = await self.transformer.transform_single_posting(posting)
                if transformed:
                    transformed_batch.append(transformed)
            except Exception as e:
                self.stats["errors"] += 1
                logger.debug(f"[{self.request_id}] FBO transform error: {e}")
                transformed_batch.append(posting)

        transformation_duration = time.time() - transformation_start
        self.stats["transformation_time"] += transformation_duration
        self.stats["total_postings"] += len(transformed_batch)

        return transformed_batch

    async def stream_postings(
            self,
            period_from: datetime,
            period_to: datetime,
            status_filter: Optional[List[str]] = None,
            batch_size: int = 1000,
            **kwargs
    ) -> AsyncGenerator[Union[list, Tuple[list, Dict[str, Any]]], None]:
        """
        Потоковое получение данных с возвратом статистики в последнем батче
        """

        self._init_stats()
        self.stats["start_time"] = datetime.now()
        self.stats["status_filter"] = status_filter[0] if status_filter else None

        logger.info(
            f"[{self.request_id}] FBO stream_postings: Starting {period_from} - {period_to}, "
            f"status={status_filter[0] if status_filter else 'all'}"
        )

        offset = 0
        max_records = 20000
        batch_counter = 0

        try:
            while offset < max_records:
                batch_counter += 1
                self.stats["total_batches"] = batch_counter


                postings_batch = await self._get_basic_postings_batch(
                    period_from, period_to, offset, status_filter, batch_size
                )

                if not postings_batch:
                    break


                transformed_batch = await self._transform_batch(postings_batch)


                if transformed_batch:
                    yield transformed_batch


                if len(postings_batch) < batch_size:
                    break

                offset += batch_size



                # Логируем прогресс каждые 10 батчей
                if batch_counter % 10 == 0:
                    logger.info(
                        f"[{self.request_id}] FBO progress: {self.stats['total_postings']} postings, "
                        f"batches: {batch_counter}, offset: {offset}"
                    )

        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"[{self.request_id}] FBO stream error: {e}")
            raise

        finally:

            self.stats["end_time"] = datetime.now()


            final_stats = self.get_execution_stats()


            logger.info(
                f"[{self.request_id}] FBO processing complete. "
                f"Method time: {final_stats['method_duration']:.3f}s, "
                f"API time: {final_stats['api_total_time']:.3f}s, "
                f"Transformation: {final_stats['transformation_time']:.3f}s, "
                f"Rate limiting: {final_stats['rate_limiting_delay']:.3f}s, "
                f"API calls: {final_stats['api_calls_count']}"
            )


            yield {
                "_metadata": {
                    "type": "statistics",
                    "request_id": self.request_id,
                    "stats": final_stats,
                    "total_postings": self.stats["total_postings"],
                    "status": "completed"
                }
            }

    async def get_postings_with_limits(
            self,
            period_from: datetime,
            period_to: datetime,
            status_filter: Optional[List[str]] = None,
            max_records: int = 20000
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Получение всех данных с возвратом статистики
        """
        all_postings = []

        # Используем stream_postings для получения данных
        async for batch in self.stream_postings(
                period_from=period_from,
                period_to=period_to,
                status_filter=status_filter,
                batch_size=1000
        ):
            if isinstance(batch, dict) and "_metadata" in batch:

                stats = batch["_metadata"]["stats"]
                continue

            all_postings.extend(batch)

            if len(all_postings) >= max_records:
                break


        final_stats = self.get_execution_stats()

        metadata = {
            "success": True,
            "total_retrieved": len(all_postings),
            "request_id": self.request_id,
            "stats": final_stats,
            "duration": final_stats.get("method_duration", 0),
            "api_calls": final_stats.get("api_calls_count", 0),
            "api_time": final_stats.get("api_total_time", 0),
            "transformation_time": final_stats.get("transformation_time", 0),
            "rate_limiting_delay": final_stats.get("rate_limiting_delay", 0)
        }

        return all_postings, metadata

    async def get_postings_with_stats(
            self,
            period_from: datetime,
            period_to: datetime,
            status_filter: Optional[List[str]] = None,
            require_details: bool = False,
            max_records: int = 10000
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Алиас для совместимости"""
        return await self.get_postings_with_limits(
            period_from=period_from,
            period_to=period_to,
            status_filter=status_filter,
            max_records=max_records
        )

    def _record_resource_usage(self, stage: str = "general"):
        """Запись использования ресурсов (для совместимости)"""
        try:
            memory_info = self.resource_monitor.get_memory_usage()

            if "resource_usage" not in self.stats:
                self.stats["resource_usage"] = {}

            self.stats["resource_usage"][stage] = {
                "timestamp": datetime.now().isoformat(),
                "memory_mb": memory_info["rss_mb"],
                "cpu_percent": self.resource_monitor.get_cpu_usage()["percent"]
            }
        except Exception as e:
            logger.debug(f"[{self.request_id}] Error recording resource usage: {e}")