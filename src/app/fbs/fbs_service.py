import asyncio
import json
import logging
import os
import time
import psutil
from typing import AsyncGenerator, Dict, Any, List, Optional, Union
from datetime import datetime

import aiohttp
from tenacity import retry, stop_after_attempt, wait_exponential

from src.app.core.base_service import BaseOzonService
from src.app.fbs.fbs_transformer import FBSTransformer

logger = logging.getLogger(__name__)


class ResourceMonitor:


    @staticmethod
    def get_memory_usage() -> Dict[str, Any]:
        """Получить информацию об использовании памяти"""
        try:
            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()

            # Получаем использование памяти в MB
            rss_mb = memory_info.rss / 1024 / 1024
            vms_mb = memory_info.vms / 1024 / 1024

            # Процент использования памяти процессом
            memory_percent = process.memory_percent()

            return {
                "rss_mb": round(rss_mb, 2),
                "vms_mb": round(vms_mb, 2),
                "percent": round(memory_percent, 2),
                "threads": process.num_threads()
            }
        except Exception as e:
            logger.warning(f"Error getting memory usage: {e}")
            return {"rss_mb": 0, "vms_mb": 0, "percent": 0, "threads": 0}

    @staticmethod
    def get_cpu_usage() -> Dict[str, Any]:
        """Получить информацию об использовании CPU"""
        try:
            process = psutil.Process(os.getpid())

            # CPU для процесса
            cpu_percent = process.cpu_percent(interval=0.1)

            # CPU times
            cpu_times = process.cpu_times()

            return {
                "percent": round(cpu_percent, 2),
                "user_time": round(cpu_times.user, 2),
                "system_time": round(cpu_times.system, 2),
            }
        except Exception as e:
            logger.warning(f"Error getting CPU usage: {e}")
            return {"percent": 0, "user_time": 0, "system_time": 0}


class FBSService(BaseOzonService):
    """FBS сервис - работает с API v3"""

    def __init__(self, client_id: str, api_key: str, request_id: Optional[str] = None):
        super().__init__(client_id, api_key, request_id)
        self.transformer = FBSTransformer()
        self.next_token = None

        # Rate limiter для API v3 FBS (5 RPS для стандартного аккаунта)
        self._min_interval = 0.2  # 200 мс между запросами = 5 RPS
        self._last_request_time = 0
        self._rate_lock = asyncio.Lock()

        # Semaphore для контроля параллельных запросов (5 одновременно)
        self._semaphore = asyncio.Semaphore(5)

        # Мониторинг ресурсов
        self.resource_monitor = ResourceMonitor()
        self._initial_memory = None
        self._initial_cpu = None
        self._peak_memory = 0
        self._peak_cpu = 0

        # Метрики времени
        self._method_start_time = 0.0
        self._method_end_time = 0.0
        self._api_active_time = 0.0
        self._rate_limiting_time = 0.0
        self._transformation_time = 0.0
        self._api_calls_count = 0
        self._last_request_time = 0.0

        # Дополнительная статистика для FBS
        self.stats.update({
            "awaiting_packaging": 0,
            "awaiting_deliver": 0,
            "details_processed": 0,
            "initial_memory_mb": 0,
            "final_memory_mb": 0,
            "memory_increase_mb": 0,
            "peak_cpu_percent": 0,
            "total_transformed": 0,
        })

    def get_api_version(self) -> str:
        return "v3"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=5)
    )
    async def _make_api_request(self, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Переопределяем с ретраями для FBS"""
        # Шаг 1: Контроль параллелизма через семафор
        async with self._semaphore:
            # Шаг 2: Rate limiting (контроль частоты)
            async with self._rate_lock:
                current_time = time.perf_counter()
                if self._last_request_time > 0:
                    time_since_last = current_time - self._last_request_time

                    if time_since_last < self._min_interval:  # 200 мс для 5 RPS
                        sleep_time = self._min_interval - time_since_last
                        rate_start = time.perf_counter()
                        await asyncio.sleep(sleep_time)
                        rate_duration = time.perf_counter() - rate_start
                        self._rate_limiting_time += rate_duration

                self._last_request_time = time.perf_counter()

        # Шаг 3: Выполнение API запроса
        api_start = time.perf_counter()
        try:
            return await super()._make_api_request(endpoint, payload)
        finally:
            api_duration = time.perf_counter() - api_start
            self._api_active_time += api_duration
            self._api_calls_count += 1


    async def _get_fbs_list_batch(
            self,
            period_from: datetime,
            period_to: datetime,
            offset: int = 0,
            limit: int = 1000,
            next_token: Optional[str] = None,  # <-- Добавляем параметр курсора
            status_filter: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Получение списка FBS отправлений (v3 API)
        """
        endpoint = "/v3/posting/fbs/list"


        filter_dict = {
            "since": self._format_date_for_ozon(period_from),
            "to": self._format_date_for_ozon(period_to)
        }


        if status_filter and status_filter.strip():
            filter_dict["status"] = status_filter.strip()

        payload = {
            "dir": "ASC",
            "filter": filter_dict,
            "limit": limit,
            "offset": offset,
            "with": {
                "analytics_data": True,
                "financial_data": True,
                "barcodes": True
            }



        }


        if next_token:
            payload["next_token"] = next_token
        else:
            payload["offset"] = 0  # Только для первого запроса

        logger.info(f"[{self.request_id}] FBS: Getting list, offset={offset}, limit={limit}")
        return await self._make_api_request(endpoint, payload)

    async def stream_postings(
            self,
            period_from: datetime,
            period_to: datetime,
            status_filter: Optional[Union[str, List[str]]] = None,
            require_details: bool = False,
            **kwargs
    ) -> AsyncGenerator[list, None]:
        """
        Основной метод: потоковое получение FBS данных для 1С
        """
        self.stats["start_time"] = datetime.now()
        self._method_start_time = time.perf_counter()

        # Сбрасываем время последнего запроса
        self._last_request_time = 0.0

        self._initial_memory = self.resource_monitor.get_memory_usage()
        self._initial_cpu = self.resource_monitor.get_cpu_usage()
        self._peak_memory = self._initial_memory["rss_mb"]
        self._peak_cpu = self._initial_cpu["percent"]

        self.stats["initial_memory_mb"] = self._initial_memory["rss_mb"]

        logger.info(f"[{self.request_id}] FBS: Starting processing {period_from} - {period_to}")

        normalized_status_filter = None
        if status_filter:
            if isinstance(status_filter, str):
                normalized_status_filter = status_filter.strip()
            elif isinstance(status_filter, list):
                if status_filter:
                    normalized_status_filter = str(status_filter[0]).strip()

        logger.info(f"[{self.request_id}] Using status filter: {normalized_status_filter}")

        offset = 0
        has_more = True
        page_num = 0
        next_token = None


        try:
            while has_more:
                page_num += 1
                batch_start = time.perf_counter()

                # Получаем список отправлений
                list_response = await self._get_fbs_list_batch(
                    period_from=period_from,
                    period_to=period_to,
                    offset=offset,
                    status_filter=normalized_status_filter,
                    next_token = next_token  # Передаем курсор
                )

                result = list_response.get("result", {})
                postings = result.get("postings", [])

                if not postings:
                    logger.info(f"[{self.request_id}] No more FBS postings")
                    break

                logger.info(f"[{self.request_id}] Got {len(postings)} postings from list (page {page_num})")


                transform_start = time.perf_counter()
                transformed_batch = []
                successful_transforms = 0

                for posting in postings:
                    try:
                        if not isinstance(posting, dict):
                            logger.error(f"[{self.request_id}] Invalid posting type: {type(posting)}")
                            continue

                        transformed = await self.transformer.transform_single_posting(posting)
                        if transformed:
                            transformed_batch.append(transformed)
                            successful_transforms += 1


                            status = posting.get("status", "")
                            if status == "awaiting_packaging":
                                self.stats["awaiting_packaging"] += 1
                            elif status == "awaiting_deliver":
                                self.stats["awaiting_deliver"] += 1

                    except Exception as e:
                        self.stats["errors"] += 1
                        logger.error(f"[{self.request_id}] FBS transform error: {e}")

                transform_duration = time.perf_counter() - transform_start
                self._transformation_time += transform_duration
                self.stats["total_transformed"] += successful_transforms


                if transformed_batch:
                    self.stats["total_batches"] += 1
                    self.stats["total_postings"] += len(transformed_batch)
                    yield transformed_batch

                has_more = result.get("has_next", False)
                next_token = result.get("next_token")  # <-- Сохраняем курсор
                if has_more:
                    offset += len(postings)
                    logger.debug(f"[{self.request_id}] Moving to next page, new offset={offset}")

                else:
                    offset = None

                batch_duration = time.perf_counter() - batch_start
                logger.debug(f"[{self.request_id}] Page {page_num} completed in {batch_duration:.3f}s")

        except Exception as e:
            logger.error(f"[{self.request_id}] FBS stream error: {e}", exc_info=True)
            raise

        finally:
            self._method_end_time = time.perf_counter()
            self.stats["end_time"] = datetime.now()

            final_memory = self.resource_monitor.get_memory_usage()
            final_cpu = self.resource_monitor.get_cpu_usage()

            self.stats["final_memory_mb"] = final_memory["rss_mb"]
            self.stats["memory_increase_mb"] = final_memory["rss_mb"] - self._initial_memory["rss_mb"]

            if final_cpu["percent"] > self._peak_cpu:
                self._peak_cpu = final_cpu["percent"]
            self.stats["peak_cpu_percent"] = self._peak_cpu

            method_duration = self._method_end_time - self._method_start_time

            # ВЫВОД МЕТРИК
            logger.info(
                f"[{self.request_id}] FBS get_postings completed. "
                f"Duration: {method_duration:.3f}s, "
                f"API: {self._api_active_time:.3f}s, "
                f"Transformation: {self._transformation_time:.3f}s, "
                f"Rate limiting: {self._rate_limiting_time:.3f}s, "
                f"Posts: {self.stats['total_transformed']}, "
                f"Memory: {self.stats['memory_increase_mb']:.1f}MB increase, "
                f"CPU peak: {self.stats['peak_cpu_percent']:.1f}%"
            )

            module_duration = (self.stats["end_time"] - self.stats["start_time"]).total_seconds()
            logger.info(
                f"[{self.request_id}] FBS processing complete. "
                f"Module time: {module_duration:.3f}s, "
                f"Method time: {method_duration:.3f}s, "
                f"API time: {self._api_active_time:.3f}s, "
                f"Transformation: {self._transformation_time:.3f}s, "
                f"Rate limiting: {self._rate_limiting_time:.3f}s, "
                f"API calls: {self._api_calls_count}, "
                f"Total records: {self.stats['total_transformed']}"
            )


    def get_metrics(self) -> Dict[str, Any]:
        """Получение метрик производительности"""
        method_duration = self._method_end_time - self._method_start_time if self._method_end_time > 0 else 0

        return {
            "method_duration": method_duration,
            "api_active_time": self._api_active_time,
            "transformation_time": self._transformation_time,
            "rate_limiting_time": self._rate_limiting_time,
            "api_calls_count": self._api_calls_count,
            "total_postings": self.stats["total_transformed"],
            "memory_increase_mb": self.stats["memory_increase_mb"],
            "peak_cpu_percent": self.stats["peak_cpu_percent"],
            "awaiting_packaging": self.stats["awaiting_packaging"],
            "awaiting_deliver": self.stats["awaiting_deliver"],
            "errors": self.stats["errors"],
            "total_batches": self.stats["total_batches"]
        }