import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class FBOTransformer:
    """ трансформер для преобразования данных Ozon в словари для 1С"""

    async def transform_single_posting(self, posting_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Преобразование данных отправления в словарь для 1С"""


        if "result" in posting_data:
            posting_data = posting_data["result"]

        if not posting_data:
            logger.debug("Empty posting_data")
            return None


        posting_number = self._extract_posting_number(posting_data)
        if not posting_number:
            logger.debug(f"No posting number found. Keys: {list(posting_data.keys())}")
            return None

        logger.debug(f"Transforming posting: {posting_number}")

        try:
            embedded_dict = {
                "posting_number": posting_number,
                "order_number": str(posting_data.get("order_id", "")) if posting_data.get("order_id") else None,
                "status": posting_data.get("status", ""),
                "status_ru": self._translate_status(posting_data.get("status", "")),
                "created_at": self._to_iso_string(posting_data.get("created_at")),
                "in_process_at": self._to_iso_string(posting_data.get("in_process_at")),
                "товары": self._extract_product_items_dict(posting_data, posting_number),
                "аналитика": self._extract_analytics_data_dict(posting_data),
                "доставка": self._extract_delivery_data_dict(posting_data),
                "клиент": self._extract_customer_data_dict(posting_data)
            }

            logger.debug(f"Successfully created dictionary for {posting_number}")
            return embedded_dict

        except Exception as e:
            logger.error(f"Failed to transform posting {posting_number}: {e}")
            return None

    def _extract_posting_number(self, posting_data: Dict[str, Any]) -> Optional[str]:
        """Извлечение номера отправления из данных"""
        possible_keys = ["posting_number", "postingNumber", "posting"]
        for key in possible_keys:
            if key in posting_data:
                value = posting_data[key]
                return str(value) if value else None
        return None

    def _extract_product_items_dict(self, posting_data: Dict[str, Any], posting_number: str) -> List[Dict[str, Any]]:
        """Извлечение товаров в список словарей"""
        product_items = []
        products = posting_data.get("products", [])

        for idx, product in enumerate(products, 1):
            try:
                quantity = product.get("quantity", 0)
                if quantity <= 0:
                    continue

                price = self._safe_float(product.get("price", "0"))
                total = price * quantity

                product_dict = {
                    "line_number": idx,
                    "sku": int(product.get("sku", 0)) if product.get("sku") else 0,  # ← int!
                    "name": product.get("name", f"Товар {idx}"),
                    "quantity": quantity,
                    "price": price,
                    "total": total,
                    "unit": "шт",
                    "vat_rate": 20.0,
                    "posting_number": posting_number,
                    "offer_id": product.get("offer_id", ""),
                    "currency_code": product.get("currency_code", "RUB")
                }
                product_items.append(product_dict)

            except Exception as e:
                logger.debug(f"Error extracting product: {e}")
                continue

        return product_items

    def _extract_analytics_data_dict(self, posting_data: Dict[str, Any]) -> Dict[str, Any]:
        """Извлечение аналитических данных в словарь"""
        analytics = posting_data.get("analytics_data", {})

        return {
            "warehouse_name": analytics.get("warehouse_name"),
            "region": analytics.get("region"),
            "city": analytics.get("city"),
            "delivery_type": analytics.get("delivery_type"),
            "warehouse_id": analytics.get("warehouse_id"),
            "tpl_provider": analytics.get("tpl_provider")
        }

    def _extract_delivery_data_dict(self, posting_data: Dict[str, Any]) -> Dict[str, Any]:
        """Извлечение данных доставки в словарь"""
        delivery_method = posting_data.get("delivery_method", {})
        addressee = posting_data.get("addressee", {})
        warehouse = posting_data.get("warehouse", {})

        return {
            "method": delivery_method.get("name"),
            "tracking_number": posting_data.get("tracking_number"),
            "warehouse": warehouse.get("name"),
            "delivery_date": self._to_iso_string(posting_data.get("delivery_date")),
            "address": addressee.get("address", ""),
            "tpl_provider": delivery_method.get("tpl_provider")
        }

    def _extract_customer_data_dict(self, posting_data: Dict[str, Any]) -> Dict[str, Any]:
        """Извлечение данных клиента в словарь"""
        customer = posting_data.get("customer", {})
        addressee = posting_data.get("addressee", {})

        return {
            "name": customer.get("name") or addressee.get("name"),
            "phone": customer.get("phone") or addressee.get("phone"),
            "email": customer.get("email"),
            "address": customer.get("address", ""),
            "delivery_address": addressee.get("address", "")
        }

    def _translate_status(self, status: str) -> str:
        """Перевод статуса на русский"""
        status_map = {
            "awaiting_deliver": "Ожидает отгрузки",
            "delivering": "Доставляется",
            "delivered": "Доставлено",
            "cancelled": "Отменено",
        }
        return status_map.get(status, status)

    def _to_iso_string(self, date_value: Any) -> Optional[str]:
        """Преобразование даты в ISO строку"""
        if not date_value:
            return None

        try:
            if isinstance(date_value, str):
                # Если уже содержит информацию о временной зоне
                if date_value.endswith('Z'):
                    return date_value.replace('Z', '+00:00')
                elif '+' in date_value or '-' in date_value[-6:]:
                    return date_value
                else:
                    return f"{date_value}+00:00"
            elif isinstance(date_value, datetime):
                return date_value.isoformat()
            else:
                return str(date_value)
        except Exception:
            return None

    def _safe_float(self, value: Any) -> float:
        """ преобразование в float"""
        try:
            if isinstance(value, (int, float)):
                return float(value)
            elif isinstance(value, str):
                # Убираем пробелы и заменяем запятые на точки
                cleaned = value.strip().replace(' ', '').replace(',', '.')
                return float(cleaned) if cleaned else 0.0
            else:
                return 0.0
        except (ValueError, TypeError):
            return 0.0