import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class FBSTransformer:
    """Трансформер для преобразования FBS данных в формат 1С"""


    async def transform_single_posting(self, posting_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Преобразование FBS отправления в словарь для 1С"""

        try:

            posting_number = self._extract_posting_number(posting_data)
            if not posting_number:
                logger.debug("No posting number in FBS data")
                return None

            logger.debug(f"Transforming FBS posting: {posting_number}")


            embedded_dict = {
                "posting_number": posting_number,
                "order_number": str(posting_data.get("order_id", "")) if posting_data.get("order_id") else None,
                "order_id": posting_data.get("order_id"),
                "status": posting_data.get("status", ""),
                "status_ru": self._translate_fbs_status(posting_data.get("status", "")),
                "created_at": self._to_iso_string(posting_data.get("created_at")),
                "in_process_at": self._to_iso_string(posting_data.get("in_process_at")),
                "shipment_date": self._to_iso_string(posting_data.get("shipment_date")),
                "delivery_date": self._to_iso_string(posting_data.get("delivery_date")),
                # Упрощаем - не вызываем вспомогательные методы
                "товары": [],  # временно пусто
                "упаковки": [],  # временно пусто
                "аналитика": {},
                "доставка": {},
                "финансы": {},
                "клиент": {},
                # FBS специфичные поля
                "is_express": posting_data.get("is_express", False),
                "warehouse_id": posting_data.get("warehouse_id"),
                "delivery_method_id": posting_data.get("delivery_method", {}).get("id") if isinstance(
                    posting_data.get("delivery_method"), dict) else None,
                "tpl_integration_type": posting_data.get("tpl_integration_type"),
                "is_multibox": posting_data.get("is_multibox", False),
                "parent_posting_number": posting_data.get("parent_posting_number"),
                "is_partial": posting_data.get("is_partial", False)
            }

            logger.debug(f"Successfully transformed FBS posting {posting_number}")
            return embedded_dict

        except Exception as e:
            logger.error(f"Failed to transform FBS posting: {e}", exc_info=True)
            return None

    def _extract_fbs_product_items(self, posting_data: Dict[str, Any], posting_number: str) -> List[Dict[str, Any]]:
        """Извлечение товаров для FBS (с учетом специфики)"""
        product_items = []
        products = posting_data.get("products", [])

        for idx, product in enumerate(products, 1):
            try:
                quantity = product.get("quantity", 0)
                if quantity <= 0:
                    continue

                # FBS специфичные поля
                mandatory_mark = product.get("mandatory_mark")
                gtd = product.get("gtd")
                currency_value = product.get("currency_value", {})

                product_dict = {
                    "line_number": idx,
                    "sku": int(product.get("sku", 0)) if product.get("sku") else 0,
                    "offer_id": product.get("offer_id", ""),
                    "name": product.get("name", f"Товар {idx}"),
                    "quantity": quantity,
                    "price": self._safe_float(product.get("price", "0")),
                    "total": self._safe_float(product.get("price", "0")) * quantity,
                    "unit": "шт",
                    "vat_rate": 20.0,
                    "posting_number": posting_number,
                    "currency_code": currency_value.get("currency_code", "RUB"),
                    # FBS специфичные поля
                    "is_kgt": product.get("is_kgt", False),
                    "mandatory_mark": mandatory_mark,
                    "gtd": gtd,
                    "is_oversize": product.get("is_oversize", False),
                    "dimensions": product.get("dimensions"),
                    "item_services": product.get("item_services", [])
                }
                product_items.append(product_dict)

            except Exception as e:
                logger.debug(f"Error extracting FBS product: {e}")
                continue

        return product_items

    def _extract_packages(self, posting_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Извлечение данных об упаковках (для подтверждения)"""
        packages = []
        posting_packages = posting_data.get("packages", [])

        for pkg in posting_packages:
            try:
                package_dict = {
                    "package_id": pkg.get("package_id"),
                    "weight": pkg.get("weight"),
                    "width": pkg.get("width"),
                    "height": pkg.get("height"),
                    "depth": pkg.get("depth"),
                    "products": [
                        {
                            "sku": prod.get("sku"),
                            "quantity": prod.get("quantity"),
                            "item_index": prod.get("item_index")
                        }
                        for prod in pkg.get("products", [])
                    ]
                }
                packages.append(package_dict)
            except Exception:
                continue

        return packages

    def _extract_fbs_analytics(self, posting_data: Dict[str, Any]) -> Dict[str, Any]:
        """Извлечение аналитических данных для FBS"""
        analytics = posting_data.get("analytics_data", {})

        return {
            "warehouse_name": analytics.get("warehouse_name"),
            "warehouse_id": analytics.get("warehouse_id"),
            "region": analytics.get("region"),
            "city": analytics.get("city"),
            "delivery_type": analytics.get("delivery_type"),
            "tpl_provider": analytics.get("tpl_provider"),
            "delivery_date_begin": self._to_iso_string(analytics.get("delivery_date_begin")),
            "delivery_date_end": self._to_iso_string(analytics.get("delivery_date_end")),
            "is_legal": analytics.get("is_legal", False),
            "is_premium": analytics.get("is_premium", False)
        }

    def _extract_fbs_delivery(self, posting_data: Dict[str, Any]) -> Dict[str, Any]:
        """Извлечение данных доставки для FBS"""
        delivery_method = posting_data.get("delivery_method", {})
        address = posting_data.get("address", {})

        return {
            "method": delivery_method.get("name"),
            "method_id": delivery_method.get("id"),
            "tracking_number": posting_data.get("tracking_number"),
            "tpl_integration_type": posting_data.get("tpl_integration_type"),
            "warehouse": posting_data.get("warehouse", {}).get("name"),
            "delivery_date": self._to_iso_string(posting_data.get("delivery_date")),
            "address": {
                "address_tail": address.get("address_tail"),
                "city": address.get("city"),
                "comment": address.get("comment"),
                "country": address.get("country"),
                "district": address.get("district"),
                "latitude": address.get("latitude"),
                "longitude": address.get("longitude"),
                "provider_pvz_code": address.get("provider_pvz_code"),
                "pvz_code": address.get("pvz_code"),
                "region": address.get("region"),
                "zip_code": address.get("zip_code")
            },
            "tpl_provider": delivery_method.get("tpl_provider")
        }

    def _extract_fbs_financial_data(self, posting_data: Dict[str, Any]) -> Dict[str, Any]:
        """Извлечение финансовых данных для FBS"""
        financial_data = posting_data.get("financial_data", {})
        products = financial_data.get("products", [])

        total_products = 0.0
        total_commission = 0.0
        total_payout = 0.0

        for product in products:
            total_products += self._safe_float(product.get("price", 0)) * product.get("quantity", 0)

            commissions = product.get("commissions", [])
            for commission in commissions:
                total_commission += self._safe_float(commission.get("value", 0))

            payout = product.get("payout", {})
            total_payout += self._safe_float(payout.get("total", 0))

        return {
            "total_products": total_products,
            "total_commission": total_commission,
            "total_payout": total_payout,
            "delivery_cost": self._safe_float(financial_data.get("posting_services", {}).get("delivery_cost", 0)),
            "refund_cost": self._safe_float(financial_data.get("posting_services", {}).get("refund_cost", 0)),
            "currency": "RUB"
        }

    def _extract_fbs_customer_data(self, posting_data: Dict[str, Any]) -> Dict[str, Any]:
        """Извлечение данных клиента для FBS"""
        customer = posting_data.get("customer", {})
        recipient = posting_data.get("recipient", {})

        return {
            "name": customer.get("name") or recipient.get("name"),
            "phone": customer.get("phone") or recipient.get("phone"),
            "email": customer.get("email"),
            "address": self._format_address(customer),
            "delivery_address": self._format_address(recipient),
            "is_legal": customer.get("is_legal", False)
        }

    def _translate_fbs_status(self, status: str) -> str:
        """Перевод статуса FBS на русский"""
        status_map = {
            "awaiting_registration": "Ожидает регистрации",
            "acceptance_in_progress": "Приемка в процессе",
            "awaiting_approve": "Ожидает подтверждения",
            "awaiting_packaging": "Ожидает упаковки",
            "awaiting_deliver": "Ожидает отгрузки",
            "delivering": "Доставляется",
            "driver_pickup": "Водитель забрал",
            "delivered": "Доставлено",
            "cancelled": "Отменено",
            "arbitration": "Арбитраж",
            "not_accepted": "Не принят на складе",
            "sent_by_seller": "Отправлен продавцом",
            # FBS специфичные статусы
            "returning_to_seller": "Возврат продавцу",
            "returned_to_seller": "Возвращен продавцу",
            "awaiting_return_registration": "Ожидает регистрации возврата",
            "awaiting_return_packaging": "Ожидает упаковки возврата"
        }
        return status_map.get(status, status)


    def _extract_posting_number(self, posting_data: Dict[str, Any]) -> Optional[str]:
        """Извлечение номера отправления"""
        possible_keys = ["posting_number", "postingNumber", "posting"]
        for key in possible_keys:
            if key in posting_data:
                value = posting_data[key]
                return str(value) if value else None
        return None

    def _to_iso_string(self, date_value: Any) -> Optional[str]:
        """Преобразование даты в ISO строку"""
        if not date_value:
            return None
        try:
            if isinstance(date_value, str):
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
        """Безопасное преобразование в float"""
        try:
            if isinstance(value, (int, float)):
                return float(value)
            elif isinstance(value, str):
                cleaned = value.strip().replace(' ', '').replace(',', '.')
                return float(cleaned) if cleaned else 0.0
            else:
                return 0.0
        except (ValueError, TypeError):
            return 0.0

    def _format_address(self, address_data: Dict[str, Any]) -> str:
        """Форматирование адреса в строку"""
        if not address_data:
            return ""

        parts = [
            address_data.get("zip_code"),
            address_data.get("country"),
            address_data.get("region"),
            address_data.get("city"),
            address_data.get("address_tail")
        ]

        return ", ".join([p for p in parts if p])