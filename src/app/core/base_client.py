# common/base_client.py
import aiohttp
import asyncio
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass
import backoff

logger = logging.getLogger(__name__)


@dataclass
class RequestParams:
    method: str
    path: str
    json_data: Optional[Dict[str, Any]] = None
    headers: Optional[Dict[str, str]] = None


class BaseOzonClient:
    """Базовый HTTP клиент для Ozon API"""

    def __init__(self, config):
        self.config = config
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def _ensure_session(self):
        if not self.session or self.session.closed:
            connector = aiohttp.TCPConnector(
                limit=self.config.max_concurrent_requests
            )
            self.session = aiohttp.ClientSession(
                connector=connector,
                timeout=aiohttp.ClientTimeout(total=self.config.timeout)
            )

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    @backoff.on_exception(
        backoff.expo,
        (aiohttp.ClientError, asyncio.TimeoutError),
        max_tries=3
    )
    async def make_request(self, params: RequestParams) -> Dict[str, Any]:
        """Базовый метод для выполнения запросов"""
        await asyncio.sleep(self.config.rate_limit_delay)
        await self._ensure_session()

        headers = {
            "Client-Id": self.config.client_id,
            "Api-Key": self.config.api_key,
            "Content-Type": "application/json"
        }

        if params.headers:
            headers.update(params.headers)

        url = f"{self.config.base_url}{params.path}"

        try:
            async with self.session.request(
                    method=params.method,
                    url=url,
                    headers=headers,
                    json=params.json_data,
                    timeout=aiohttp.ClientTimeout(total=15)
            ) as response:

                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"API error {response.status}: {error_text[:200]}")
                    raise Exception(f"API returned {response.status}")

                return await response.json()

        except aiohttp.ClientError as e:
            logger.error(f"Network error: {e}")
            raise
        except asyncio.TimeoutError:
            logger.error("Request timeout")
            raise