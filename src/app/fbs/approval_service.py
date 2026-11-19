import logging
from typing import Dict, Any, List, Optional
import aiohttp
from datetime import datetime

logger = logging.getLogger(__name__)


class FBSApprovalService:
    """Сервис для подтверждения FBS отгрузок"""

    def __init__(self, client_id: str, api_key: str):
        self.client_id = client_id
        self.api_key = api_key
        self.base_url = "https://api-seller.ozon.ru"
        self.session: Optional[aiohttp.ClientSession] = None

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
                connector=aiohttp.TCPConnector(limit=10)
            )

    async def close(self):
        """Закрытие сессии"""
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None


    async def approve_single_posting(
            self,
            posting_number: str,
            packages: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Подтверждение одной отгрузки в Ozon"""

        if not posting_number:
            return {
                "success": False,
                "error": "Не указан номер отправления"
            }


        if not self.session or self.session.closed:
            await self.start()


        if not packages or not self._validate_packages(packages):
            return {
                "success": False,
                "error": "Некорректные данные упаковок"
            }

        try:
            payload = {
                "packages": packages,
                "posting_number": posting_number
            }

            headers = {
                "Client-Id": self.client_id,
                "Api-Key": self.api_key,
                "Content-Type": "application/json"
            }

            # Отправляем запрос на подтверждение
            async with self.session.post(
                    f"{self.base_url}/v1/carriage/approve",
                    json=payload,
                    headers=headers
            ) as response:

                if response.status == 200:
                    result = await response.json()
                    logger.info(f"Успешно подтверждена отгрузка {posting_number}")

                    return {
                        "success": True,
                        "posting_number": posting_number,
                        "ozon_response": result,
                        "approved_at": datetime.now().isoformat()
                    }
                else:
                    error_text = await response.text()
                    logger.error(f"Ошибка подтверждения {posting_number}: {response.status} - {error_text}")

                    return {
                        "success": False,
                        "posting_number": posting_number,
                        "error": f"API error {response.status}: {error_text}",
                        "status_code": response.status
                    }

        except aiohttp.ClientError as e:
            logger.error(f"Сетевая ошибка при подтверждении {posting_number}: {e}")
            return {
                "success": False,
                "posting_number": posting_number,
                "error": f"Сетевая ошибка: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Ошибка при подтверждении {posting_number}: {e}")
            return {
                "success": False,
                "posting_number": posting_number,
                "error": str(e)
            }

    async def batch_approve_postings(
            self,
            approvals_list: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Массовое подтверждение отгрузок"""
        results = []
        successful = 0
        failed = 0

        for approval in approvals_list:
            posting_number = approval.get("posting_number")
            packages = approval.get("packages", [])

            if not posting_number or not packages:
                results.append({
                    "success": False,
                    "posting_number": posting_number,
                    "error": "Отсутствует номер отправления или данные упаковок"
                })
                failed += 1
                continue

            result = await self.approve_single_posting(posting_number, packages)
            results.append(result)

            if result.get("success"):
                successful += 1
            else:
                failed += 1

        return {
            "total": len(approvals_list),
            "successful": successful,
            "failed": failed,
            "results": results
        }

    def _validate_packages(self, packages: List[Dict[str, Any]]) -> bool:
        """Валидация упаковок перед отправкой"""
        if not packages:
            return False

        for package in packages:

            if not package.get("products"):
                return False


            required_fields = ["weight", "width", "height", "depth"]
            if not all(key in package for key in required_fields):
                return False


            for field in required_fields:
                if package.get(field, 0) <= 0:
                    return False


            for product in package.get("products", []):
                if not product.get("sku") or not product.get("quantity") or product.get("quantity") <= 0:
                    return False

        return True