import logging
from abc import ABC
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class BaseTransformer(ABC):
    """Базовый трансформер для преобразования данных"""

    def _safe_float(self, value: Any) -> float:
        """Безопасное преобразование в float"""
        try:
            if isinstance(value, (int, float)):
                return float(value)
            elif isinstance(value, str):

                cleaned = value.strip().replace(' ', '')

                # Если запятая используется как разделитель тысяч (1,000.75)
                # Запятая перед точкой - разделитель тысяч, удаляем ее
                if ',' in cleaned and '.' in cleaned:
                    if cleaned.find(',') < cleaned.find('.'):
                        # Запятая перед точкой: 1,000.75 -> 1000.75
                        cleaned = cleaned.replace(',', '')
                    else:
                        # Запятая после точки: 1.000,75 -> 1000.75
                        cleaned = cleaned.replace('.', '').replace(',', '.')
                elif ',' in cleaned:
                    # Только запятая: 1000,75 -> 1000.75
                    cleaned = cleaned.replace(',', '.')

                return float(cleaned) if cleaned else 0.0
            else:
                return 0.0
        except (ValueError, TypeError):
            return 0.0

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

    def _extract_customer_data_dict(self, posting_data: Dict[str, Any]) -> Dict[str, Any]:
        """Извлечение данных клиента (общее для FBO/FBS)"""
        customer = posting_data.get("customer", {})
        addressee = posting_data.get("addressee", {})

        return {
            "name": customer.get("name") or addressee.get("name"),
            "phone": customer.get("phone") or addressee.get("phone"),
            "email": customer.get("email"),
            "address": customer.get("address", ""),
            "delivery_address": addressee.get("address", "")
        }